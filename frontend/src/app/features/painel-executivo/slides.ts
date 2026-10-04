// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar os três slides do Painel Executivo: contratos, RH e tarefas.

import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { GraficoComponent, SerieGrafico } from '../../shared/componentes/grafico/grafico.component';
import { dataCurta, emMil, MESES_CURTOS, moedaCurta, SlideContratos, SlideRh, SlideTarefas } from './painel-executivo.models';

/** Cartão de indicador: número grande e legenda. `alerta` pinta de vermelho. */
@Component({
  selector: 'app-indicador',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<div class="indicador" [class.alerta]="alerta()"><strong>{{ valor() }}</strong><span>{{ rotulo() }}</span></div>`,
})
export class IndicadorComponent {
  readonly valor = input.required<string | number>();
  readonly rotulo = input.required<string>();
  readonly alerta = input(false);
}

@Component({
  selector: 'app-slide-contratos',
  imports: [GraficoComponent, IndicadorComponent, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let d = dados();
    <div class="indicadores">
      <app-indicador [valor]="d.numeros.contratos_ativos" rotulo="Contratos ativos" />
      <app-indicador [valor]="d.numeros.contratos_a_vencer" rotulo="Vencem em até 90 dias" [alerta]="d.numeros.contratos_a_vencer > 0" />
      <app-indicador [valor]="moeda(d.numeros.valor_global_ativos)" rotulo="Valor global dos ativos" />
      <app-indicador [valor]="moeda(d.execucao.total_pago)" [rotulo]="'Pago em ' + d.exercicio" />
      <app-indicador [valor]="moeda(d.execucao.saldo_empenho)" rotulo="Saldo de empenho" />
      <app-indicador [valor]="d.alertas_altos" rotulo="Contratos com risco alto" [alerta]="d.alertas_altos > 0" />
    </div>
    <div class="grade-slide">
      <section><h3>Execução mensal em {{ d.exercicio }}</h3>
        <app-grafico tipo="bar" titulo="Execução mensal: previsto, medido e pago" formato="moedaMil" [rotulos]="meses" [series]="mensal()" [altura]="alturaGrafico()" /></section>
      <section><h3>Acumulado no exercício</h3>
        <app-grafico tipo="line" titulo="Execução acumulada" formato="moedaMil" [rotulos]="meses" [series]="acumulado()" [altura]="alturaGrafico()" /></section>
      <section><h3>Vencimentos</h3>
        <app-grafico tipo="bar" titulo="Contratos vencendo em 30, 60 e 90 dias" [rotulos]="faixas()" [series]="vencimentos()" [altura]="alturaGrafico()" [semLegenda]="true" /></section>
      <section class="lista-slide"><h3>Maiores riscos</h3>
        <ul>
          @for (r of d.maiores_riscos; track r.contrato_numero) {
            <li><span class="selo-risco" [class.alta]="r.gravidade === 'alta'">{{ r.gravidade === 'alta' ? 'Alto' : 'Médio' }}</span>
              <a [routerLink]="r.rota"><strong>{{ r.contrato_numero }} {{ r.contrato_apelido }}</strong></a>
              <small>{{ r.principal }}</small></li>
          } @empty { <li class="estado-vazio">Nenhum risco identificado.</li> }
        </ul></section>
    </div>
  `,
})
export class SlideContratosComponent {
  readonly dados = input.required<SlideContratos>();
  readonly compacto = input(false);
  protected readonly meses = MESES_CURTOS;
  protected readonly moeda = moedaCurta;
  protected readonly alturaGrafico = computed(() => (this.compacto() ? 170 : 0));
  protected readonly mensal = computed<SerieGrafico[]>(() => {
    const m = this.dados().execucao.meses;
    return [{ nome: 'Previsto', dados: m.map((x) => emMil(x.previsto)), cor: '#c9ced4' }, { nome: 'Medido', dados: m.map((x) => emMil(x.medido)), cor: '#2f5d8a' },
            { nome: 'Pago', dados: m.map((x) => emMil(x.pago)), cor: '#c82331' }];
  });
  protected readonly acumulado = computed<SerieGrafico[]>(() => {
    const m = this.dados().acumulado;
    return [{ nome: 'Previsto', dados: m.map((x) => emMil(x.previsto)), cor: '#9aa3ad' }, { nome: 'Medido', dados: m.map((x) => emMil(x.medido)), cor: '#2f5d8a' },
            { nome: 'Pago', dados: m.map((x) => emMil(x.pago)), cor: '#c82331' }];
  });
  protected readonly faixas = computed(() => this.dados().vencimentos.map((v) => `até ${v.ate_dias} dias`));
  protected readonly vencimentos = computed<SerieGrafico[]>(() => [{ nome: 'Contratos', dados: this.dados().vencimentos.map((v) => v.contratos), cor: '#e0a100' }]);
}

@Component({
  selector: 'app-slide-rh',
  imports: [GraficoComponent, IndicadorComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let d = dados();
    <div class="indicadores">
      <app-indicador [valor]="d.afastados_hoje.length" rotulo="Fora hoje (férias ou licença)" />
      <app-indicador [valor]="d.ferias_a_vencer.length" rotulo="Com férias a vencer (90 dias)" [alerta]="d.ferias_a_vencer.length > 0" />
      <app-indicador [valor]="d.alertas_setor.length" rotulo="Setores com muitos afastados" [alerta]="d.alertas_setor.length > 0" />
    </div>
    <div class="grade-slide">
      <section><h3>Pessoas afastadas por mês em {{ d.ano }}</h3>
        <app-grafico tipo="bar" titulo="Pessoas afastadas por mês" [rotulos]="meses" [series]="porMes()" [empilhado]="true" [altura]="alturaGrafico()" /></section>
      <section><h3>Dias de afastamento por setor</h3>
        <app-grafico tipo="bar" titulo="Dias de afastamento por setor" [rotulos]="setores()" [series]="porSetor()" [horizontal]="true" [semLegenda]="true" [altura]="alturaGrafico()" /></section>
      <section class="lista-slide"><h3>Fora hoje</h3>
        <ul>
          @for (a of d.afastados_hoje; track a.nome) {
            <li><strong>{{ a.nome }}</strong><small>{{ a.setor }} · {{ a.tipo === 'ferias' ? 'férias' : 'licença-prêmio' }} até {{ data(a.fim) }}</small></li>
          } @empty { <li class="estado-vazio">Ninguém afastado hoje.</li> }
        </ul></section>
      <section class="lista-slide"><h3>Férias a vencer</h3>
        <ul>
          @for (f of d.ferias_a_vencer; track f.nome) {
            <li><strong>{{ f.nome }}</strong><small>{{ f.setor }} · {{ f.disponivel }} dias até {{ data(f.periodo_fim) }}</small></li>
          } @empty { <li class="estado-vazio">Nada vencendo nos próximos 90 dias.</li> }
        </ul></section>
    </div>
  `,
})
export class SlideRhComponent {
  readonly dados = input.required<SlideRh>();
  readonly compacto = input(false);
  protected readonly meses = MESES_CURTOS;
  protected readonly data = (iso: string) => dataCurta(iso);
  protected readonly alturaGrafico = computed(() => (this.compacto() ? 170 : 0));
  protected readonly porMes = computed<SerieGrafico[]>(() => [
    { nome: 'Férias', dados: this.dados().por_mes.map((m) => m.ferias), cor: '#2f9e6b' },
    { nome: 'Licença-prêmio', dados: this.dados().por_mes.map((m) => m.licenca_premio), cor: '#2f5d8a' },
  ]);
  protected readonly setores = computed(() => this.dados().por_setor.map((s) => s.setor));
  protected readonly porSetor = computed<SerieGrafico[]>(() => [{ nome: 'Dias', dados: this.dados().por_setor.map((s) => s.dias), cor: '#c82331' }]);
}

@Component({
  selector: 'app-slide-tarefas',
  imports: [GraficoComponent, IndicadorComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @let d = dados();
    <div class="indicadores">
      <app-indicador [valor]="d.abertas" rotulo="Abertas" />
      <app-indicador [valor]="d.atrasadas" rotulo="Atrasadas" [alerta]="d.atrasadas > 0" />
      <app-indicador [valor]="d.vencem_hoje" rotulo="Vencem hoje" />
      <app-indicador [valor]="d.criticas" rotulo="Críticas" [alerta]="d.criticas > 0" />
      <app-indicador [valor]="d.em_validacao" rotulo="Em validação" />
      <app-indicador [valor]="d.concluidas_30_dias" rotulo="Concluídas em 30 dias" />
    </div>
    <div class="grade-slide">
      <section><h3>Criadas × concluídas por semana</h3>
        <app-grafico tipo="line" titulo="Tarefas criadas e concluídas por semana" [rotulos]="semanas()" [series]="evolucao()" [altura]="alturaGrafico()" /></section>
      <section><h3>Situação por equipe</h3>
        <app-grafico tipo="bar" titulo="Tarefas em dia e atrasadas por equipe" [rotulos]="equipes()" [series]="porEquipe()" [empilhado]="true" [horizontal]="true" [altura]="alturaGrafico()" /></section>
      <section class="lista-slide largura-total"><h3>Carga das equipes</h3>
        <ul>
          @for (e of d.equipes; track e.equipe) {
            <li><strong>{{ e.equipe }}</strong><small>{{ e.abertas }} abertas · {{ e.atrasadas }} atrasadas · {{ e.criticas }} críticas · {{ e.faixa }}</small></li>
          } @empty { <li class="estado-vazio">Nenhuma equipe com tarefas.</li> }
        </ul></section>
    </div>
  `,
})
export class SlideTarefasComponent {
  readonly dados = input.required<SlideTarefas>();
  readonly compacto = input(false);
  protected readonly alturaGrafico = computed(() => (this.compacto() ? 170 : 0));
  protected readonly semanas = computed(() => this.dados().semanas.map((s) => dataCurta(s.inicio)));
  protected readonly evolucao = computed<SerieGrafico[]>(() => [
    { nome: 'Criadas', dados: this.dados().semanas.map((s) => s.criadas), cor: '#9aa3ad' },
    { nome: 'Concluídas', dados: this.dados().semanas.map((s) => s.concluidas), cor: '#c82331' },
  ]);
  protected readonly equipes = computed(() => this.dados().equipes.map((e) => e.equipe));
  protected readonly porEquipe = computed<SerieGrafico[]>(() => [
    { nome: 'Em dia', dados: this.dados().equipes.map((e) => e.abertas - e.atrasadas), cor: '#2f9e6b' },
    { nome: 'Atrasadas', dados: this.dados().equipes.map((e) => e.atrasadas), cor: '#c82331' },
  ]);
}
