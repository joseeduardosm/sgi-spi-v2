// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de detalhe do contrato e a troca entre as suas abas.

import { BotaoCopiarComponent } from '../../../shared/componentes/botao-copiar/botao-copiar.component';
import { AvatarComponent } from '../../diretorio/avatar.component';
import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { AtalhosService } from '../../../core/navegacao/atalhos.service';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { hojeIso } from '../../../shared/utilitarios/formatadores';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { AlteracoesApiService } from '../compartilhado/alteracoes-api.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { CHAVE_CONTEXTO_CARTEIRA, ContextoCarteira, ContratosApiService } from '../compartilhado/contratos-api.service';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ParametrosContratosService } from '../compartilhado/parametros-contratos.service';
import { AlteracaoCampo, DetalheContrato, NotaEmpenho, OrcamentoExecutivo, Prorrogacao, VizinhosContrato } from '../compartilhado/contratos.models';
import { HistoricoCampoComponent } from '../compartilhado/historico-campo.component';
import { LinhaDoTempoComponent } from '../compartilhado/linha-do-tempo.component';
import { MESES, PAPEIS, PERIODICIDADES, ROTULOS_CAMPO, ROTULOS_SITUACAO, ROTULOS_TIPO_ITEM } from '../compartilhado/rotulos';
import { AbaChecklistsComponent } from './aba-checklists.component';
import { AbaCorrecoesComponent } from './aba-correcoes.component';
import { AbaDocumentosComponent } from './aba-documentos.component';
import { PortariasEquipeComponent } from './portarias-equipe.component';
import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { AbaDiarioComponent } from './aba-diario.component';
import { AbaExecucaoComponent } from './aba-execucao.component';
import { AbaFormulariosComponent } from './aba-formularios.component';
import { AbaNotasComponent } from './aba-notas.component';
import { AbaPrevisaoComponent } from './aba-previsao.component';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
/** Abas da tela de detalhe. */
type Aba = 'principal' | 'itens' | 'previsao' | 'processos' | 'equipe' | 'documentos' | 'checklists' | 'formularios' | 'correcoes' | 'notas' | 'diario' | 'execucao';

/** Tela 3: detalhe do contrato com abas. */
@Component({
  selector: 'app-detalhe-contrato',
  imports: [EsqueletoComponent, 
    RouterLink, AvatarComponent, BotaoCopiarComponent, CabecalhoModuloComponent, HistoricoCampoComponent, LinhaDoTempoComponent, AbaPrevisaoComponent, AbaDocumentosComponent,
    AbaChecklistsComponent, AbaCorrecoesComponent, AbaFormulariosComponent, AbaNotasComponent, AbaDiarioComponent, AbaExecucaoComponent, PortariasEquipeComponent, ...PIPES_FORMATACAO,
  ],
  templateUrl: './detalhe-contrato.component.html',
})
export class DetalheContratoComponent {
  // Id do contrato, vindo da URL (/contratos/:id) graças ao withComponentInputBinding
  readonly id = input.required<string>();

  private readonly api = inject(ContratosApiService);
  private readonly parametros = inject(ParametrosContratosService);
  private readonly alteracoes = inject(AlteracoesApiService);
  private readonly execucao = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly atalhos = inject(AtalhosService);
  private readonly autenticacao = inject(AutenticacaoService);
  /** Usuário logado (no diário, os próprios registros ficam à direita). */
  protected readonly usuarioId = computed(() => this.autenticacao.usuario()?.id ?? null);

  // Abas na ordem de exibição
  protected readonly abas: { id: Aba; rotulo: string }[] = [
    { id: 'principal', rotulo: 'Principal' },
    { id: 'itens', rotulo: 'Itens' },
    { id: 'previsao', rotulo: 'Previsão orçamentária' },
    { id: 'processos', rotulo: 'Processos' },
    { id: 'equipe', rotulo: 'Equipe' },
    { id: 'documentos', rotulo: 'Documentos Importantes' },
    { id: 'checklists', rotulo: 'Checklists' },
    { id: 'formularios', rotulo: 'Formulários de avaliação' },
    { id: 'correcoes', rotulo: 'Correções de itens' },
    { id: 'notas', rotulo: 'Notas de Empenho' },
    { id: 'diario', rotulo: 'Diário de bordo' },
    { id: 'execucao', rotulo: 'Execução' },
  ];
  // Estado: aba aberta, contrato, histórico de campos e prorrogações
  protected readonly aba = signal<Aba>('principal');
  protected readonly contrato = signal<DetalheContrato | null>(null);
  protected readonly historico = signal<AlteracaoCampo[]>([]);
  protected readonly prorrogacoes = signal<Prorrogacao[]>([]);
  // Constantes expostas ao template
  protected readonly hoje = hojeIso();
  protected readonly papeis = PAPEIS;
  protected readonly rotulosSituacao = ROTULOS_SITUACAO;
  protected readonly rotulosTipo = ROTULOS_TIPO_ITEM;
  protected readonly rotulosCampo = ROTULOS_CAMPO;
  protected readonly meses = MESES;

  // Integrante da equipe por papel, para montar a aba Equipe
  protected readonly membro = computed(() => {
    const equipe = this.contrato()?.equipe ?? [];
    return Object.fromEntries(equipe.map((m) => [m.papel, m]));
  });
  protected readonly periodicidade = computed(() => PERIODICIDADES.find((p) => p.valor === this.contrato()?.periodicidade_meses)?.rotulo ?? '');
  /** Notas de Empenho do contrato (para o saldo do exercício na aba Principal). */
  protected readonly notas = signal<NotaEmpenho[]>([]);
  /** Saldo remanescente e decisões de empenho do exercício (cartão executivo). */
  protected readonly orcamento = signal<OrcamentoExecutivo | null>(null);
  /** Prazo do reforço de empenho já passou. */
  protected readonly reforcoVencido = computed(() => {
    const o = this.orcamento();
    return !!o && Number(o.reforco) > 0 && !!o.pedir_reforco_ate && o.pedir_reforco_ate < this.hoje;
  });
  /** " · jan a ago" (meses concluídos que entram no saldo remanescente) ou " · nenhum mês concluído". */
  protected readonly mesesConcluidos = computed(() => {
    const meses = this.orcamento()?.meses_concluidos ?? [];
    const nome = (d: string) => ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'][Number(d.slice(5, 7)) - 1];
    if (!meses.length) return ' · nenhum mês concluído';
    return meses.length === 1 ? ` · ${nome(meses[0].competencia)}` : ` · ${nome(meses[0].competencia)} a ${nome(meses[meses.length - 1].competencia)}`;
  });
  /** Uma linha com a decisão do empenho: reforço (e até quando), sobra para cancelar ou cobertura completa. */
  protected readonly decisaoEmpenho = computed(() => {
    const o = this.orcamento();
    if (!o) return '';
    const moeda = (v: string) => Number(v).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const mes = (d: string | null) => (d ? `${d.slice(5, 7)}/${d.slice(0, 4)}` : '');
    if (Number(o.reforco) > 0) {
      const ate = o.pedir_reforco_ate ? ` até ${o.pedir_reforco_ate.split('-').reverse().join('/')}` : '';
      return `Falta empenhar ${moeda(o.reforco)}${ate}${this.reforcoVencido() ? ' (vencido)' : ''}`;
    }
    if (Number(o.disponivel_cancelar) > 0) return `Empenho cobre até ${mes(o.coberto_ate)} · sobra ${moeda(o.disponivel_cancelar)}`;
    return o.meses_restantes ? `Empenho cobre até ${mes(o.coberto_ate)}` : 'Sem meses a empenhar no exercício';
  });
  /** Exercício considerado no saldo de empenho (o ano atual). */
  protected readonly exercicio = Number(this.hoje.slice(0, 4));
  /** NEs do exercício: o ano vem do número da NE (ex.: `2026NE00007`); sem ele, do ano do cadastro. */
  protected readonly notasDoExercicio = computed(() => this.notas().filter((n) => (/^(\d{4})/.exec(n.numero)?.[1] ?? n.criado_em.slice(0, 4)) === String(this.exercicio)));
  /** Totais do exercício: valor empenhado, consumido, cancelado, comprometido por medições e saldo livre. */
  protected readonly saldoExercicio = computed(() => {
    const soma = (f: (n: NotaEmpenho) => string) => this.notasDoExercicio().reduce((t, n) => t + Number(f(n)), 0);
    const valor = soma((n) => n.valor_original);
    const consumido = soma((n) => n.consumido);
    const cancelado = soma((n) => n.cancelado);
    const comprometido = soma((n) => n.comprometido);
    return { valor, consumido, cancelado, comprometido, livre: valor - consumido - cancelado - comprometido };
  });
  /** Largura (em %) de cada trecho da barra de uma NE, sobre o valor original. */
  protected trechos(n: NotaEmpenho): { consumido: number; cancelado: number; comprometido: number } {
    const v = Number(n.valor_original) || 1;
    const pct = (x: string) => Math.min(100, Math.max(0, (Number(x) / v) * 100));
    return { consumido: pct(n.consumido), cancelado: pct(n.cancelado), comprometido: pct(n.comprometido) };
  }

  /** Dias até o fim da vigência atual (negativo se já terminou). */
  protected readonly diasRestantes = computed(() => {
    const c = this.contrato();
    if (!c) return 0;
    return Math.round((new Date(c.data_fim + 'T00:00:00').getTime() - new Date(this.hoje + 'T00:00:00').getTime()) / 86_400_000);
  });
  protected readonly faixaVigencia = computed<'ok' | 'alerta' | 'perigo'>(() => (this.diasRestantes() < 0 ? 'perigo' : this.diasRestantes() <= this.parametros.valores().dias_vigencia_a_vencer ? 'alerta' : 'ok'));
  protected readonly textoVigencia = computed(() => {
    const d = this.diasRestantes();
    return d < 0 ? `vencida há ${-d} dia(s)` : d === 0 ? 'vence hoje' : `faltam ${d} dia(s)`;
  });
  /** Processos SEI (gestão e execução) e o processo financeiro (SIGEO) para a aba Processos. */
  protected readonly processos = computed(() => {
    const c = this.contrato();
    if (!c) return [];
    return [
      { chave: 'gestao', rotulo: 'Gestão', campoNumero: 'sei_gestao_numero', numero: c.sei_gestao_numero, link: c.sei_gestao_link },
      { chave: 'execucao', rotulo: 'Execução', campoNumero: 'sei_execucao_numero', numero: c.sei_execucao_numero, link: c.sei_execucao_link },
      // Processo financeiro: sem link no SEI; é por ele que a conferência diária acha as OBs pagas no SIGEO
      { chave: 'financeiro', rotulo: 'Financeiro', campoNumero: 'processo_financeiro', numero: c.processo_financeiro, link: '', nota: 'Usado para achar as OBs pagas no SIGEO.' },
    ];
  });
  // Só permite prorrogar quem pode editar e com todos os códigos orçamentários dos itens preenchidos
  protected readonly podeProrrogar = computed(() => {
    const c = this.contrato();
    return !!c?.permissoes.pode_editar && c.itens.every((i) => i.codigo_classe && i.codigo_natureza_despesa && i.codigo_siafisico && i.codigo_catmat_catser);
  });
  protected readonly totais = computed(() => {
    const c = this.contrato();
    return c ? { base: c.base_mensal, global: c.valor_global } : null;
  });

  /** Anterior e próximo contrato na lista que a pessoa estava vendo (carteira); nulo quando abriu o contrato por outro caminho. */
  protected readonly vizinhos = signal<VizinhosContrato | null>(null);

  constructor() {
    this.parametros.carregar();
    // Abre a aba indicada na URL (?aba=...) uma vez
    // Links antigos (?aba=portaria) caem na aba Equipe, onde a portaria passou a ficar
    const pedida = this.rota.snapshot.queryParamMap.get('aba');
    const aba = (pedida === 'portaria' ? 'equipe' : pedida) as Aba | null;
    if (aba && this.abas.some((a) => a.id === aba)) this.aba.set(aba);
    // A cada contrato (inclusive ao navegar ‹ › para outro, pois o Angular reaproveita este componente), recarrega os dados e os vizinhos
    effect(() => {
      this.id();
      untracked(() => {
        this.contrato.set(null);
        this.vizinhos.set(null);
        this.carregar();
        this.carregarVizinhos();
      });
    });
  }

  /** Pede ao servidor o anterior/próximo na mesma lista da carteira (busca, "Meus contratos" e ordenação guardadas ao abrir). */
  private carregarVizinhos(): void {
    let contexto: ContextoCarteira = { busca: '', meus: false, ordenarPor: 'numero', direcao: 'desc' };
    try {
      contexto = { ...contexto, ...JSON.parse(sessionStorage.getItem(CHAVE_CONTEXTO_CARTEIRA) ?? '{}') };
    } catch {
      // sem contexto guardado: vale a ordem padrão da carteira
    }
    this.api.vizinhos(this.id(), contexto).subscribe({ next: (v) => this.vizinhos.set(v.posicao ? v : null), error: () => this.vizinhos.set(null) });
  }

  /** Carrega contrato, histórico e prorrogações em paralelo (`forkJoin` espera as três respostas). */
  /** Baixa o contrato como planilha XLSX já preenchida. */
  protected baixarXlsx(): void {
    this.execucao.baixarContratoXlsx(this.id()).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar a planilha') });
  }

  protected carregar(): void {
    forkJoin({
      contrato: this.api.consultar(this.id()),
      historico: this.api.historico(this.id()),
      prorrogacoes: this.alteracoes.prorrogacoes(this.id()),
      notas: this.api.notas(this.id()).pipe(catchError(() => of([] as NotaEmpenho[]))),
      orcamento: this.api.orcamentoExecutivo(this.id(), this.exercicio).pipe(catchError(() => of(null))),
    }).subscribe({
      next: ({ contrato, historico, prorrogacoes, notas, orcamento }) => {
        this.notas.set(notas);
        this.orcamento.set(orcamento);
        this.contrato.set(contrato);
        // O nome da tela nos recentes e favoritos passa a ser o número do contrato
        this.atalhos.rotularAtual(`Contrato ${contrato.numero}`);
        this.historico.set(historico);
        this.prorrogacoes.set(prorrogacoes);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o contrato'),
    });
  }

  /** Troca de aba e guarda a escolha na URL (recarregar a página mantém a aba). */
  protected escolher(aba: Aba): void {
    this.aba.set(aba);
    void this.roteador.navigate([], { queryParams: { aba }, replaceUrl: true });
  }

  // Traduz o id da empresa no histórico para a razão social
  protected nomeEmpresa = (valor: unknown): string => (valor === this.contrato()?.empresa.id ? this.contrato()!.empresa.razao_social : '');

  /** Pede confirmação e desfaz a última prorrogação. */
  protected async desfazer(prorrogacao: Prorrogacao): Promise<void> {
    const confirmado = await this.dialogos.confirmar({
      titulo: 'Desfazer a última prorrogação?',
      mensagem: `A vigência volta a terminar em ${prorrogacao.fim_anterior.split('-').reverse().join('/')}. O termo aditivo sai dos documentos importantes e a previsão da vigência é removida.`,
      rotuloConfirmar: 'Desfazer prorrogação',
      segundos: 5,
    });
    if (!confirmado) return;
    this.alteracoes.desfazerProrrogacao(this.id(), prorrogacao.id).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Baixa o Termo Aditivo da prorrogação (guardado como documento importante). */
  /** Gera e baixa o relatório da aba Itens (PDF). */
  protected baixarRelatorioItens(): void {
    this.dialogos.executar(this.api.baixarRelatorioItens(this.id()), 'Gerando o relatório dos itens…').subscribe({
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório'),
    });
  }

  protected baixarTermo(prorrogacao: Prorrogacao): void {
    if (prorrogacao.codigo_documento) this.api.baixarDocumento(this.id(), prorrogacao.codigo_documento).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
