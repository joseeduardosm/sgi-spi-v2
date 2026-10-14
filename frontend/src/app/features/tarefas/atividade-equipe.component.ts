// Criado por José Eduardo Santana Martins
// Este arquivo serve para a visão "O que aconteceu" da equipe (só liderança): por dia, em cada tarefa, o que foi feito.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { ICONES_EVENTO, diaRelativo, rotuloDia } from './eventos-tarefa';
import { TarefasApiService } from './tarefas-api.service';
import { AtividadeDiaria, AtividadeDiariaItem, Pessoa, ROTULOS_STATUS } from './tarefas.models';

const PERIODOS = [
  { valor: 'hoje', rotulo: 'Hoje', dias: 0 },
  { valor: '2', rotulo: 'Hoje e ontem', dias: 1 },
  { valor: '7', rotulo: '7 dias', dias: 6 },
  { valor: '30', rotulo: '30 dias', dias: 29 },
];
const GRUPOS = [
  { valor: 'entregas', rotulo: 'Entregas e validações' },
  { valor: 'comentarios', rotulo: 'Comentários' },
  { valor: 'situacao', rotulo: 'Situação' },
  { valor: 'prazos', rotulo: 'Prazos' },
  { valor: 'atribuicoes', rotulo: 'Atribuições' },
];

/**
 * "O que aconteceu": seções Hoje, Ontem e dias anteriores; em cada dia, um cartão por tarefa (inclui subtarefas) com as linhas do que houve, por hora.
 * Só a liderança da equipe abre (a API responde 403 para os demais, e o botão nem aparece para eles). Os filtros trocam o período, a pessoa e o tipo.
 */
@Component({
  selector: 'app-atividade-equipe',
  imports: [DatePipe, FormsModule, RouterLink, EsqueletoComponent],
  template: `
    <div class="barra-atividade">
      <div class="chips-linha" role="group" aria-label="Período">
        @for (p of periodos; track p.valor) {
          <button type="button" [class.ativo]="periodo() === p.valor" [attr.aria-pressed]="periodo() === p.valor" (click)="trocarPeriodo(p.valor)">{{ p.rotulo }}</button>
        }
      </div>
      <select aria-label="Filtrar por pessoa" [ngModel]="pessoaId()" (ngModelChange)="pessoaId.set($event); carregar()">
        <option [ngValue]="null">Todas as pessoas</option>
        @for (p of pessoas(); track p.id) { <option [ngValue]="p.id">{{ p.nome }}</option> }
      </select>
      <input type="search" aria-label="Buscar tarefa" placeholder="Título ou número" [ngModel]="busca()" (ngModelChange)="digitar($event)" />
      <label class="alternar-raias"><input type="checkbox" [checked]="automaticos()" (change)="automaticos.set(!automaticos()); carregar()" /> Avisos automáticos</label>
    </div>
    <div class="chips-linha" role="group" aria-label="Tipo de acontecimento">
      @for (g of grupos; track g.valor) {
        <button type="button" [class.ativo]="tipos().includes(g.valor)" [attr.aria-pressed]="tipos().includes(g.valor)" (click)="alternarTipo(g.valor)">{{ g.rotulo }}</button>
      }
    </div>

    @if (dados(); as d) {
      @for (dia of d.dias; track dia.data) {
        <section class="dia-atividade" [attr.aria-label]="rotulo(dia.data)">
          <header>
            <h3>{{ rotulo(dia.data) }} <small>{{ dia.data | date: 'dd/MM/yyyy' }}</small></h3>
            <span class="resumo-dia">
              {{ dia.resumo.tarefas }} {{ dia.resumo.tarefas === 1 ? 'tarefa' : 'tarefas' }}
              @if (dia.resumo.entregues) { · {{ dia.resumo.entregues }} {{ dia.resumo.entregues === 1 ? 'entrega' : 'entregas' }} }
              @if (dia.resumo.concluidas) { · {{ dia.resumo.concluidas }} {{ dia.resumo.concluidas === 1 ? 'concluída' : 'concluídas' }} }
              @if (dia.resumo.comentarios) { · {{ dia.resumo.comentarios }} {{ dia.resumo.comentarios === 1 ? 'comentário' : 'comentários' }} }
              @if (dia.resumo.automaticos_ocultos) { · <small>{{ dia.resumo.automaticos_ocultos }} aviso(s) automático(s) oculto(s)</small> }
            </span>
          </header>
          @for (t of dia.tarefas; track t.numero) {
            <article class="cartao-atividade">
              <h4>
                <a [routerLink]="['/tarefas', t.numero]" title="Abrir a tarefa (Ctrl+clique abre em outra aba)">{{ t.titulo }}</a>
                <small>#{{ t.numero }}</small>
                <a class="abrir-nova-aba" [href]="'/tarefas/' + t.numero" target="_blank" rel="noopener" [attr.aria-label]="'Abrir a tarefa ' + t.numero + ' em nova aba'" title="Abrir em nova aba">↗</a>
                <span class="rotulo-status" [attr.data-status]="t.status">{{ rotulosStatus[t.status] }}</span>
              </h4>
              @if (t.tarefa_pai_numero) { <small class="rastro-subtarefa">↳ subtarefa de #{{ t.tarefa_pai_numero }}</small> }
              <ul class="linhas-atividade">
                @for (i of t.itens; track i.id) {
                  <li [attr.data-tipo]="i.tipo" [class.automatico]="i.automatico">
                    <span class="hora">{{ i.hora | date: 'HH:mm' }}</span>
                    <svg class="icone-evento-linha" viewBox="0 0 24 24" aria-hidden="true"><path [attr.d]="icone(i.tipo)" /></svg>
                    <div>
                      <strong>{{ i.autor }}</strong> <span>{{ frase(i) }}</span>
                      @if (i.texto) { <p class="texto-atividade">{{ i.texto }}</p> }
                    </div>
                  </li>
                }
              </ul>
            </article>
          }
        </section>
      } @empty {
        <p class="estado-vazio">Nada aconteceu neste período{{ pessoaId() || tipos().length || busca() ? ' com estes filtros' : '' }}.</p>
      }
    } @else if (erro()) {
      <p class="estado-vazio" role="alert">{{ erro() }}</p>
    } @else {
      <app-esqueleto tipo="lista" [linhas]="6" />
    }
  `,
  styles: `
    .barra-atividade { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 4px 0 10px; }
    .barra-atividade select, .barra-atividade input[type='search'] { flex: 0 1 220px; min-width: 150px; }
    .dia-atividade { margin: 18px 0; }
    .dia-atividade header { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid var(--spi-borda); }
    .dia-atividade h3 { margin: 0; font-size: 1.05rem; text-transform: capitalize; }
    .dia-atividade h3 small { margin-left: 8px; color: var(--spi-apagado); font-weight: 400; text-transform: none; }
    .resumo-dia { color: var(--spi-apagado); font-size: 0.85rem; }
    .cartao-atividade { margin: 0 0 10px; padding: 12px 16px; background: var(--bs-body-bg, #fff); border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-g); }
    .cartao-atividade h4 { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin: 0 0 6px; font-size: 0.98rem; }
    .cartao-atividade h4 a { color: inherit; text-decoration: none; }
    .cartao-atividade h4 a:hover { text-decoration: underline; }
    .linhas-atividade { margin: 0; padding: 0; list-style: none; }
    .linhas-atividade li { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; font-size: 0.9rem; }
    .linhas-atividade li.automatico { opacity: 0.65; }
    .hora { flex: 0 0 42px; color: var(--spi-apagado); font-variant-numeric: tabular-nums; font-size: 0.82rem; }
    .icone-evento-linha { flex: 0 0 16px; width: 16px; height: 16px; margin-top: 2px; fill: none; stroke: var(--spi-apagado); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .linhas-atividade strong { margin-right: 5px; }
    .texto-atividade { margin: 2px 0 0; color: var(--spi-texto); white-space: pre-wrap; overflow-wrap: anywhere; }
  `,
})
export class AtividadeEquipeComponent implements OnInit {
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);

  readonly equipeId = input.required<string>();
  /** Pessoas da equipe, para o filtro por autor. */
  readonly pessoas = input<Pessoa[]>([]);

  protected readonly periodos = PERIODOS;
  protected readonly grupos = GRUPOS;
  protected readonly rotulosStatus = ROTULOS_STATUS;
  protected readonly periodo = signal('2');
  protected readonly pessoaId = signal<number | null>(null);
  protected readonly tipos = signal<string[]>([]);
  protected readonly busca = signal('');
  protected readonly automaticos = signal(false);
  protected readonly dados = signal<AtividadeDiaria | null>(null);
  protected readonly erro = signal('');
  private temporizador: ReturnType<typeof setTimeout> | null = null;
  protected readonly agora = computed(() => new Date());

  ngOnInit(): void {
    this.carregar();
  }

  protected rotulo(dia: string): string {
    return rotuloDia(dia);
  }

  protected icone(tipo: string): string {
    return ICONES_EVENTO[tipo] ?? 'M12 12h.01';
  }

  protected trocarPeriodo(valor: string): void {
    this.periodo.set(valor);
    this.carregar();
  }

  protected alternarTipo(valor: string): void {
    this.tipos.update((l) => (l.includes(valor) ? l.filter((x) => x !== valor) : [...l, valor]));
    this.carregar();
  }

  /** Busca ao parar de digitar (a pessoa está escrevendo: sem pedir a cada tecla). */
  protected digitar(texto: string): void {
    this.busca.set(texto);
    if (this.temporizador) clearTimeout(this.temporizador);
    this.temporizador = setTimeout(() => this.carregar(), 350);
  }

  protected carregar(): void {
    const dias = PERIODOS.find((p) => p.valor === this.periodo())?.dias ?? 1;
    this.api.atividadeDaEquipe(this.equipeId(), {
      de: diaRelativo(dias), ate: diaRelativo(0), pessoaId: this.pessoaId(), tipos: this.tipos(), busca: this.busca(), automaticos: this.automaticos(),
    }).subscribe({
      next: (r) => { this.dados.set(r); this.erro.set(''); },
      error: (e) => { this.erro.set(e?.error?.detalhe ?? 'Não foi possível carregar a atividade.'); this.dialogos.mostrarErro(e, 'Não foi possível carregar a atividade'); },
    });
  }

  /** O que aconteceu, em uma frase curta (o texto do comentário ou da justificativa vem abaixo). */
  protected frase(i: AtividadeDiariaItem): string {
    const d = i.dados;
    const status = (v: unknown) => (typeof v === 'string' ? (ROTULOS_STATUS as Record<string, string>)[v] ?? v : '');
    const data = (v: unknown) => (typeof v === 'string' && v ? new Date(v).toLocaleDateString('pt-BR') : '');
    switch (i.tipo) {
      case 'comentario': return i.titulo === 'Comentário' ? 'comentou' : i.titulo.toLowerCase();
      case 'entregue': return 'entregou para validação';
      case 'validada': return 'validou a entrega';
      case 'devolvida': return 'devolveu a entrega';
      case 'reaberta': return 'reabriu a tarefa';
      case 'status': return d['de'] && d['para'] ? `mudou a situação de ${status(d['de'])} para ${status(d['para'])}` : i.titulo.toLowerCase();
      case 'prazo': return d['de'] && d['para'] ? `mudou o prazo de ${data(d['de'])} para ${data(d['para'])}` : 'mudou o prazo';
      case 'transferida': return d['de'] && d['para'] ? `transferiu de ${String(d['de'])} para ${String(d['para'])}` : 'transferiu a tarefa';
      case 'criada': return 'criou a tarefa';
      case 'checklist': return i.agrupados > 1 ? `fez ${i.agrupados} alterações no checklist` : i.titulo.toLowerCase();
      default: return i.titulo.toLowerCase();
    }
  }
}
