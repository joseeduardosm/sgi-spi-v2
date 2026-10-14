// Criado por José Eduardo Santana Martins
// Este arquivo serve para o painel gerencial do Patrimônio: indicadores, gráfico por andar/sala/setor/grupo, bens fora de garantia e exportação.
import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { GraficoComponent, SerieGrafico } from '../../shared/componentes/grafico/grafico.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../shared/utilitarios/formatadores.pipes';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { Agrupamento, Bem, PainelPatrimonio, ROTULOS_CONSERVACAO, ROTULOS_GARANTIA, ROTULOS_SITUACAO } from './patrimonio.models';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
const ROTULOS_AGRUPAMENTO: Record<Agrupamento, string> = { andar: 'Andar', sala: 'Sala', setor: 'Setor', grupo: 'Grupo de material' };

@Component({
  selector: 'app-painel-patrimonio',
  imports: [EsqueletoComponent, FormsModule, RouterLink, DatePipe, ...PIPES_FORMATACAO, GraficoComponent, CabecalhoPatrimonioComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Painel do Patrimônio" descricao="Quantidade e valor por andar, sala, setor ou grupo, e os bens fora de garantia." />
    <section class="painel-gestao patrimonio">
      <div class="pat-barra">
        <div class="campo"><label for="pn-agrupar">Agrupar por</label>
          <select id="pn-agrupar" name="agrupar" [(ngModel)]="agrupar" (ngModelChange)="carregar()">@for (a of agrupamentos; track a[0]) { <option [value]="a[0]">{{ a[1] }}</option> }</select></div>
        <div class="campo"><label for="pn-metrica">Mostrar</label>
          <select id="pn-metrica" name="metrica" [ngModel]="metrica()" (ngModelChange)="metrica.set($event)"><option value="quantidade">Quantidade</option><option value="valor">Valor atual</option></select></div>
        <div class="campo"><label for="pn-situacao">Situação</label>
          <select id="pn-situacao" name="situacao" [(ngModel)]="situacao" (ngModelChange)="carregar()"><option value="">Todas</option>@for (s of situacoes; track s[0]) { @if (s[0] !== 'baixado') { <option [value]="s[0]">{{ s[1] }}</option> } }</select></div>
        <div class="campo"><label for="pn-conservacao">Conservação</label>
          <select id="pn-conservacao" name="conservacao" [(ngModel)]="conservacao" (ngModelChange)="carregar()"><option value="">Todas</option>@for (c of conservacoes; track c[0]) { <option [value]="c[0]">{{ c[0] }} · {{ c[1] }}</option> }</select></div>
        <div class="campo"><label for="pn-garantia">Garantia</label>
          <select id="pn-garantia" name="garantia" [(ngModel)]="garantia" (ngModelChange)="carregar()"><option value="">Todas</option>@for (g of garantias; track g[0]) { <option [value]="g[0]">{{ g[1] }}</option> }</select></div>
        <span class="espacador"></span>
        <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('painel', 'xlsx')">Excel</button>
        <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('painel', 'pdf')">PDF</button>
      </div>

      @if (painel(); as p) {
        <div class="pat-indicadores">
          <div><b>{{ p.indicadores.total_bens }}</b><span>Bens</span></div>
          <div><b>{{ p.indicadores.valor_aquisicao | moeda }}</b><span>Valor de aquisição</span></div>
          <div><b>{{ p.indicadores.valor_atual | moeda }}</b><span>Valor atual</span></div>
          <div class="alerta"><b>{{ p.indicadores.fora_garantia }}</b><span>Fora de garantia</span></div>
          <div><b>{{ p.indicadores.aguardando_baixa }}</b><span>Inservíveis e extraviados aguardando baixa</span></div>
          <div class="alerta"><b>{{ p.indicadores.solicitacoes_pendentes }}</b><span>Solicitações aguardando aprovação</span></div>
          <div><b>{{ p.indicadores.dados_contabeis_pendentes }}</b><span>Dados contábeis pendentes</span></div>
          <div><b>{{ p.indicadores.movimentacoes_em_aberto }}</b><span>Movimentações em aberto</span></div>
        </div>

        <h3 class="pat-subtitulo">{{ metrica() === 'valor' ? 'Valor atual' : 'Quantidade de bens' }} por {{ rotulosAgrupamento[p.agrupar_por].toLowerCase() }}</h3>
        @if (p.grupos.length) {
          @defer (on idle) { <app-grafico tipo="bar" [horizontal]="true" [rotulos]="rotulos()" [series]="series()" [formato]="metrica() === 'valor' ? 'moeda' : 'numero'" [semLegenda]="true"
                       [altura]="alturaGrafico()" [titulo]="'Bens por ' + rotulosAgrupamento[p.agrupar_por].toLowerCase()" /> } @placeholder { <app-esqueleto tipo="cartao" /> }
          <p class="pat-dica">Toque numa linha da tabela para listar os bens do grupo.</p>
          <div class="tabela-gestao-envoltorio"><table class="tabela-gestao">
            <thead><tr><th>{{ rotulosAgrupamento[p.agrupar_por] }}</th><th class="num">Bens</th><th class="num">Valor atual</th></tr></thead>
            <tbody>@for (g of p.grupos; track g.chave) {
              <tr class="pat-linha-clicavel" (click)="abrirGrupo(g.chave, g.rotulo)" [class.ativa]="grupoAberto()?.chave === g.chave"><td>{{ g.rotulo }}</td><td class="num">{{ g.quantidade }}</td><td class="num">{{ g.valor | moeda }}</td></tr>
            }</tbody></table></div>
          @if (grupoAberto(); as ga) {
            <div class="pat-painel-acao"><strong>{{ ga.rotulo }}: {{ bensGrupo().length }} bem(ns)</strong>
              @for (b of bensGrupo(); track b.id) { <a class="pat-evento-curto" [routerLink]="['/patrimonio/bens', b.id]">{{ b.rotulo }} · {{ b.descricao }} · {{ b.sala_rotulo }}</a> }</div>
          }
        } @else { <p class="estado-vazio">Sem bens para os filtros escolhidos.</p> }

        <h3 class="pat-subtitulo">Bens fora de garantia ({{ p.fora_garantia.length }})
          <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('fora-garantia', 'xlsx')">Excel</button>
          <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('fora-garantia', 'pdf')">PDF</button></h3>
        @if (p.vencendo_90_dias.length) {
          <div class="pat-aviso"><strong>{{ p.vencendo_90_dias.length }} bem(ns) com a garantia vencendo nos próximos 90 dias:</strong>
            @for (b of p.vencendo_90_dias; track b.id) { <a [routerLink]="['/patrimonio/bens', b.id]">{{ b.rotulo }} ({{ b.dias }} dia(s))</a> }</div>
        }
        <div class="tabela-gestao-envoltorio"><table class="tabela-gestao">
          <thead><tr><th>Chapa</th><th>Descrição</th><th>Sala</th><th>Fim da garantia</th></tr></thead>
          <tbody>@for (b of p.fora_garantia; track b.id) {
            <tr><td><a [routerLink]="['/patrimonio/bens', b.id]">{{ b.rotulo }}</a></td><td>{{ b.descricao }}</td><td>{{ b.sala }}</td><td>{{ b.fim_garantia | date: 'dd/MM/yyyy' }}</td></tr>
          } @empty { <tr><td colspan="4" class="estado-vazio">Nenhum bem fora de garantia.</td></tr> }</tbody></table></div>

        @if (p.contabeis_pendentes.length) {
          <h3 class="pat-subtitulo">Dados contábeis pendentes ({{ p.contabeis_pendentes.length }})</h3>
          <p class="pat-dica">Entram na contagem, mas ficam fora dos totais de valor.</p>
          <ul class="pat-lista-itens">@for (b of p.contabeis_pendentes; track b.id) { <li><div><a [routerLink]="['/patrimonio/bens', b.id]"><strong>{{ b.rotulo }}</strong></a> <span>{{ b.descricao }}</span><small>{{ b.sala }}</small></div></li> }</ul>
        }
      } @else { <app-esqueleto tipo="painel" [linhas]="4" /> }
    </section>
  `,
})
export class PainelPatrimonioComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly painel = signal<PainelPatrimonio | null>(null);
  protected readonly metrica = signal<'quantidade' | 'valor'>('quantidade');
  protected readonly grupoAberto = signal<{ chave: string; rotulo: string } | null>(null);
  protected readonly bensGrupo = signal<Bem[]>([]);
  protected agrupar: Agrupamento = 'andar';
  protected situacao = '';
  protected conservacao: number | '' = '';
  protected garantia = '';
  protected readonly rotulosAgrupamento = ROTULOS_AGRUPAMENTO;
  protected readonly agrupamentos = Object.entries(ROTULOS_AGRUPAMENTO);
  protected readonly situacoes = Object.entries(ROTULOS_SITUACAO);
  protected readonly conservacoes = Object.entries(ROTULOS_CONSERVACAO);
  protected readonly garantias = Object.entries(ROTULOS_GARANTIA);

  protected readonly rotulos = computed(() => this.painel()?.grupos.map((g) => g.rotulo) ?? []);
  protected readonly series = computed<SerieGrafico[]>(() => [{ nome: this.metrica() === 'valor' ? 'Valor atual' : 'Bens', dados: (this.painel()?.grupos ?? []).map((g) => (this.metrica() === 'valor' ? Number(g.valor) : g.quantidade)) }]);
  /** Altura proporcional ao número de barras (cada uma precisa de espaço para o rótulo). */
  protected readonly alturaGrafico = computed(() => Math.max(220, (this.painel()?.grupos.length ?? 1) * 34 + 60));

  ngOnInit(): void {
    this.carregar();
  }

  protected carregar(): void {
    this.grupoAberto.set(null);
    this.api.painel({ agrupar_por: this.agrupar, situacao: this.situacao, conservacao: this.conservacao, garantia: this.garantia }).subscribe({
      next: (p) => this.painel.set(p), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel'),
    });
  }

  protected abrirGrupo(chave: string, rotulo: string): void {
    this.grupoAberto.set({ chave, rotulo });
    this.api.bensDoGrupo({ agrupar_por: this.agrupar, chave, situacao: this.situacao, conservacao: this.conservacao, garantia: this.garantia }).subscribe((b) => this.bensGrupo.set(b));
  }

  protected exportar(relatorio: 'painel' | 'fora-garantia', formato: 'xlsx' | 'pdf'): void {
    const filtros = relatorio === 'painel' ? { agrupar_por: this.agrupar, situacao: this.situacao, conservacao: this.conservacao, garantia: this.garantia } : {};
    this.dialogos.executar(this.api.exportar(relatorio, formato, filtros), 'Gerando o relatório…').subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório') });
  }
}
