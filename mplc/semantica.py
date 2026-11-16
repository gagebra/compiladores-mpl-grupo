"""
Entrega 3 — analise semantica.

Tabela de simbolos, escopos aninhados e verificacao de tipos, em duas passadas:

  1a passada: percorre so as funcoes do programa e coleta a assinatura de
     cada uma no escopo 0 (global). Por isso uma funcao pode ser chamada
     antes de aparecer no arquivo.
  2a passada: percorre cada corpo com uma PILHA de escopos. O topo da pilha
     e o escopo atual; a busca de um nome vai do topo para a base, e e isso
     que da o sombreamento. Fechar um bloco e desempilhar.

Cada escopo, alem de estar na pilha enquanto vive, fica guardado numa lista
em ordem de abertura: e essa lista que o --tabela imprime, e e ela que deixa
o numero do escopo e o pai dele disponiveis depois que a pilha ja esvaziou.

A analise tambem anota a arvore para as fases seguintes:
  - cada expressao ganha extra['tipo_expr'];
  - cada variavel, declaracao, atribuicao e parametro ganha extra['simbolo'],
    o Simbolo exato a que o nome se refere (com o numero do slot no registro
    de ativacao da funcao).
"""
from mplc.erros import ErroMPL

NUMERICOS = ('inteiro', 'real')


class Simbolo:
    def __init__(self, nome, categoria, tipo, linha, params=None, slot=None):
        self.nome = nome
        self.categoria = categoria    # 'funcao', 'parametro' ou 'variavel'
        self.tipo = tipo              # para funcao: o tipo de retorno
        self.linha = linha
        self.params = params or []    # para funcao: lista de tipos dos parametros
        self.slot = slot              # para parametro/variavel: posicao no registro de ativacao

    def linha_tabela(self):
        if self.categoria == 'funcao':
            tipo = f"{self.tipo}({','.join(self.params)})"
        else:
            tipo = self.tipo
        return f"  {self.nome}|{self.categoria}|{tipo}|{self.linha}"


class Escopo:
    def __init__(self, numero, descricao, pai):
        self.numero = numero
        self.descricao = descricao    # 'global', 'funcao <nome>' ou 'bloco'
        self.pai = pai                # o Escopo pai (None no global)
        self.simbolos = {}            # dict preserva a ordem de insercao

    def cabecalho(self):
        if self.pai is None:
            return f"escopo {self.numero} {self.descricao}"
        return f"escopo {self.numero} {self.descricao} pai {self.pai.numero}"


class Tabela:
    """O resultado da analise: todos os escopos, na ordem em que abriram."""

    def __init__(self):
        self.escopos = []
        self.funcoes = {}             # nome -> Simbolo da funcao
        self.locais = {}              # nome da funcao -> quantidade de slots de parametros e variaveis


def compativel(destino, origem):
    """Regra 3.1: so existe a conversao inteiro -> real."""
    return destino == origem or (destino == 'real' and origem == 'inteiro')


class Analisador:
    def __init__(self):
        self.tabela = Tabela()
        self.pilha = []
        self.funcao_atual = None
        self.proximo_slot = 0

    # --------------------------------------------------------------- escopos
    def abrir(self, descricao):
        pai = self.pilha[-1] if self.pilha else None
        esc = Escopo(len(self.tabela.escopos), descricao, pai)
        self.tabela.escopos.append(esc)
        self.pilha.append(esc)
        return esc

    def fechar(self):
        self.pilha.pop()

    def declarar(self, nome, categoria, tipo, no):
        topo = self.pilha[-1]
        if nome in topo.simbolos:
            anterior = topo.simbolos[nome]
            self.erro(no, f"'{nome}' ja foi declarado neste escopo (na linha {anterior.linha})")
        sim = Simbolo(nome, categoria, tipo, no.linha, slot=self.proximo_slot)
        self.proximo_slot += 1
        topo.simbolos[nome] = sim
        return sim

    def buscar(self, nome):
        # do topo para a base: o escopo mais interno vence (sombreamento)
        for esc in reversed(self.pilha[1:]):   # o global so tem funcoes
            if nome in esc.simbolos:
                return esc.simbolos[nome]
        return None

    def erro(self, no, msg):
        raise ErroMPL('semantico', no.linha, no.coluna, msg)

    # ------------------------------------------------------------- programa
    def analisar(self, programa):
        glob = self.abrir('global')

        # 1a passada: so as assinaturas
        for f in programa.filhos:
            if f.nome in glob.simbolos:
                ant = glob.simbolos[f.nome]
                self.erro(f, f"a funcao '{f.nome}' ja foi definida na linha {ant.linha} "
                             f"(a MPL nao tem sobrecarga)")
            tipos = [p.tipo for p in f.filhos[0].filhos]
            glob.simbolos[f.nome] = Simbolo(f.nome, 'funcao', f.tipo, f.linha, params=tipos)
        self.tabela.funcoes = glob.simbolos

        # principal: existe, sem parametros, devolve vazio
        if 'principal' not in glob.simbolos:
            raise ErroMPL('semantico', 1, 1, "o programa nao tem a funcao 'principal'")
        p = glob.simbolos['principal']
        no_p = next(f for f in programa.filhos if f.nome == 'principal')
        if p.params:
            self.erro(no_p, "a funcao 'principal' nao pode receber parametros")
        if p.tipo != 'vazio':
            self.erro(no_p, f"a funcao 'principal' tem que devolver vazio, nao {p.tipo}")

        # 2a passada: os corpos
        for f in programa.filhos:
            self.funcao(f)

        self.fechar()
        return self.tabela

    def funcao(self, no):
        self.funcao_atual = self.tabela.funcoes[no.nome]
        self.proximo_slot = 0
        params, corpo = no.filhos

        self.abrir(f'funcao {no.nome}')
        for p in params.filhos:
            p.extra['simbolo'] = self.declarar(p.nome, 'parametro', p.tipo, p)
        self.bloco(corpo)
        self.fechar()

        self.tabela.locais[no.nome] = self.proximo_slot
        if no.tipo != 'vazio' and not garante_retorno(corpo):
            self.erro(no, f"a funcao '{no.nome}' devolve {no.tipo}, mas existe um caminho "
                          f"que chega ao fim sem 'retorne'")

    # ------------------------------------------------------------- comandos
    def bloco(self, no):
        self.abrir('bloco')
        for cmd in no.filhos:
            self.comando(cmd)
        self.fechar()

    def comando(self, no):
        tipo = no.tipo_no
        if tipo == 'declaracao':
            if no.filhos:
                t = self.expressao(no.filhos[0])
                if not compativel(no.tipo, t):
                    self.erro(no, f"nao da para iniciar '{no.nome}' ({no.tipo}) com um valor {t}")
            # declara DEPOIS de olhar a expressao: em `inteiro x = x + 1;`
            # o x da direita e o de fora
            no.extra['simbolo'] = self.declarar(no.nome, 'variavel', no.tipo, no)

        elif tipo == 'atribuicao':
            sim = self.buscar(no.nome)
            if sim is None:
                self.erro(no, f"a variavel '{no.nome}' nao foi declarada")
            t = self.expressao(no.filhos[0])
            if not compativel(sim.tipo, t):
                self.erro(no, f"nao da para guardar um valor {t} em '{no.nome}', que e {sim.tipo}")
            no.extra['simbolo'] = sim

        elif tipo == 'chamada':
            # como comando, qualquer tipo de retorno serve (o valor e descartado)
            self.chamada(no)

        elif tipo in ('se', 'enquanto'):
            t = self.expressao(no.filhos[0])
            if t != 'logico':
                self.erro(no.filhos[0], f"a condicao do '{tipo}' tem que ser logico, nao {t}")
            for b in no.filhos[1:]:
                self.bloco(b)

        elif tipo == 'escreva':
            self.expressao(no.filhos[0])

        elif tipo == 'retorne':
            esperado = self.funcao_atual.tipo
            if not no.filhos:
                if esperado != 'vazio':
                    self.erro(no, f"a funcao '{self.funcao_atual.nome}' tem que devolver um {esperado}")
            else:
                if esperado == 'vazio':
                    self.erro(no, f"a funcao '{self.funcao_atual.nome}' e vazio e nao devolve valor "
                                  f"(use 'retorne;')")
                t = self.expressao(no.filhos[0])
                if not compativel(esperado, t):
                    self.erro(no, f"a funcao '{self.funcao_atual.nome}' devolve {esperado}, "
                                  f"mas este retorne entrega {t}")

        elif tipo == 'bloco':
            self.bloco(no)

    # ----------------------------------------------------------- expressoes
    def expressao(self, no):
        t = self._expressao(no)
        no.extra['tipo_expr'] = t
        return t

    def _expressao(self, no):
        tipo = no.tipo_no
        if tipo == 'literal':
            return no.tipo

        if tipo == 'variavel':
            sim = self.buscar(no.nome)
            if sim is None:
                if no.nome in self.tabela.funcoes:
                    self.erro(no, f"'{no.nome}' e uma funcao; para chamar, use {no.nome}(...)")
                self.erro(no, f"a variavel '{no.nome}' nao foi declarada")
            no.extra['simbolo'] = sim
            return sim.tipo

        if tipo == 'chamada':
            t = self.chamada(no)
            if t == 'vazio':
                self.erro(no, f"a funcao '{no.nome}' e vazio e nao devolve valor; "
                              f"so pode ser chamada como comando")
            return t

        if tipo == 'unario':
            t = self.expressao(no.filhos[0])
            if no.op == 'nao':
                if t != 'logico':
                    self.erro(no, f"'nao' precisa de um logico, e recebeu {t}")
                return 'logico'
            if t not in NUMERICOS:
                self.erro(no, f"o '-' unario precisa de um numero, e recebeu {t}")
            return t

        if tipo == 'binario':
            a = self.expressao(no.filhos[0])
            b = self.expressao(no.filhos[1])
            return self.tipo_binario(no, no.op, a, b)

        raise AssertionError(f'no inesperado: {no.rotulo}')

    def tipo_binario(self, no, op, a, b):
        """A tabela 3.2 da especificacao."""
        def recusa(exigencia):
            self.erro(no, f"'{op}' {exigencia}, mas recebeu {a} e {b}")

        if op == '+':
            if a == 'texto' and b == 'texto':
                return 'texto'
            if a in NUMERICOS and b in NUMERICOS:
                return 'inteiro' if a == b == 'inteiro' else 'real'
            if 'texto' in (a, b):
                recusa("junta dois textos (numero nao vira texto)")
            recusa("precisa de dois numeros ou de dois textos")
        if op in ('-', '*', '/'):
            if a in NUMERICOS and b in NUMERICOS:
                return 'inteiro' if a == b == 'inteiro' else 'real'
            recusa("precisa de dois numeros")
        if op == '%':
            if a == b == 'inteiro':
                return 'inteiro'
            recusa("so aceita inteiro e inteiro")
        if op in ('==', '!='):
            if a == b or (a in NUMERICOS and b in NUMERICOS):
                return 'logico'
            recusa("compara dois valores do mesmo tipo")
        if op in ('<', '<=', '>', '>='):
            if a in NUMERICOS and b in NUMERICOS:
                return 'logico'
            recusa("compara dois numeros")
        if op in ('e', 'ou'):
            if a == b == 'logico':
                return 'logico'
            recusa("precisa de dois logicos")
        raise AssertionError(op)

    def chamada(self, no):
        f = self.tabela.funcoes.get(no.nome)
        if f is None:
            if self.buscar(no.nome) is not None:
                self.erro(no, f"'{no.nome}' e uma variavel, nao uma funcao")
            self.erro(no, f"a funcao '{no.nome}' nao existe")
        if len(no.filhos) != len(f.params):
            self.erro(no, f"'{no.nome}' recebe {len(f.params)} argumento(s), "
                          f"mas foi chamada com {len(no.filhos)}")
        for i, (arg, esperado) in enumerate(zip(no.filhos, f.params), 1):
            t = self.expressao(arg)
            if not compativel(esperado, t):
                self.erro(arg, f"o argumento {i} de '{no.nome}' tem que ser {esperado}, nao {t}")
        no.extra['tipo_expr'] = f.tipo
        return f.tipo


def garante_retorno(no):
    """
    Decide pela ESTRUTURA, nunca pelo valor das condicoes:
      - um retorne garante;
      - um bloco garante se algum comando dele garante;
      - um se garante so se tiver senao e os DOIS lados garantirem;
      - um enquanto nunca garante (pode nao rodar nenhuma vez).
    """
    tipo = no.tipo_no
    if tipo == 'retorne':
        return True
    if tipo == 'bloco':
        return any(garante_retorno(c) for c in no.filhos)
    if tipo == 'se':
        return len(no.filhos) == 3 and garante_retorno(no.filhos[1]) and garante_retorno(no.filhos[2])
    return False


def analisar(arvore):
    """Percorre a arvore, monta a tabela e confere os tipos. Devolve a tabela."""
    return Analisador().analisar(arvore)


def despejar(tabela):
    """Devolve as linhas do --tabela, no formato da secao 4 do contrato."""
    linhas = []
    for esc in tabela.escopos:
        linhas.append(esc.cabecalho())
        for sim in esc.simbolos.values():
            linhas.append(sim.linha_tabela())
    return linhas
