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

  protected readonly painel = signal<PainelContratos | null>(null);
  protected exercicio = new Date().getFullYear();
  protected empresaId = '';
  protected contratoId = '';

  protected readonly escala = computed(() => {
    const meses = this.painel()?.execucao.meses ?? [];
    return Math.max(1, ...meses.flatMap((m) => [Number(m.previsto), Number(m.medido), Number(m.pago)]));
  });
  protected readonly alertasAltos = computed(() => this.painel()?.alertas.reduce((t, c) => t + c.riscos.filter((r) => r.gravidade === 'alta').length, 0) ?? 0);
  protected readonly percentualPago = computed(() => {
    const e = this.painel()?.execucao;
    return e && Number(e.total_previsto) ? (Number(e.total_pago) * 100) / Number(e.total_previsto) : 0;
  });

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

  protected carregar(): void {
    this.api.painel({ exercicio: this.exercicio, empresa_id: this.empresaId, contrato_id: this.contratoId }).subscribe({
      next: (p) => this.painel.set(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel'),
    });
  }

  protected altura(valor: string): number {
    return (Number(valor) / this.escala()) * 100;
  }
}
