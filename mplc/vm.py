"""
Entrega 4, terceira metade — a maquina virtual.

Uma maquina de pilha:
  - uma PILHA DE OPERANDOS, compartilhada, onde as instrucoes buscam e deixam
    os valores;
  - uma PILHA DE REGISTROS DE ATIVACAO: cada chamada empilha um registro
    novo, com os seus proprios slots (parametros, locais e temporarios), o
    ponto de volta (funcao e pc de quem chamou) e a linha do fonte em que a
    chamada aconteceu. E isso que faz a recursao funcionar: fatorial(5) e
    fatorial(4) nunca dividem o mesmo `n`.

O laco principal e ITERATIVO: a recursao do programa MPL nao vira recursao
do Python. Por isso o estouro de pilha e detectado pela propria VM (limite de
registros de ativacao), com erro de execucao e codigo de saida 2.

Aritmetica inteira (LINGUAGEM.md 3.2):
  - divisao truncada em direcao a zero:  -7 / 2 == -3
  - resto com o sinal do dividendo:      -7 % 3 == -1
O `//` e o `%` do Python seguem o sinal do divisor, e por isso nao sao usados
diretamente.
"""
import re

from mplc.erros import ErroMPL

LIMITE_CHAMADAS = 100000


def div_trunc(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def resto_trunc(a, b):
    return a - b * div_trunc(a, b)


def formatar(tipo, v):
    """A tabela 4.5 da especificacao."""
    if tipo == 'ESCREVE_I':
        return str(v)
    if tipo == 'ESCREVE_R':
        return f'{v:.6f}'
    if tipo == 'ESCREVE_L':
        return 'verdadeiro' if v else 'falso'
    return v


_ESCAPES = {'n': '\n', 't': '\t', '"': '"', '\\': '\\'}
_TEXTO = re.compile(r'"((?:\\.|[^"\\])*)"')


def ler_texto(literal):
    m = _TEXTO.match(literal)
    corpo = m.group(1)
    return re.sub(r'\\(.)', lambda x: _ESCAPES[x.group(1)], corpo)


class Funcao:
    def __init__(self, nome, nparams, nslots):
        self.nome = nome
        self.nparams = nparams
        self.nslots = nslots
        self.codigo = []      # lista de (opcode, argumento, linha_fonte)
        self.rotulos = {}


def carregar(texto):
    """Le o .mplb e devolve (funcoes, nome_da_entrada)."""
    funcoes, entrada, atual, linha_fonte = {}, 'principal', None, 0
    for n, bruta in enumerate(texto.split('\n'), 1):
        s = bruta.strip()
        if not s or s.startswith('#'):
            continue
        if not s.startswith('EMPILHA_T') and '#' in s:
            s = s.split('#', 1)[0].strip()
        partes = s.split(None, 1)
        op = partes[0]
        arg = partes[1] if len(partes) > 1 else None

        if op == '.mplb':
            continue
        if op == '.entrada':
            entrada = arg
        elif op == '.funcao':
            nome, nparams, nslots = arg.split()
            atual = Funcao(nome, int(nparams), int(nslots))
            funcoes[nome] = atual
        elif op == '.fim':
            atual = None
        elif op == '.linha':
            linha_fonte = int(arg)
        elif op.endswith(':'):
            atual.rotulos[op[:-1]] = len(atual.codigo)
        else:
            if op == 'EMPILHA_I':
                arg = int(arg)
            elif op == 'EMPILHA_R':
                arg = float(arg)
            elif op == 'EMPILHA_L':
                arg = (arg == 'verdadeiro')
            elif op == 'EMPILHA_T':
                arg = ler_texto(arg)
            elif op in ('CARREGA', 'GUARDA'):
                arg = int(arg)
            elif op == 'CHAMA':
                nome, nargs = arg.split()
                arg = (nome, int(nargs))
            atual.codigo.append((op, arg, linha_fonte))

    # resolve os rotulos e as funcoes chamadas, para o laco nao procurar por nome
    for f in funcoes.values():
        resolvido = []
        for op, arg, ln in f.codigo:
            if op in ('DESVIA', 'DESVIA_SE_FALSO'):
                arg = f.rotulos[arg]
            elif op == 'CHAMA':
                arg = funcoes[arg[0]]
            resolvido.append((op, arg, ln))
        f.codigo = resolvido
    return funcoes, entrada


def executar(texto_mplb, saida):
    """Executa o bytecode. Escreve o que o programa imprimir em `saida`."""
    funcoes, entrada = carregar(texto_mplb)
    escrito = []
    try:
        _rodar(funcoes[entrada], escrito)
    finally:
        if escrito:
            saida.write('\n'.join(escrito) + '\n')
            saida.flush()


def _rodar(principal, escrito):
    pilha = []
    # registro de ativacao: [funcao, pc, slots, linha da chamada]
    quadros = []
    f = principal
    codigo = f.codigo
    slots = [None] * f.nslots
    pc = 0
    linha = 0

    def erro(msg):
        raise ErroMPL('execucao', linha, 1, msg)

    while True:
        op, arg, linha = codigo[pc]
        pc += 1

        if op == 'CARREGA':
            pilha.append(slots[arg])
        elif op == 'GUARDA':
            slots[arg] = pilha.pop()
        elif op in ('EMPILHA_I', 'EMPILHA_R', 'EMPILHA_L', 'EMPILHA_T'):
            pilha.append(arg)

        elif op in ('SOMA_I', 'SOMA_R', 'CONCATENA'):
            b = pilha.pop(); pilha[-1] = pilha[-1] + b
        elif op in ('SUB_I', 'SUB_R'):
            b = pilha.pop(); pilha[-1] = pilha[-1] - b
        elif op in ('MUL_I', 'MUL_R'):
            b = pilha.pop(); pilha[-1] = pilha[-1] * b
        elif op == 'DIV_I':
            b = pilha.pop()
            if b == 0:
                erro('divisao por zero')
            pilha[-1] = div_trunc(pilha[-1], b)
        elif op == 'DIV_R':
            b = pilha.pop()
            if b == 0:
                erro('divisao por zero')
            pilha[-1] = pilha[-1] / b
        elif op == 'RESTO_I':
            b = pilha.pop()
            if b == 0:
                erro('resto da divisao por zero')
            pilha[-1] = resto_trunc(pilha[-1], b)
        elif op == 'NEG_I' or op == 'NEG_R':
            pilha[-1] = -pilha[-1]
        elif op == 'PARA_REAL':
            pilha[-1] = float(pilha[-1])

        elif op == 'IGUAL':
            b = pilha.pop(); pilha[-1] = pilha[-1] == b
        elif op == 'DIFERENTE':
            b = pilha.pop(); pilha[-1] = pilha[-1] != b
        elif op == 'MENOR':
            b = pilha.pop(); pilha[-1] = pilha[-1] < b
        elif op == 'MENOR_IGUAL':
            b = pilha.pop(); pilha[-1] = pilha[-1] <= b
        elif op == 'MAIOR':
            b = pilha.pop(); pilha[-1] = pilha[-1] > b
        elif op == 'MAIOR_IGUAL':
            b = pilha.pop(); pilha[-1] = pilha[-1] >= b
        elif op == 'E':
            b = pilha.pop(); pilha[-1] = pilha[-1] and b
        elif op == 'OU':
            b = pilha.pop(); pilha[-1] = pilha[-1] or b
        elif op == 'NAO':
            pilha[-1] = not pilha[-1]

        elif op == 'DESVIA':
            pc = arg
        elif op == 'DESVIA_SE_FALSO':
            if not pilha.pop():
                pc = arg

        elif op == 'CHAMA':
            if len(quadros) >= LIMITE_CHAMADAS:
                erro(f'estouro de pilha: mais de {LIMITE_CHAMADAS} chamadas aninhadas '
                     f'(recursao sem fim?)')
            quadros.append((f, pc, slots, linha))
            f = arg
            novos = [None] * f.nslots
            n = f.nparams
            if n:
                novos[:n] = pilha[-n:]
                del pilha[-n:]
            slots, codigo, pc = novos, f.codigo, 0
        elif op == 'RETORNA' or op == 'RETORNA_VAZIO':
            if not quadros:
                return
            f, pc, slots, linha = quadros.pop()
            codigo = f.codigo
        elif op == 'DESCARTA':
            pilha.pop()

        elif op.startswith('ESCREVE'):
            escrito.append(formatar(op, pilha.pop()))
        else:
            raise ErroMPL('execucao', linha, 1, f'instrucao desconhecida {op}')
