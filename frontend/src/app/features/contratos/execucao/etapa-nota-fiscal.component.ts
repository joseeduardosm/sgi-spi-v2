import { Component, inject, input, OnChanges, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, NotaFiscal } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { paraDecimalApi, paraDecimalTela } from '../compartilhado/rotulos';

const RETENCOES = [
  { chave: 'ir', rotulo: 'IR' },
  { chave: 'inss', rotulo: 'INSS' },
  { chave: 'iss', rotulo: 'ISS' },
  { chave: 'pis', rotulo: 'PIS/PASEP' },
  { chave: 'cofins', rotulo: 'COFINS' },
] as const;

interface CamposNota {
  numero: string;
  valor_bruto: string;
  retencoes: Record<string, string>;
}

/** Etapa 3: nota fiscal principal (e adicional opcional), retenções, líquido e vencimento. */
@Component({
  selector: 'app-etapa-nota-fiscal',
  imports: [FormsModule, EnvioPdfComponent, ...PIPES_FORMATACAO],
  templateUrl: './etapa-nota-fiscal.component.html',
})
export class EtapaNotaFiscalComponent implements OnChanges {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly retencoes = RETENCOES;

  protected principal: CamposNota = this.vazia();
  protected adicional: CamposNota = this.vazia();
  protected origem: 'medicao' | 'manual' = 'medicao';
  protected recebidaEm = '';
  protected prazo = 30;
  protected possuiAdicional = false;
  protected arquivo: File | null = null;
  protected arquivoAdicional: File | null = null;

  private vazia(): CamposNota {
    return { numero: '', valor_bruto: '', retencoes: Object.fromEntries(RETENCOES.map((r) => [r.chave, ''])) };
  }

  private deNota(nota: NotaFiscal | null): CamposNota {
    if (!nota) return this.vazia();
    return {
      numero: nota.numero,
      valor_bruto: paraDecimalTela(nota.valor_bruto),
      retencoes: Object.fromEntries(RETENCOES.map((r) => [r.chave, paraDecimalTela(nota[`retencao_${r.chave}` as keyof NotaFiscal] as string)])),
    };
  }

  ngOnChanges(): void {
    const d = this.detalhe();
    this.principal = this.deNota(d.nota_fiscal);
    this.adicional = this.deNota(d.nota_fiscal_adicional);
    this.possuiAdicional = !!d.nota_fiscal_adicional;
    this.origem = d.origem_valor_nf ?? 'medicao';
    this.recebidaEm = d.nf_recebida_em ?? '';
    this.prazo = d.prazo_pagamento_dias ?? 30;
  }

  protected numero(valor: string): number {
    return Number(paraDecimalApi(valor)) || 0;
  }

  protected bruto(nota: CamposNota, principal: boolean): number {
    return principal && this.origem === 'medicao' ? Number(this.detalhe().valor_autorizado) : this.numero(nota.valor_bruto);
  }

  protected somaRetencoes(nota: CamposNota): number {
    return Object.values(nota.retencoes).reduce((t, v) => t + this.numero(v), 0);
  }

  protected liquido(nota: CamposNota, principal: boolean): number {
    return Math.max(0, this.bruto(nota, principal) - this.somaRetencoes(nota));
  }

  protected vencimento(): string {
    if (!this.recebidaEm || !this.prazo) return '—';
    const data = new Date(`${this.recebidaEm}T00:00:00Z`);
    data.setUTCDate(data.getUTCDate() + Number(this.prazo));
    return data.toISOString().slice(0, 10).split('-').reverse().join('/');
  }

  /** NF + NF adicional (brutos): o que a OB vai debitar nas NEs apontadas na medição. */
  protected totalAPagar(): number {
    return this.bruto(this.principal, true) + (this.possuiAdicional ? this.numero(this.adicional.valor_bruto) : 0);
  }

  protected saldoLivreNotas(): number {
    return this.detalhe().notas_selecionadas.reduce((t, n) => t + Number(n.saldo_livre), 0);
  }

  protected valido(): boolean {
    const d = this.detalhe();
    const principalOk = !!this.principal.numero.trim() && !!this.recebidaEm && this.prazo >= 1 && this.prazo <= 3650 &&
      (!!this.arquivo || !!d.nota_fiscal?.arquivo) && this.bruto(this.principal, true) > 0 && this.somaRetencoes(this.principal) <= this.bruto(this.principal, true);
    const adicionalOk = !this.possuiAdicional || (!!this.adicional.numero.trim() && this.numero(this.adicional.valor_bruto) > 0 &&
      (!!this.arquivoAdicional || !!d.nota_fiscal_adicional?.arquivo) && this.somaRetencoes(this.adicional) <= this.numero(this.adicional.valor_bruto));
    return principalOk && adicionalOk && this.totalAPagar() <= this.saldoLivreNotas() + 0.005;
  }

  protected async concluir(): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Concluir a nota fiscal?', mensagem: 'A etapa do CADIN será liberada.', rotuloConfirmar: 'Concluir nota fiscal' });
    if (!ok) return;
    const d = this.detalhe();
    const campos: Record<string, string | boolean | File | null> = {
      numero: this.principal.numero.trim(), recebida_em: this.recebidaEm, prazo_pagamento_dias: String(this.prazo), origem_valor: this.origem,
      valor_bruto: this.origem === 'manual' ? paraDecimalApi(this.principal.valor_bruto) : null, arquivo: this.arquivo,
      possui_adicional: this.possuiAdicional,
    };
    for (const r of RETENCOES) campos[`retencao_${r.chave}`] = paraDecimalApi(this.principal.retencoes[r.chave]);
    if (this.possuiAdicional) {
      campos['adicional_numero'] = this.adicional.numero.trim();
      campos['adicional_valor_bruto'] = paraDecimalApi(this.adicional.valor_bruto);
      campos['arquivo_adicional'] = this.arquivoAdicional;
      for (const r of RETENCOES) campos[`adicional_retencao_${r.chave}`] = paraDecimalApi(this.adicional.retencoes[r.chave]);
    }
    this.dialogos.executar(this.api.notaFiscal(d.contrato_id, d.id, campos), 'Enviando a nota fiscal…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível concluir a nota fiscal'),
    });
  }

  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
