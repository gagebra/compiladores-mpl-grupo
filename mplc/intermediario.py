"""
Entrega 4, primeira metade — codigo de tres enderecos.

Cada instrucao tem NO MAXIMO UM OPERADOR. Uma expressao como a + b * c vira
duas linhas, com um temporario no meio:

    t0 = b * c
    t1 = a + t0

Representacao interna: uma lista de FuncaoIR, cada uma com a sua lista de
instrucoes. Cada instrucao e uma tupla (tipo, linha_fonte, ...campos). Os
operandos sao:

    Temp(n)          um temporario tN, local a funcao
    Var(slot, nome)  um parametro ou variavel (slot no registro de ativacao)
    Const(tipo, v)   um literal

A conversao implicita inteiro -> real (LINGUAGEM.md 3.1) aparece explicita
no IR, como `tN = paraReal x`, e sempre DEPOIS da operacao inteira que gerou
o valor. E por isso que `real a = 7 / 2;` da 3.000000: a divisao inteira
acontece antes da conversao.

Formato do --ir:

    funcao <nome> <tipo> (<param> <tipo>, ...)
      t0 = n <= 1
      seFalso t0 desvie L0
      retorne 1
    L0:
      ...
    fim
"""
import re
from decimal import Decimal

from mplc.semantica import NUMERICOS


# ------------------------------------------------------------------ operandos
class Temp:
    __slots__ = ('n',)

    def __init__(self, n):
        self.n = n


class Var:
    __slots__ = ('slot', 'nome')

    def __init__(self, slot, nome):
        self.slot = slot
        self.nome = nome


class Const:
    __slots__ = ('tipo', 'valor')

    def __init__(self, tipo, valor):
        self.tipo = tipo
        self.valor = valor


class FuncaoIR:
    def __init__(self, nome, tipo, params, nlocais):
        self.nome = nome
        self.tipo = tipo
        self.params = params          # lista de (nome_exibido, tipo)
        self.nlocais = nlocais        # slots de parametros e variaveis
        self.ntemps = 0
        self.instrucoes = []
        self.nomes = {}               # slot -> nome exibido no --ir


class CodigoIR:
    def __init__(self):
        self.funcoes = []


# ----------------------------------------------------------- textos de exibicao
def texto_mpl(s):
    """Devolve o literal de texto com aspas e escapes na forma do fonte."""
    s = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\t', '\\t')
    return f'"{s}"'


def real_posicional(v):
    """Real sem notacao cientifica: 1e-05 tem um 'e' e um '-' que nao sao operadores."""
    r = repr(float(v))
    if 'e' in r or 'E' in r:
        r = format(Decimal(r), 'f')
        if '.' not in r:
            r += '.0'
    return r


def mostrar_const(c):
    if c.tipo == 'inteiro':
        return str(c.valor)
    if c.tipo == 'real':
        return real_posicional(c.valor)
    if c.tipo == 'logico':
        return 'verdadeiro' if c.valor else 'falso'
    return texto_mpl(c.valor)


_OP_PALAVRA = re.compile(r'(?<![a-zA-Z_])(e|ou|nao)(?![a-zA-Z_])')
_PARECE_TEMP = re.compile(r't\d+$')


# ------------------------------------------------------------------ o gerador
class GeradorIR:
    def __init__(self, tabela):
        self.tabela = tabela
        self.rotulos = 0
        self.f = None

    def novo_rotulo(self):
        r = f'L{self.rotulos}'
        self.rotulos += 1
        return r

    def novo_temp(self):
        t = Temp(self.f.ntemps)
        self.f.ntemps += 1
        return t

    def emitir(self, *instr):
        self.f.instrucoes.append(instr)

    def nome_exibido(self, sim):
        """Nome legivel e sem ambiguidade para o slot de um simbolo."""
        if sim.slot in self.f.nomes:
            return self.f.nomes[sim.slot]
        base = sim.nome
        if _OP_PALAVRA.search(base):         # ex.: `e1` seria lido como o operador `e`
            base = f'v{sim.slot}'
        elif _PARECE_TEMP.match(base):       # os nomes tN sao dos temporarios
            base = '_' + base
        nome, k = base, 2
        usados = set(self.f.nomes.values())
        while nome in usados:                # sombreamento: x, x.2, x.3 ...
            nome = f'{base}.{k}'
            k += 1
        self.f.nomes[sim.slot] = nome
        return nome

    def var(self, sim):
        return Var(sim.slot, self.nome_exibido(sim))

    # ----------------------------------------------------------- programa
    def programa(self, arvore):
        codigo = CodigoIR()
        for no in arvore.filhos:
            codigo.funcoes.append(self.funcao(no))
        return codigo

    def funcao(self, no):
        params, corpo = no.filhos
        self.f = FuncaoIR(no.nome, no.tipo, [], self.tabela.locais[no.nome])
        for p in params.filhos:
            self.f.params.append((self.nome_exibido(p.simbolo), p.tipo))
        self.bloco(corpo)
        # garante um ponto de saida: funcao vazio pode acabar sem retorne
        ultima = self.f.instrucoes[-1][0] if self.f.instrucoes else None
        if ultima != 'retorne':
            fim = corpo.linha
            self.emitir('retorne', fim, None)
        return self.f

    # ------------------------------------------------------------ comandos
    def bloco(self, no):
        for c in no.filhos:
            self.comando(c)

    def comando(self, no):
        tipo = no.tipo_no
        ln = no.linha
        if tipo == 'declaracao':
            if no.filhos:
                valor = self.converter(self.expressao(no.filhos[0], ln),
                                       no.filhos[0].tipo_expr, no.tipo, ln)
            else:
                valor = Const(no.tipo, {'inteiro': 0, 'real': 0.0, 'logico': False, 'texto': ''}[no.tipo])
            self.emitir('copia', ln, self.var(no.simbolo), valor)

        elif tipo == 'atribuicao':
            valor = self.converter(self.expressao(no.filhos[0], ln),
                                   no.filhos[0].tipo_expr, no.simbolo.tipo, ln)
            self.emitir('copia', ln, self.var(no.simbolo), valor)

        elif tipo == 'chamada':
            self.chamada(no, ln, como_comando=True)

        elif tipo == 'escreva':
            e = no.filhos[0]
            self.emitir('escreva', ln, self.expressao(e, ln), e.tipo_expr)

        elif tipo == 'retorne':
            if no.filhos:
                e = no.filhos[0]
                valor = self.converter(self.expressao(e, ln), e.tipo_expr, self.f.tipo, ln)
                self.emitir('retorne', ln, valor)
            else:
                self.emitir('retorne', ln, None)

        elif tipo == 'se':
            cond = self.expressao(no.filhos[0], ln)
            senao = self.novo_rotulo()
            self.emitir('seFalso', ln, cond, senao)
            self.bloco(no.filhos[1])
            if len(no.filhos) == 3:
                fim = self.novo_rotulo()
                self.emitir('desvie', ln, fim)
                self.emitir('rotulo', ln, senao)
                self.bloco(no.filhos[2])
                self.emitir('rotulo', ln, fim)
            else:
                self.emitir('rotulo', ln, senao)

        elif tipo == 'enquanto':
            inicio, fim = self.novo_rotulo(), self.novo_rotulo()
            self.emitir('rotulo', ln, inicio)
            cond = self.expressao(no.filhos[0], ln)
            self.emitir('seFalso', ln, cond, fim)
            self.bloco(no.filhos[1])
            self.emitir('desvie', ln, inicio)
            self.emitir('rotulo', ln, fim)

        elif tipo == 'bloco':
            self.bloco(no)

    # ---------------------------------------------------------- expressoes
    def converter(self, op, de, para, ln):
        """A unica conversao implicita: inteiro -> real."""
        if de == 'inteiro' and para == 'real':
            if isinstance(op, Const):
                return Const('real', float(op.valor))
            t = self.novo_temp()
            self.emitir('paraReal', ln, t, op)
            return t
        return op

    def expressao(self, no, ln):
        """Gera o codigo da expressao e devolve o operando com o resultado."""
        tipo = no.tipo_no
        if tipo == 'literal':
            return Const(no.tipo, no.valor)
        if tipo == 'variavel':
            return self.var(no.simbolo)
        if tipo == 'chamada':
            return self.chamada(no, ln, como_comando=False)
        if tipo == 'unario':
            a = self.expressao(no.filhos[0], ln)
            t = self.novo_temp()
            self.emitir('unario', ln, t, no.op, a, no.tipo_expr)
            return t
        if tipo == 'binario':
            esq, dir_ = no.filhos
            a = self.expressao(esq, ln)
            b = self.expressao(dir_, ln)
            ta, tb = esq.tipo_expr, dir_.tipo_expr
            # tipo em que a operacao acontece (os dois lados ja convertidos)
            if ta in NUMERICOS and tb in NUMERICOS:
                tipo_op = 'real' if 'real' in (ta, tb) else 'inteiro'
                a = self.converter(a, ta, tipo_op, ln)
                b = self.converter(b, tb, tipo_op, ln)
            else:
                tipo_op = ta
            t = self.novo_temp()
            self.emitir('binario', ln, t, no.op, a, b, tipo_op)
            return t
        raise AssertionError(no.rotulo)

    def chamada(self, no, ln, como_comando):
        f = self.tabela.funcoes[no.nome]
        args = []
        for arg, tipo_param in zip(no.filhos, f.params):
            args.append(self.converter(self.expressao(arg, ln), arg.tipo_expr, tipo_param, ln))
        if como_comando or f.tipo == 'vazio':
            self.emitir('chama', ln, None, no.nome, args, f.tipo)
            return None
        t = self.novo_temp()
        self.emitir('chama', ln, t, no.nome, args, f.tipo)
        return t


def gerar(arvore, tabela):
    """Devolve o codigo de tres enderecos."""
    return GeradorIR(tabela).programa(arvore)


# ------------------------------------------------------------------- despejo
def mostrar(op):
    if isinstance(op, Temp):
        return f't{op.n}'
    if isinstance(op, Var):
        return op.nome
    return mostrar_const(op)


def instrucao_texto(ins):
    k = ins[0]
    if k == 'copia':
        return f'{mostrar(ins[2])} = {mostrar(ins[3])}'
    if k == 'binario':
        _, _, t, op, a, b, _ = ins
        return f'{mostrar(t)} = {mostrar(a)} {op} {mostrar(b)}'
    if k == 'unario':
        _, _, t, op, a, _ = ins
        return f'{mostrar(t)} = {op} {mostrar(a)}'
    if k == 'paraReal':
        return f'{mostrar(ins[2])} = paraReal {mostrar(ins[3])}'
    if k == 'chama':
        _, _, t, nome, args, _ = ins
        chamada = f'chama {nome}' + (' ' + ', '.join(mostrar(a) for a in args) if args else '')
        return f'{mostrar(t)} = {chamada}' if t is not None else chamada
    if k == 'escreva':
        return f'escreva {mostrar(ins[2])}'
    if k == 'retorne':
        return 'retorne' + (f' {mostrar(ins[2])}' if ins[2] is not None else '')
    if k == 'seFalso':
        return f'seFalso {mostrar(ins[2])} desvie {ins[3]}'
    if k == 'desvie':
        return f'desvie {ins[2]}'
    raise AssertionError(k)


def despejar(codigo):
    """Devolve as linhas do --ir."""
    linhas = []
    for f in codigo.funcoes:
        params = ', '.join(f'{n} {t}' for n, t in f.params)
        linhas.append(f'funcao {f.nome} {f.tipo} ({params})')
        for ins in f.instrucoes:
            if ins[0] == 'rotulo':
                linhas.append(f'{ins[2]}:')
            else:
                linhas.append('  ' + instrucao_texto(ins))
        linhas.append('fim')
        linhas.append('')
    return linhas[:-1]
