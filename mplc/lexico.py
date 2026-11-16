"""
Entrega 1 — analise lexica.

Transforma o texto do programa numa lista de tokens.

O analisador e um automato escrito a mao: le o fonte caractere por caractere,
contando linha e coluna (ambas comecam em 1), e decide pelo primeiro
caractere qual "sub-automato" vai reconhecer o token:

  letra ou _      -> identificador ou palavra reservada
  digito          -> inteiro ou real (o ponto exige digito dos dois lados)
  "               -> texto, com os escapes \\n \\t \\" \\\\
  / seguido de /  -> comentario de linha
  / seguido de *  -> comentario de bloco (nao aninha; o primeiro */ fecha)
  simbolo         -> operador ou delimitador, testando SEMPRE os de dois
                     caracteres (<= >= == !=) antes dos de um.

O ultimo token e sempre FIM_ARQUIVO, com lexema vazio, na posicao logo
depois do ultimo caractere do arquivo (CONTRATOS.md secao 7).
"""
from mplc.erros import ErroMPL


class Token:
    __slots__ = ('tipo', 'lexema', 'linha', 'coluna')

    def __init__(self, tipo, lexema, linha, coluna):
        self.tipo = tipo          # 'ID', 'INTEIRO', 'MAIS', ... (a lista esta no contrato)
        self.lexema = lexema      # o texto exato como apareceu no fonte
        self.linha = linha
        self.coluna = coluna      # a coluna do PRIMEIRO caractere do token

    def __str__(self):
        # esta e a linha que o --tokens imprime; nao mexam no formato
        return f"{self.linha},{self.coluna},{self.tipo},{self.lexema}"

    def __repr__(self):
        return f"Token({self.tipo}, {self.lexema!r}, {self.linha}:{self.coluna})"


PALAVRAS_RESERVADAS = {
    'funcao': 'FUNCAO',
    'retorne': 'RETORNE',
    'se': 'SE',
    'senao': 'SENAO',
    'enquanto': 'ENQUANTO',
    'escreva': 'ESCREVA',
    'inteiro': 'TIPO_INTEIRO',
    'real': 'TIPO_REAL',
    'logico': 'TIPO_LOGICO',
    'texto': 'TIPO_TEXTO',
    'vazio': 'TIPO_VAZIO',
    'verdadeiro': 'LOGICO',
    'falso': 'LOGICO',
    'e': 'E',
    'ou': 'OU',
    'nao': 'NAO',
}

# Os de dois caracteres vem num dicionario separado e sao testados primeiro.
SIMBOLOS_DUPLOS = {
    '==': 'IGUAL',
    '!=': 'DIFERENTE',
    '<=': 'MENOR_IGUAL',
    '>=': 'MAIOR_IGUAL',
}

SIMBOLOS_SIMPLES = {
    '+': 'MAIS',
    '-': 'MENOS',
    '*': 'VEZES',
    '/': 'DIVIDE',
    '%': 'RESTO',
    '<': 'MENOR',
    '>': 'MAIOR',
    '=': 'ATRIBUI',
    '(': 'ABRE_PAR',
    ')': 'FECHA_PAR',
    '{': 'ABRE_CHAVE',
    '}': 'FECHA_CHAVE',
    ',': 'VIRGULA',
    ';': 'PONTO_VIRGULA',
}

ESCAPES_VALIDOS = {'n', 't', '"', '\\'}


def eh_letra(c):
    return ('a' <= c <= 'z') or ('A' <= c <= 'Z') or c == '_'


def eh_digito(c):
    return '0' <= c <= '9'


class Lexico:
    def __init__(self, fonte):
        # Tira um eventual BOM do comeco: ele nao e parte do programa.
        if fonte.startswith('﻿'):
            fonte = fonte[1:]
        self.fonte = fonte
        self.pos = 0
        self.linha = 1
        self.coluna = 1
        self.tokens = []

    # ------------------------------------------------------------- leitura
    def atual(self):
        return self.fonte[self.pos] if self.pos < len(self.fonte) else ''

    def proximo(self, k=1):
        p = self.pos + k
        return self.fonte[p] if p < len(self.fonte) else ''

    def avancar(self):
        """Consome um caractere, atualizando linha e coluna."""
        c = self.fonte[self.pos]
        self.pos += 1
        if c == '\n':
            self.linha += 1
            self.coluna = 1
        else:
            self.coluna += 1
        return c

    def erro(self, linha, coluna, msg):
        raise ErroMPL('lexico', linha, coluna, msg)

    def emitir(self, tipo, lexema, linha, coluna):
        self.tokens.append(Token(tipo, lexema, linha, coluna))

    # --------------------------------------------------------------- laco
    def analisar(self):
        while self.pos < len(self.fonte):
            c = self.atual()

            if c in ' \t\r\n':
                self.avancar()
            elif c == '/' and self.proximo() == '/':
                self.comentario_linha()
            elif c == '/' and self.proximo() == '*':
                self.comentario_bloco()
            elif eh_letra(c):
                self.identificador()
            elif eh_digito(c):
                self.numero()
            elif c == '"':
                self.texto()
            elif c == '.':
                # um ponto que nao veio depois de digitos: o caso do `.5`
                self.erro(self.linha, self.coluna,
                          "numero real sem digito antes do ponto (escreva 0.5, nao .5)")
            else:
                self.simbolo()

        self.emitir('FIM_ARQUIVO', '', self.linha, self.coluna)
        return self.tokens

    # ---------------------------------------------------------- comentarios
    def comentario_linha(self):
        while self.pos < len(self.fonte) and self.atual() != '\n':
            self.avancar()

    def comentario_bloco(self):
        linha, coluna = self.linha, self.coluna
        self.avancar()  # /
        self.avancar()  # *
        while True:
            if self.pos >= len(self.fonte):
                self.erro(linha, coluna, "comentario de bloco aberto aqui e nunca fechado com */")
            if self.atual() == '*' and self.proximo() == '/':
                self.avancar()
                self.avancar()
                return
            self.avancar()

    # ----------------------------------------------------- nomes e numeros
    def identificador(self):
        linha, coluna, ini = self.linha, self.coluna, self.pos
        while self.pos < len(self.fonte) and (eh_letra(self.atual()) or eh_digito(self.atual())):
            self.avancar()
        lexema = self.fonte[ini:self.pos]
        self.emitir(PALAVRAS_RESERVADAS.get(lexema, 'ID'), lexema, linha, coluna)

    def numero(self):
        linha, coluna, ini = self.linha, self.coluna, self.pos
        while eh_digito(self.atual()):
            self.avancar()
        tipo = 'INTEIRO'
        if self.atual() == '.':
            if not eh_digito(self.proximo()):
                # o caso do `3.`: o defeito esta no ponto
                self.erro(self.linha, self.coluna,
                          "numero real sem digito depois do ponto (escreva 3.0, nao 3.)")
            self.avancar()  # .
            while eh_digito(self.atual()):
                self.avancar()
            tipo = 'REAL'
            if self.atual() == '.':
                self.erro(self.linha, self.coluna, "numero com dois pontos decimais")
        self.emitir(tipo, self.fonte[ini:self.pos], linha, coluna)

    # --------------------------------------------------------------- texto
    def texto(self):
        linha, coluna, ini = self.linha, self.coluna, self.pos
        self.avancar()  # aspas de abertura
        while True:
            c = self.atual()
            if c == '' or c == '\n':
                self.erro(linha, coluna, "texto aberto aqui e nao fechado na mesma linha")
            if c == '"':
                self.avancar()
                break
            if c == '\\':
                l, col = self.linha, self.coluna
                seguinte = self.proximo()
                if seguinte in ('', '\n'):
                    self.erro(linha, coluna, "texto aberto aqui e nao fechado na mesma linha")
                if seguinte not in ESCAPES_VALIDOS:
                    self.erro(l, col, f"escape invalido '\\{seguinte}' (aceitos: \\n \\t \\\" \\\\)")
                self.avancar()
                self.avancar()
                continue
            self.avancar()
        self.emitir('TEXTO', self.fonte[ini:self.pos], linha, coluna)

    # ------------------------------------------------------------ simbolos
    def simbolo(self):
        linha, coluna = self.linha, self.coluna
        dois = self.atual() + self.proximo()
        if dois in SIMBOLOS_DUPLOS:
            self.avancar()
            self.avancar()
            self.emitir(SIMBOLOS_DUPLOS[dois], dois, linha, coluna)
            return
        c = self.atual()
        if c in SIMBOLOS_SIMPLES:
            self.avancar()
            self.emitir(SIMBOLOS_SIMPLES[c], c, linha, coluna)
            return
        if c == '!':
            self.erro(linha, coluna, "'!' sozinho nao existe; para negar use 'nao', para diferente use '!='")
        self.erro(linha, coluna, f"caractere inesperado {c!r}")


def analisar(fonte):
    """Recebe o texto do programa. Devolve a lista de Token."""
    return Lexico(fonte).analisar()
