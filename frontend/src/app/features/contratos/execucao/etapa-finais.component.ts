// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar as etapas 5 (checklist mensal), 6 (documento consolidado) e 7 (Ordem Bancária).

import { DatePipe } from '@angular/common';
import { Component, inject, input, output } from '@angular/core';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, DocumentoMensal, Etapa } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ROTULOS_ETAPA } from '../compartilhado/rotulos';

/** Etapas 5 (checklist mensal), 6 (documento consolidado) e 7 (Ordem Bancária). */
@Component({
  selector: 'app-etapa-finais',
  imports: [DatePipe, EnvioPdfComponent, ...PIPES_FORMATACAO],
  template: `
    @let d = detalhe();
    @switch (etapa()) {
      @case ('checklist') {
        <section class="cartao-dados" aria-labelledby="titulo-checklist-mensal">
          <header>
            <div><h2 id="titulo-checklist-mensal">6. Documentos mensais do checklist</h2>
              <small>Os obrigatórios precisam ser anexados; os opcionais podem ficar sem anexo. Com todos anexados, a etapa conclui sozinha.</small></div>
            @if (editavel()) {
              <button type="button" class="acao-primaria" [disabled]="obrigatoriosPendentes(d) > 0" (click)="concluirChecklist()"
                      [title]="obrigatoriosPendentes(d) ? 'Anexe os documentos obrigatórios' : ''">Concluir checklist</button>
            }
          </header>
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <thead><tr><th>Nº</th><th>Documento</th><th>Tipo</th><th>Situação</th><th>Arquivo</th></tr></thead>
              <tbody>
                @for (doc of d.documentos; track doc.id) {
                  <tr>
                    <td>{{ doc.ordem }}</td>
                    <td><strong>{{ doc.nome }}</strong>@if (doc.observacao) { <small>{{ doc.observacao }}</small> }</td>
                    <td>{{ doc.obrigatorio ? 'Obrigatório' : 'Opcional' }}</td>
                    <td><span class="selo-situacao" [class.pendente]="!doc.arquivo" [class.vermelho]="!doc.arquivo && doc.obrigatorio">{{ doc.arquivo ? 'Anexado' : doc.obrigatorio ? 'Pendente' : 'Não anexado' }}</span></td>
                    <td>
                      @if (doc.arquivo) { <button type="button" class="link-arquivo" (click)="baixar(doc.arquivo.anexo_id)">Baixar</button> }
                      @if (editavel()) { <app-envio-pdf [rotulo]="doc.arquivo ? 'Substituir' : 'Selecionar documento PDF'" (selecionado)="enviarDocumento(doc, $event)" /> }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </section>
      }
      @case ('consolidado') {
        <section class="cartao-dados" aria-labelledby="titulo-consolidado">
          <header><h2 id="titulo-consolidado">7. Documento consolidado</h2></header>
          <div class="corpo">
            <p class="dica-formulario" style="margin: 0 0 12px">O sistema reúne medição, notas fiscais, retenção de tributos, avaliação assinada, histórico do CADIN, checklist e resumo executivo em um único PDF.</p>
            @if (d.etapa_atual !== 'consolidado' && d.etapa_atual !== 'ordem_bancaria' && d.etapa_atual !== 'concluida') {
              <p class="aviso-bloco">Liberado quando todas as etapas anteriores estiverem concluídas.
                @if (d.etapas_abertas.length) { Falta concluir: <b>{{ faltando(d) }}</b>. }
              </p>
            }
            <div class="acoes-cartao esquerda">
              @if (d.pode_editar && (d.etapa_atual === 'consolidado' || d.etapa_atual === 'ordem_bancaria')) {
                <button type="button" class="acao-primaria" (click)="gerarConsolidado()">Gerar e baixar documento unificado</button>
              }
              @if (d.consolidado) { <button type="button" class="acao-secundaria" (click)="baixar(d.consolidado.anexo_id)">Baixar documento consolidado</button> }
            </div>
            @if (d.consolidado) { <p class="dica-formulario">Gerado em {{ d.consolidado.enviado_em | date: 'dd/MM/yyyy HH:mm' }} · {{ d.consolidado.tamanho | tamanho }}</p> }
          </div>
        </section>
      }
      @case ('ordem_bancaria') {
        <section class="cartao-dados" aria-labelledby="titulo-ob">
          <header><h2 id="titulo-ob">8. Ordem Bancária</h2></header>
          <div class="corpo">
            @if (d.ordem_bancaria) {
              <p class="aviso-bloco informativo">Competência concluída em {{ d.concluida_em | date: 'dd/MM/yyyy HH:mm' }}. O valor de {{ d.valor_a_pagar | moeda }} (NF + NF adicional) foi debitado nas NEs.</p>
              <button type="button" class="acao-secundaria" (click)="baixar(d.ordem_bancaria.anexo_id)">Baixar Ordem Bancária</button>
            } @else {
              <p class="dica-formulario" style="margin: 0 0 12px">Ao anexar a OB, {{ d.valor_a_pagar | moeda }} (NF + NF adicional, brutos) será debitado nas NEs {{ d.notas_selecionadas.map(n => n.numero).join(', ') }}, nessa ordem, e a competência será concluída.</p>
              @if (editavel()) {
                <div class="acoes-cartao esquerda">
                  <app-envio-pdf rotulo="Selecionar OB em PDF" (selecionado)="ob = $event" />
                  <button type="button" class="acao-primaria" [disabled]="!ob" (click)="enviarOb()">Anexar OB e concluir</button>
                </div>
              }
            }
          </div>
        </section>
      }
    }
  `,
})
export class EtapaFinaisComponent {
  readonly detalhe = input.required<DetalheCompetencia>();
  // Etapa a exibir (a tela da competência escolhe entre as três)
  readonly etapa = input.required<Etapa>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  // PDF da OB escolhido
  protected ob: File | null = null;

  /** Anexa o PDF de um documento do checklist. */
  protected enviarDocumento(documento: DocumentoMensal, arquivo: File | null): void {
    if (!arquivo) return;
    const d = this.detalhe();
    this.dialogos.executar(this.api.documentoMensal(d.contrato_id, d.id, documento.id, arquivo), 'Enviando o documento…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar o documento'),
    });
  }

  /** Quantos documentos obrigatórios ainda estão sem anexo (desabilita "Concluir checklist"). */
  protected obrigatoriosPendentes(d: DetalheCompetencia): number {
    return d.documentos.filter((doc) => doc.obrigatorio && !doc.arquivo).length;
  }

  /** Conclui o checklist; se faltarem opcionais, pede confirmação. */
  protected async concluirChecklist(): Promise<void> {
    const d = this.detalhe();
    const semAnexo = d.documentos.filter((doc) => !doc.arquivo).length;
    if (semAnexo) {
      const ok = await this.dialogos.confirmar({
        titulo: 'Concluir o checklist?',
        mensagem: `${semAnexo} documento(s) opcional(is) ficará(ão) sem anexo. Depois de concluída, a etapa só pode ser reaberta pelo SuperRoot ou pelo gestor.`,
        rotuloConfirmar: 'Concluir checklist',
      });
      if (!ok) return;
    }
    this.api.concluirChecklist(d.contrato_id, d.id).subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível concluir o checklist'),
    });
  }

  /** Gera o consolidado e já baixa o arquivo. */
  protected gerarConsolidado(): void {
    const d = this.detalhe();
    this.dialogos.executar(this.api.consolidado(d.contrato_id, d.id), 'Gerando o documento consolidado…').subscribe({
      next: (novo) => {
        this.atualizado.emit(novo);
        if (novo.consolidado) this.baixar(novo.consolidado.anexo_id);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o documento consolidado'),
    });
  }

  /** Anexa a OB depois de confirmar: debita as NEs e conclui a competência. */
  protected async enviarOb(): Promise<void> {
    if (!this.ob) return;
    const d = this.detalhe();
    const ok = await this.dialogos.confirmar({
      titulo: 'Anexar a OB e concluir a competência?',
      mensagem: `O valor será debitado nas Notas de Empenho e a competência ficará concluída. Só o SuperRoot ou o gestor do contrato podem reabrir (com estorno).`,
      rotuloConfirmar: 'Anexar OB e concluir',
      segundos: 5,
    });
    if (!ok) return;
    this.dialogos.executar(this.api.ordemBancaria(d.contrato_id, d.id, this.ob), 'Registrando a Ordem Bancária…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar a OB'),
    });
  }

  /** Baixa um PDF da competência. */
  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Etapas ainda abertas (ex.: retenção, CADIN, checklist) antes do consolidado. */
  protected faltando(d: DetalheCompetencia): string {
    return d.etapas_abertas.map((e) => ROTULOS_ETAPA[e]).join(', ');
  }
}
