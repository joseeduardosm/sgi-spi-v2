// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar o painel de contratos (pendências, alertas, execução orçamentária e números).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { GraficoComponent, SerieGrafico } from '../../../shared/componentes/grafico/grafico.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { PainelContratos } from '../compartilhado/contratos.models';

const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

/**
 * Painel de contratos: o que eu preciso fazer (pendências), onde está o risco (alertas),
 * como está a execução orçamentária do exercício e os números da carteira.
 */
@Component({
  selector: 'app-painel',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent, GraficoComponent, ...PIPES_FORMATACAO],
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

  // Séries do gráfico (em milhares de reais) e rótulos dos meses (AAAA-MM-DD → Jan, Fev…)
  protected readonly rotulosMeses = computed(() => (this.painel()?.execucao.meses ?? []).map((m) => MESES[Number(m.competencia.slice(5, 7)) - 1]));
  protected readonly series = computed<SerieGrafico[]>(() => {
    const meses = this.painel()?.execucao.meses ?? [];
    const mil = (v: string) => Number(v) / 1000;
    return [{ nome: 'Previsto', dados: meses.map((m) => mil(m.previsto)), cor: '#c9ced4' }, { nome: 'Medido', dados: meses.map((m) => mil(m.medido)), cor: '#2f5d8a' },
            { nome: 'Pago', dados: meses.map((m) => mil(m.pago)), cor: '#c82331' }];
  });
  // Quantidade de riscos de gravidade alta (destaque no cartão)
  protected readonly alertasAltos = computed(() => this.painel()?.alertas.reduce((t, c) => t + c.riscos.filter((r) => r.gravidade === 'alta').length, 0) ?? 0);
  // Quanto do previsto no exercício já foi pago
  /**
   * Exercícios oferecidos no seletor: lista fixa (não muda ao escolher), do ano do contrato mais antigo
   * da carteira (ou 8 anos atrás) até 2 anos à frente, do mais recente para o mais antigo.
   */
  protected readonly exercicios = computed(() => listaExercicios(this.painel()?.contratos.map((c) => c.rotulo) ?? [], this.exercicio));

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

/** Anos do seletor de exercício; o ano do contrato vem do rótulo "NNN/AAAA · ...". Inclui sempre o escolhido. */
export function listaExercicios(rotulosContratos: string[], escolhido: number): number[] {
  const atual = new Date().getFullYear();
  const anos = rotulosContratos.map((r) => Number(/\d{1,4}\/(\d{4})/.exec(r)?.[1])).filter((a) => a > 1990);
  const inicio = Math.min(atual - 8, escolhido, ...anos);
  const fim = Math.max(atual + 2, escolhido);
  return Array.from({ length: fim - inicio + 1 }, (_, i) => fim - i);
}
