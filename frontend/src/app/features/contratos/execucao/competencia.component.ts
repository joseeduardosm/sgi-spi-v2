import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { DetalheCompetencia, Etapa } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ROTULOS_ETAPA, ROTULOS_SITUACAO_COMPETENCIA } from '../compartilhado/rotulos';
import { EtapaAvaliacaoComponent } from './etapa-avaliacao.component';
import { EtapaCadinComponent } from './etapa-cadin.component';
import { EtapaFinaisComponent } from './etapa-finais.component';
import { EtapaMedicaoComponent } from './etapa-medicao.component';
import { EtapaNotaFiscalComponent } from './etapa-nota-fiscal.component';

/** Tela 5: execução de uma competência (etapas 1 a 7). */
@Component({
  selector: 'app-competencia',
  imports: [
    FormsModule, RouterLink, CabecalhoModuloComponent, EtapaMedicaoComponent, EtapaAvaliacaoComponent, EtapaNotaFiscalComponent,
    EtapaCadinComponent, EtapaFinaisComponent, ...PIPES_FORMATACAO,
  ],
  templateUrl: './competencia.component.html',
  host: { '(document:keydown.escape)': 'reabrindo.set(false)' },
})
export class CompetenciaComponent implements OnInit {
  readonly id = input.required<string>();
  readonly competencia = input.required<string>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly detalhe = signal<DetalheCompetencia | null>(null);
  protected readonly selecionada = signal<Etapa>('medicao');
  protected readonly rotulos = ROTULOS_ETAPA;
  protected readonly situacoes = ROTULOS_SITUACAO_COMPETENCIA;
  protected readonly etapasVisiveis = computed(() => (this.detalhe()?.etapas ?? []).filter((e) => e !== 'concluida'));
  protected readonly reabrindo = signal(false);
  protected etapaReabrir: Etapa | '' = '';
  protected justificativa = '';

  ngOnInit(): void {
    this.api.porIdentificador(this.id(), this.competencia()).subscribe({
      next: (d) => this.aplicar(d, true),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a competência'),
    });
  }

  protected aplicar(detalhe: DetalheCompetencia, reposicionar = false): void {
    const anterior = this.detalhe()?.etapa_atual;
    this.detalhe.set(detalhe);
    // Ao avançar de etapa, a tela acompanha a nova etapa aberta
    if (reposicionar || anterior !== detalhe.etapa_atual) {
      this.selecionada.set(detalhe.etapa_atual === 'concluida' ? 'ordem_bancaria' : detalhe.etapa_atual);
    }
  }

  protected indice(etapa: Etapa): number {
    return this.detalhe()?.etapas.indexOf(etapa) ?? -1;
  }

  protected concluida(etapa: Etapa): boolean {
    return this.indice(etapa) < this.indice(this.detalhe()!.etapa_atual);
  }

  protected bloqueada(etapa: Etapa): boolean {
    const d = this.detalhe()!;
    return !d.liberada || this.indice(etapa) > this.indice(d.etapa_atual);
  }

  /** A etapa selecionada aceita gravação (é a etapa aberta e o usuário pode editar). */
  protected editavel(etapa: Etapa): boolean {
    const d = this.detalhe()!;
    return d.pode_editar && d.liberada && d.etapa_atual === etapa;
  }

  protected etapasAnteriores(): Etapa[] {
    const d = this.detalhe();
    return d ? d.etapas.filter((e) => this.indice(e) < this.indice(d.etapa_atual)) : [];
  }

  protected reabrir(): void {
    const d = this.detalhe();
    if (!d || !this.etapaReabrir) return;
    this.api.reabrir(d.contrato_id, d.id, this.etapaReabrir, this.justificativa.trim()).subscribe({
      next: (novo) => {
        this.reabrindo.set(false);
        this.justificativa = '';
        this.aplicar(novo, true);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível reabrir a etapa'),
    });
  }
}
