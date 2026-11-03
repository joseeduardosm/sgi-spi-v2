// Criado por José Eduardo Santana Martins
// Este arquivo serve para mostrar os relatórios do atendimento dos Chamados: indicadores com tendência, semanas, desempenho da equipe,
// satisfação, categorias e (para quem escolhe setor) a quebra por setor responsável. Também exporta a lista do período (PDF ou XLSX).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { CORES_GRAFICO, GraficoComponent, SerieGrafico } from '../../shared/componentes/grafico/grafico.component';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { IconeComponent, NomeIcone } from '../../shared/componentes/icone/icone.component';
import { MinigraficoComponent } from '../../shared/componentes/minigrafico/minigrafico.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoChamadosComponent } from './cabecalho-chamados.component';
import { ChamadosApiService } from './chamados-api.service';
import { LinhaRelatorio, NOTAS_SATISFACAO, PessoaEquipe, RelatorioChamados, ROTULOS_PRIORIDADE } from './chamados.models';

/** Períodos rápidos, em dias (0 = personalizado). Mesmo desenho da tela de Desempenho das Tarefas. */
const PERIODOS = [{ dias: 7, rotulo: 'Últimos 7 dias' }, { dias: 30, rotulo: 'Últimos 30 dias' }, { dias: 90, rotulo: 'Últimos 90 dias' }, { dias: 365, rotulo: 'Último ano' }];

/** Cores das séries: a paleta dos gráficos do portal, sempre na mesma ordem (vermelho, azul, verde...). */
const COR_ABERTOS = CORES_GRAFICO[0];
const COR_RESOLVIDOS = CORES_GRAFICO[1];
const COR_EQUIPE_RESOLVIDOS = CORES_GRAFICO[2];
const COR_EQUIPE_ASSUMIDOS = CORES_GRAFICO[1];

type Tom = 'info' | 'sucesso' | 'alerta' | 'perigo' | 'neutro';
type JanelaEquipe = '7d' | '30d' | 'semana';

/** Um cartão de indicador: ícone com o tom (o significado), número, rótulo, contexto, a minissérie do período e a lista que ele abre. */
interface Cartao {
  icone: NomeIcone; tom: Tom; valor: string; rotulo: string; contexto: string; serie: (number | null)[]; atencao?: boolean; lista: Record<string, string>;
}

/** "2026-11-02" → "02/11/2026" (para o texto do recorte na lista). */
function dataBr(iso: string): string {
  return iso.split('-').reverse().join('/');
}

/** Soma dias a uma data ISO (sem fuso: só o calendário). */
function somarDias(iso: string, dias: number): string {
  const d = new Date(iso + 'T12:00:00');
  d.setDate(d.getDate() + dias);
  return isoSaoPaulo(d);
}

function isoSaoPaulo(data: Date): string {
  return data.toLocaleDateString('sv-SE', { timeZone: 'America/Sao_Paulo' });
}

@Component({
  selector: 'app-relatorios-chamados',
  imports: [FormsModule, RouterLink, CabecalhoChamadosComponent, EsqueletoComponent, GraficoComponent, IconeComponent, MinigraficoComponent],
  styleUrl: './relatorios-chamados.component.scss',
  template: `
    <div class="modulo-chamados relatorios-chamados">
      <app-cabecalho-chamados titulo="Relatórios" [descricao]="'Acompanhe o desempenho de ' + (r()?.area ?? 'seu setor') + ' no período selecionado.'" />

      <!-- Filtros: período sempre; setor só para quem tem Controle total ou lidera um setor com setores abaixo -->
      <section class="rc-filtros" aria-label="Filtros do relatório">
        <div class="rc-filtro">
          <span class="rc-filtro-icone"><app-icone nome="calendario" /></span>
          <div class="campo"><label for="rc-periodo">Período</label>
            <select id="rc-periodo" [ngModel]="periodo()" (ngModelChange)="trocarPeriodo($event)">
              @for (p of periodos; track p.dias) { <option [ngValue]="p.dias">{{ p.rotulo }}</option> }
              <option [ngValue]="0">Personalizado</option>
            </select></div>
        </div>
        @if (periodo() === 0) {
          <div class="campo"><label for="rc-de">De</label><input id="rc-de" type="date" [(ngModel)]="de" (change)="carregar()" /></div>
          <div class="campo"><label for="rc-ate">Até</label><input id="rc-ate" type="date" [(ngModel)]="ate" (change)="carregar()" /></div>
        }
        @if (r()?.pode_escolher_setor) {
          <div class="rc-filtro rc-filtro-setor">
            <span class="rc-filtro-icone"><app-icone nome="predio" /></span>
            <div class="campo"><label for="rc-setor">Setor</label>
              <select id="rc-setor" [(ngModel)]="setorId" (ngModelChange)="carregar()">
                <option [ngValue]="null">Todos os que eu vejo</option>
                @for (s of r()!.setores_opcoes; track s.id) { <option [ngValue]="s.id">{{ s.nome }}</option> }
              </select></div>
          </div>
        }
        <button type="button" class="acao-secundaria rc-exportar" (click)="abrirExportacao()"><app-icone nome="baixar" /> Exportar</button>
      </section>

      @if (r(); as r) {
        <!-- Indicadores: cada um com a tendência do período (semana a semana) no rodapé -->
        <section class="rc-cartoes" aria-label="Resumo do período">
          @for (c of cartoes(); track c.rotulo) {
            <a class="rc-cartao" [attr.data-tom]="c.tom" routerLink="/chamados/fila" [queryParams]="c.lista" [attr.aria-label]="c.rotulo + ': ' + c.valor + '. Abrir a lista'">
              <span class="rc-cartao-icone"><app-icone [nome]="c.icone" /></span>
              <b>{{ c.valor }}</b>
              <span class="rc-cartao-rotulo">{{ c.rotulo }}</span>
              <small [class.rc-atencao]="c.atencao">{{ c.contexto }}</small>
              <app-minigrafico [dados]="c.serie" [tom]="c.tom" />
            </a>
          }
        </section>

        <div class="rc-linha">
          <article class="rc-bloco">
            <header>
              <div><h2><app-icone nome="grafico-colunas" /> Abertos e resolvidos por semana</h2><small>Semanas de segunda a domingo, dentro do período.</small></div>
              <ul class="rc-legenda" aria-hidden="true">
                <li><i [style.background]="corAbertos"></i>Abertos</li><li><i [style.background]="corResolvidos"></i>Resolvidos</li>
              </ul>
            </header>
            @defer (on idle) {
              <app-grafico tipo="bar" titulo="Chamados abertos e resolvidos por semana" [rotulos]="rotulosSemanas()" [series]="seriesSemanas()"
                [altura]="280" [semLegenda]="true" [valores]="true" [clicavel]="true" (pontoClicado)="abrirSemana($event.indice, $event.serie)" />
            } @placeholder { <app-esqueleto tipo="cartao" /> }
          </article>

          <article class="rc-bloco">
            <header>
              <div><h2><app-icone nome="usuarios" /> Desempenho da equipe</h2><small>{{ textoJanela() }}</small></div>
              <div class="chips-filtro" role="group" aria-label="Janela do desempenho">
                <button type="button" [class.ativo]="janela() === '7d'" [attr.aria-pressed]="janela() === '7d'" (click)="janela.set('7d')">Últimos 7 dias</button>
                <button type="button" [class.ativo]="janela() === '30d'" [attr.aria-pressed]="janela() === '30d'" (click)="janela.set('30d')">Últimos 30 dias</button>
                <button type="button" [class.ativo]="janela() === 'semana'" [attr.aria-pressed]="janela() === 'semana'" (click)="janela.set('semana')">Por semana</button>
              </div>
            </header>
            @if (r.equipe?.length) {
              <ul class="rc-legenda rc-legenda-direita" aria-hidden="true">
                <li><i [style.background]="corEquipeResolvidos"></i>Resolvidos</li><li><i [style.background]="corEquipeAssumidos"></i>Assumidos</li>
              </ul>
              @defer (on idle) {
                <app-grafico tipo="bar" [horizontal]="true" titulo="Resolvidos e assumidos por pessoa" [rotulos]="rotulosEquipe()" [series]="seriesEquipe()"
                  [altura]="alturaEquipe()" [semLegenda]="true" [valores]="true" [clicavel]="true" (pontoClicado)="abrirPessoa($event.indice, $event.serie)" />
              } @placeholder { <app-esqueleto tipo="cartao" /> }
            } @else { <p class="estado-vazio">Ninguém do setor atendeu chamados no período.</p> }
          </article>
        </div>

        <div class="rc-linha rc-linha-igual">
          <article class="rc-bloco">
            <header><div><h2><app-icone nome="estrela" /> Notas de satisfação</h2><small>Quantas pessoas avaliaram e qual a nota média.</small></div></header>
            <div class="rc-satisfacao">
              <!-- Anel: quantos responderam entre os que receberam a pesquisa -->
              <div class="rc-anel" role="img" [attr.aria-label]="r.resumo.satisfacao_respostas + ' de ' + r.resumo.satisfacao_pedidas + ' responderam'">
                <svg viewBox="0 0 120 120" aria-hidden="true">
                  <circle class="fundo" cx="60" cy="60" r="50" />
                  <circle class="valor" cx="60" cy="60" r="50" [attr.stroke-dasharray]="anelRespostas() + ' 314.16'" />
                </svg>
                <span><b>{{ r.resumo.satisfacao_respostas }}</b><small>de {{ r.resumo.satisfacao_pedidas }}<br />responderam</small></span>
              </div>
              <div class="rc-nota">
                <span class="rc-nota-titulo"><app-icone nome="estrela" /> Nota média</span>
                <div class="rc-nota-valor">
                  <b>{{ r.resumo.satisfacao_media === null ? '0,0' : decimal(r.resumo.satisfacao_media, 1) }}</b>
                  <span class="rc-estrelas" [attr.aria-label]="'Nota ' + (r.resumo.satisfacao_media ?? 0) + ' de 5'">
                    @for (e of [1, 2, 3, 4, 5]; track e) { <span [class.cheia]="e <= estrelasCheias()"><app-icone nome="estrela" /></span> }
                  </span>
                </div>
                <ul class="rc-distribuicao">
                  @for (n of notas; track n[0]; let i = $index) {
                    <li class="rc-clicavel" tabindex="0" [attr.aria-label]="'Abrir os chamados com nota ' + n[1]" (click)="abrirNota(n[0], n[1])"
                        (keydown.enter)="abrirNota(n[0], n[1])"><span>{{ n[1] }}</span><i><em [style.width.%]="percentualNota(i)"></em></i><b>{{ r.notas[i] }}</b></li>
                  }
                </ul>
              </div>
            </div>
          </article>

          <article class="rc-bloco">
            <header><div><h2><app-icone nome="etiqueta" /> Por categoria</h2><small>As categorias com mais chamados abertos no período.</small></div></header>
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th scope="col">Categoria</th><th scope="col">Abertos</th><th scope="col">Resolvidos</th><th scope="col">Resolvidos no prazo</th></tr></thead>
                <tbody>
                  @for (x of r.por_categoria; track x.nome) {
                    <tr class="rc-clicavel" tabindex="0" [attr.aria-label]="'Abrir os chamados abertos de ' + x.nome" (click)="abrirLinha('categoria', x, 'abertos')"
                        (keydown.enter)="abrirLinha('categoria', x, 'abertos')">
                      <td>{{ x.nome }}</td><td>{{ x.abertos }}</td>
                      <td><button type="button" class="acao-secundaria acao-pequena" [disabled]="!x.resolvidos" [attr.aria-label]="'Abrir os resolvidos de ' + x.nome"
                        (click)="$event.stopPropagation(); abrirLinha('categoria', x, 'resolvidos')">{{ x.resolvidos }}</button></td>
                      <td>{{ pct(x.no_prazo_pct) }}</td></tr>
                  }
                  @empty { <tr><td colspan="4" class="estado-vazio">Nenhum chamado no período.</td></tr> }
                </tbody>
              </table>
            </div>
          </article>
        </div>

        @if (r.pode_escolher_setor) {
          <article class="rc-bloco rc-setores">
            <div class="rc-aviso-setor">
              <app-icone nome="alerta" />
              <div><strong>Por setor responsável</strong><small>Prioridade dos abertos no período: {{ textoPrioridades(r) }}.</small></div>
            </div>
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th scope="col">Setor</th><th scope="col">Abertos</th><th scope="col">Resolvidos</th><th scope="col">Resolvidos no prazo</th></tr></thead>
                <tbody>
                  @for (x of r.por_setor; track x.nome) {
                    <tr class="rc-clicavel" tabindex="0" [attr.aria-label]="'Abrir os chamados abertos de ' + x.nome" (click)="abrirLinha('setor', x, 'abertos')"
                        (keydown.enter)="abrirLinha('setor', x, 'abertos')">
                      <td>{{ x.nome }}</td><td>{{ x.abertos }}</td>
                      <td><button type="button" class="acao-secundaria acao-pequena" [disabled]="!x.resolvidos" [attr.aria-label]="'Abrir os resolvidos de ' + x.nome"
                        (click)="$event.stopPropagation(); abrirLinha('setor', x, 'resolvidos')">{{ x.resolvidos }}</button></td>
                      <td>{{ pct(x.no_prazo_pct) }}</td></tr>
                  }
                  @empty { <tr><td colspan="4" class="estado-vazio">Nenhum chamado no período.</td></tr> }
                </tbody>
              </table>
            </div>
          </article>
        }
      } @else {
        <app-esqueleto tipo="painel" />
      }
    </div>

    @if (exportando()) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="exportando.set(false)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-exportacao" (keydown.escape)="exportando.set(false)">
        <header>
          <div><span class="modal-sobretitulo">Relatórios</span><h2 id="titulo-exportacao">Exportar chamados</h2></div>
          <button type="button" aria-label="Fechar" (click)="exportando.set(false)">×</button>
        </header>
        <form (submit)="$event.preventDefault(); exportar()">
          <p class="dica-formulario" style="margin-top: 0">Chamados abertos no período (até 1 ano): Nº, título, descrição, solicitante, setor responsável,
            responsável e status. O título do arquivo leva o setor e as datas.</p>
          <div class="grade-formulario">
            <div><label for="exp-de">Data de início</label><input id="exp-de" name="de" type="date" required [(ngModel)]="exportacao.de" /></div>
            <div><label for="exp-ate">Data de fim</label><input id="exp-ate" name="ate" type="date" required [(ngModel)]="exportacao.ate" /></div>
            @if (r()?.pode_escolher_setor) {
              <div class="ocupa-duas"><label for="exp-setor">Setor</label>
                <select id="exp-setor" name="setor" [(ngModel)]="exportacao.setorId">
                  <option [ngValue]="null">Todos os que eu vejo</option>
                  @for (s of r()!.setores_opcoes; track s.id) { <option [ngValue]="s.id">{{ s.nome }}</option> }
                </select></div>
            }
            <div><label for="exp-solucao">Solução</label>
              <select id="exp-solucao" name="solucao" [(ngModel)]="exportacao.comSolucao">
                <option [ngValue]="false">Sem solução</option><option [ngValue]="true">Com solução (coluna a mais)</option>
              </select></div>
            <div><label for="exp-formato">Formato</label>
              <select id="exp-formato" name="formato" [(ngModel)]="exportacao.formato">
                <option value="pdf">PDF (paisagem)</option><option value="xlsx">Planilha (XLSX)</option>
              </select></div>
          </div>
          <footer>
            <button type="button" class="acao-secundaria" (click)="exportando.set(false)">Cancelar</button>
            <button type="submit" class="acao-primaria" [class.carregando]="gerando()" [disabled]="gerando() || !exportacao.de || !exportacao.ate">Exportar</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class RelatoriosChamadosComponent implements OnInit {
  private readonly api = inject(ChamadosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  protected readonly periodos = PERIODOS;
  protected readonly notas = NOTAS_SATISFACAO;
  protected readonly corAbertos = COR_ABERTOS;
  protected readonly corResolvidos = COR_RESOLVIDOS;
  protected readonly corEquipeResolvidos = COR_EQUIPE_RESOLVIDOS;
  protected readonly corEquipeAssumidos = COR_EQUIPE_ASSUMIDOS;
  protected readonly periodo = signal(30);
  protected readonly r = signal<RelatorioChamados | null>(null);
  /** Janela do gráfico da equipe: últimos 7 dias, últimos 30 dias ou média por semana do período. */
  protected readonly janela = signal<JanelaEquipe>('7d');
  protected de = '';
  protected ate = '';
  protected setorId: number | null = null;
  // Exportação (modal): começa com o período e o setor que estão na tela
  protected readonly exportando = signal(false);
  protected readonly gerando = signal(false);
  protected exportacao = { de: '', ate: '', setorId: null as number | null, comSolucao: false, formato: 'pdf' as 'pdf' | 'xlsx' };

  protected readonly rotulosSemanas = computed(() => (this.r()?.semanas ?? []).map((s) => {
    const inicio = new Date(s.inicio + 'T12:00:00');
    const fim = new Date(inicio.getTime() + 6 * 86400000);
    const dm = (d: Date) => d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
    return `${dm(inicio)} – ${dm(fim)}`;
  }));
  protected readonly seriesSemanas = computed<SerieGrafico[]>(() => {
    const semanas = this.r()?.semanas ?? [];
    return [{ nome: 'Abertos', dados: semanas.map((s) => s.abertos), cor: COR_ABERTOS }, { nome: 'Resolvidos', dados: semanas.map((s) => s.resolvidos), cor: COR_RESOLVIDOS }];
  });

  /** Os seis cartões do topo, cada um com a série semanal correspondente. */
  protected readonly cartoes = computed<Cartao[]>(() => {
    const r = this.r();
    if (!r) return [];
    const x = r.resumo, s = r.semanas;
    const periodo = `de ${dataBr(r.inicio)} a ${dataBr(r.fim)}`;
    const abertos = this.recorte(`Abertos ${periodo}`, 'todos', { aberto_de: r.inicio, aberto_ate: r.fim });
    const resolvidos = this.recorte(`Resolvidos ${periodo}`, 'todos', { resolvido_de: r.inicio, resolvido_ate: r.fim });
    const prazoBaixo = x.atendimento_no_prazo_pct !== null && x.atendimento_no_prazo_pct < 75;
    return [
      { icone: 'chamado', tom: 'info', valor: String(x.abertos_no_periodo), rotulo: 'Abertos no período', contexto: `${s.length} semana(s) no período`,
        serie: s.map((w) => w.abertos), lista: abertos },
      { icone: 'concluido', tom: 'sucesso', valor: String(x.resolvidos_no_periodo), rotulo: 'Resolvidos no período',
        contexto: `No prazo: ${this.pct(x.solucao_no_prazo_pct)} (${x.solucao_no_prazo} de ${x.solucao_com_prazo})`, serie: s.map((w) => w.resolvidos),
        lista: resolvidos },
      { icone: 'relogio', tom: 'alerta', valor: String(x.em_aberto_agora), rotulo: 'Em aberto agora', contexto: 'Fila no fim de cada semana abaixo',
        serie: s.map((w) => w.em_aberto_fim), lista: this.recorte('Em aberto agora', 'abertos', {}) },
      { icone: 'ampulheta', tom: 'neutro', valor: this.duracao(x.horas_mediana_solucao), rotulo: 'Até resolver',
        contexto: 'Mediana, em horas corridas', serie: s.map((w) => w.horas_mediana_solucao), lista: resolvidos },
      { icone: 'recarregar', tom: 'perigo', valor: String(x.reabertos), rotulo: 'Reabertos', contexto: '"Não resolveu" depois da solução', serie: s.map((w) => w.reabertos),
        atencao: x.reabertos > 0, lista: this.recorte(`Reabertos entre os resolvidos ${periodo}`, 'todos', { resolvido_de: r.inicio, resolvido_ate: r.fim, reabertos: 'true' }) },
      { icone: 'concluido', tom: 'sucesso', valor: this.pct(x.atendimento_no_prazo_pct), rotulo: 'Atendidos no prazo',
        contexto: `${x.atendimento_no_prazo} de ${x.atendimento_com_prazo} com prazo`, serie: s.map((w) => w.atendimento_no_prazo_pct), atencao: prazoBaixo, lista: abertos },
    ];
  });

  /** Pessoas na ordem da janela escolhida (quem mais resolveu primeiro). */
  private readonly equipeOrdenada = computed(() => {
    const [res, ass] = this.campos();
    return [...(this.r()?.equipe ?? [])].sort((a, b) => b[res] - a[res] || b[ass] - a[ass] || a.nome.localeCompare(b.nome));
  });
  protected readonly rotulosEquipe = computed(() => this.equipeOrdenada().map((p) => p.nome));
  protected readonly seriesEquipe = computed<SerieGrafico[]>(() => {
    const [res, ass] = this.campos();
    const pessoas = this.equipeOrdenada();
    return [{ nome: 'Resolvidos', dados: pessoas.map((p) => p[res]), cor: COR_EQUIPE_RESOLVIDOS },
            { nome: 'Assumidos', dados: pessoas.map((p) => p[ass]), cor: COR_EQUIPE_ASSUMIDOS }];
  });
  /** Altura que cabe duas barras por pessoa sem apertar os nomes. */
  protected readonly alturaEquipe = computed(() => Math.max(220, this.equipeOrdenada().length * 56 + 40));
  protected readonly textoJanela = computed(() => ({
    '7d': 'Resolvidos e assumidos por pessoa nos últimos 7 dias do período.',
    '30d': 'Resolvidos e assumidos por pessoa nos últimos 30 dias do período.',
    semana: 'Média por semana de cada pessoa no período escolhido.',
  })[this.janela()]);

  protected readonly anelRespostas = computed(() => {
    const x = this.r()?.resumo;
    return x && x.satisfacao_pedidas ? ((x.satisfacao_respostas / x.satisfacao_pedidas) * 314.16).toFixed(1) : '0';
  });
  protected readonly estrelasCheias = computed(() => Math.round(this.r()?.resumo.satisfacao_media ?? 0));

  ngOnInit(): void {
    this.trocarPeriodo(30);
  }

  private campos(): [keyof PessoaEquipe & `resolvidos_${string}`, keyof PessoaEquipe & `assumidos_${string}`] {
    const j = this.janela();
    return j === '7d' ? ['resolvidos_7d', 'assumidos_7d'] : j === '30d' ? ['resolvidos_30d', 'assumidos_30d'] : ['resolvidos_semana', 'assumidos_semana'];
  }

  protected trocarPeriodo(dias: number): void {
    this.periodo.set(dias);
    if (dias) {
      const hoje = new Date();
      this.ate = isoSaoPaulo(hoje);
      this.de = isoSaoPaulo(new Date(hoje.getTime() - (dias - 1) * 86400000));
    }
    this.carregar();
  }

  protected carregar(): void {
    this.api.relatorios(this.de, this.ate, this.setorId).subscribe({
      next: (x) => this.r.set(x),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível montar o relatório'),
    });
  }

  /** Parâmetros da lista para um recorte: os setores do relatório (o mesmo setor escolhido) + o filtro + o texto que a lista mostra. */
  private recorte(titulo: string, filtro: 'todos' | 'abertos', extra: Record<string, string>): Record<string, string> {
    const area = this.r()?.area;
    return { filtro, titulo: area ? `${titulo} · ${area}` : titulo, escopo_relatorio: 'true', ...(this.setorId !== null ? { relatorio_setor_id: String(this.setorId) } : {}), ...extra };
  }

  private irParaLista(params: Record<string, string>): void {
    this.roteador.navigate(['/chamados/fila'], { queryParams: params });
  }

  /** Barra da semana: abertos (série 0) ou resolvidos (série 1) naquela semana, dentro do período do relatório. */
  protected abrirSemana(indice: number, serie: number): void {
    const r = this.r();
    const semana = r?.semanas[indice];
    if (!r || !semana) return;
    const de = semana.inicio < r.inicio ? r.inicio : semana.inicio;
    const fimSemana = somarDias(semana.inicio, 6);
    const ate = fimSemana > r.fim ? r.fim : fimSemana;
    const texto = `de ${dataBr(de)} a ${dataBr(ate)}`;
    this.irParaLista(serie === 0
      ? this.recorte(`Abertos ${texto}`, 'todos', { aberto_de: de, aberto_ate: ate })
      : this.recorte(`Resolvidos ${texto}`, 'todos', { resolvido_de: de, resolvido_ate: ate }));
  }

  /** Barra da pessoa: resolvidos (série 0) ou assumidos (série 1) por ela, na janela escolhida no gráfico. */
  protected abrirPessoa(indice: number, serie: number): void {
    const r = this.r();
    const pessoa = this.equipeOrdenada()[indice];
    if (!r || !pessoa) return;
    const j = this.janela();
    const de = j === '7d' ? somarDias(r.fim, -6) : j === '30d' ? somarDias(r.fim, -29) : r.inicio;
    const texto = `de ${dataBr(de)} a ${dataBr(r.fim)}`;
    this.irParaLista(serie === 0
      ? this.recorte(`Resolvidos por ${pessoa.nome} ${texto}`, 'todos', { resolvido_por: String(pessoa.usuario_id), resolvido_de: de, resolvido_ate: r.fim })
      : this.recorte(`Assumidos por ${pessoa.nome} ${texto}`, 'todos', { assumido_por: String(pessoa.usuario_id), assumido_de: de, assumido_ate: r.fim }));
  }

  /** Linha da categoria ou do setor: os abertos (a linha) ou os resolvidos (o número da coluna) no período. */
  protected abrirLinha(tipo: 'categoria' | 'setor', linha: LinhaRelatorio, qual: 'abertos' | 'resolvidos'): void {
    const r = this.r();
    if (!r || !linha.id) return;
    const filtro: Record<string, string> = tipo === 'categoria' ? { categoria_id: linha.id } : { setor_id: linha.id };
    const datas: Record<string, string> = qual === 'abertos' ? { aberto_de: r.inicio, aberto_ate: r.fim } : { resolvido_de: r.inicio, resolvido_ate: r.fim };
    this.irParaLista(this.recorte(`${qual === 'abertos' ? 'Abertos' : 'Resolvidos'} em ${linha.nome} de ${dataBr(r.inicio)} a ${dataBr(r.fim)}`, 'todos', { ...filtro, ...datas }));
  }

  /** Linha da nota de satisfação: os resolvidos no período que receberam essa nota. */
  protected abrirNota(nota: number, rotulo: string): void {
    const r = this.r();
    if (!r) return;
    this.irParaLista(this.recorte(`Nota "${rotulo}" nos resolvidos de ${dataBr(r.inicio)} a ${dataBr(r.fim)}`, 'todos',
      { nota: String(nota), resolvido_de: r.inicio, resolvido_ate: r.fim }));
  }

  protected percentualNota(indice: number): number {
    const notas = this.r()?.notas ?? [];
    const maior = Math.max(...notas, 0);
    return maior ? (notas[indice] / maior) * 100 : 0;
  }

  protected abrirExportacao(): void {
    this.exportacao = { de: this.de, ate: this.ate, setorId: this.setorId, comSolucao: false, formato: 'pdf' };
    this.exportando.set(true);
  }

  protected exportar(): void {
    const x = this.exportacao;
    this.gerando.set(true);
    this.api.exportarRelatorio(x.de, x.ate, x.setorId, x.comSolucao, x.formato).subscribe({
      next: () => { this.gerando.set(false); this.exportando.set(false); },
      error: (e) => { this.gerando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível exportar os chamados'); },
    });
  }

  /** Mediana de solução: menos de 1 hora em minutos ("40 min"); senão em horas ("3,5 h"). */
  protected duracao(horas: number | null): string {
    if (horas === null) return '—';
    return horas < 1 ? `${Math.max(1, Math.round(horas * 60))} min` : `${this.decimal(horas)} h`;
  }

  /** Número com vírgula decimal (pt-BR). */
  protected decimal(valor: number, casasMinimas = 0): string {
    return valor.toLocaleString('pt-BR', { minimumFractionDigits: casasMinimas, maximumFractionDigits: 1 });
  }

  protected pct(valor: number | null): string {
    return valor === null ? '—' : `${valor.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`;
  }

  protected textoPrioridades(r: RelatorioChamados): string {
    return Object.entries(r.por_prioridade).map(([p, n]) => `${ROTULOS_PRIORIDADE[p as keyof typeof ROTULOS_PRIORIDADE]} ${n}`).join(' · ');
  }
}
