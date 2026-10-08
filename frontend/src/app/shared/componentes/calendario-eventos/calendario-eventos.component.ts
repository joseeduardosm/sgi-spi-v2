// Criado por José Eduardo Santana Martins
// Este arquivo serve para o calendário genérico de eventos (mês e semana): cada evento no seu dia, colorido pela gravidade; quem usa busca os dados do período.

import { Component, computed, effect, input, output, signal } from '@angular/core';

import { chaveDia, semanasDoMes } from '../../../features/tarefas/tarefas.models';

/** Evento exibido: o que importa para desenhar (os dados completos ficam com quem usa). */
export interface EventoCalendarioGenerico {
  /** Dia do evento (AAAA-MM-DD). */
  data: string;
  /** Hora (HH:MM:SS), quando há. */
  hora?: string | null;
  rotulo: string;
  /** Linha de apoio (ex.: o contrato). */
  detalhe?: string;
  severidade: 'alta' | 'media' | 'info';
}

/** Período visível, com as datas no formato AAAA-MM-DD (as semanas que cobrem o mês, inclusive os dias de fora dele). */
export interface PeriodoCalendario { de: string; ate: string }

/** Quantos eventos cabem num dia do mês antes do "+N". */
const POR_DIA = 3;
const DIAS_SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

/** Dias (Date) das semanas exibidas: todas as do mês, ou só a da data de referência. Exportada para teste. */
export function semanasExibidas(referencia: Date, modo: 'mes' | 'semana'): Date[][] {
  if (modo === 'mes') return semanasDoMes(referencia.getFullYear(), referencia.getMonth());
  const domingo = new Date(referencia.getFullYear(), referencia.getMonth(), referencia.getDate() - referencia.getDay());
  return [Array.from({ length: 7 }, (_, i) => new Date(domingo.getFullYear(), domingo.getMonth(), domingo.getDate() + i))];
}

/**
 * Calendário de mês e de semana para qualquer lista de eventos. Ao mudar de mês ou de semana, emite `periodoMudou` com as datas que a grade cobre,
 * para quem usa buscar só aquele intervalo. Clicar num evento emite `abrir` com o índice dele na lista de entrada.
 */
@Component({
  selector: 'app-calendario-eventos',
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

    <div class="calendario calendario-eventos" [class.semana]="modo() === 'semana'" role="grid" [attr.aria-label]="tituloPeriodo()">
      <div class="cabecalho-dias" role="row">@for (d of diasSemana; track d) { <span role="columnheader">{{ d }}</span> }</div>
      @for (semana of semanas(); track $index) {
        <div class="semana-calendario" role="row">
          @for (dia of semana; track dia.getTime()) {
            @let chave = chaveDoDia(dia);
            @let doDia = porDia().get(chave) ?? [];
            <div class="dia-calendario" role="gridcell" [class.fora]="modo() === 'mes' && dia.getMonth() !== referencia().getMonth()" [class.hoje]="chave === chaveHoje">
              <span class="numero-dia">{{ dia.getDate() }}</span>
              @for (e of (modo() === 'mes' ? doDia.slice(0, porDiaMes) : doDia); track e.indice) {
                <button type="button" class="pilula-evento" [attr.data-severidade]="e.evento.severidade" [title]="titulo(e.evento)" (click)="abrir.emit(e.indice)">
                  @if (e.evento.hora) { <b>{{ e.evento.hora.slice(0, 5) }}</b> }{{ e.evento.rotulo }}
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
  `,
})
export class CalendarioEventosComponent {
  readonly eventos = input<EventoCalendarioGenerico[]>([]);
  readonly periodoMudou = output<PeriodoCalendario>();
  readonly abrir = output<number>();

  protected readonly diasSemana = DIAS_SEMANA;
  protected readonly porDiaMes = POR_DIA;
  protected readonly chaveHoje = chaveDia(new Date());
  protected readonly chaveDoDia = chaveDia;
  protected readonly modo = signal<'mes' | 'semana'>('mes');
  /** Qualquer dia do mês (ou da semana) exibido. */
  protected readonly referencia = signal(new Date());

  protected readonly semanas = computed(() => semanasExibidas(this.referencia(), this.modo()));

  /** Eventos por dia (a chave é o próprio AAAA-MM-DD), cada dia em ordem de hora; guarda o índice na lista de entrada. */
  protected readonly porDia = computed(() => {
    const mapa = new Map<string, { evento: EventoCalendarioGenerico; indice: number }[]>();
    this.eventos().forEach((evento, indice) => mapa.set(evento.data, [...(mapa.get(evento.data) ?? []), { evento, indice }]));
    for (const lista of mapa.values()) lista.sort((a, b) => (a.evento.hora ?? '').localeCompare(b.evento.hora ?? ''));
    return mapa;
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

  constructor() {
    // Avisa quem usa sempre que a grade passa a cobrir outro intervalo (inclusive na primeira exibição)
    effect(() => {
      const semanas = this.semanas();
      this.periodoMudou.emit({ de: chaveDia(semanas[0][0]), ate: chaveDia(semanas[semanas.length - 1][6]) });
    });
  }

  protected titulo(e: EventoCalendarioGenerico): string {
    return [e.hora ? e.hora.slice(0, 5) : '', e.rotulo, e.detalhe ?? ''].filter(Boolean).join(' · ');
  }

  protected hoje(): void {
    this.referencia.set(new Date());
  }

  protected andar(passo: -1 | 1): void {
    const r = this.referencia();
    this.referencia.set(this.modo() === 'mes' ? new Date(r.getFullYear(), r.getMonth() + passo, 1) : new Date(r.getFullYear(), r.getMonth(), r.getDate() + 7 * passo));
  }

  protected verSemana(dia: Date): void {
    this.referencia.set(dia);
    this.modo.set('semana');
  }
}
