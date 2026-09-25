import { Injectable, signal } from '@angular/core';
import { finalize, Observable } from 'rxjs';

import { ErroExibivel, erroExibivel } from '../utilitarios/erros-api';

export interface OpcoesConfirmacao {
  titulo: string;
  mensagem: string;
  rotuloConfirmar?: string;
  /** Segundos até liberar o botão Confirmar. Use em ações sem volta. 0 = liberado. */
  segundos?: number;
}

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
  readonly confirmacao = signal<ConfirmacaoAberta | null>(null);
  readonly segundosRestantes = signal(0);
  readonly erro = signal<(ErroExibivel & { titulo: string }) | null>(null);
  /** Mensagens das operações em andamento (a janela mostra a mais recente). */
  readonly processando = signal<string[]>([]);

  private relogio: ReturnType<typeof setInterval> | null = null;

  confirmar(opcoes: OpcoesConfirmacao): Promise<boolean> {
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
      if (segundos > 0) {
        this.relogio = setInterval(() => {
          this.segundosRestantes.update((s) => Math.max(0, s - 1));
          if (this.segundosRestantes() === 0) this.pararRelogio();
        }, 1000);
      }
    });
  }

  responderConfirmacao(confirmado: boolean): void {
    const aberta = this.confirmacao();
    if (!aberta) return;
    // Não confirma antes do fim da contagem, mesmo que o botão seja acionado por outro meio
    if (confirmado && this.segundosRestantes() > 0) return;
    this.pararRelogio();
    this.confirmacao.set(null);
    aberta.responder(confirmado);
  }

  mostrarErro(erro: unknown, titulo = 'Não foi possível concluir a operação'): void {
    this.erro.set({ ...erroExibivel(erro), titulo });
  }

  /** Aviso sem erro de API (ex.: pré-requisitos que faltam), na mesma janela dos erros. */
  avisar(titulo: string, mensagem: string): void {
    this.erro.set({ titulo, mensagem, codigo: null, correlacao: null });
  }

  fecharErro(): void {
    this.erro.set(null);
  }

  /** Exibe "Executando a solicitação" enquanto `operacao` não termina. */
  executar<T>(operacao: Observable<T>, mensagem = 'Executando a solicitação…'): Observable<T> {
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

  private pararRelogio(): void {
    if (this.relogio) clearInterval(this.relogio);
    this.relogio = null;
  }
}
