// Criado por José Eduardo Santana Martins
// Este arquivo serve para a visão em lista (estilo Asana): seções recolhíveis por situação, linhas compactas e ordem manual por arraste.

import { DatePipe } from '@angular/common';
import { classeMarcador } from './marcadores.paleta';
import { Component, computed, input, output, signal } from '@angular/core';

import { AvataresComponent } from './avatares.component';
import { PrioridadeTarefa, ROTULOS_PRIORIDADE, situacaoPrazo, STATUS, StatusTarefa, TarefaResumo } from './tarefas.models';

export type OrdemLista = 'manual' | 'prazo' | 'prioridade';

/** Peso da prioridade na ordenação "Prioridade" (crítica primeiro). */
const PESO_PRIORIDADE: Record<PrioridadeTarefa, number> = { critica: 0, alta: 1, normal: 2, baixa: 3 };

/**
 * Lista agrupada por situação. Cada seção abre e fecha (Concluída começa fechada).
 * Na ordem manual, as linhas podem ser arrastadas dentro da seção; a nova ordem vai para o espaço gravar.
 */
@Component({
  selector: 'app-lista-tarefas',
  imports: [DatePipe, AvataresComponent],
  template: `
    <div class="lista-asana" role="table" aria-label="Tarefas">
      <div class="cabecalho-lista" role="row">
        <span role="columnheader">Tarefa</span><span role="columnheader">Pessoas</span><span role="columnheader">Prazo</span>
        <span role="columnheader">Prioridade</span><span role="columnheader">Checklist</span>
      </div>
      @for (s of secoes(); track s.valor) {
        <section class="secao-lista" [attr.data-status]="s.valor" role="rowgroup">
          <button type="button" class="titulo-secao" [attr.aria-expanded]="!fechada(s.valor)" (click)="alternar(s.valor)">
            <span class="seta" [class.aberta]="!fechada(s.valor)" aria-hidden="true">▸</span>
            <span class="ponto-status" aria-hidden="true"></span>{{ s.rotulo }} <small>{{ s.itens.length }}</small>
          </button>
          @if (!fechada(s.valor)) {
            @for (t of s.itens; track t.numero) {
              <div class="linha-lista" role="row" tabindex="0" [class.alvo]="alvo() === t.numero" [class.arrastando]="arrastando()?.numero === t.numero"
                   [attr.draggable]="ordem() === 'manual'" (dragstart)="iniciar($event, t)" (dragend)="terminar()"
                   (dragover)="$event.preventDefault(); alvo.set(t.numero)" (dragleave)="alvo.set(null)" (drop)="soltar($event, t, s.itens)"
                   (click)="abrir.emit(t.numero)" (keydown.enter)="abrir.emit(t.numero)">
                <span class="celula-titulo" role="cell">
                  @if (ordem() === 'manual') { <span class="alca" aria-hidden="true" title="Arraste para reordenar">⋮⋮</span> }
                  <span class="ponto-status" [attr.data-status]="t.status" aria-hidden="true"></span>
                  <span class="texto-titulo">@if (t.bloqueada) { <span class="cadeado-tarefa" title="Bloqueada" aria-label="Tarefa bloqueada">🔒</span> }{{ t.titulo }}</span>@if (t.subtarefas_total) { <small class="numero-lista">▤ {{ t.subtarefas_concluidas }}/{{ t.subtarefas_total }}</small> }@if (t.tarefa_pai_numero) { <small class="numero-lista">↳ #{{ t.tarefa_pai_numero }}</small> }
                  @for (m of t.marcadores; track m.id) { <span [class]="classeMarcador(m.cor_indice)">{{ m.nome }}</span> }
                  <small class="numero-lista">#{{ t.numero }}@if (t.equipe) { · {{ t.equipe.nome }} }</small>
                </span>
                <span role="cell"><app-avatares [pessoas]="t.responsaveis" tamanho="pequeno" /></span>
                <span role="cell"><span class="chip-prazo" [attr.data-situacao]="situacao(t)">{{ t.prazo | date: 'dd/MM HH:mm' }}</span></span>
                <span role="cell"><span class="selo-prioridade-tarefa" [attr.data-prioridade]="t.prioridade">{{ rotulosPrioridade[t.prioridade] }}</span></span>
                <span role="cell" class="celula-checklist">@if (t.checklist_total) { {{ t.checklist_feitos }}/{{ t.checklist_total }} } @else { — }</span>
              </div>
            } @empty { <p class="lista-vazia">Nenhuma tarefa nesta situação.</p> }
          }
        </section>
      }
    </div>
  `,
})
export class ListaTarefasComponent {
  protected readonly classeMarcador = classeMarcador;
  readonly itens = input<TarefaResumo[]>([]);
  readonly ordem = input<OrdemLista>('manual');
  readonly abrir = output<number>();
  /** Nova ordem manual (números de todas as tarefas da seção, de cima para baixo). */
  readonly reordenar = output<number[]>();

  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly situacao = situacaoPrazo;
  // Seções fechadas; Concluída começa fechada para a lista abrir no que está pendente
  private readonly fechadas = signal<ReadonlySet<StatusTarefa>>(new Set(['concluida']));
  protected readonly arrastando = signal<TarefaResumo | null>(null);
  protected readonly alvo = signal<number | null>(null);

  /** Seções na ordem do pipeline, cada uma ordenada conforme a escolha. */
  protected readonly secoes = computed(() => STATUS.map((s) => ({ ...s, itens: this.ordenar(this.itens().filter((t) => t.status === s.valor)) })));

  protected fechada(s: StatusTarefa): boolean {
    return this.fechadas().has(s);
  }

  protected alternar(s: StatusTarefa): void {
    this.fechadas.update((atual) => {
      const novo = new Set(atual);
      if (novo.has(s)) novo.delete(s);
      else novo.add(s);
      return novo;
    });
  }

  // --- Ordem manual por arraste (dentro da mesma seção) ----------------------------------------------

  protected iniciar(evento: DragEvent, t: TarefaResumo): void {
    if (this.ordem() !== 'manual') return;
    this.arrastando.set(t);
    evento.dataTransfer?.setData('text/plain', String(t.numero));
  }

  protected terminar(): void {
    this.arrastando.set(null);
    this.alvo.set(null);
  }

  protected soltar(evento: DragEvent, alvo: TarefaResumo, secao: TarefaResumo[]): void {
    evento.preventDefault();
    const movida = this.arrastando();
    this.terminar();
    if (!movida || movida.numero === alvo.numero || movida.status !== alvo.status) return;
    const lista = secao.filter((t) => t.numero !== movida.numero);
    lista.splice(lista.findIndex((t) => t.numero === alvo.numero), 0, movida);
    this.reordenar.emit(lista.map((t) => t.numero));
  }

  private ordenar(lista: TarefaResumo[]): TarefaResumo[] {
    const copia = [...lista];
    const o = this.ordem();
    if (o === 'prazo') return copia.sort((a, b) => a.prazo.localeCompare(b.prazo));
    if (o === 'prioridade') return copia.sort((a, b) => PESO_PRIORIDADE[a.prioridade] - PESO_PRIORIDADE[b.prioridade] || a.prazo.localeCompare(b.prazo));
    return copia.sort((a, b) => a.ordem - b.ordem);
  }
}
