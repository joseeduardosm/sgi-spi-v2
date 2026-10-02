// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 3 (nota fiscal): envio do PDF e do XML, recebimento e prazo de pagamento.

import { Component, inject, input, OnChanges, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, NotaFiscal } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';

/** Linha do formulário: uma nota fiscal (registrada e/ou com arquivos novos escolhidos). */
interface LinhaNota {
  existente: NotaFiscal | null;
  arquivo: File | null;
  xml: File | null;
}

/** Etapa 3: a equipe junta uma ou mais NFs (PDF + XML de cada). Os valores vêm dos XMLs; as retenções são conferidas na etapa 4. */
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
  /** Uma linha por nota fiscal: a já registrada (`existente`, que mantém os arquivos) e/ou os arquivos novos escolhidos. */
  protected linhas: LinhaNota[] = [];
  protected readonly reenviando = signal(false);

  /** Sempre que a competência muda, preenche o formulário com o que já foi registrado. */
  ngOnChanges(): void {
    const d = this.detalhe();
    this.recebidaEm = d.nf_recebida_em ?? '';
    this.prazo = d.prazo_pagamento_dias ?? 30;
    this.linhas = d.notas_fiscais.length ? d.notas_fiscais.map((n) => ({ existente: n, arquivo: null, xml: null })) : [{ existente: null, arquivo: null, xml: null }];
  }

  protected adicionarNota(): void {
    this.linhas = [...this.linhas, { existente: null, arquivo: null, xml: null }];
  }

  protected removerNota(linha: LinhaNota): void {
    this.linhas = this.linhas.filter((l) => l !== linha);
  }

  /** Guarda o XML escolhido (só .xml). */
  protected escolherXml(evento: Event, linha: LinhaNota): void {
    const arquivo = (evento.target as HTMLInputElement).files?.[0] ?? null;
    if (arquivo && !arquivo.name.toLowerCase().endsWith('.xml')) {
      this.dialogos.avisar('Arquivo inválido', 'Selecione o XML da nota fiscal (arquivo .xml).');
      (evento.target as HTMLInputElement).value = '';
      return;
    }
    linha.xml = arquivo;
  }

  /** Soma dos valores brutos das notas já lidas (as notas novas só têm valor depois que o XML é lido no envio). */
  protected totalRegistrado(): number {
    return this.linhas.reduce((t, l) => t + Number(l.existente?.valor_bruto ?? 0), 0);
  }

  /** Data de vencimento do pagamento (recebimento + prazo), calculada em UTC para não sofrer com fuso. */
  protected vencimento(): string {
    if (!this.recebidaEm || !this.prazo) return '—';
    const data = new Date(`${this.recebidaEm}T00:00:00Z`);
    data.setUTCDate(data.getUTCDate() + Number(this.prazo));
    return data.toISOString().slice(0, 10).split('-').reverse().join('/');
  }

  /** Cada nota com PDF e XML (novos ou já enviados), recebimento e prazo válidos. */
  protected valido(): boolean {
    const completas = this.linhas.length > 0 && this.linhas.every((l) => (!!l.arquivo || !!l.existente?.arquivo) && (!!l.xml || !!l.existente?.xml));
    return completas && !!this.recebidaEm && this.prazo >= 1 && this.prazo <= 3650;
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
    // Os arquivos novos vão em duas listas; cada nota aponta para a posição dos seus arquivos
    const arquivos: File[] = [];
    const xmls: File[] = [];
    const notas = this.linhas.map((l) => ({
      id: l.existente?.id ?? null,
      arquivo: l.arquivo ? arquivos.push(l.arquivo) - 1 : null,
      xml: l.xml ? xmls.push(l.xml) - 1 : null,
    }));
    const dados = { recebida_em: this.recebidaEm, prazo_pagamento_dias: this.prazo, notas, arquivos, xmls };
    this.dialogos.executar(this.api.notaFiscal(d.contrato_id, d.id, dados), 'Lendo os XMLs e enviando as notas fiscais…').subscribe({
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
