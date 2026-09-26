// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 4 (retenção de tributos): nota lida do XML, conferências, retenções e líquido.

import { DatePipe } from '@angular/common';
import { Component, inject, input, OnChanges, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, NotaFiscal, Tributo } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { paraDecimalApi, paraDecimalTela } from '../compartilhado/rotulos';

const TRIBUTOS: { chave: Tributo; rotulo: string }[] = [
  { chave: 'ir', rotulo: 'IR' },
  { chave: 'inss', rotulo: 'INSS' },
  { chave: 'iss', rotulo: 'ISS' },
  { chave: 'pis', rotulo: 'PIS/PASEP' },
  { chave: 'cofins', rotulo: 'COFINS' },
  { chave: 'csll', rotulo: 'CSLL' },
];

/** Uma nota em conferência: dados do XML e as retenções digitadas (formato brasileiro). */
interface NotaEmConferencia {
  titulo: string;
  nota: NotaFiscal;
  retencoes: Record<Tributo, string>;
}

/** Etapa 4: o Financeiro (ou a equipe) confere a NF lida do XML e confirma as retenções. */
@Component({
  selector: 'app-etapa-retencao',
  imports: [FormsModule, DatePipe, ...PIPES_FORMATACAO],
  templateUrl: './etapa-retencao.component.html',
})
export class EtapaRetencaoComponent implements OnChanges {
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tributos = TRIBUTOS;
  protected notas: NotaEmConferencia[] = [];
  protected discriminacaoConferida = false;
  protected readonly reenviando = signal(false);

  /** Preenche as retenções com o que está gravado (na primeira vez, os valores lidos do XML). */
  ngOnChanges(): void {
    const d = this.detalhe();
    const montar = (titulo: string, nota: NotaFiscal): NotaEmConferencia => ({
      titulo, nota,
      retencoes: Object.fromEntries(TRIBUTOS.map((t) => [t.chave, paraDecimalTela(nota[`retencao_${t.chave}`])])) as Record<Tributo, string>,
    });
    this.notas = [
      ...(d.nota_fiscal ? [montar('Nota fiscal', d.nota_fiscal)] : []),
      ...(d.nota_fiscal_adicional ? [montar('Nota fiscal adicional', d.nota_fiscal_adicional)] : []),
    ];
    this.discriminacaoConferida = d.retencao?.discriminacao_conferida ?? false;
  }

  protected numero(valor: string): number {
    return Number(paraDecimalApi(valor)) || 0;
  }

  protected totalRetido(n: NotaEmConferencia): number {
    return TRIBUTOS.reduce((t, x) => t + this.numero(n.retencoes[x.chave]), 0);
  }

  protected liquido(n: NotaEmConferencia): number {
    return Number(n.nota.valor_bruto ?? 0) - this.totalRetido(n);
  }

  /** CNPJ formatado (00.000.000/0000-00). */
  protected cnpj(valor: string | null): string {
    const d = (valor ?? '').replace(/\D/g, '');
    return d.length === 14 ? `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}` : d || 'não informado';
  }

  protected alertas(): number {
    return this.notas.reduce((t, n) => t + n.nota.conferencias.filter((c) => c.situacao === 'alerta').length, 0);
  }

  protected valido(): boolean {
    return this.discriminacaoConferida && this.notas.every((n) => this.totalRetido(n) <= Number(n.nota.valor_bruto ?? 0) + 0.005 &&
      TRIBUTOS.every((t) => this.numero(n.retencoes[t.chave]) >= 0));
  }

  protected async salvar(): Promise<void> {
    const alertas = this.alertas();
    const ok = await this.dialogos.confirmar({
      titulo: 'Salvar a retenção de tributos?',
      mensagem: (alertas ? `Há ${alertas} conferência(s) com alerta — confira antes de salvar. ` : '') +
        'O PDF da conferência é gerado com o seu nome, a data e a hora; a etapa do CADIN é liberada e a equipe recebe um e-mail.',
      rotuloConfirmar: 'Salvar retenção',
    });
    if (!ok) return;
    const d = this.detalhe();
    const valores = (n: NotaEmConferencia) => Object.fromEntries(TRIBUTOS.map((t) => [t.chave, paraDecimalApi(n.retencoes[t.chave]) || '0']));
    const corpo = {
      principal: valores(this.notas[0]),
      adicional: this.notas[1] ? valores(this.notas[1]) : null,
      discriminacao_conferida: this.discriminacaoConferida,
    };
    this.dialogos.executar(this.api.salvarRetencao(d.contrato_id, d.id, corpo), 'Salvando a retenção e gerando o PDF…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a retenção'),
    });
  }

  protected reenviarEmail(): void {
    const d = this.detalhe();
    this.reenviando.set(true);
    this.api.reenviarEmail(d.contrato_id, d.id, 'retencao').subscribe({
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

  protected baixar(anexoId: string): void {
    const d = this.detalhe();
    this.api.baixar(d.contrato_id, d.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
