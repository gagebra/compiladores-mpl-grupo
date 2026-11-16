"""
Entrega 4, segunda metade — geracao do codigo executavel.

Traduz o codigo de tres enderecos para instrucoes de uma maquina de PILHA.
Cada instrucao de tres enderecos vira "empilha os operandos, opera, guarda":

    t1 = a + t0      ->     CARREGA 0      # a
                            CARREGA 3      # t0
                            SOMA_I
                            GUARDA 4       # t1

Parametros, variaveis e temporarios moram em SLOTS do registro de ativacao
da funcao: primeiro os parametros (na ordem), depois as variaveis locais,
depois os temporarios. O conjunto de instrucoes esta documentado no README.

O .mplb e texto, uma instrucao por linha. Diretivas comecam por ponto:

    .mplb 1                     versao do formato
    .entrada principal          onde a execucao comeca
    .funcao <nome> <nparams> <nslots>
    .linha <n>                  linha do fonte do proximo comando
    .fim

`#` comeca um comentario (fora de texto) e serve so para quem le.
"""
from mplc.intermediario import Temp, Var, Const, texto_mpl, real_posicional

ARITMETICOS = {
    ('+', 'inteiro'): 'SOMA_I', ('+', 'real'): 'SOMA_R', ('+', 'texto'): 'CONCATENA',
    ('-', 'inteiro'): 'SUB_I', ('-', 'real'): 'SUB_R',
    ('*', 'inteiro'): 'MUL_I', ('*', 'real'): 'MUL_R',
    ('/', 'inteiro'): 'DIV_I', ('/', 'real'): 'DIV_R',
    ('%', 'inteiro'): 'RESTO_I',
}

COMPARACOES = {
    '==': 'IGUAL', '!=': 'DIFERENTE',
    '<': 'MENOR', '<=': 'MENOR_IGUAL', '>': 'MAIOR', '>=': 'MAIOR_IGUAL',
    'e': 'E', 'ou': 'OU',
}

ESCRITA = {'inteiro': 'ESCREVE_I', 'real': 'ESCREVE_R', 'logico': 'ESCREVE_L', 'texto': 'ESCREVE_T'}


class Gerador:
    def __init__(self):
        self.linhas = []

    def emit(self, s, comentario=None):
        if comentario:
            s = f'{s:<22}# {comentario}'
        self.linhas.append('  ' + s)

    def slot(self, f, op):
        if isinstance(op, Temp):
            return f.nlocais + op.n, f't{op.n}'
        return op.slot, op.nome

    def empilhar(self, f, op):
        if isinstance(op, Const):
            if op.tipo == 'inteiro':
                self.emit(f'EMPILHA_I {op.valor}')
            elif op.tipo == 'real':
                self.emit(f'EMPILHA_R {real_posicional(op.valor)}')
            elif op.tipo == 'logico':
                self.emit(f"EMPILHA_L {'verdadeiro' if op.valor else 'falso'}")
            else:
                self.emit(f'EMPILHA_T {texto_mpl(op.valor)}')
        else:
            s, nome = self.slot(f, op)
            self.emit(f'CARREGA {s}', nome)

    def guardar(self, f, op):
        s, nome = self.slot(f, op)
        self.emit(f'GUARDA {s}', nome)

    def funcao(self, f):
        nslots = f.nlocais + f.ntemps
        params = ', '.join(f'{n} {t}' for n, t in f.params)
        self.linhas.append(f'.funcao {f.nome} {len(f.params)} {nslots}    # {f.tipo} ({params})')
        linha_atual = None
        for ins in f.instrucoes:
            k, ln = ins[0], ins[1]
            if k == 'rotulo':
                self.linhas.append(f'{ins[2]}:')
                continue
            if ln != linha_atual:
                self.linhas.append(f'  .linha {ln}')
                linha_atual = ln

            if k == 'copia':
                self.empilhar(f, ins[3])
                self.guardar(f, ins[2])
            elif k == 'binario':
                _, _, t, op, a, b, tipo = ins
                self.empilhar(f, a)
                self.empilhar(f, b)
                self.emit(ARITMETICOS.get((op, tipo)) or COMPARACOES[op])
                self.guardar(f, t)
            elif k == 'unario':
                _, _, t, op, a, tipo = ins
                self.empilhar(f, a)
                self.emit('NAO' if op == 'nao' else ('NEG_R' if tipo == 'real' else 'NEG_I'))
                self.guardar(f, t)
            elif k == 'paraReal':
                self.empilhar(f, ins[3])
                self.emit('PARA_REAL')
                self.guardar(f, ins[2])
            elif k == 'chama':
                _, _, t, nome, args, tipo = ins
                for a in args:
                    self.empilhar(f, a)
                self.emit(f'CHAMA {nome} {len(args)}')
                if t is not None:
                    self.guardar(f, t)
                elif tipo != 'vazio':
                    self.emit('DESCARTA', 'valor de retorno nao usado')
            elif k == 'escreva':
                self.empilhar(f, ins[2])
                self.emit(ESCRITA[ins[3]])
            elif k == 'retorne':
                if ins[2] is None:
                    self.emit('RETORNA_VAZIO')
                else:
                    self.empilhar(f, ins[2])
                    self.emit('RETORNA')
            elif k == 'seFalso':
                self.empilhar(f, ins[2])
                self.emit(f'DESVIA_SE_FALSO {ins[3]}')
            elif k == 'desvie':
                self.emit(f'DESVIA {ins[2]}')
            else:
                raise AssertionError(k)
        self.linhas.append('.fim')
        self.linhas.append('')


def gerar(codigo_intermediario):
    """Devolve as linhas do arquivo .mplb."""
    g = Gerador()
    g.linhas += ['# MPL bytecode - maquina de pilha (o conjunto de instrucoes esta no README)',
                 '.mplb 1', '.entrada principal', '']
    for f in codigo_intermediario.funcoes:
        g.funcao(f)
    return g.linhas[:-1]
