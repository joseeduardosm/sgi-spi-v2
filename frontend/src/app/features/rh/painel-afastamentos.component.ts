/**
 * =============================================================================
 * ARQUIVO: painel-afastamentos.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Painel de férias e licença-prêmio da CGP e dos autorizadores: calendário
 * em faixas (visão mensal ou anual), filtros, alertas de afastamentos
 * simultâneos, férias a vencer e a fila de ciente/aprovação.
 *
 * RESUMO TÉCNICO:
 * Componente standalone (template em painel-afastamentos.component.html).
 * Guarda o painel e a fila de aprovações em signals; computeds montam o eixo
 * do calendário (dias ou meses, com fins de semana e feriados), a posição de
 * hoje e a série do gráfico anual. Métodos calculam a faixa de cada período
 * em % da largura e chamam a API para ciente, aprovar, recusar, exportar e
 * gerar o relatório de saldos.
 *
 * FINALIDADE DE NEGÓCIO:
 * Dá a quem decide os afastamentos a visão do setor no tempo, para evitar
 * que muitas pessoas saiam juntas, e organiza o fluxo em duas etapas: o
 * superior imediato dá o "ciente e de acordo" e o autorizador aprova ou
 * recusa (com justificativa). A CGP vê todos e lança afastamentos.
 *
 * CONTEXTO NO SISTEMA:
 * Rota /rh/painel-afastamentos (rh.routes.ts). Usa RhApiService (painel,
 * aprovacoes, darCiencia, aprovar, recusarAfastamento, exportar,
 * relatorioSaldos), os tipos de rh.models.ts, trilha-afastamento.ts,
 * app-grafico e lancamento-afastamento.component.ts.
 *
 * =============================================================================
 */

import { TrilhaEtapasComponent } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { trilhaAfastamento } from './trilha-afastamento';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { GraficoComponent, SerieGrafico } from '../../shared/componentes/grafico/grafico.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { LancamentoAfastamentoComponent } from './lancamento-afastamento.component';
import { FiltrosPainel, RhApiService } from './rh-api.service';
import { Afastamento, PainelAfastamentos, ROTULOS_STATUS, ROTULOS_TIPO, SIGLAS_TIPO } from './rh.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/** Milissegundos em um dia (24 × 60 × 60 × 1000). */
const DIA_MS = 86_400_000;
/** Abreviações dos meses para o eixo, o combo e o gráfico. */
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

/** Converte "AAAA-MM-DD" em milissegundos à meia-noite UTC (evita deslocamento por fuso). */
function dia(texto: string): number {
  return Date.parse(`${texto}T00:00:00Z`);
}

/** "AAAA-MM-DD" para "DD/MM/AAAA". */
function dataBr(texto: string): string {
  return texto.split('-').reverse().join('/');
}

/**
 * Painel de afastamentos: uma faixa por período ("[F] Nome – Setor"), amarela quando aguarda aprovação e verde
 * quando aprovada; visão mensal (dias) ou anual (meses); filtros por pessoa, setor (com os filhos) e tipo.
 * A CGP vê todos; o autorizador vê os autorizados e a si mesmo.
 */
@Component({
  selector: 'app-painel-afastamentos',
  imports: [TrilhaEtapasComponent, EsqueletoComponent, LinkificarPipe, FormsModule, DatePipe, GraficoComponent, CabecalhoRhComponent, LancamentoAfastamentoComponent],
  templateUrl: './painel-afastamentos.component.html',
  // Esc fecha o detalhe do período e a janela de recusa
  host: { '(document:keydown.escape)': 'detalhe.set(null); recusando.set(null)' },
})
export class PainelAfastamentosComponent implements OnInit {
  protected readonly trilha = trilhaAfastamento;
  // inject() obtém os serviços pela injeção de dependência do Angular.
  private readonly api = inject(RhApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tipos = ROTULOS_TIPO;
  protected readonly siglas = SIGLAS_TIPO;
  protected readonly status = ROTULOS_STATUS;
  protected readonly meses = MESES;
  /** Filtros enviados à API; começam no mês e ano atuais, sem pessoa, setor ou tipo. */
  protected filtros: FiltrosPainel = { visao: 'mensal', ano: new Date().getFullYear(), mes: new Date().getMonth() + 1, pessoa_id: null, setor_id: null, tipo: '' };
  // signal(): estado reativo; computed(): valor derivado que se recalcula quando os signals lidos mudam
  protected readonly painel = signal<PainelAfastamentos | null>(null);
  // Gráfico anual: pessoas distintas afastadas em cada mês (férias × licença-prêmio), a partir dos períodos que o painel já devolve
  protected readonly serieAnual = computed<SerieGrafico[]>(() => {
    const p = this.painel();
    if (!p || p.visao !== 'anual') return [];
    const ano = Number(p.inicio.slice(0, 4));
    const contar = (tipo: string) => MESES.map((_, i) => {
      // Datas ISO montadas à mão (toISOString converteria para UTC e poderia mudar o dia)
      const mm = String(i + 1).padStart(2, '0');
      const ini = `${ano}-${mm}-01`;
      const fim = `${ano}-${mm}-${String(new Date(ano, i + 1, 0).getDate()).padStart(2, '0')}`;
      return new Set(p.periodos.filter((a) => a.tipo === tipo && a.inicio <= fim && a.fim >= ini).map((a) => a.usuario_id)).size;
    });
    return [{ nome: 'Férias', dados: contar('ferias'), cor: '#2f9e6b' }, { nome: 'Licença-prêmio', dados: contar('licenca_premio'), cor: '#2f5d8a' }];
  });
  /** Pedidos que esperam a ação do usuário logado (ciente ou aprovação). */
  protected readonly aprovacoes = signal<Afastamento[]>([]);
  protected readonly hoje = new Date().toISOString().slice(0, 10);
  /** Anos do combo: do ano passado até três à frente. */
  protected readonly anos = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 1 + i);

  /** Marcas do eixo: dias do mês (visão mensal) ou meses (visão anual), em % da largura. */
  protected readonly eixo = computed(() => {
    const p = this.painel();
    if (!p) return [];
    // Janela exibida em ms; o fim soma um dia porque o último dia também ocupa espaço
    const inicio = dia(p.inicio);
    const total = dia(p.fim) + DIA_MS - inicio;
    if (p.visao === 'anual') {
      return MESES.map((rotulo, m) => ({ rotulo, posicao: ((Date.UTC(this.filtros.ano, m, 1) - inicio) / total) * 100, fimDeSemana: false, feriado: null as string | null, marca: true, mes: true }));
    }
    // Feriados e pontos facultativos da janela (marcados como os fins de semana, com a descrição no título)
    const feriados = new Map(p.feriados.map((f) => [f.data, f]));
    const dias = Math.round(total / DIA_MS);
    return Array.from({ length: dias }, (_, i) => {
      const d = new Date(inicio + i * DIA_MS);
      const feriado = feriados.get(d.toISOString().slice(0, 10));
      // Linha forte na segunda-feira (início da semana) e no dia 1; as demais ficam só na grade suave do trilho
      return { rotulo: String(d.getUTCDate()), posicao: (i / dias) * 100, fimDeSemana: d.getUTCDay() === 0 || d.getUTCDay() === 6, feriado: feriado?.descricao ?? null,
        marca: d.getUTCDay() === 1 || d.getUTCDate() === 1, mes: d.getUTCDate() === 1 };
    });
  });

  /** Posição (%) de hoje na janela do gráfico; nulo se hoje está fora dela. */
  protected readonly hojePosicao = computed(() => {
    const p = this.painel();
    if (!p) return null;
    const inicio = dia(p.inicio);
    const total = dia(p.fim) + DIA_MS - inicio;
    const agora = new Date();
    const hoje = Date.UTC(agora.getFullYear(), agora.getMonth(), agora.getDate());
    return hoje >= inicio && hoje < inicio + total ? ((hoje - inicio) / total) * 100 : null;
  });

  /** Carrega o painel e a fila de aprovações ao abrir a tela. */
  ngOnInit(): void {
    this.carregar();
  }

  /** Busca o painel com os filtros atuais e a fila de aprovações (falha na fila é ignorada). */
  protected carregar(): void {
    this.api.painel(this.filtros).subscribe({
      next: (p) => this.painel.set(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel'),
    });
    this.api.aprovacoes().subscribe({ next: (a) => this.aprovacoes.set(a), error: () => undefined });
  }

  /** Posição e largura (%) do período dentro da janela exibida. */
  protected barra(a: Afastamento): { esquerda: number; largura: number } {
    const p = this.painel()!;
    const inicio = dia(p.inicio);
    const total = dia(p.fim) + DIA_MS - inicio;
    // Recorta o período à janela (pode começar antes ou terminar depois) e garante largura mínima visível
    const de = Math.max(dia(a.inicio), inicio);
    const ate = Math.min(dia(a.fim) + DIA_MS, dia(p.fim) + DIA_MS);
    return { esquerda: ((de - inicio) / total) * 100, largura: Math.max(((ate - de) / total) * 100, 0.6) };
  }

  /** Atalho para o template formatar AAAA-MM-DD como DD/MM/AAAA. */
  protected data(texto: string): string {
    return dataBr(texto);
  }

  /** Abre a janela de lançamento de afastamento pela CGP. */
  protected readonly lancando = signal(false);

  /** CGP: relatório de saldos de férias e LP de todos os servidores. */
  protected saldos(formato: 'pdf' | 'xlsx'): void {
    this.dialogos.executar(this.api.relatorioSaldos(formato), 'Gerando o relatório de saldos…').subscribe({
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório'),
    });
  }

  /** Exporta os períodos com os filtros atuais em PDF ou Excel (download feito pelo serviço). */
  protected exportar(formato: 'pdf' | 'xlsx'): void {
    this.dialogos.executar(this.api.exportar(this.filtros, formato), 'Gerando o arquivo…').subscribe({
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível exportar'),
    });
  }

  /** Etapa 1: o superior imediato dá o ciente e de acordo (não aprova); o pedido segue para o aprovador. */
  protected async darCiencia(a: Afastamento): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Ciente e de acordo?',
      mensagem: `${ROTULOS_TIPO[a.tipo]} de ${a.nome} (${a.setor}), de ${dataBr(a.inicio)} a ${dataBr(a.fim)} (${a.dias} dias). Isso não aprova o pedido: ele segue para a aprovação.`,
      rotuloConfirmar: 'Ciente e de acordo',
    });
    if (!ok) return;
    this.dialogos.executar(this.api.darCiencia(a.id), 'Registrando…').subscribe({
      next: () => this.carregar(),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível registrar o ciente e de acordo'),
    });
  }

  /** Ciente a partir do detalhe do período: a própria janela já serve de confirmação. */
  protected darCienciaDoDetalhe(a: Afastamento): void {
    this.dialogos.executar(this.api.darCiencia(a.id), 'Registrando…').subscribe({
      next: () => {
        this.detalhe.set(null);
        this.carregar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível registrar o ciente e de acordo'),
    });
  }

  /** Etapa 2: o autorizador aprova o pedido, após confirmação (o servidor recebe e-mail pelo backend). */
  protected async aprovar(a: Afastamento): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Aprovar pedido?',
      mensagem: `${ROTULOS_TIPO[a.tipo]} de ${a.nome} (${a.setor}), de ${dataBr(a.inicio)} a ${dataBr(a.fim)} (${a.dias} dias).`,
      rotuloConfirmar: 'Aprovar',
    });
    if (!ok) return;
    this.dialogos.executar(this.api.aprovar(a.id), 'Aprovando…').subscribe({
      next: () => this.carregar(),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível aprovar'),
    });
  }

  // Detalhe do período clicado no gráfico
  protected readonly detalhe = signal<Afastamento | null>(null);

  /** Aprovar a partir do detalhe: a própria janela já é a confirmação. */
  protected aprovarDoDetalhe(a: Afastamento): void {
    this.dialogos.executar(this.api.aprovar(a.id), 'Aprovando…').subscribe({
      next: () => {
        this.detalhe.set(null);
        this.carregar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível aprovar'),
    });
  }

  // Recusa: janela com a justificativa (obrigatória)
  protected readonly recusando = signal<Afastamento | null>(null);
  protected justificativa = '';

  /** Recusa o pedido em análise com a justificativa digitada (obrigatória) e recarrega. */
  protected recusar(): void {
    const a = this.recusando();
    if (!a || !this.justificativa.trim()) return;
    this.dialogos.executar(this.api.recusarAfastamento(a.id, this.justificativa.trim()), 'Recusando…').subscribe({
      next: () => {
        this.recusando.set(null);
        this.justificativa = '';
        this.carregar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível recusar'),
    });
  }
}
