# Compilador MPL do grupo

Compilador completo para a MPL (`LINGUAGEM.md`), escrito em Python 3 só com
a biblioteca padrão, sem gerador de parser. As quatro fases ficam em `mplc/`:

| Fase | Arquivo | Despejo |
|---|---|---|
| Léxico | `mplc/lexico.py` | `./compilar --tokens prog.mpl` |
| Sintático | `mplc/sintatico.py` | `./compilar --ast prog.mpl` |
| Semântico | `mplc/semantica.py` | `./compilar --tabela prog.mpl` |
| Intermediário | `mplc/intermediario.py` | `./compilar --ir prog.mpl` |
| Geração | `mplc/gerador.py` | `./compilar prog.mpl` grava `prog.mplb` |
| Máquina virtual | `mplc/vm.py` | `./executar prog.mplb` |

```bash
make verificar          # as quatro entregas: 93 de 93
./compilar exemplos/demonstracao.mpl && ./executar exemplos/demonstracao.mplb
```

---

## Entrega 1: tabela de tokens

O léxico é um autômato escrito à mão (`Lexico.analisar`). Ele lê caractere
por caractere, contando linha e coluna a partir de 1, e escolhe o
sub-autômato pelo primeiro caractere. Os símbolos de dois caracteres são
sempre testados **antes** dos de um, para `<=` não virar `<` `=`.

| TIPO | Expressão regular / regra | Exemplo |
|---|---|---|
| `ID` | `[A-Za-z_][A-Za-z0-9_]*` que não seja palavra reservada | `soma`, `_x1` |
| `INTEIRO` | `[0-9]+` | `42` |
| `REAL` | `[0-9]+\.[0-9]+` (dígito obrigatório dos dois lados) | `3.14` |
| `LOGICO` | `verdadeiro` \| `falso` | `falso` |
| `TEXTO` | `"([^"\\\n]` \| `\\[nt"\\])*"` (numa linha só) | `"a\nb"` |
| `FUNCAO` `RETORNE` `SE` `SENAO` `ENQUANTO` `ESCREVA` | a palavra exata | `funcao` |
| `TIPO_INTEIRO` `TIPO_REAL` `TIPO_LOGICO` `TIPO_TEXTO` `TIPO_VAZIO` | `inteiro` `real` `logico` `texto` `vazio` | |
| `E` `OU` `NAO` | `e` `ou` `nao` | |
| `MAIS` `MENOS` `VEZES` `DIVIDE` `RESTO` | `+` `-` `*` `/` `%` | |
| `IGUAL` `DIFERENTE` | `==` `!=` | |
| `MENOR_IGUAL` `MAIOR_IGUAL` | `<=` `>=` | |
| `MENOR` `MAIOR` | `<` `>` | |
| `ATRIBUI` | `=` | |
| `ABRE_PAR` `FECHA_PAR` `ABRE_CHAVE` `FECHA_CHAVE` | `(` `)` `{` `}` | |
| `VIRGULA` `PONTO_VIRGULA` | `,` `;` | |
| `FIM_ARQUIVO` | fim da entrada (lexema vazio) | |
| *(descartado)* espaço | `[ \t\r\n]+` | |
| *(descartado)* comentário de linha | `//[^\n]*` | |
| *(descartado)* comentário de bloco | `/\*` … primeiro `*/` (não aninha) | |

Identificadores e palavras reservadas são reconhecidos pela mesma regra; no
fim do lexema, um dicionário diz se ele é reservado. Por isso `sePossivel` é
um `ID` só.

**Erros léxicos** (`erro lexico: linha L, coluna C: ...`, código 1), sempre
no caractere que estragou o token:

| Situação | Posição relatada |
|---|---|
| `3.`: ponto sem dígito depois | o ponto |
| `.5`: ponto sem dígito antes | o ponto |
| escape inválido (`"a\qb"`) | a barra invertida |
| texto sem aspas de fechamento na mesma linha | a aspa de abertura |
| `/*` nunca fechado | onde o comentário **começou** |
| caractere fora da linguagem (`@`, `!` sozinho, `#`…) | o caractere |

---

## Entrega 2: gramática (EBNF)

```ebnf
programa    = { funcao } FIM_ARQUIVO ;
funcao      = "funcao" tipo_ret ID "(" [ parametro { "," parametro } ] ")" bloco ;
tipo_ret    = tipo | "vazio" ;
tipo        = "inteiro" | "real" | "logico" | "texto" ;
parametro   = tipo ID ;
bloco       = "{" { comando } "}" ;

comando     = declaracao | atribuicao | chamada ";" | se | enquanto
            | escreva | retorne | bloco ;
declaracao  = tipo ID [ "=" expressao ] ";" ;
atribuicao  = ID "=" expressao ";" ;
se          = "se" "(" expressao ")" bloco [ "senao" bloco ] ;
enquanto    = "enquanto" "(" expressao ")" bloco ;
escreva     = "escreva" "(" expressao ")" ";" ;
retorne     = "retorne" [ expressao ] ";" ;

(* um nivel por precedencia, do mais fraco (1) para o mais forte (8) *)
expressao   = ou ;
ou          = e          { "ou" e } ;                               (* 1 *)
e           = igualdade  { "e" igualdade } ;                        (* 2 *)
igualdade   = relacional { ( "==" | "!=" ) relacional } ;           (* 3 *)
relacional  = aditiva    { ( "<" | "<=" | ">" | ">=" ) aditiva } ;  (* 4 *)
aditiva     = multiplic  { ( "+" | "-" ) multiplic } ;              (* 5 *)
multiplic   = unario     { ( "*" | "/" | "%" ) unario } ;           (* 6 *)
unario      = ( "nao" | "-" ) unario | primario ;                   (* 7 *)
primario    = INTEIRO | REAL | LOGICO | TEXTO                       (* 8 *)
            | chamada | ID | "(" expressao ")" ;
chamada     = ID "(" [ expressao { "," expressao } ] ")" ;
```

**Como a precedência está codificada:** cada nível só enxerga como operando o
nível imediatamente mais forte, então um operador mais forte fica sempre mais
fundo na árvore. A repetição `{ op operando }` vira um **laço** no parser
(`Parser.binario`), que pendura cada novo nó por cima do anterior e por isso
associa à esquerda: `10 - 4 - 3` vira `(10 - 4) - 3`. `nao` e `-` unário
chamam a si mesmos e associam à direita. Os seis níveis binários são uma
tabela (`NIVEIS_BINARIOS`) e uma única função recursiva no nível; os níveis 7
e 8 são `unario` e `primario`.

No `comando`, um `ID` decide pelo token seguinte: `=` é atribuição, `(` é
chamada.

**Erros sintáticos** apontam o token que **apareceu** no lugar do esperado.
Faltando `;` no fim da linha 2, o erro sai no primeiro token da linha 3.

```
$ ./compilar --ast prog.mpl      # escreva(10 - 4 - 3); escreva(1 + 2 * 3);
      escreva
        binario -
          binario -
            literal inteiro 10
            literal inteiro 4
          literal inteiro 3
      escreva
        binario +
          literal inteiro 1
          binario *
            literal inteiro 2
            literal inteiro 3
```

---

## Entrega 3: escopos

Usamos uma **pilha de escopos** durante a análise e, ao lado dela, uma
**lista de todos os escopos em ordem de abertura**. Cada `Escopo` tem
número, descrição, ponteiro para o pai e um dicionário de símbolos (que
preserva a ordem de declaração). Abrir um bloco é empilhar; fechar é
desempilhar; procurar um nome é percorrer a pilha do topo para a base, e o
primeiro que achar vence. É isso que dá o sombreamento, e a variável de fora
"volta" sozinha quando o bloco interno sai da pilha.

Escolhemos a pilha porque ela espelha exatamente a regra da linguagem: um
nome só é visível enquanto o seu bloco está aberto. A lista paralela existe
porque o `--tabela` precisa de todos os escopos depois que a pilha já
esvaziou, com o número e o pai de cada um.

Para a Entrega 4, cada parâmetro ou variável recebe na declaração um **slot**
no registro de ativação da sua função (contador por função). Dois `x` em
blocos diferentes ficam com slots diferentes, e o gerador não precisa mais
saber de escopos.

Regras de organização:

- **Duas passadas.** A primeira coleta a assinatura de todas as funções no
  escopo 0, então dá para chamar uma função antes de ela aparecer. A segunda
  percorre os corpos.
- O corpo de função abre **dois** escopos: `funcao <nome>` (parâmetros) e
  `bloco` (variáveis locais). Todo bloco abre um, inclusive os de `se`,
  `senao`, `enquanto` e os blocos soltos.
- Na declaração `inteiro x = expr;`, a expressão é conferida **antes** de `x`
  entrar no escopo, então o `x` da direita é o de fora.

O que é recusado: nome repetido no mesmo escopo (variável, parâmetro ou
função), variável ou função não declarada, operador com tipos fora da tabela
3.2, qualquer conversão que não seja `inteiro → real` (atribuição, argumento,
retorno), número errado de argumentos, função `vazio` dentro de expressão,
condição não `logico`, `retorne` com/sem valor no tipo errado, falta de
`principal` ou `principal` com parâmetro ou retorno não `vazio`.

**Garantia de retorno** (`garante_retorno`), sempre pela estrutura do código e
nunca pelo valor das condições: `retorne` garante; um bloco garante se algum
comando dele garante; `se` só garante com `senao` e os dois lados garantindo;
`enquanto` nunca garante.

---

## Entrega 4: código intermediário, `.mplb` e VM

### Código de três endereços (`--ir`)

No máximo um operador por linha. A conversão `inteiro → real` aparece
explícita (`paraReal`), sempre **depois** da operação inteira. Por isso
`real a = 7 / 2;` dá `3.000000`.

```
funcao fatorial inteiro (n inteiro)
  t0 = n <= 1
  seFalso t0 desvie L0
  retorne 1
  desvie L1
L0:
  t1 = n - 1
  t2 = chama fatorial t1
  t3 = n * t2
  retorne t3
L1:
  retorne
fim
```

`se` gera `seFalso cond desvie Lsenao` e, com `senao`, um `desvie Lfim`;
`enquanto` gera `Linicio:` … `seFalso cond desvie Lfim` … `desvie Linicio`.
Variáveis sombreadas aparecem como `x`, `x.2`, `x.3`.

### O `.mplb`

Texto, uma instrução por linha, com comentários `#` mostrando o nome de cada
slot:

```
.funcao fatorial 1 5    # inteiro (n inteiro)
  .linha 2
  CARREGA 0             # n
  EMPILHA_I 1
  MENOR_IGUAL
  GUARDA 1              # t0
  CARREGA 1             # t0
  DESVIA_SE_FALSO L0
  ...
.fim
```

### Conjunto de instruções da VM

A VM é uma máquina de pilha. "Desempilha b, a" quer dizer que `b` estava no
topo.

| Instrução | O que faz com a pilha |
|---|---|
| `EMPILHA_I n` | empilha o inteiro `n` |
| `EMPILHA_R x` | empilha o real `x` |
| `EMPILHA_L verdadeiro\|falso` | empilha o lógico |
| `EMPILHA_T "..."` | empilha o texto (escapes na forma do fonte) |
| `CARREGA s` | empilha o valor do slot `s` do registro de ativação atual |
| `GUARDA s` | desempilha um valor e grava no slot `s` |
| `SOMA_I` / `SOMA_R` | desempilha b, a; empilha a + b |
| `SUB_I` / `SUB_R` | desempilha b, a; empilha a − b |
| `MUL_I` / `MUL_R` | desempilha b, a; empilha a × b |
| `DIV_I` | desempilha b, a; empilha a / b **truncado em direção a zero**; b = 0 é erro de execução |
| `DIV_R` | desempilha b, a; empilha a / b real; b = 0 é erro de execução |
| `RESTO_I` | desempilha b, a; empilha a − b·(a DIV_I b): o **sinal do dividendo**; b = 0 é erro |
| `CONCATENA` | desempilha b, a (textos); empilha a seguido de b |
| `NEG_I` / `NEG_R` | troca o topo por −topo |
| `PARA_REAL` | troca o inteiro do topo pelo mesmo valor em real |
| `IGUAL` `DIFERENTE` | desempilha b, a; empilha o lógico a == b / a != b |
| `MENOR` `MENOR_IGUAL` `MAIOR` `MAIOR_IGUAL` | desempilha b, a; empilha o lógico a < b, a ≤ b, a > b, a ≥ b |
| `E` / `OU` | desempilha b, a (lógicos); empilha a e b / a ou b (os dois lados já foram avaliados) |
| `NAO` | troca o lógico do topo pelo contrário |
| `DESVIA L` | continua no rótulo `L` |
| `DESVIA_SE_FALSO L` | desempilha um lógico; se for falso, continua em `L` |
| `CHAMA f n` | desempilha os `n` argumentos, cria um **registro de ativação** novo para `f` com eles nos slots 0..n−1, guarda o ponto de volta e entra em `f`; mais de 100 000 registros aninhados é estouro de pilha (erro de execução) |
| `RETORNA` | o valor de retorno fica no topo; descarta o registro atual e volta para quem chamou |
| `RETORNA_VAZIO` | descarta o registro atual e volta, sem valor; no `principal` encerra o programa |
| `DESCARTA` | desempilha e joga fora (função não-`vazio` chamada como comando) |
| `ESCREVE_I` `ESCREVE_R` `ESCREVE_L` `ESCREVE_T` | desempilha e imprime com quebra de linha, no formato da seção 4.5 (`real` com 6 casas, `verdadeiro`/`falso`) |

Diretivas (não executam nada): `.mplb 1` (versão), `.entrada principal`,
`.funcao <nome> <nparams> <nslots>`, `.fim`, `.linha <n>` (linha do fonte dos
comandos seguintes, usada nas mensagens de erro de execução) e `Lk:`
(rótulo).

**Registro de ativação:** cada `CHAMA` empilha `(função, pc de volta, slots,
linha)` numa pilha própria da VM. Os slots são, em ordem, os parâmetros, as
variáveis locais e os temporários da função. O laço da VM é iterativo, então
a recursão do programa MPL não usa a pilha do Python. Erros de execução saem
como `erro execucao: linha L, coluna 1: ...` com código 2, na linha do
comando que estava rodando.

### Programa próprio: `exemplos/demonstracao.mpl`

Torre de Hanói recursiva (com texto e concatenação), raiz quadrada pelo
método de Newton (reais e conversão `inteiro → real` no argumento), sequência
de Collatz (laço, `%`, `se/senao`) e sombreamento de variável num bloco de
`enquanto`. A saída esperada está em `exemplos/demonstracao.saida`.

```bash
./compilar exemplos/demonstracao.mpl && ./executar exemplos/demonstracao.mplb
```

---

<details>
<summary>Enunciado original do trabalho (README do esqueleto)</summary>

# Minha pequena linguagem

Trabalho semestral de **Compiladores** — Ciência da Computação, UNISAGRADO.  
Prof. Luiz Ricardo Mantovani da Silva · 2026-2

O trabalho consiste em desenvolver um **compilador completo** para a MPL, uma linguagem pequena de palavras-chave em português. O compilador vai ler um programa em `.mpl`, atravessar as quatro fases da disciplina e produzir um arquivo que **roda de verdade** numa máquina virtual.

---

## Comece por aqui

```bash
git clone https://github.com/LuizRMSilva1973/compiladores-lab.git
cd compiladores-lab
```

```bash
make verificar E=1
```

Vai dar vermelho — é para dar. O esqueleto responde à linha de comando mas ainda não tem nenhuma fase escrita. O vermelho é o seu ponto de partida, e ele vai virando verde conforme vocês preenchem `mplc/`.

Não precisa instalar nada além do Python 3. Se o notebook de vocês der trabalho, o [Google Cloud Shell](https://shell.cloud.google.com) já vem com Python 3.12, Java 21 e git — e é o mesmo ambiente da correção.

---

## Os três documentos que mandam

| Arquivo | O que decide |
|---|---|
| [LINGUAGEM.md](LINGUAGEM.md) | **O que** o compilador aceita: a sintaxe e as regras de tipo da MPL |
| [CONTRATOS.md](CONTRATOS.md) | **Como** ele se comunica: a linha de comando e o formato de cada despejo |
| [entregas/](entregas/) | O enunciado de cada entrega, com o que vale nota |

Quando a sua intuição discordar de um deles, é o arquivo que vale. Se o arquivo estiver errado, me procurem — já aconteceu de eu escrever um exemplo errado no contrato e só descobrir rodando.

---

## As entregas

| # | Entrega | Turma A (quarta) | Turma B (segunda) | Vale |
|---|---|---|---|---|
| [E1](entregas/E1.md) | Analisador léxico | 02/09 | 31/08 | 0,8 |
| [E2](entregas/E2.md) | Analisador sintático e árvore | 30/09 | 28/09 | 1,2 |
| [E3](entregas/E3.md) | Tabela de símbolos e tipos | 28/10 | 26/10 | 1,2 |
| [E4](entregas/E4.md) | Código intermediário, geração e VM | 18/11 | 16/11 | 1,8 |
| [Apres.](entregas/APRESENTACAO.md) | Demonstração e defesa | 25/11 | 23/11 | 1,0 |

São **quatro entregas sobre o mesmo compilador**, não quatro trabalhos. O que for implementado na E1 continua funcionando na E4 — e o verificador da E4 confere tudo o que veio antes. Deixar a E1 pela metade custa caro em novembro.

---

## Regras do jogo

**A entrega é o repositório, nunca a máquina de vocês.** A correção clona o repositório numa máquina limpa e roda `make verificar E=n`. Se não passar lá, não conta como entregue. Testem antes de entregar — de preferência na Cloud Shell, que é o ambiente da correção.

**Grupos de até 3.** O mesmo grupo do começo ao fim. Mudança de grupo só até a E1.

**Gerador de parser proibido nas Entregas 1 e 2.** ANTLR, PLY, yacc, lark e parentes escondem exatamente a parte que está sendo ensinada. Da E3 em diante o assunto é outro, e aí não faz diferença. Na apresentação vocês podem — e devem — comparar o parser com o que um gerador produziria.

**A linguagem de implementação é de vocês, entre as que o ambiente da correção já tem:** Python 3.12, Java 21, C e C++ (gcc 13), Ruby 3.2 ou PHP 8.3. O verificador não olha para dentro — ele roda `./compilar` e `./executar` e compara o que sai. O esqueleto em `mplc/` é Python porque é o caminho mais curto, mas ninguém é obrigado a usá-lo.

A lista existe por um motivo prático: a correção roda numa Cloud Shell limpa, e o que não estiver lá não roda. Querem outra linguagem? Falem comigo **antes** de começar — o critério é ela existir no ambiente sem instalação. Em nenhum caso dependam de biblioteca externa: só a biblioteca padrão.

---

## O verificador

```bash
make verificar E=2      # confere a Entrega 2 e, junto, a 1
make verificar          # confere as quatro
make evidencias E=2     # grava evidencias/verificacao-2.txt, que vai na entrega
```

**Antes de entregar, rodem `make prova`.** Ele clona o repositório de vocês num diretório limpo e verifica lá — que é exatamente o que a correção faz. É o teste que pega o defeito mais comum de todos, e que não tem nada a ver com compiladores: *funciona aqui e não no clone*. Arquivo esquecido fora do commit, caminho absoluto, passo de compilação que ninguém roda. Vale para qualquer linguagem, e é a única prova que realmente antecipa a correção.

Ele não lê o código de vocês. Ele roda o compilador e compara a saída com um corpus de **10 programas válidos**, **26 programas que precisam ser recusados na compilação** e **3 que precisam falhar na execução** — com a fase e a linha do erro conferidas.

Os programas recusados são metade da nota escondida do trabalho. Um compilador que aceita tudo passa em todos os testes positivos e não vale nada: é por isso que o corpus tem mais programas errados do que certos.

**A correção usa um segundo corpus, que vocês não têm.** Mesma linguagem, mesmas regras, programas diferentes. Uma implementação correta passa nos dois sem que vocês precisem fazer nada; um programa que apenas reproduza as saídas esperadas deste corpus passa aqui e reprova lá. Estou dizendo isto abertamente para ninguém perder tempo pelo caminho errado.

---

## Testar o envio (antes da apresentação)

O envio final é um pull request na vitrine [compiladores-mpl-2026-2](https://github.com/LuizRMSilva1973/compiladores-mpl-2026-2), depois da apresentação. Dá para **testar o envio agora**, no repositório do grupo, sem mostrar o código a ninguém:

- **No GitHub:** a ação **Teste de envio** (`.github/workflows/teste-de-envio.yml`) roda a cada `git push` no repositório de vocês. O resultado aparece na aba *Actions*.
  1. **Análise preliminar** — os mesmos portões e o mesmo verificador do envio de verdade.
  2. **Segunda análise** — só se a preliminar passar: um retorno técnico sobre o código (organização, clareza, tratamento de erros), **uma vez por dia por grupo**. Não vale nota.
- **Na máquina de vocês:** `make teste-envio` roda só a análise preliminar.

Quem clonou antes de 26/10 traz a ação para o repositório do grupo com:

```bash
git pull https://github.com/LuizRMSilva1973/compiladores-lab.git main
```

---

## Como entregar

1. `git push` no repositório do grupo.
2. Abram a [página do trabalho](https://profluiz.mantovanitec.com/disciplinas/aulas/compiladores/trabalho.html).
3. No formulário do fim da página: escolham a entrega, identifiquem os integrantes (nome, RA e e-mail), colem a URL do repositório e anexem o `evidencias/verificacao-N.txt`.
4. Cada integrante recebe uma cópia por e-mail. **Guardem esse e-mail**: é o comprovante.
</details>

**Integrantes:** Gabriel Gebra (RA 23110437) email: gagebrabr@gmail.com e Kauê de Alcântara Ribeiro (RA 23110121) email: Kauealbr@gmail.com
