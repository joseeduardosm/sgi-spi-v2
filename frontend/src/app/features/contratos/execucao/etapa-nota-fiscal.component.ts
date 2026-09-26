// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 3 (nota fiscal): envio do PDF e do XML, recebimento e prazo de pagamento.

import { Component, inject, input, OnChanges, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';

/** Etapa 3: a equipe junta a NF (PDF + XML, e a adicional se houver). Os valores vêm do XML; as retenções são conferidas na etapa 4. */
@Component({
  selector: 'app-etapa-nota-fiscal',
  imports: [FormsModule, DatePipe, EnvioPdfComponent, ...PIPES_FORMATACAO],
  templateUrl: './etapa-nota-fiscal.component.html',
})
export class EtapaNotaFiscalComponent implements OnChanges {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);

  protected recebidaEm = '';
  protected prazo = 30;
  protected possuiAdicional = false;
  protected arquivo: File | null = null;
  protected xml: File | null = null;
  protected arquivoAdicional: File | null = null;
  protected xmlAdicional: File | null = null;
  protected readonly reenviando = signal(false);

  /** Sempre que a competência muda, preenche o formulário com o que já foi registrado. */
  ngOnChanges(): void {
    const d = this.detalhe();
    this.possuiAdicional = !!d.nota_fiscal_adicional;
    this.recebidaEm = d.nf_recebida_em ?? '';
    this.prazo = d.prazo_pagamento_dias ?? 30;
    this.arquivo = this.xml = this.arquivoAdicional = this.xmlAdicional = null;
  }

  /** Guarda o XML escolhido (só .xml). */
  protected escolherXml(evento: Event, adicional: boolean): void {
    const arquivo = (evento.target as HTMLInputElement).files?.[0] ?? null;
    if (arquivo && !arquivo.name.toLowerCase().endsWith('.xml')) {
      this.dialogos.avisar('Arquivo inválido', 'Selecione o XML da nota fiscal (arquivo .xml).');
      (evento.target as HTMLInputElement).value = '';
      return;
    }
    if (adicional) this.xmlAdicional = arquivo;
    else this.xml = arquivo;
  }

  /** Data de vencimento do pagamento (recebimento + prazo), calculada em UTC para não sofrer com fuso. */
  protected vencimento(): string {
    if (!this.recebidaEm || !this.prazo) return '—';
    const data = new Date(`${this.recebidaEm}T00:00:00Z`);
    data.setUTCDate(data.getUTCDate() + Number(this.prazo));
    return data.toISOString().slice(0, 10).split('-').reverse().join('/');
  }

  /** PDF e XML (novos ou já enviados), recebimento e prazo válidos. */
  protected valido(): boolean {
    const d = this.detalhe();
    const principal = (!!this.arquivo || !!d.nota_fiscal?.arquivo) && (!!this.xml || !!d.nota_fiscal?.xml);
    const adicional = !this.possuiAdicional || ((!!this.arquivoAdicional || !!d.nota_fiscal_adicional?.arquivo) &&
      (!!this.xmlAdicional || !!d.nota_fiscal_adicional?.xml));
    return principal && adicional && !!this.recebidaEm && this.prazo >= 1 && this.prazo <= 3650;
  }

  /** Envia (multipart) os arquivos e as datas; a etapa conclui e o Financeiro é avisado por e-mail. */
  protected async concluir(): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Juntar a nota fiscal?',
      mensagem: 'O XML é lido para preencher número, valor e retenções. A retenção de tributos (Financeiro, que recebe um e-mail com cópia para a equipe), o CADIN e o checklist ficam liberados ao mesmo tempo; o documento consolidado só é gerado com os três concluídos.',
      rotuloConfirmar: 'Juntar nota fiscal',
    });
    if (!ok) return;
    const d = this.detalhe();
    const campos: Record<string, string | boolean | File | null> = {
      recebida_em: this.recebidaEm, prazo_pagamento_dias: String(this.prazo), possui_adicional: this.possuiAdicional,
      arquivo: this.arquivo, xml: this.xml,
    };
    if (this.possuiAdicional) {
      campos['arquivo_adicional'] = this.arquivoAdicional;
      campos['xml_adicional'] = this.xmlAdicional;
    }
    this.dialogos.executar(this.api.notaFiscal(d.contrato_id, d.id, campos), 'Lendo o XML e enviando a nota fiscal…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível juntar a nota fiscal'),
    });
  }

  /** Reenvia o e-mail ao Financeiro. */
  protected reenviarEmail(): void {
    const d = this.detalhe();
    this.reenviando.set(true);
    this.api.reenviarEmail(d.contrato_id, d.id, 'nf').subscribe({
      next: (novo) => {
        this.reenviando.set(false);
        this.atualizado.emit(novo);
      },
      error: (e) => {
        this.reenviando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível reenviar o e-mail');
      },
    });
  }

  /** Baixa um arquivo da competência (PDF ou XML). */
  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
