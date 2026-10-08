// Criado por José Eduardo Santana Martins
// Este arquivo serve para o painel "agenda da pessoa" ao atribuir uma tarefa: carga e tarefas dela em lista ou em linha do tempo (Gantt).

import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AvataresComponent } from './avatares.component';
import { TarefasApiService } from './tarefas-api.service';
import { AgendaPessoa, barraGantt, ItemAgenda, ROTULOS_PRIORIDADE, ROTULOS_STATUS, STATUS } from './tarefas.models';

type Aba = 'lista' | 'gantt';
/** Aba escolhida da última vez (preferência do navegador). */
const CHAVE_ABA = 'tarefas.agenda.aba';
/** Janela do Gantt: 7 dias para trás e 21 para frente (4 semanas). */
const DIAS_ANTES = 7;
const DIAS_JANELA = 28;

/**
 * Mostra a carga e as tarefas de quem está sendo escolhido como responsável,
 * para decidir a atribuição olhando a agenda da pessoa (como nos apps de gestão de equipes).
 * Por decisão do usuário, os títulos de todas as tarefas aparecem; só as "abríveis" viram link.
 */
@Component({
  selector: 'app-agenda-pessoa',
  imports: [DatePipe, DecimalPipe, RouterLink, AvataresComponent],
  template: `
    @if (agenda(); as a) {
      <section class="agenda-pessoa" [attr.aria-label]="'Agenda de ' + a.pessoa.nome">
        <header>
          <app-avatares [pessoas]="[{ id: a.pessoa.id, nome: a.pessoa.nome, login: a.pessoa.login }]" tamanho="grande" />
          <div>
            <strong>{{ a.pessoa.nome }}</strong>
            <small>{{ a.pessoa.a_fazer }} a fazer · {{ a.pessoa.em_andamento }} em andamento@if (a.pessoa.atrasadas) { · <b class="texto-erro">{{ a.pessoa.atrasadas }} atrasada(s)</b> }</small>
          </div>
          <span class="faixa-carga" [attr.data-faixa]="a.pessoa.faixa">{{ a.pessoa.faixa }} · {{ a.pessoa.carga | number: '1.0-1' }} pts</span>
        </header>
        <div class="alternar-visao pequeno" role="tablist" aria-label="Forma de ver a agenda">
          <button type="button" role="tab" [class.ativo]="aba() === 'lista'" [attr.aria-selected]="aba() === 'lista'" (click)="escolher('lista')">Lista</button>
          <button type="button" role="tab" [class.ativo]="aba() === 'gantt'" [attr.aria-selected]="aba() === 'gantt'" (click)="escolher('gantt')">Linha do tempo</button>
        </div>

        @if (aba() === 'lista') {
          @for (g of grupos(); track g.valor) {
            @if (g.itens.length) {
              <p class="grupo-agenda"><span class="ponto-status" [attr.data-status]="g.valor"></span>{{ g.rotulo }} <small>{{ g.itens.length }}</small></p>
              <ul class="itens-agenda">
                @for (i of g.itens; track i.numero) {
                  <li>
                    @if (i.abrivel) { <a [routerLink]="['/tarefas', i.numero]" target="_blank">{{ i.titulo }}</a> } @else { <span>{{ i.titulo }}</span> }
                    <small>#{{ i.numero }} · {{ i.equipe?.nome ?? 'Pessoal' }}</small>
                    <span class="chip-prazo" [attr.data-situacao]="i.status === 'concluida' ? 'concluida' : i.atrasada ? 'atrasada' : 'normal'">{{ i.prazo | date: 'dd/MM' }}</span>
                    @if (i.prioridade === 'alta' || i.prioridade === 'critica') {
                      <span class="selo-prioridade-tarefa" [attr.data-prioridade]="i.prioridade">{{ rotulosPrioridade[i.prioridade] }}</span>
                    }
                  </li>
                }
              </ul>
            }
          }
          @if (!a.itens.length) { <p class="dica-formulario">Nenhuma tarefa em aberto. Agenda livre.</p> }
        } @else {
          <!-- Gantt: régua com as semanas, marca de hoje e uma barra por tarefa (início → prazo ou conclusão) -->
          <div class="gantt">
            <div class="regua-gantt">
              @for (s of marcasSemana; track s.getTime()) { <span [style.left.%]="posicao(s)">{{ s | date: 'dd/MM' }}</span> }
              <i class="hoje-gantt" [style.left.%]="posicao(agora)" title="Hoje"></i>
            </div>
            @for (b of barras(); track b.item.numero) {
              <div class="linha-gantt" [title]="'#' + b.item.numero + ' ' + b.item.titulo + ' · ' + rotulosStatus[b.item.status] + ' · prazo ' + (b.item.prazo | date: 'dd/MM HH:mm')">
                <span class="rotulo-gantt">{{ b.item.titulo }}</span>
                <div class="trilho-gantt">
                  <i class="hoje-gantt" [style.left.%]="posicao(agora)"></i>
                  <span class="barra-gantt" [attr.data-status]="b.item.status" [class.atrasada]="b.item.atrasada"
                        [class.cortada-inicio]="b.barra.cortadaInicio" [class.cortada-fim]="b.barra.cortadaFim"
                        [style.left.%]="b.barra.esquerda" [style.width.%]="b.barra.largura"></span>
                </div>
              </div>
            } @empty { <p class="dica-formulario">Nenhuma tarefa nestas 4 semanas.</p> }
          </div>
        }
      </section>
    } @else if (carregando()) {
      <p class="dica-formulario">Carregando a agenda…</p>
    }
  `,
})
export class AgendaPessoaComponent {
  /** Pessoa cuja agenda aparece (vazio: o painel some). */
  readonly pessoaId = input<number | null>(null);
  private readonly api = inject(TarefasApiService);

  protected readonly rotulosStatus = ROTULOS_STATUS;
  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly agenda = signal<AgendaPessoa | null>(null);
  protected readonly carregando = signal(false);
  protected readonly aba = signal<Aba>(lerAba());

  // Janela do Gantt (meia-noite local de 7 dias atrás) e as marcas de cada semana
  protected readonly agora = new Date();
  private readonly inicioJanela = new Date(this.agora.getFullYear(), this.agora.getMonth(), this.agora.getDate() - DIAS_ANTES);
  protected readonly marcasSemana = Array.from({ length: DIAS_JANELA / 7 }, (_, i) =>
    new Date(this.inicioJanela.getFullYear(), this.inicioJanela.getMonth(), this.inicioJanela.getDate() + 7 * i));

  /** Tarefas agrupadas por situação (lista). */
  protected readonly grupos = computed(() => STATUS.map((s) => ({ ...s, itens: (this.agenda()?.itens ?? []).filter((i) => i.status === s.valor) })));

  /** Barras do Gantt: só as tarefas que tocam a janela, em ordem de prazo. */
  protected readonly barras = computed(() => (this.agenda()?.itens ?? [])
    .map((item) => ({ item, barra: barraGantt(item, this.inicioJanela, DIAS_JANELA) }))
    .filter((b): b is { item: ItemAgenda; barra: NonNullable<typeof b.barra> } => b.barra !== null));

  constructor() {
    // Recarrega sempre que a pessoa escolhida muda
    effect(() => {
      const id = this.pessoaId();
      this.agenda.set(null);
      if (!id) return;
      this.carregando.set(true);
      this.api.agenda(id).subscribe({
        next: (a) => { if (this.pessoaId() === id) this.agenda.set(a); this.carregando.set(false); },
        error: () => this.carregando.set(false),
      });
    });
  }

  /** Posição (%) de uma data na janela do Gantt. */
  protected posicao(data: Date): number {
    return ((data.getTime() - this.inicioJanela.getTime()) / (DIAS_JANELA * 86_400_000)) * 100;
  }

  protected escolher(aba: Aba): void {
    this.aba.set(aba);
    try {
      localStorage.setItem(CHAVE_ABA, aba);
    } catch {
      // Sem armazenamento disponível: a escolha vale só nesta visita
    }
  }
}

/** Aba lembrada do navegador; na falta, a lista. */
function lerAba(): Aba {
  try {
    return localStorage.getItem(CHAVE_ABA) === 'gantt' ? 'gantt' : 'lista';
  } catch {
    return 'lista';
  }
}
