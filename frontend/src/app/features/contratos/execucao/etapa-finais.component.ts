// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar as etapas 5 (checklist mensal), 6 (documento consolidado) e 7 (Ordem Bancária).

import { DatePipe } from '@angular/common';
import { Component, inject, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, DocumentoMensal, Etapa } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ROTULOS_ETAPA } from '../compartilhado/rotulos';
import { LinkificarPipe } from '../../../shared/utilitarios/linkificar.pipe';

/** Etapas 5 (checklist mensal), 6 (documento consolidado) e 7 (Ordem Bancária). */
@Component({
  selector: 'app-etapa-finais',
  imports: [LinkificarPipe, DatePipe, FormsModule, EnvioPdfComponent, ...PIPES_FORMATACAO],
  template: `
    @let d = detalhe();
    @switch (etapa()) {
      @case ('checklist') {
        <section class="cartao-dados" aria-labelledby="titulo-checklist-mensal">
          <header>
            <div><h2 id="titulo-checklist-mensal">6. Documentos mensais do checklist</h2>
              <small>Os obrigatórios precisam ser anexados; os opcionais podem ficar sem anexo. Com todos anexados, a etapa conclui sozinha.</small></div>
            @if (editavel() && sugestoes(d) > 0) {
              <button type="button" class="acao-secundaria" (click)="trazerTodos()">Trazer os documentos válidos de outros contratos ({{ sugestoes(d) }})</button>
            }
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
                    <td>{{ $index + 1 }}</td>
                    <td><strong>{{ doc.nome }}</strong>@if (doc.observacao) { <small [innerHTML]="doc.observacao | linkificar"></small> }</td>
                    <td>{{ doc.obrigatorio ? 'Obrigatório' : 'Opcional' }}@if (doc.com_validade) { <small>Com validade</small> }</td>
                    <td><span class="selo-situacao" [class.pendente]="!doc.arquivo" [class.vermelho]="!doc.arquivo && doc.obrigatorio">{{ doc.arquivo ? 'Anexado' : doc.obrigatorio ? 'Pendente' : 'Não anexado' }}</span></td>
                    <td>
                      @if (doc.arquivo) { <button type="button" class="link-arquivo" (click)="baixar(doc.arquivo.anexo_id)">Baixar</button> }
                      @if (doc.com_validade && doc.arquivo && doc.validade_ate) {
                        <small [style.color]="vencimento(doc.validade_ate) === 'vencido' ? '#b3261e' : vencimento(doc.validade_ate) === 'perto' ? '#8a6d00' : '#6a7786'">
                          Válido até {{ doc.validade_ate | dataBr }}@if (vencimento(doc.validade_ate) === 'perto') { (vence em até 30 dias) }@if (vencimento(doc.validade_ate) === 'vencido') { (vencido) }
                        </small>
                      }
                      @if (doc.reaproveitado_contrato) {
                        <small class="reaproveitado-contrato">Reaproveitado do contrato {{ doc.reaproveitado_contrato }} (competência {{ doc.reaproveitado_de | date: 'MM/yyyy' }})@if (doc.validade_ate) { · válido até {{ doc.validade_ate | dataBr }} }: confira e conclua</small>
                      } @else if (doc.reaproveitado_de) { <small style="color: #2f6f9f">Reaproveitado da competência de {{ doc.reaproveitado_de | date: 'MM/yyyy' }}: confira e conclua</small> }
                      @if (editavel() && doc.sugestao_outro_contrato; as s) {
                        <div class="sugestao-outro-contrato">
                          <small>Disponível do contrato {{ s.contrato_numero }} (competência {{ s.competencia | date: 'MM/yyyy' }}) · válido até {{ s.validade_ate | dataBr }}</small>
                          <button type="button" class="acao-secundaria acao-pequena" (click)="usarDeOutroContrato(doc, s.origem_id)">Usar este documento</button>
                        </div>
                      }
                      @if (editavel() && doc.com_validade) {
                        <label class="campo-validade">Válido até *
                          <input type="date" [name]="'validade-' + doc.id" [ngModel]="validades[doc.id] ?? doc.validade_ate ?? ''" (ngModelChange)="validades[doc.id] = $event" /></label>
                      }
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
            <p class="dica-formulario" style="margin: 0 0 12px">Um único PDF na ordem de execução: medição, avaliação (quando houver), nota fiscal, retenção de tributos, CADIN, checklist e resumo executivo. Cada documento enviado vem precedido de uma contracapa, e as páginas são numeradas em sequência.</p>
            @if (d.etapa_atual !== 'consolidado' && d.etapa_atual !== 'ordem_bancaria' && d.etapa_atual !== 'concluida') {
              <p class="aviso-bloco">Liberado quando todas as etapas anteriores estiverem concluídas.
                @if (d.etapas_abertas.length) { Falta concluir: <b>{{ faltando(d) }}</b>. }
              </p>
            }
            <div class="acoes-cartao esquerda">
              <!-- 1ª geração: quem pode editar. Gerar novamente (substitui o atual): só o gestor ou o SuperRoot, inclusive após a OB -->
              @if (!d.consolidado && d.pode_editar && (d.etapa_atual === 'consolidado' || d.etapa_atual === 'ordem_bancaria')) {
                <button type="button" class="acao-primaria" (click)="gerarConsolidado()">Gerar e baixar documento unificado</button>
              }
              @if (d.consolidado && d.pode_gerar_consolidado_novamente) {
                <button type="button" class="acao-primaria" (click)="gerarConsolidado(true)">Gerar novamente</button>
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
              <p class="aviso-bloco informativo">Competência concluída em {{ d.concluida_em | date: 'dd/MM/yyyy HH:mm' }}. O valor de {{ d.valor_a_pagar | moeda }} (soma das NFs) foi debitado nas NEs.</p>
              <button type="button" class="acao-secundaria" (click)="baixar(d.ordem_bancaria.anexo_id)">Baixar Ordem Bancária</button>
            } @else {
              <p class="dica-formulario" style="margin: 0 0 12px">Ao anexar a OB, {{ d.valor_a_pagar | moeda }} (soma das NFs, brutos) será debitado nas NEs {{ d.notas_selecionadas.map(n => n.numero).join(', ') }}, nessa ordem, e a competência será concluída.</p>
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
  // Validade digitada para cada documento com validade (por id), antes de escolher o arquivo
  protected validades: Record<string, string> = {};
  // PDF da OB escolhido
  protected ob: File | null = null;

  /** Situação da validade: vencida, a vencer em até 30 dias ou em dia. */
  protected vencimento(validade: string): 'vencido' | 'perto' | 'ok' {
    const dias = (new Date(validade + 'T00:00:00').getTime() - new Date().setHours(0, 0, 0, 0)) / 86_400_000;
    return dias < 0 ? 'vencido' : dias <= 30 ? 'perto' : 'ok';
  }

  /** Anexa o PDF de um documento do checklist. */
  protected enviarDocumento(documento: DocumentoMensal, arquivo: File | null): void {
    if (!arquivo) return;
    const d = this.detalhe();
    const validade = this.validades[documento.id] ?? '';
    if (documento.com_validade && !validade) {
      this.dialogos.avisar('Informe a validade', 'Este é um documento com validade: preencha "Válido até" e escolha o arquivo de novo.');
      return;
    }
    this.dialogos.executar(this.api.documentoMensal(d.contrato_id, d.id, documento.id, arquivo, documento.com_validade ? validade : undefined), 'Enviando o documento…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível anexar o documento'),
    });
  }

  /** Quantos documentos têm um igual, ainda válido, em outro contrato da mesma empresa. */
  protected sugestoes(d: DetalheCompetencia): number {
    return d.documentos.filter((doc) => !doc.arquivo && doc.sugestao_outro_contrato).length;
  }

  /** Traz o documento de outro contrato da mesma empresa (confirmação do usuário: nada é copiado sozinho). */
  protected usarDeOutroContrato(documento: DocumentoMensal, origemId: string): void {
    const d = this.detalhe();
    this.api.reaproveitarDocumento(d.contrato_id, d.id, documento.id, origemId).subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível trazer o documento'),
    });
  }

  /** Traz de uma vez todos os documentos válidos de outros contratos da mesma empresa. */
  protected async trazerTodos(): Promise<void> {
    const d = this.detalhe();
    const ok = await this.dialogos.confirmar({
      titulo: 'Trazer os documentos de outros contratos?',
      mensagem: `${this.sugestoes(d)} documento(s) ainda válido(s) de outros contratos da empresa serão copiados para esta competência. Confira antes de concluir.`,
      rotuloConfirmar: 'Trazer documentos',
    });
    if (!ok) return;
    this.api.reaproveitarTodos(d.contrato_id, d.id).subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível trazer os documentos'),
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

  /** Gera o consolidado e já baixa o arquivo; ao gerar novamente, confirma antes a substituição. */
  protected async gerarConsolidado(novamente = false): Promise<void> {
    const d = this.detalhe();
    if (novamente) {
      const ok = await this.dialogos.confirmar({
        titulo: 'Gerar novamente o documento consolidado?',
        mensagem: 'O documento atual será substituído por um novo, montado com os arquivos que estão na competência agora.',
        rotuloConfirmar: 'Gerar novamente',
      });
      if (!ok) return;
    }
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
