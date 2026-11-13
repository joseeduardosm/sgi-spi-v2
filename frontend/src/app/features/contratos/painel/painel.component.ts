/**
 * =============================================================================
 * ARQUIVO: painel.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Controla o painel de contratos: pendências do usuário, alertas de risco,
 * execução orçamentária do exercício (previsto, medido e pago) e os números
 * gerais da carteira.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template em painel.component.html. Lê exercício,
 * empresa e contrato da query string, chama ContratosApiService.painel e
 * transforma a execução mensal em séries do GraficoComponent (pago acima do
 * previsto vira uma barra vermelha empilhada). Exporta listaExercicios, usada
 * também pela tela de alertas de risco.
 *
 * FINALIDADE DE NEGÓCIO:
 * É a página de entrada da gestão de contratos: mostra ao servidor o que
 * precisa da ação dele, onde estão os riscos e como o dinheiro do exercício
 * está sendo usado, apoiando o acompanhamento orçamentário da SPI.
 *
 * CONTEXTO NO SISTEMA:
 * Rota /contratos/painel. Usa ContratosApiService, PainelContratos
 * (contratos.models), GraficoComponent, OrcamentoExecutivoComponent e os
 * pipes de formatação. Leva às telas minhas-pendencias e alertas-de-risco.
 *
 * =============================================================================
 */

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { GraficoComponent, SerieGrafico } from '../../../shared/componentes/grafico/grafico.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { OrcamentoExecutivoComponent } from '../compartilhado/orcamento-executivo.component';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { PainelContratos } from '../compartilhado/contratos.models';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

/**
 * Painel de contratos: o que eu preciso fazer (pendências), onde está o risco (alertas),
 * como está a execução orçamentária do exercício e os números da carteira.
 */
@Component({
  selector: 'app-painel',
  imports: [EsqueletoComponent, FormsModule, RouterLink, CabecalhoModuloComponent, GraficoComponent, OrcamentoExecutivoComponent, ...PIPES_FORMATACAO],
  templateUrl: './painel.component.html',
})
export class PainelComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);

  // Dados do painel e os filtros do topo
  protected readonly painel = signal<PainelContratos | null>(null);
  protected exercicio = new Date().getFullYear();
  protected empresaId = '';
  protected contratoId = '';

  // Séries do gráfico (em milhares de reais) e rótulos dos meses (AAAA-MM-DD → Jan, Fev…).
  // Os valores chegam da API como texto decimal (ex.: "1234.56") e são convertidos com Number.
  // Previsto = previsão mensal; medido = medições concluídas; pago = Ordens Bancárias (OB) pagas.
  protected readonly rotulosMeses = computed(() => (this.painel()?.execucao.meses ?? []).map((m) => MESES[Number(m.competencia.slice(5, 7)) - 1]));
  protected readonly series = computed<SerieGrafico[]>(() => {
    const meses = this.painel()?.execucao.meses ?? [];
    const mil = (v: string) => Number(v) / 1000;
    // Pago em verde até o previsto; o que passa do previsto vira uma sobrebarra vermelha em cima do pago (mesma pilha)
    const ate = meses.map((m) => mil(String(Math.min(Number(m.pago), Number(m.previsto) || Number(m.pago)))));
    const excedente = meses.map((m) => mil(String(Math.max(Number(m.pago) - Number(m.previsto), 0))));
    return [{ nome: 'Previsto', dados: meses.map((m) => mil(m.previsto)), cor: '#c9ced4', pilha: 'previsto' },
            { nome: 'Medido', dados: meses.map((m) => mil(m.medido)), cor: '#2f5d8a', pilha: 'medido' },
            { nome: 'Pago', dados: ate, cor: '#2f9e6b', pilha: 'pago' },
            ...(excedente.some((v) => v > 0) ? [{ nome: 'Pago acima do previsto', dados: excedente, cor: '#c82331', pilha: 'pago' }] : [])];
  });
  // Quantidade de riscos de gravidade alta (destaque no cartão)
  protected readonly alertasAltos = computed(() => this.painel()?.alertas.reduce((t, c) => t + c.riscos.filter((r) => r.gravidade === 'alta').length, 0) ?? 0);
  /**
   * Exercícios oferecidos no seletor: lista fixa (não muda ao escolher), do ano mais antigo entre o
   * contrato mais antigo da carteira e 8 anos atrás até 2 anos à frente, do mais recente para o mais antigo.
   * Exercício é o ano orçamentário (de janeiro a dezembro).
   */
  protected readonly exercicios = computed(() => listaExercicios(this.painel()?.contratos.map((c) => c.rotulo) ?? [], this.exercicio));

  // Quanto do previsto no exercício já foi pago, em % (0 quando não há previsto, para não dividir por zero)
  protected readonly percentualPago = computed(() => {
    const e = this.painel()?.execucao;
    return e && Number(e.total_previsto) ? (Number(e.total_pago) * 100) / Number(e.total_previsto) : 0;
  });

  /** Lê os filtros da URL (permite voltar das telas dedicadas com a mesma seleção) e carrega. */
  ngOnInit(): void {
    const parametros = this.rota.snapshot.queryParamMap;
    this.exercicio = Number(parametros.get('exercicio')) || this.exercicio;
    this.empresaId = parametros.get('empresa_id') ?? '';
    this.contratoId = parametros.get('contrato_id') ?? '';
    this.carregar();
  }

  /** Filtros atuais, repassados à tela de alertas (a lista de pendências não usa filtros). */
  protected filtrosUrl(): Record<string, string | number> {
    const filtros: Record<string, string | number> = { exercicio: this.exercicio };
    if (this.empresaId) filtros['empresa_id'] = this.empresaId;
    if (this.contratoId) filtros['contrato_id'] = this.contratoId;
    return filtros;
  }

  /** Busca o painel na API com os filtros atuais. */
  protected carregar(): void {
    this.api.painel({ exercicio: this.exercicio, empresa_id: this.empresaId, contrato_id: this.contratoId }).subscribe({
      next: (p) => this.painel.set(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel'),
    });
  }
}

/**
 * Anos do seletor de exercício; o ano do contrato vem do rótulo "NNN/AAAA · ...". Inclui sempre o escolhido.
 * Exportada porque a tela de alertas de risco usa a mesma lista.
 * @param rotulosContratos rótulos dos contratos da carteira (o ano é lido pela expressão regular).
 * @param escolhido exercício selecionado no momento (entra mesmo se estiver fora da faixa).
 * @returns anos em ordem decrescente, de (ano atual + 2, ou o escolhido) até o mais antigo.
 */
export function listaExercicios(rotulosContratos: string[], escolhido: number): number[] {
  const atual = new Date().getFullYear();
  const anos = rotulosContratos.map((r) => Number(/\d{1,4}\/(\d{4})/.exec(r)?.[1])).filter((a) => a > 1990);
  const inicio = Math.min(atual - 8, escolhido, ...anos);
  const fim = Math.max(atual + 2, escolhido);
  return Array.from({ length: fim - inicio + 1 }, (_, i) => fim - i);
}
