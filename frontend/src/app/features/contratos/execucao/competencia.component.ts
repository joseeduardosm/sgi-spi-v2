// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de execução de uma competência: barra de etapas, etapa exibida e reabertura.

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
import { EtapaRetencaoComponent } from './etapa-retencao.component';

/** Tela 5: execução de uma competência (etapas 1 a 7). */
@Component({
  selector: 'app-competencia',
  imports: [
    FormsModule, RouterLink, CabecalhoModuloComponent, EtapaMedicaoComponent, EtapaAvaliacaoComponent, EtapaNotaFiscalComponent,
    EtapaCadinComponent, EtapaFinaisComponent, EtapaRetencaoComponent, ...PIPES_FORMATACAO,
  ],
  templateUrl: './competencia.component.html',
  // Esc fecha a janela de reabertura
  host: { '(document:keydown.escape)': 'reabrindo.set(false)' },
})
export class CompetenciaComponent implements OnInit {
  // Parâmetros da URL /contratos/:id/execucao/:competencia (id do contrato e identificador, ex.: 2026-03)
  readonly id = input.required<string>();
  readonly competencia = input.required<string>();
  /** `?etapa=` do link dos e-mails: abre direto nessa etapa (se já liberada). */
  readonly etapa = input<string | undefined>(undefined);

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);

  // Competência carregada e a etapa mostrada na tela (pode ser uma já concluída, só para consulta)
  protected readonly detalhe = signal<DetalheCompetencia | null>(null);
  protected readonly selecionada = signal<Etapa>('medicao');
  protected readonly rotulos = ROTULOS_ETAPA;
  protected readonly situacoes = ROTULOS_SITUACAO_COMPETENCIA;
  // Etapas mostradas na barra (sem "concluída")
  protected readonly etapasVisiveis = computed(() => (this.detalhe()?.etapas ?? []).filter((e) => e !== 'concluida'));
  // Janela de reabertura: etapa escolhida e justificativa
  protected readonly reabrindo = signal(false);
  protected etapaReabrir: Etapa | '' = '';
  protected justificativa = '';

  /** Carrega a competência pelo identificador da URL. */
  ngOnInit(): void {
    this.api.porIdentificador(this.id(), this.competencia()).subscribe({
      next: (d) => this.aplicar(d, true),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a competência'),
    });
  }

  /** Recebe a competência atualizada (de qualquer etapa) e decide qual etapa exibir. */
  protected aplicar(detalhe: DetalheCompetencia, reposicionar = false): void {
    const anterior = this.detalhe()?.etapa_atual;
    // A etapa em tela acabou de ser concluída (ex.: CADIN feito enquanto a retenção segue aberta)?
    const concluiuAEmTela = !!this.detalhe()?.etapas_abertas.includes(this.selecionada()) && !detalhe.etapas_abertas.includes(this.selecionada());
    this.detalhe.set(detalhe);
    // Ao avançar de etapa, a tela acompanha a próxima etapa aberta
    if (reposicionar || anterior !== detalhe.etapa_atual || concluiuAEmTela) {
      const proxima = detalhe.etapas_abertas.find((e) => e !== 'retencao' || detalhe.pode_conferir_retencao) ?? detalhe.etapas_abertas[0];
      this.selecionada.set(detalhe.etapa_atual === 'concluida' ? 'ordem_bancaria' : proxima ?? detalhe.etapa_atual);
      // Link direto (e-mails): abre a etapa pedida, se ela existe e não está bloqueada
      const pedida = this.etapa() as Etapa | undefined;
      if (reposicionar && pedida && detalhe.etapas.includes(pedida) && !this.bloqueada(pedida)) this.selecionada.set(pedida);
    }
  }

  /** Posição da etapa na sequência desta competência. */
  protected indice(etapa: Etapa): number {
    return this.detalhe()?.etapas.indexOf(etapa) ?? -1;
  }

  /** A etapa já foi concluída (retenção, CADIN e checklist correm em paralelo e concluem em qualquer ordem). */
  protected concluida(etapa: Etapa): boolean {
    return this.detalhe()!.etapas_concluidas.includes(etapa);
  }

  /** A etapa está aberta agora (pode haver mais de uma: retenção, CADIN e checklist). */
  protected aberta(etapa: Etapa): boolean {
    return this.detalhe()!.etapas_abertas.includes(etapa);
  }

  /** A etapa ainda não pode ser aberta (período não terminou ou etapa futura). */
  protected bloqueada(etapa: Etapa): boolean {
    const d = this.detalhe()!;
    return !d.liberada || (!this.concluida(etapa) && !this.aberta(etapa));
  }

  /** A etapa selecionada aceita gravação (é a etapa aberta e o usuário pode editar). */
  protected editavel(etapa: Etapa): boolean {
    const d = this.detalhe()!;
    // A retenção de tributos também pode ser feita pelo Financeiro (sem poder editar o contrato)
    const pode = etapa === 'retencao' ? d.pode_conferir_retencao : d.pode_editar;
    return pode && d.liberada && this.aberta(etapa);
  }

  /** Etapas anteriores à atual, oferecidas na reabertura. */
  protected etapasAnteriores(): Etapa[] {
    const d = this.detalhe();
    return d ? d.etapas.filter((e) => this.indice(e) < this.indice(d.etapa_atual)) : [];
  }

  /** Reabre a competência na etapa escolhida, com a justificativa. */
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
