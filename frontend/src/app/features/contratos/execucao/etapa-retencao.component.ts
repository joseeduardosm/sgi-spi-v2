// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a etapa 4 (retenção de tributos): nota lida do XML, conferências, retenções e líquido.

import { DatePipe } from '@angular/common';
import { Component, inject, input, OnChanges, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { DetalheCompetencia, NotaFiscal, Tributo } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { OpcaoEmailComponent } from '../compartilhado/opcao-email.component';
import { HistoricoRecusasComponent } from './historico-recusas.component';
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
  imports: [FormsModule, DatePipe, OpcaoEmailComponent, HistoricoRecusasComponent, ...PIPES_FORMATACAO],
  templateUrl: './etapa-retencao.component.html',
})
export class EtapaRetencaoComponent implements OnChanges {
  // "Enviar por e-mail" começa desmarcado: só envia quem marcar
  protected readonly enviarEmail = signal(false);
  readonly detalhe = input.required<DetalheCompetencia>();
  readonly editavel = input(false);
  readonly atualizado = output<DetalheCompetencia>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tributos = TRIBUTOS;
  protected notas: NotaEmConferencia[] = [];
  protected discriminacaoConferida = false;
  protected readonly reenviando = signal(false);
  // Janela de recusa da nota (justificativa obrigatória)
  protected readonly recusando = signal(false);
  protected justificativaRecusa = '';

  /** Preenche as retenções com o que está gravado (na primeira vez, os valores lidos do XML). */
  ngOnChanges(): void {
    const d = this.detalhe();
    const montar = (titulo: string, nota: NotaFiscal): NotaEmConferencia => ({
      titulo, nota,
      retencoes: Object.fromEntries(TRIBUTOS.map((t) => [t.chave, paraDecimalTela(nota[`retencao_${t.chave}`])])) as Record<Tributo, string>,
    });
    const varias = d.notas_fiscais.length > 1;
    this.notas = d.notas_fiscais.map((n) => montar(varias ? `Nota fiscal ${n.ordem}` : 'Nota fiscal', n));
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

  /** Abre o PDF da nota em uma nova aba. */
  protected verNota(n: NotaEmConferencia): void {
    const d = this.detalhe();
    if (n.nota.arquivo) this.api.abrirEmNovaAba(d.contrato_id, d.id, n.nota.arquivo.anexo_id, (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a nota'));
  }

  /** Soma de uma coluna do quadro "Total das notas" (bruto ou retenções), com os valores digitados. */
  protected totalGeral(campo: 'bruto' | 'retido' | 'liquido'): number {
    return this.notas.reduce((t, n) => t + (campo === 'bruto' ? Number(n.nota.valor_bruto ?? 0) : campo === 'retido' ? this.totalRetido(n) : this.liquido(n)), 0);
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
        'O PDF da conferência é gerado com o seu nome, a data e a hora; a etapa do CADIN é liberada' + (this.enviarEmail() ? ' e a equipe recebe um e-mail.' : '. Nenhum e-mail será enviado agora.'),
      rotuloConfirmar: 'Salvar retenção',
    });
    if (!ok) return;
    const d = this.detalhe();
    const valores = (n: NotaEmConferencia) => Object.fromEntries(TRIBUTOS.map((t) => [t.chave, paraDecimalApi(n.retencoes[t.chave]) || '0']));
    const corpo = {
      notas: this.notas.map((n) => ({ nota_id: n.nota.id, ...valores(n) })),
      discriminacao_conferida: this.discriminacaoConferida,
      enviar_email: this.enviarEmail(),
    };
    this.dialogos.executar(this.api.salvarRetencao(d.contrato_id, d.id, corpo), 'Salvando a retenção e gerando o PDF…').subscribe({
      next: (novo) => this.atualizado.emit(novo),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a retenção'),
    });
  }

  /** Recusa a nota: a etapa da nota fiscal reabre e a equipe e todos os prepostos recebem o e-mail com o PDF da recusa. */
  protected recusar(): void {
    const d = this.detalhe();
    if (this.justificativaRecusa.trim().length < 10) return;
    this.dialogos.executar(this.api.recusarNota(d.contrato_id, d.id, this.justificativaRecusa.trim()), 'Registrando a recusa e gerando o PDF…').subscribe({
      next: (novo) => {
        this.recusando.set(false);
        this.justificativaRecusa = '';
        this.atualizado.emit(novo);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível recusar a nota'),
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
