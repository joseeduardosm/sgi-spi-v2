// Criado por José Eduardo Santana Martins
// Este arquivo serve para a visão "Desempenho" da equipe (só liderança): burndown, vazão, tempo de ciclo, fluxo acumulado e produtividade por pessoa.

import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { GraficoComponent, SerieGrafico } from '../../shared/componentes/grafico/grafico.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AjudaGrafico, AjudaGraficoComponent } from './ajuda-grafico.component';
import { TarefasApiService } from './tarefas-api.service';
import { DesempenhoEquipe, Marcador } from './tarefas.models';

const PERIODOS = [{ dias: 30, rotulo: 'Últimos 30 dias' }, { dias: 60, rotulo: 'Últimos 60 dias' }, { dias: 90, rotulo: 'Últimos 90 dias' }, { dias: 180, rotulo: 'Últimos 180 dias' }];

function iso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** "2026-06-03" → "03/06" (rótulo curto dos eixos). */
function diaMes(dia: string): string {
  const [, m, d] = dia.split('-');
  return `${d}/${m}`;
}

/** Explicações em linguagem comum, exibidas no "?" de cada gráfico. */
const AJUDAS: Record<'burndown' | 'vazao' | 'ciclo' | 'fluxo', AjudaGrafico> = {
  burndown: {
    titulo: 'Burndown',
    oQueE: 'Mostra quantas tarefas ainda faltam fazer, dia após dia, e se o ritmo da equipe dá conta de zerar a lista até o fim do período.',
    comoLer: 'A linha vermelha (Real) é o que está aberto de fato em cada dia: ela deve descer conforme a equipe conclui tarefas. A linha cinza tracejada (Ideal) é o caminho que seria perfeito, descendo sempre no mesmo ritmo, do total que já existia no início até zero no último dia. A linha azul (Escopo) é o total de tarefas do período, e sobe quando entra tarefa nova.',
    atencao: 'Linha vermelha acima da cinza: a equipe está atrasada em relação ao ideal. Abaixo: está adiantada. Se a azul sobe, o trabalho cresceu no meio do período, e por isso a vermelha pode não cair mesmo com entregas. Se o período começou antes de existirem tarefas, a linha cinza fica em zero.',
  },
  vazao: {
    titulo: 'Vazão semanal',
    oQueE: 'Mostra quantas tarefas a equipe entrega por semana e quantas chegam, para você ver se o trabalho entra mais rápido do que sai.',
    comoLer: 'Cada semana tem duas barras: cinza são as tarefas criadas e verde são as concluídas. A linha vermelha é a média das concluídas nas últimas 4 semanas, que suaviza os altos e baixos e mostra a tendência.',
    atencao: 'Barras cinzas sempre maiores que as verdes significam que a fila está crescendo. Linha vermelha subindo indica que a equipe está entregando cada vez mais; descendo, cada vez menos.',
  },
  ciclo: {
    titulo: 'Tempo de ciclo e lead time',
    oQueE: 'Mostra quantos dias uma tarefa leva para ficar pronta, olhando só as tarefas concluídas em cada semana.',
    comoLer: 'Lead time (azul) conta da criação da tarefa até a conclusão, incluindo o tempo parada esperando. Ciclo (verde) conta só do momento em que alguém começou a trabalhar até concluir. A linha cheia é a mediana: metade das tarefas levou menos que isso. A tracejada é o P85: 85 de cada 100 tarefas levaram menos que isso, bom para prometer prazo com segurança.',
    atencao: 'Lead time muito maior que o ciclo quer dizer que as tarefas ficam muito tempo na fila antes de alguém começar. Só aparece valor depois que há tarefas concluídas; sem conclusões, o gráfico fica em zero.',
  },
  fluxo: {
    titulo: 'Fluxo acumulado',
    oQueE: 'Mostra, para cada dia, quantas tarefas estão em cada situação (concluída, em validação, em andamento e as demais), empilhadas uma sobre a outra.',
    comoLer: 'Cada faixa colorida é uma situação. A espessura da faixa em um dia é a quantidade de tarefas nessa situação naquele dia. A altura total é tudo o que existe.',
    atencao: 'Uma faixa que vai engordando com o tempo indica gargalo: as tarefas estão se acumulando naquela etapa (por exemplo, muitas esperando validação). Faixas estáveis e a verde (concluídas) crescendo são sinal de fluxo saudável.',
  },
};

@Component({
  selector: 'app-desempenho-tarefas',
  imports: [FormsModule, DecimalPipe, GraficoComponent, AjudaGraficoComponent],
  template: `
    <section class="desempenho" aria-label="Desempenho da equipe">
      <div class="filtros-desempenho">
        <div class="campo"><label for="de-periodo">Período</label>
          <select id="de-periodo" [ngModel]="periodo()" (ngModelChange)="trocarPeriodo($event)">
            @for (p of periodos; track p.dias) { <option [ngValue]="p.dias">{{ p.rotulo }}</option> }
            <option [ngValue]="0">Personalizado</option>
          </select></div>
        @if (periodo() === 0) {
          <div class="campo"><label for="de-de">De</label><input id="de-de" type="date" [(ngModel)]="de" (change)="carregar()" /></div>
          <div class="campo"><label for="de-ate">Até</label><input id="de-ate" type="date" [(ngModel)]="ate" (change)="carregar()" /></div>
        }
        @if (marcadores().length) {
          <div class="campo"><label for="de-marcador">Marcador</label>
            <select id="de-marcador" [(ngModel)]="marcadorId" (ngModelChange)="carregar()">
              <option value="">Todos</option>
              @for (m of marcadores(); track m.id) { <option [value]="m.id">{{ m.nome }}</option> }
            </select></div>
        }
      </div>

      @if (d(); as d) {
        @if (d.escopo === 'pessoa') {
          <p class="dica-formulario">Desempenho de <strong>{{ d.equipe_nome }}</strong>: as tarefas em que a pessoa é responsável, de qualquer equipe e também as pessoais{{ pessoaDeOutro() ? ' (você vê as das equipes que lidera)' : '' }}.</p>
        }
        <div class="indicadores-desempenho" role="group" aria-label="Resumo do período">
          <div><b>{{ d.resumo.abertas_agora }}</b><small>abertas agora</small></div>
          <div><b>{{ d.resumo.concluidas_no_periodo }}</b><small>concluídas no período</small></div>
          <div><b>{{ d.resumo.criadas_no_periodo }}</b><small>criadas no período</small></div>
          <div><b>{{ d.resumo.vazao_media_semanal | number: '1.0-1' }}</b><small>concluídas por semana</small></div>
          <div><b>{{ d.resumo.ciclo_mediano_dias === null ? '—' : (d.resumo.ciclo_mediano_dias | number: '1.0-1') }}</b><small>dias de ciclo (mediana)</small></div>
          <div><b>{{ d.resumo.lead_mediano_dias === null ? '—' : (d.resumo.lead_mediano_dias | number: '1.0-1') }}</b><small>dias de lead time (mediana)</small></div>
        </div>

        @if (d.sla; as sla) {
          <div class="indicadores-desempenho" role="group" aria-label="Cumprimento do SLA no período" title="Prazos em dias úteis por prioridade (política em Administração › SLA); tarefas controladas por outros módulos ficam de fora">
            <div><b>{{ sla.percentual_resolucao === null ? '—' : (sla.percentual_resolucao | number: '1.0-1') + '%' }}</b><small>resolvidas no prazo ({{ sla.resolucoes_no_prazo }} de {{ sla.resolucoes_no_prazo + sla.resolucoes_fora }})</small></div>
            <div><b>{{ sla.percentual_resposta === null ? '—' : (sla.percentual_resposta | number: '1.0-1') + '%' }}</b><small>respondidas no prazo ({{ sla.respostas_no_prazo }} de {{ sla.respostas_no_prazo + sla.respostas_fora }})</small></div>
            <div><b>{{ sla.abertas_estouradas }}</b><small>abertas com SLA estourado</small></div>
            <div><b>{{ sla.abertas_em_risco }}</b><small>abertas com SLA em risco</small></div>
          </div>
        }

        <div class="grade-graficos-desempenho">
          <article class="cartao-dados">
            <header><div><h2>Burndown</h2><small>Tarefas abertas por dia, contra a linha ideal até zerar no fim do período. A linha de escopo mostra o que entrou no meio.</small></div></header>
            <div class="corpo"><app-grafico tipo="line" titulo="Burndown de tarefas" [rotulos]="rotulosBurndown()" [series]="seriesBurndown()" [altura]="280" /></div>
            <app-ajuda-grafico [ajuda]="ajudas.burndown" />
          </article>
          <article class="cartao-dados">
            <header><div><h2>Vazão semanal</h2><small>Tarefas criadas e concluídas por semana (barras) e média móvel de 4 semanas das concluídas (linha).</small></div></header>
            <div class="corpo"><app-grafico tipo="bar" titulo="Vazão semanal" [rotulos]="rotulosSemanas()" [series]="seriesVazao()" [altura]="280" /></div>
            <app-ajuda-grafico [ajuda]="ajudas.vazao" />
          </article>
          <article class="cartao-dados">
            <header><div><h2>Tempo de ciclo e lead time</h2><small>Mediana e percentil 85, em dias, das tarefas concluídas em cada semana. Ciclo: da 1ª vez em andamento até concluir. Lead time: da criação até concluir.</small></div></header>
            <div class="corpo"><app-grafico tipo="line" titulo="Tempo de ciclo e lead time em dias" [rotulos]="rotulosSemanas()" [series]="seriesCiclo()" [altura]="280" /></div>
            <app-ajuda-grafico [ajuda]="ajudas.ciclo" />
          </article>
          <article class="cartao-dados">
            <header><div><h2>Fluxo acumulado</h2><small>Quantas tarefas estão em cada situação a cada dia. Faixas que engordam indicam gargalo.</small></div></header>
            <div class="corpo"><app-grafico tipo="line" titulo="Fluxo acumulado por situação" [rotulos]="rotulosFluxo()" [series]="seriesFluxo()" [empilhado]="true" [altura]="280" /></div>
            <app-ajuda-grafico [ajuda]="ajudas.fluxo" />
          </article>
        </div>

        @if (d.escopo !== 'pessoa') {
        <article class="cartao-dados">
          <header><div><h2>Concluídas por pessoa</h2><small>No período, contando todos os responsáveis de cada tarefa.</small></div></header>
          <div class="corpo">
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th>Pessoa</th><th class="num">Concluídas</th><th class="num">Lead time médio (dias)</th><th class="num" title="Concluídas no período dentro do prazo de resolução">SLA no prazo</th></tr></thead>
                <tbody>
                  @for (p of d.pessoas; track p.usuario_id) {
                    <tr><td>{{ p.nome }}</td><td class="num">{{ p.concluidas }}</td><td class="num">{{ p.lead_medio_dias === null ? '—' : (p.lead_medio_dias | number: '1.0-1') }}</td><td class="num">{{ p.sla_percentual == null ? '—' : (p.sla_percentual | number: '1.0-1') + '%' }}</td></tr>
                  } @empty { <tr><td colspan="4" class="estado-vazio">Nenhuma tarefa concluída no período.</td></tr> }
                </tbody>
              </table>
            </div>
          </div>
        </article>
        }
      } @else {
        <p class="estado-vazio">{{ carregando() ? 'Carregando…' : 'Sem dados.' }}</p>
      }
    </section>
  `,
})
export class DesempenhoTarefasComponent implements OnInit {
  /** Equipe cujo desempenho aparece (liderança) ou, vazio, a pessoa de `pessoaId`. */
  readonly equipeId = input<string>('');
  /** Pessoa cujo desempenho aparece (a própria pessoa, a liderança ou o SuperRoot); inclui as tarefas pessoais. */
  readonly pessoaId = input<number | null>(null);
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);

  protected readonly periodos = PERIODOS;
  protected readonly ajudas = AJUDAS;
  protected readonly periodo = signal(30);
  protected readonly d = signal<DesempenhoEquipe | null>(null);
  protected readonly carregando = signal(true);
  protected readonly marcadores = signal<Marcador[]>([]);
  /** A pessoa consultada não é quem está logado (a liderança vê só as tarefas das equipes que lidera). */
  protected readonly pessoaDeOutro = computed(() => this.pessoaId() !== null && this.pessoaId() !== this.autenticacao.usuario()?.id);
  protected de = '';
  protected ate = '';
  protected marcadorId = '';

  protected readonly rotulosBurndown = computed(() => (this.d()?.burndown.dias ?? []).map(diaMes));
  protected readonly rotulosFluxo = computed(() => (this.d()?.fluxo.dias ?? []).map(diaMes));
  protected readonly rotulosSemanas = computed(() => (this.d()?.vazao ?? []).map((s) => `sem. ${diaMes(s.semana_inicio)}`));

  protected readonly seriesBurndown = computed<SerieGrafico[]>(() => {
    const b = this.d()?.burndown;
    return b ? [
      { nome: 'Real (abertas)', dados: b.real, cor: '#c82331', semPontos: true, area: true },
      { nome: 'Ideal', dados: b.ideal, cor: '#7b8490', tracejada: true, semPontos: true, area: false },
      { nome: 'Escopo', dados: b.escopo, cor: '#2f5d8a', semPontos: true, area: false },
    ] : [];
  });

  protected readonly seriesVazao = computed<SerieGrafico[]>(() => {
    const v = this.d()?.vazao ?? [];
    return [
      { nome: 'Criadas', dados: v.map((x) => x.criadas), cor: '#7b8490' },
      { nome: 'Concluídas', dados: v.map((x) => x.concluidas), cor: '#2f9e6b' },
      { nome: 'Média móvel (4 sem.)', dados: v.map((x) => x.media_movel), cor: '#c82331', linha: true },
    ];
  });

  protected readonly seriesCiclo = computed<SerieGrafico[]>(() => {
    const c = this.d()?.ciclo ?? [];
    return [
      { nome: 'Ciclo (mediana)', dados: c.map((x) => x.ciclo_mediana), cor: '#2f9e6b' },
      { nome: 'Ciclo (P85)', dados: c.map((x) => x.ciclo_p85), cor: '#2f9e6b', tracejada: true },
      { nome: 'Lead time (mediana)', dados: c.map((x) => x.lead_mediana), cor: '#2f5d8a' },
      { nome: 'Lead time (P85)', dados: c.map((x) => x.lead_p85), cor: '#2f5d8a', tracejada: true },
    ];
  });

  protected readonly seriesFluxo = computed<SerieGrafico[]>(() => {
    const f = this.d()?.fluxo;
    return f ? [
      { nome: 'Concluídas', dados: f.concluida, cor: '#2f9e6b', area: true, semPontos: true },
      { nome: 'Em validação', dados: f.em_validacao, cor: '#8a4fb3', area: true, semPontos: true },
      { nome: 'Em andamento', dados: f.em_andamento, cor: '#e0a100', area: true, semPontos: true },
      { nome: 'A fazer', dados: f.a_fazer, cor: '#7b8490', area: true, semPontos: true },
    ] : [];
  });

  ngOnInit(): void {
    if (this.equipeId()) this.api.marcadores(this.equipeId(), '', 200).subscribe({ next: (m) => this.marcadores.set(m), error: () => undefined });
    this.trocarPeriodo(30);
  }

  protected trocarPeriodo(dias: number): void {
    this.periodo.set(dias);
    if (dias > 0) {
      const fim = new Date();
      const inicio = new Date();
      inicio.setDate(inicio.getDate() - (dias - 1));
      this.ate = iso(fim);
      this.de = iso(inicio);
    }
    this.carregar();
  }

  protected carregar(): void {
    if (!this.de || !this.ate) return;
    this.carregando.set(true);
    const pedido = this.equipeId() ? this.api.desempenho(this.equipeId(), this.de, this.ate, this.marcadorId)
      : this.api.desempenhoPessoa(this.pessoaId() ?? 0, this.de, this.ate, this.marcadorId);
    pedido.subscribe({
      next: (r) => { this.d.set(r); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar o desempenho'); },
    });
  }
}
