// Programa de demonstracao do grupo.
// Mostra recursao (Torre de Hanoi), reais e conversao inteiro -> real
// (raiz quadrada pelo metodo de Newton), lacos e resto com sinal
// (sequencia de Collatz) e escopos com sombreamento.

// ---------------------------------------------------------- Torre de Hanoi
funcao inteiro hanoi(inteiro n, texto origem, texto destino, texto apoio) {
  se (n == 0) {
    retorne 0;
  }
  inteiro antes = hanoi(n - 1, origem, apoio, destino);
  escreva("  disco " + nomeDisco(n) + ": " + origem + " -> " + destino);
  inteiro depois = hanoi(n - 1, apoio, destino, origem);
  retorne antes + 1 + depois;
}

funcao texto nomeDisco(inteiro n) {
  se (n == 1) {
    retorne "pequeno";
  } senao {
    se (n == 2) {
      retorne "medio";
    }
  }
  retorne "grande";
}

// ------------------------------------------------- raiz quadrada (Newton)
funcao real modulo(real x) {
  se (x < 0) {
    retorne -x;
  }
  retorne x;
}

funcao real raiz(real x) {
  real palpite = x / 2;
  enquanto (modulo(palpite * palpite - x) > 0.000001) {
    palpite = (palpite + x / palpite) / 2;
  }
  retorne palpite;
}

// --------------------------------------------------------------- Collatz
funcao inteiro passosCollatz(inteiro n) {
  inteiro passos = 0;
  enquanto (n != 1) {
    se (n % 2 == 0) {
      n = n / 2;
    } senao {
      n = 3 * n + 1;
    }
    passos = passos + 1;
  }
  retorne passos;
}

funcao vazio principal() {
  escreva("Torre de Hanoi com 3 discos:");
  inteiro movimentos = hanoi(3, "A", "C", "B");
  escreva("movimentos:");
  escreva(movimentos);

  escreva("Raiz quadrada por Newton:");
  escreva(raiz(2));
  escreva(raiz(144.0));

  escreva("Passos de Collatz ate chegar em 1:");
  inteiro n = 27;
  inteiro i = 0;
  enquanto (i < 3) {
    inteiro n = passosCollatz(n + i);   // este n esconde o de fora...
    escreva(n);
    i = i + 1;
  }
  escreva(n);                           // ...que volta a valer 27 aqui
  escreva(-7 / 2);
  escreva(-7 % 2);
}
