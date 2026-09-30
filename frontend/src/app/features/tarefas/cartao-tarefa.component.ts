// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cartão compacto de uma tarefa no quadro (estilo Trello): etiquetas, título, prazo, contadores e avatares.

import { DatePipe } from '@angular/common';
import { Component, computed, input, output } from '@angular/core';

import { AvataresComponent } from './avatares.component';
import { ROTULOS_PRIORIDADE, situacaoPrazo, TarefaResumo } from './tarefas.models';

/**
 * Cartão do quadro. Clicar abre a tarefa (evento `abrir`); o arraste é controlado pela coluna.
 * - faixas coloridas no topo: os marcadores (o nome aparece ao passar o mouse);
 * - borda esquerda: a cor da prioridade (alta e crítica chamam atenção);
 * - rodapé: chip do prazo colorido, checklist, comentários, anexos e os avatares dos envolvidos.
 */
@Component({
  selector: 'app-cartao-tarefa',
  imports: [DatePipe, AvataresComponent],
  template: `
    @let t = tarefa();
    <article class="cartao-quadro" [attr.data-prioridade]="t.prioridade" [class.destacado]="destacado()" tabindex="0" role="button"
             [attr.aria-label]="'Abrir tarefa ' + t.numero + ': ' + t.titulo" (click)="abrir.emit(t.numero)" (keydown.enter)="abrir.emit(t.numero)">
      @if (t.marcadores.length) {
        <div class="etiquetas">
          @for (m of t.marcadores; track m.id) { <span class="etiqueta" [style.background]="m.cor" [title]="m.nome">{{ m.nome }}</span> }
        </div>
      }
      <p class="titulo-quadro">{{ t.titulo }}</p>
      <div class="rodape-quadro">
        <span class="chip-prazo" [attr.data-situacao]="situacao()" [title]="'Prazo: ' + (t.prazo | date: 'dd/MM/yyyy HH:mm')">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>
          {{ t.prazo | date: 'dd/MM' }}@if (t.prorrogacoes) { <b title="Prazo alterado">↻{{ t.prorrogacoes }}</b> }
        </span>
        @if (t.checklist_total) {
          <span class="contador" [class.completo]="t.checklist_feitos === t.checklist_total" title="Checklist">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
            {{ t.checklist_feitos }}/{{ t.checklist_total }}</span>
        }
        @if (t.comentarios) {
          <span class="contador" title="Comentários">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" /></svg>{{ t.comentarios }}</span>
        }
        @if (t.anexos) {
          <span class="contador" title="Anexos">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.4 11.1l-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5" /></svg>{{ t.anexos }}</span>
        }
        @if (t.prioridade === 'alta' || t.prioridade === 'critica') {
          <span class="selo-prioridade-tarefa" [attr.data-prioridade]="t.prioridade">{{ rotulosPrioridade[t.prioridade] }}</span>
        }
        <span class="numero-quadro">#{{ t.numero }}</span>
        <app-avatares [pessoas]="t.envolvidos" tamanho="pequeno" />
      </div>
    </article>
  `,
})
export class CartaoTarefaComponent {
  readonly tarefa = input.required<TarefaResumo>();
  /** Destaque temporário (ex.: tarefa recém-criada pela criação rápida). */
  readonly destacado = input(false);
  readonly abrir = output<number>();

  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly situacao = computed(() => situacaoPrazo(this.tarefa()));
}
