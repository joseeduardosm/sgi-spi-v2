// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de execução de uma competência: barra de etapas, etapa exibida e reabertura.

import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

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
/** Quantas vezes (a cada 2,5 s) a tela consulta o resultado do e-mail antes de parar. */
const LIMITE_CONSULTAS_EMAIL = 8;

@Component({
  selector: 'app-competencia',
  imports: [
    FormsModule, RouterLink, CabecalhoModuloComponent, EtapaMedicaoComponent, EtapaAvaliacaoComponent, EtapaNotaFiscalComponent,
    EtapaCadinComponent, EtapaFinaisComponent, EtapaRetencaoComponent, ...PIPES_FORMATACAO,
  ],
  templateUrl: './competencia.component.html',
  // Esc fecha a janela de reabertura
  host: { '(document:keydown.escape)': 'reabrindo.set(false); incluindo.set(false)' },
})
export class CompetenciaComponent implements OnInit {
  // Parâmetros da URL /contratos/:id/execucao/:competencia (id do contrato e identificador, ex.: 2026-03)
  readonly id = input.required<string>();
  readonly competencia = input.required<string>();
  /** `?etapa=` do link dos e-mails: abre direto nessa etapa (se já liberada). */
  readonly etapa = input<string | undefined>(undefined);

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

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
  // Janela "Incluir nova medição" (medição adicional): justificativa e anexo PDF opcional
  protected readonly incluindo = signal(false);
  protected readonly enviandoAdicional = signal(false);
  protected justificativaAdicional = '';
  protected anexoAdicional: File | null = null;

  /** Carrega a competência pelo identificador da URL. */
  ngOnInit(): void {
    this.api.porIdentificador(this.id(), this.competencia()).subscribe({
      next: (d) => this.aplicar(d, true),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a competência'),
    });
  }

  /** Consultas seguidas feitas à espera do resultado do e-mail em segundo plano. */
  private consultasEmail = 0;

  /** Recebe a competência atualizada (de qualquer etapa) e decide qual etapa exibir. */
  protected aplicar(detalhe: DetalheCompetencia, reposicionar = false): void {
    const anterior = this.detalhe()?.etapa_atual;
    // A etapa em tela acabou de ser concluída (ex.: CADIN feito enquanto a retenção segue aberta)?
    const concluiuAEmTela = !!this.detalhe()?.etapas_abertas.includes(this.selecionada()) && !detalhe.etapas_abertas.includes(this.selecionada());
    this.detalhe.set(detalhe);
    // E-mail em segundo plano (medição concluída ou PDF da avaliação gerado) ainda sem resultado: consulta de novo em instantes
    const enviando = (!!detalhe.medicao_concluida_em && detalhe.email_medicao.enviado_em === null)
      || (!!detalhe.avaliacao?.pdf_gerado && detalhe.avaliacao.email.enviado_em === null);
    // Reinicia a contagem quando a pessoa age; sem resultado de e-mail (ex.: e-mail não pedido) a consulta para após algumas tentativas
    if (reposicionar) this.consultasEmail = 0;
    if (enviando && this.consultasEmail++ < LIMITE_CONSULTAS_EMAIL) setTimeout(() => this.api.porIdentificador(this.id(), this.competencia()).subscribe({ next: (d) => this.detalhe() && this.aplicar(d) }), 2500);
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

  /** Zera a competência (todas as etapas, inclusive a medição), depois de um alerta com contagem de 5 segundos. */
  protected async zerar(): Promise<void> {
    const d = this.detalhe();
    if (!d) return;
    const ok = await this.dialogos.confirmar({
      titulo: `Zerar a competência ${d.rotulo}?`,
      mensagem: 'ATENÇÃO: todas as etapas desta competência serão zeradas: a medição (quantidades medidas, ciências e Notas de Empenho escolhidas), a avaliação, a nota fiscal, a retenção, o CADIN, o checklist e o consolidado. Se a competência já foi paga, a ordem bancária será estornada no extrato das Notas de Empenho. Os arquivos ficam guardados no histórico, mas deixam de valer. Esta ação não pode ser desfeita.',
      rotuloConfirmar: 'Zerar competência',
      segundos: 5,
      perigo: true,
    });
    if (!ok) return;
    this.api.zerar(d.contrato_id, d.id).subscribe({
      next: (novo) => this.aplicar(novo, true),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível zerar a competência'),
    });
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

  /** Abre a janela de justificativa da nova medição. */
  protected abrirInclusao(): void {
    this.justificativaAdicional = '';
    this.anexoAdicional = null;
    this.incluindo.set(true);
  }

  protected escolherAnexoAdicional(evento: Event): void {
    this.anexoAdicional = (evento.target as HTMLInputElement).files?.[0] ?? null;
  }

  /** Cria a medição adicional e abre a tela dela. */
  protected incluirMedicao(): void {
    const d = this.detalhe();
    if (!d || !this.justificativaAdicional.trim()) return;
    this.enviandoAdicional.set(true);
    this.api.incluirMedicaoAdicional(d.contrato_id, d.id, this.justificativaAdicional.trim(), this.anexoAdicional).subscribe({
      next: (nova) => {
        this.enviandoAdicional.set(false);
        this.incluindo.set(false);
        void this.roteador.navigate(['/contratos', nova.contrato_id, 'execucao', nova.identificador]);
      },
      error: (e) => {
        this.enviandoAdicional.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível incluir a nova medição');
      },
    });
  }

  /** Exclui a medição adicional (para refazê-la do zero) e volta à lista de execução do contrato. */
  protected async excluirAdicional(): Promise<void> {
    const d = this.detalhe();
    if (!d) return;
    const ok = await this.dialogos.confirmar({
      titulo: `Excluir a ${d.rotulo}?`,
      mensagem: 'A medição adicional será apagada com tudo o que foi preenchido nela (quantidades, ciências, avaliação, nota fiscal, retenção, CADIN e checklist). Depois você pode incluir uma nova medição do zero. Esta ação não pode ser desfeita.',
      rotuloConfirmar: 'Excluir medição adicional',
      segundos: 5,
      perigo: true,
    });
    if (!ok) return;
    this.api.excluirMedicaoAdicional(d.contrato_id, d.id).subscribe({
      next: () => void this.roteador.navigate(['/contratos', d.contrato_id], { queryParams: { aba: 'execucao' } }),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir a medição adicional'),
    });
  }

  /** Abre o anexo da justificativa em outra aba. */
  protected abrirAnexoAdicional(anexoId: string): void {
    const d = this.detalhe();
    if (d) this.api.abrirEmNovaAba(d.contrato_id, d.id, anexoId, (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir o anexo'));
  }
}
