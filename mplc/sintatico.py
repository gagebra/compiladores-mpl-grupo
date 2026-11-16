"""
Entrega 2 — analise sintatica.

Descida recursiva escrita a mao: uma funcao por regra da gramatica, e uma
funcao por nivel de precedencia (LINGUAGEM.md secao 3.3). A gramatica em
EBNF esta no README.md.

Como a precedencia vira arvore: cada nivel chama o nivel IMEDIATAMENTE mais
forte para obter os seus operandos. Assim, quanto mais forte o operador,
mais fundo ele fica na arvore. Os binarios usam um LACO (e nao recursao a
direita), e e o laco que deixa a associatividade a esquerda:
`10 - 4 - 3` vira `(10 - 4) - 3`. `nao` e o `-` unario chamam a si mesmos,
e por isso associam a direita.

Erros: o parser para no primeiro, e aponta o token que APARECEU no lugar do
esperado (CONTRATOS.md secao 7).
"""
from mplc.erros import ErroMPL


class No:
    """Um no da arvore. O rotulo e o que sai no --ast."""

    def __init__(self, rotulo, filhos=None, linha=0, coluna=0, **extra):
        self.rotulo = rotulo      # 'binario +', 'literal inteiro 1', 'bloco', ...
        self.filhos = filhos or []
        self.linha = linha
        self.coluna = coluna
        self.extra = extra        # o que a semantica quiser pendurar depois

    @property
    def tipo_no(self):
        return self.extra['no']

    def __getattr__(self, nome):
        # atalho: no.nome, no.op, no.tipo... leem de `extra`
        extra = self.__dict__.get('extra', {})
        if nome in extra:
            return extra[nome]
        raise AttributeError(nome)


TIPOS_DADO = {
    'TIPO_INTEIRO': 'inteiro',
    'TIPO_REAL': 'real',
    'TIPO_LOGICO': 'logico',
    'TIPO_TEXTO': 'texto',
}

# Descricao legivel de cada tipo de token, para as mensagens de erro.
NOMES = {
    'PONTO_VIRGULA': "';'", 'ABRE_PAR': "'('", 'FECHA_PAR': "')'",
    'ABRE_CHAVE': "'{'", 'FECHA_CHAVE': "'}'", 'VIRGULA': "','",
    'ATRIBUI': "'='", 'ID': 'um nome', 'FIM_ARQUIVO': 'o fim do arquivo',
}

# Os niveis binarios, do mais fraco (1) para o mais forte (6).
# Cada entrada: tipos de token aceitos naquele nivel.
NIVEIS_BINARIOS = [
    {'OU'},                                              # 1
    {'E'},                                               # 2
    {'IGUAL', 'DIFERENTE'},                              # 3
    {'MENOR', 'MENOR_IGUAL', 'MAIOR', 'MAIOR_IGUAL'},    # 4
    {'MAIS', 'MENOS'},                                   # 5
    {'VEZES', 'DIVIDE', 'RESTO'},                        # 6
]


def descrever(tok):
    if tok.tipo == 'FIM_ARQUIVO':
        return 'o fim do arquivo'
    return f"'{tok.lexema}'"


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ------------------------------------------------------------ utilitarios
    @property
    def atual(self):
        return self.tokens[self.pos]

    def olhar(self, k=1):
        i = min(self.pos + k, len(self.tokens) - 1)
        return self.tokens[i]

    def avancar(self):
        tok = self.tokens[self.pos]
        if tok.tipo != 'FIM_ARQUIVO':
            self.pos += 1
        return tok

    def eh(self, *tipos):
        return self.atual.tipo in tipos

    def erro(self, esperado, tok=None):
        tok = tok or self.atual
        raise ErroMPL('sintatico', tok.linha, tok.coluna,
                      f"esperava {esperado}, mas veio {descrever(tok)}")

    def esperar(self, tipo, descricao=None):
        if self.atual.tipo != tipo:
            self.erro(descricao or NOMES.get(tipo, tipo))
        return self.avancar()

    # ------------------------------------------------------------- programa
    # programa = { funcao } FIM_ARQUIVO
    def programa(self):
        funcoes = []
        while not self.eh('FIM_ARQUIVO'):
            if not self.eh('FUNCAO'):
                self.erro("'funcao' (todo codigo da MPL fica dentro de uma funcao)")
            funcoes.append(self.funcao())
        return No('programa', funcoes, 1, 1, no='programa')

    # funcao = "funcao" tipo_retorno ID "(" [ parametro { "," parametro } ] ")" bloco
    def funcao(self):
        inicio = self.esperar('FUNCAO')
        if self.eh('TIPO_VAZIO'):
            tipo = 'vazio'
            self.avancar()
        elif self.atual.tipo in TIPOS_DADO:
            tipo = TIPOS_DADO[self.avancar().tipo]
        else:
            self.erro("o tipo de retorno (inteiro, real, logico, texto ou vazio)")
        nome = self.esperar('ID', 'o nome da funcao')
        self.esperar('ABRE_PAR')
        params = []
        if not self.eh('FECHA_PAR'):
            params.append(self.parametro())
            while self.eh('VIRGULA'):
                self.avancar()
                params.append(self.parametro())
        self.esperar('FECHA_PAR', "',' ou ')'")
        corpo = self.bloco()
        nos_params = No('parametros', params, inicio.linha, inicio.coluna, no='parametros')
        return No(f'funcao {nome.lexema} {tipo}', [nos_params, corpo],
                  inicio.linha, inicio.coluna,
                  no='funcao', nome=nome.lexema, tipo=tipo)

    # parametro = tipo ID
    def parametro(self):
        if self.atual.tipo not in TIPOS_DADO:
            self.erro("o tipo do parametro (inteiro, real, logico ou texto)")
        tok_tipo = self.avancar()
        nome = self.esperar('ID', 'o nome do parametro')
        tipo = TIPOS_DADO[tok_tipo.tipo]
        return No(f'parametro {nome.lexema} {tipo}', [], nome.linha, nome.coluna,
                  no='parametro', nome=nome.lexema, tipo=tipo)

    # bloco = "{" { comando } "}"
    def bloco(self):
        abre = self.esperar('ABRE_CHAVE')
        comandos = []
        while not self.eh('FECHA_CHAVE'):
            if self.eh('FIM_ARQUIVO'):
                self.erro("'}' para fechar o bloco")
            comandos.append(self.comando())
        self.avancar()
        return No('bloco', comandos, abre.linha, abre.coluna, no='bloco')

    # ------------------------------------------------------------- comandos
    # comando = declaracao | atribuicao | chamada ";" | se | enquanto
    #         | escreva | retorne | bloco
    def comando(self):
        t = self.atual.tipo
        if t in TIPOS_DADO:
            return self.declaracao()
        if t == 'ID':
            seguinte = self.olhar().tipo
            if seguinte == 'ATRIBUI':
                return self.atribuicao()
            if seguinte == 'ABRE_PAR':
                cham = self.chamada()
                self.esperar('PONTO_VIRGULA')
                cham.extra['comando'] = True
                return cham
            self.erro("'=' ou '(' depois do nome", self.olhar())
        if t == 'SE':
            return self.se()
        if t == 'ENQUANTO':
            return self.enquanto()
        if t == 'ESCREVA':
            return self.escreva()
        if t == 'RETORNE':
            return self.retorne()
        if t == 'ABRE_CHAVE':
            return self.bloco()
        if t == 'TIPO_VAZIO':
            self.erro("um comando ('vazio' so pode ser tipo de retorno de funcao)")
        self.erro("um comando")

    # declaracao = tipo ID [ "=" expressao ] ";"
    def declaracao(self):
        tok_tipo = self.avancar()
        tipo = TIPOS_DADO[tok_tipo.tipo]
        nome = self.esperar('ID', 'o nome da variavel')
        filhos = []
        if self.eh('ATRIBUI'):
            self.avancar()
            filhos.append(self.expressao())
        self.esperar('PONTO_VIRGULA', "';' ou '='" if not filhos else "';'")
        return No(f'declaracao {nome.lexema} {tipo}', filhos, tok_tipo.linha, tok_tipo.coluna,
                  no='declaracao', nome=nome.lexema, tipo=tipo)

    # atribuicao = ID "=" expressao ";"
    def atribuicao(self):
        nome = self.avancar()
        self.esperar('ATRIBUI')
        valor = self.expressao()
        self.esperar('PONTO_VIRGULA')
        return No(f'atribuicao {nome.lexema}', [valor], nome.linha, nome.coluna,
                  no='atribuicao', nome=nome.lexema)

    # se = "se" "(" expressao ")" bloco [ "senao" bloco ]
    def se(self):
        tok = self.avancar()
        self.esperar('ABRE_PAR', "'(' depois do 'se'")
        cond = self.expressao()
        self.esperar('FECHA_PAR')
        if not self.eh('ABRE_CHAVE'):
            self.erro("'{' (as chaves do 'se' sao obrigatorias)")
        filhos = [cond, self.bloco()]
        if self.eh('SENAO'):
            self.avancar()
            if not self.eh('ABRE_CHAVE'):
                self.erro("'{' (as chaves do 'senao' sao obrigatorias)")
            filhos.append(self.bloco())
        return No('se', filhos, tok.linha, tok.coluna, no='se')

    # enquanto = "enquanto" "(" expressao ")" bloco
    def enquanto(self):
        tok = self.avancar()
        self.esperar('ABRE_PAR', "'(' depois do 'enquanto'")
        cond = self.expressao()
        self.esperar('FECHA_PAR')
        if not self.eh('ABRE_CHAVE'):
            self.erro("'{' (as chaves do 'enquanto' sao obrigatorias)")
        return No('enquanto', [cond, self.bloco()], tok.linha, tok.coluna, no='enquanto')

    # escreva = "escreva" "(" expressao ")" ";"
    def escreva(self):
        tok = self.avancar()
        self.esperar('ABRE_PAR', "'(' depois do 'escreva'")
        valor = self.expressao()
        self.esperar('FECHA_PAR')
        self.esperar('PONTO_VIRGULA')
        return No('escreva', [valor], tok.linha, tok.coluna, no='escreva')

    # retorne = "retorne" [ expressao ] ";"
    def retorne(self):
        tok = self.avancar()
        filhos = []
        if not self.eh('PONTO_VIRGULA'):
            filhos.append(self.expressao())
        self.esperar('PONTO_VIRGULA')
        return No('retorne', filhos, tok.linha, tok.coluna, no='retorne')

    # ------------------------------------------------------------ expressoes
    # expressao = ou
    def expressao(self):
        return self.binario(0)

    # Niveis 1 a 6 (ou, e, igualdade, relacional, aditivo, multiplicativo):
    #   nivel_n = nivel_(n+1) { op_n nivel_(n+1) }
    # O laco e que da a associatividade a esquerda.
    def binario(self, nivel):
        if nivel == len(NIVEIS_BINARIOS):
            return self.unario()
        esquerda = self.binario(nivel + 1)
        while self.atual.tipo in NIVEIS_BINARIOS[nivel]:
            op = self.avancar()
            direita = self.binario(nivel + 1)
            esquerda = No(f'binario {op.lexema}', [esquerda, direita], op.linha, op.coluna,
                          no='binario', op=op.lexema)
        return esquerda

    # nivel 7: unario = ( "nao" | "-" ) unario | primario
    def unario(self):
        if self.eh('NAO', 'MENOS'):
            op = self.avancar()
            operando = self.unario()
            return No(f'unario {op.lexema}', [operando], op.linha, op.coluna,
                      no='unario', op=op.lexema)
        return self.primario()

    # nivel 8: primario = literal | chamada | ID | "(" expressao ")"
    def primario(self):
        tok = self.atual
        t = tok.tipo
        if t == 'INTEIRO':
            self.avancar()
            v = int(tok.lexema)
            return No(f'literal inteiro {v}', [], tok.linha, tok.coluna,
                      no='literal', tipo='inteiro', valor=v)
        if t == 'REAL':
            self.avancar()
            v = float(tok.lexema)
            return No(f'literal real {v:.6f}', [], tok.linha, tok.coluna,
                      no='literal', tipo='real', valor=v)
        if t == 'LOGICO':
            self.avancar()
            return No(f'literal logico {tok.lexema}', [], tok.linha, tok.coluna,
                      no='literal', tipo='logico', valor=(tok.lexema == 'verdadeiro'))
        if t == 'TEXTO':
            self.avancar()
            return No(f'literal texto {tok.lexema}', [], tok.linha, tok.coluna,
                      no='literal', tipo='texto', valor=decodificar_texto(tok.lexema),
                      bruto=tok.lexema)
        if t == 'ID':
            if self.olhar().tipo == 'ABRE_PAR':
                return self.chamada()
            self.avancar()
            return No(f'variavel {tok.lexema}', [], tok.linha, tok.coluna,
                      no='variavel', nome=tok.lexema)
        if t == 'ABRE_PAR':
            self.avancar()
            dentro = self.expressao()
            self.esperar('FECHA_PAR')
            return dentro
        self.erro("uma expressao")

    # chamada = ID "(" [ expressao { "," expressao } ] ")"
    def chamada(self):
        nome = self.avancar()
        self.esperar('ABRE_PAR')
        args = []
        if not self.eh('FECHA_PAR'):
            args.append(self.expressao())
            while self.eh('VIRGULA'):
                self.avancar()
                args.append(self.expressao())
        self.esperar('FECHA_PAR', "',' ou ')'")
        return No(f'chamada {nome.lexema}', args, nome.linha, nome.coluna,
                  no='chamada', nome=nome.lexema, comando=False)


def decodificar_texto(lexema):
    """Tira as aspas e troca os escapes pelo caractere que eles representam."""
    corpo = lexema[1:-1]
    saida, i = [], 0
    tabela = {'n': '\n', 't': '\t', '"': '"', '\\': '\\'}
    while i < len(corpo):
        c = corpo[i]
        if c == '\\':
            saida.append(tabela[corpo[i + 1]])
            i += 2
        else:
            saida.append(c)
            i += 1
    return ''.join(saida)


def analisar(tokens):
    """Recebe a lista de Token. Devolve a raiz da arvore (um No 'programa')."""
    return Parser(tokens).programa()


def despejar(no, nivel=0, saida=None):
    """Imprime a arvore no formato do --ast. Ja esta pronto: dois espacos por nivel."""
    saida = saida if saida is not None else []
    saida.append('  ' * nivel + no.rotulo)
    for f in no.filhos:
        despejar(f, nivel + 1, saida)
    return saida
