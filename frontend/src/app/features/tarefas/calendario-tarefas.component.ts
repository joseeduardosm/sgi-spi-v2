// Criado por José Eduardo Santana Martins
// Este arquivo serve para a visão Calendário das tarefas (mês e semana): cada tarefa no dia do prazo; arrastar para outro dia pede a mudança de prazo.

import { DatePipe } from '@angular/common';
import { Component, computed, input, output, signal } from '@angular/core';

import { chaveDia, porDiaDoPrazo, semanasDoMes, TarefaResumo } from './tarefas.models';

/** Pedido de novo prazo: a tarefa foi solta em outro dia (o espaço abre a janela com a justificativa). */
export interface Reprogramacao { tarefa: TarefaResumo; dia: Date }

/** Quantas tarefas cabem num dia do mês antes do "+N". */
const POR_DIA = 3;
const DIAS_SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

@Component({
  selector: 'app-calendario-tarefas',
  imports: [DatePipe],
  template: `
    <div class="barra-calendario">
      <div class="navegacao-calendario">
        <button type="button" class="acao-secundaria" (click)="hoje()">Hoje</button>
        <button type="button" class="botao-icone" aria-label="Anterior" (click)="andar(-1)">‹</button>
        <button type="button" class="botao-icone" aria-label="Próximo" (click)="andar(1)">›</button>
        <h3>{{ tituloPeriodo() }}</h3>
      </div>
      <div class="alternar-visao pequeno" role="group" aria-label="Período do calendário">
        <button type="button" [class.ativo]="modo() === 'mes'" [attr.aria-pressed]="modo() === 'mes'" (click)="modo.set('mes')">Mês</button>
        <button type="button" [class.ativo]="modo() === 'semana'" [attr.aria-pressed]="modo() === 'semana'" (click)="modo.set('semana')">Semana</button>
      </div>
    </div>

    <div class="calendario" [class.semana]="modo() === 'semana'" role="grid" [attr.aria-label]="tituloPeriodo()">
      <div class="cabecalho-dias" role="row">@for (d of diasSemana; track d) { <span role="columnheader">{{ d }}</span> }</div>
      @for (semana of semanas(); track $index) {
        <div class="semana-calendario" role="row">
          @for (dia of semana; track dia.getTime()) {
            @let chave = chaveDoDia(dia);
            @let doDia = porDia().get(chave) ?? [];
            <div class="dia-calendario" role="gridcell" [class.fora]="modo() === 'mes' && dia.getMonth() !== referencia().getMonth()"
                 [class.hoje]="chave === chaveHoje" [class.alvo]="alvo() === chave"
                 (dragover)="$event.preventDefault(); alvo.set(chave)" (dragleave)="alvo.set(null)" (drop)="soltar($event, dia)">
              <span class="numero-dia">{{ dia.getDate() }}</span>
              @for (t of (modo() === 'mes' ? doDia.slice(0, porDiaMes) : doDia); track t.numero) {
                <button type="button" class="pilula-tarefa" [attr.data-status]="t.status" [class.atrasada]="t.atrasada" draggable="true"
                        [title]="(t.prazo | date: 'HH:mm') + ' · #' + t.numero + ' ' + t.titulo"
                        (dragstart)="iniciar($event, t)" (dragend)="arrastando.set(null)" (click)="abrir.emit(t.numero)">
                  <b>{{ t.prazo | date: 'HH:mm' }}</b> {{ t.titulo }}
                </button>
              }
              @if (modo() === 'mes' && doDia.length > porDiaMes) {
                <button type="button" class="link-simples mais-dia" (click)="verSemana(dia)">+{{ doDia.length - porDiaMes }} mais</button>
              }
            </div>
          }
        </div>
      }
    </div>
    <p class="dica-formulario">Arraste uma tarefa para outro dia para alterar o prazo (a justificativa é obrigatória). Tarefas no dia do prazo.</p>
  `,
})
export class CalendarioTarefasComponent {
  readonly itens = input<TarefaResumo[]>([]);
  readonly abrir = output<number>();
  readonly reprogramar = output<Reprogramacao>();

  protected readonly diasSemana = DIAS_SEMANA;
  protected readonly porDiaMes = POR_DIA;
  protected readonly chaveHoje = chaveDia(new Date());
  protected readonly chaveDoDia = chaveDia;
  protected readonly modo = signal<'mes' | 'semana'>('mes');
  /** Data de referência: qualquer dia do mês (ou da semana) exibido. */
  protected readonly referencia = signal(new Date());
  protected readonly arrastando = signal<TarefaResumo | null>(null);
  protected readonly alvo = signal<string | null>(null);

  protected readonly porDia = computed(() => porDiaDoPrazo(this.itens()));

  /** Semanas exibidas: todas as do mês, ou só a da data de referência. */
  protected readonly semanas = computed(() => {
    const r = this.referencia();
    if (this.modo() === 'mes') return semanasDoMes(r.getFullYear(), r.getMonth());
    const domingo = new Date(r.getFullYear(), r.getMonth(), r.getDate() - r.getDay());
    return [Array.from({ length: 7 }, (_, i) => new Date(domingo.getFullYear(), domingo.getMonth(), domingo.getDate() + i))];
  });

  protected readonly tituloPeriodo = computed(() => {
    const r = this.referencia();
    if (this.modo() === 'mes') {
      const texto = r.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
      return texto.charAt(0).toUpperCase() + texto.slice(1);
    }
    const semana = this.semanas()[0];
    const curta = (d: Date) => d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
    return `${curta(semana[0])} – ${curta(semana[6])} de ${semana[6].getFullYear()}`;
  });

  protected hoje(): void {
    this.referencia.set(new Date());
  }

  /** Avança ou volta um mês (ou uma semana). */
  protected andar(passo: -1 | 1): void {
    const r = this.referencia();
    this.referencia.set(this.modo() === 'mes' ? new Date(r.getFullYear(), r.getMonth() + passo, 1) : new Date(r.getFullYear(), r.getMonth(), r.getDate() + 7 * passo));
  }

  /** "+N mais": abre a semana daquele dia, onde cabem todas as tarefas. */
  protected verSemana(dia: Date): void {
    this.referencia.set(dia);
    this.modo.set('semana');
  }

  protected iniciar(evento: DragEvent, t: TarefaResumo): void {
    this.arrastando.set(t);
    evento.dataTransfer?.setData('text/plain', String(t.numero));
  }

  protected soltar(evento: DragEvent, dia: Date): void {
    evento.preventDefault();
    const t = this.arrastando();
    this.arrastando.set(null);
    this.alvo.set(null);
    if (t && chaveDia(new Date(t.prazo)) !== chaveDia(dia)) this.reprogramar.emit({ tarefa: t, dia });
  }
}
