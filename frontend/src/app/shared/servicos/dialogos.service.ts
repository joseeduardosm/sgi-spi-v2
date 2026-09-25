// Criado por José Eduardo Santana Martins
// Este arquivo serve para abrir, de qualquer tela, os diálogos globais de confirmação, erro e processamento.

import { Injectable, signal } from '@angular/core';
import { finalize, Observable } from 'rxjs';

import { ErroExibivel, erroExibivel } from '../utilitarios/erros-api';

/** Opções de uma confirmação. */
export interface OpcoesConfirmacao {
  titulo: string;
  mensagem: string;
  rotuloConfirmar?: string;
  /** Segundos até liberar o botão Confirmar. Use em ações sem volta. 0 = liberado. */
  segundos?: number;
}

/** Confirmação em exibição, com a função que entrega a resposta a quem pediu. */
interface ConfirmacaoAberta extends Required<OpcoesConfirmacao> {
  responder: (confirmado: boolean) => void;
}

/**
 * Diálogos globais do portal, desenhados uma única vez pelo `DialogosComponent` do layout:
 * - confirmação com contagem regressiva para ações que não têm volta;
 * - erro com o código de correlação para o suporte;
 * - "Executando a solicitação" enquanto operações demoradas (PDFs, consolidados) rodam.
 */
@Injectable({ providedIn: 'root' })
export class DialogosService {
  // Estado lido pelo DialogosComponent: confirmação aberta, contagem, erro e operações em andamento
  readonly confirmacao = signal<ConfirmacaoAberta | null>(null);
  readonly segundosRestantes = signal(0);
  readonly erro = signal<(ErroExibivel & { titulo: string }) | null>(null);
  /** Mensagens das operações em andamento (a janela mostra a mais recente). */
  readonly processando = signal<string[]>([]);

  // Temporizador da contagem regressiva
  private relogio: ReturnType<typeof setInterval> | null = null;

  /**
   * Abre uma confirmação e devolve uma Promise com a resposta (true = confirmou).
   * Uso: `if (await dialogos.confirmar({...})) { ... }`.
   */
  confirmar(opcoes: OpcoesConfirmacao): Promise<boolean> {
    // Uma confirmação por vez: se havia outra aberta, ela é cancelada
    this.responderConfirmacao(false);
    return new Promise<boolean>((resolver) => {
      const segundos = Math.max(0, opcoes.segundos ?? 0);
      this.confirmacao.set({
        rotuloConfirmar: 'Confirmar',
        ...opcoes,
        segundos,
        responder: resolver,
      });
      this.segundosRestantes.set(segundos);
      // Contagem regressiva: diminui 1 por segundo até liberar o botão Confirmar
      if (segundos > 0) {
        this.relogio = setInterval(() => {
          this.segundosRestantes.update((s) => Math.max(0, s - 1));
          if (this.segundosRestantes() === 0) this.pararRelogio();
        }, 1000);
      }
    });
  }

  /** Resposta do usuário (botões Confirmar/Cancelar ou Esc). */
  responderConfirmacao(confirmado: boolean): void {
    const aberta = this.confirmacao();
    if (!aberta) return;
    // Não confirma antes do fim da contagem, mesmo que o botão seja acionado por outro meio
    if (confirmado && this.segundosRestantes() > 0) return;
    this.pararRelogio();
    this.confirmacao.set(null);
    aberta.responder(confirmado);
  }

  /** Mostra o erro de uma chamada à API (mensagem, código e correlação). */
  mostrarErro(erro: unknown, titulo = 'Não foi possível concluir a operação'): void {
    this.erro.set({ ...erroExibivel(erro), titulo });
  }

  /** Aviso sem erro de API (ex.: pré-requisitos que faltam), na mesma janela dos erros. */
  avisar(titulo: string, mensagem: string): void {
    this.erro.set({ titulo, mensagem, codigo: null, correlacao: null });
  }

  /** Fecha a janela de erro/aviso. */
  fecharErro(): void {
    this.erro.set(null);
  }

  /** Exibe "Executando a solicitação" enquanto `operacao` não termina. */
  executar<T>(operacao: Observable<T>, mensagem = 'Executando a solicitação…'): Observable<T> {
    // Observable "embrulho": ao ser assinado, registra a mensagem e repassa tudo da operação original;
    // `finalize` remove a mensagem quando a operação termina, com sucesso ou erro
    return new Observable<T>((assinante) => {
      this.processando.update((lista) => [...lista, mensagem]);
      const remover = () =>
        this.processando.update((lista) => {
          const indice = lista.lastIndexOf(mensagem);
          return indice < 0 ? lista : [...lista.slice(0, indice), ...lista.slice(indice + 1)];
        });
      return operacao.pipe(finalize(remover)).subscribe(assinante);
    });
  }

  /** Cancela o temporizador da contagem. */
  private pararRelogio(): void {
    if (this.relogio) clearInterval(this.relogio);
    this.relogio = null;
  }
}
