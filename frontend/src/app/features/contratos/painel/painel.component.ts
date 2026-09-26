// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar o painel de contratos (pendências, alertas, execução orçamentária e números).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { PainelContratos } from '../compartilhado/contratos.models';

/**
 * Painel de contratos: o que eu preciso fazer (pendências), onde está o risco (alertas),
 * como está a execução orçamentária do exercício e os números da carteira.
 */
@Component({
  selector: 'app-painel',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent, ...PIPES_FORMATACAO],
  templateUrl: './painel.component.html',
})
export class PainelComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);

  /** Ocorrências mostradas em cada cartão; o restante fica nas telas dedicadas. */
  protected readonly LIMITE = 5;

  // Dados do painel e os filtros do topo
  protected readonly painel = signal<PainelContratos | null>(null);
  protected exercicio = new Date().getFullYear();
  protected empresaId = '';
  protected contratoId = '';

  // Maior valor do gráfico: serve de 100% para a altura das barras
  protected readonly escala = computed(() => {
    const meses = this.painel()?.execucao.meses ?? [];
    return Math.max(1, ...meses.flatMap((m) => [Number(m.previsto), Number(m.medido), Number(m.pago)]));
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

  /** Altura da barra do gráfico, em % da escala. */
  protected altura(valor: string): number {
    return (Number(valor) / this.escala()) * 100;
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
