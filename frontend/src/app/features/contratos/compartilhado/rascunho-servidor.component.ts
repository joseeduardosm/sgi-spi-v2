/**
 * =============================================================================
 * ARQUIVO: rascunho-servidor.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Gerenciar o rascunho compartilhado de um formulário do contrato: mostra o
 * aviso do rascunho salvo pela equipe e oferece salvar, carregar e excluir.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template embutido. Ao iniciar, lê o rascunho na
 * API (ExecucaoApiService). Os métodos públicos salvar(), apagar() e
 * recarregar() são chamados pela tela que o usa (via referência ao
 * componente). O salvar envia a versão vista, para a API detectar conflito
 * quando outra pessoa salvou antes.
 *
 * FINALIDADE DE NEGÓCIO:
 * Permite que um membro da equipe de fiscalização comece a preencher o diário,
 * a avaliação ou a medição e outro continue de onde parou, sem perder o
 * trabalho, e evita que um sobrescreva o rascunho do outro sem perceber.
 *
 * CONTEXTO NO SISTEMA:
 * Usado pela aba Diário do contrato e pelas etapas de medição e avaliação da
 * competência. Complementa o rascunho automático salvo no navegador.
 *
 * =============================================================================
 */

import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, output, signal } from '@angular/core';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { ExecucaoApiService, RascunhoServidor, TipoRascunho } from './execucao-api.service';

/**
 * Rascunho **no servidor** de um formulário (diário, avaliação ou medição), visível à equipe: adicional ao rascunho automático do navegador.
 *
 * Mostra, quando existe, "Rascunho salvo por fulano em …" com **Carregar no formulário** e **Excluir rascunho**. O botão "Salvar rascunho" fica
 * na tela de quem usa o componente e chama `salvar()`; depois de registrar de verdade, a tela chama `apagar()`.
 */
@Component({
  selector: 'app-rascunho-servidor',
  imports: [DatePipe],
  template: `
    @if (rascunho(); as r) {
      <p class="aviso-formulario aviso-rascunho" role="status">
        <span>Rascunho salvo por <strong>{{ r.atualizado_por_nome }}</strong> em {{ r.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}. {{ observacao() }}</span>
        <span class="acoes-linha">
          @if (editavel()) { <button type="button" class="acao-secundaria acao-pequena" (click)="carregar.emit(r.dados)">Carregar no formulário</button> }
          @if (editavel()) { <button type="button" class="acao-secundaria acao-pequena" (click)="excluir()">Excluir rascunho</button> }
        </span>
      </p>
    }
  `,
})
export class RascunhoServidorComponent implements OnInit {
  /** Contrato dono do rascunho. */
  readonly contratoId = input.required<string>();
  /** Qual formulário (diário, avaliação ou medição). */
  readonly tipo = input.required<TipoRascunho>();
  /** Id da competência (avaliação e medição); vazio no diário. */
  readonly chave = input('');
  /** Quem pode editar o contrato vê as ações; os demais só veem o aviso. */
  readonly editavel = input(false);
  /** Campos do formulário a guardar; `null` quando não há nada preenchido. */
  readonly obterDados = input.required<() => Record<string, unknown> | null>();
  /** Frase extra exibida no aviso (ex.: o que acontece ao carregar). */
  readonly observacao = input('');
  /** Pedido de carregar o rascunho no formulário (a tela aplica os campos). */
  readonly carregar = output<Record<string, unknown>>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  /** Rascunho atual no servidor (`null` se não há). */
  protected readonly rascunho = signal<RascunhoServidor | null>(null);
  /** Salvando agora (a tela pode usar para desabilitar o botão). */
  readonly salvando = signal(false);

  /** Lê o rascunho ao montar. Os inputs só estão disponíveis a partir daqui, não no construtor. */
  ngOnInit(): void {
    this.recarregar();
  }

  /** Lê de novo o rascunho do servidor (ex.: depois de um conflito). */
  recarregar(): void {
    this.api.lerRascunho(this.contratoId(), this.tipo(), this.chave()).subscribe({ next: (r) => this.rascunho.set(r), error: () => this.rascunho.set(null) });
  }

  /** Salva o que está no formulário para a equipe (por cima do rascunho anterior, se a versão for a que a pessoa viu). */
  salvar(): void {
    // `obterDados` é um input que guarda uma função: o primeiro () lê o input, o segundo executa a função
    const dados = this.obterDados()();
    if (dados === null) {
      this.dialogos.avisar('Nada para salvar', 'Preencha algum campo antes de salvar o rascunho.');
      return;
    }
    this.salvando.set(true);
    this.api.salvarRascunho(this.contratoId(), this.tipo(), this.chave(), dados, this.rascunho()?.versao ?? null).subscribe({
      next: (r) => {
        this.salvando.set(false);
        this.rascunho.set(r);
        this.dialogos.avisar('Rascunho salvo', 'A equipe do contrato já pode ver este rascunho.');
      },
      error: (e) => {
        this.salvando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível salvar o rascunho');
        // Conflito: outra pessoa salvou antes; mostra o rascunho dela para a pessoa decidir
        this.recarregar();
      },
    });
  }

  /** Apaga o rascunho do servidor em silêncio (depois de registrar de verdade). */
  apagar(): void {
    if (!this.rascunho()) return;
    this.api.apagarRascunho(this.contratoId(), this.tipo(), this.chave()).subscribe({ next: () => this.rascunho.set(null), error: () => this.rascunho.set(null) });
  }

  /** Exclusão pedida pelo usuário: confirma antes, pois o rascunho some para toda a equipe. */
  protected async excluir(): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Excluir o rascunho?', mensagem: 'O rascunho salvo some para toda a equipe.', rotuloConfirmar: 'Excluir', perigo: true });
    if (!ok) return;
    this.api.apagarRascunho(this.contratoId(), this.tipo(), this.chave()).subscribe({
      next: () => this.rascunho.set(null),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir o rascunho'),
    });
  }
}
