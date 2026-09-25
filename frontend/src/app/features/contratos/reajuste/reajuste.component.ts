// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de reajuste: abertura, evidência do índice, memória, apostilamento e conclusão.

import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { AlteracoesApiService } from '../compartilhado/alteracoes-api.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DetalheContrato, PainelReajuste, Reajuste } from '../compartilhado/contratos.models';
import { paraDecimalApi, paraDecimalTela } from '../compartilhado/rotulos';

/** Tela 6: reajuste (evidência do índice, memória, apostilamento e conclusão). */
@Component({
  selector: 'app-reajuste',
  imports: [FormsModule, RouterLink, DatePipe, CabecalhoModuloComponent, EnvioPdfComponent, ...PIPES_FORMATACAO],
  templateUrl: './reajuste.component.html',
})
export class ReajusteComponent implements OnInit {
  readonly id = input.required<string>();

  private readonly api = inject(AlteracoesApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  // Contrato e painel carregados
  protected readonly contrato = signal<DetalheContrato | null>(null);
  protected readonly painel = signal<PainelReajuste | null>(null);
  // Campos da abertura (mês de referência AAAA-MM e vigência) e da memória (índice e teto por item)
  protected mesReferencia = '';
  protected vigencia: number | null = null;
  protected indices: Record<string, string> = {};
  protected referenciais: Record<string, string> = {};
  // PDFs escolhidos: evidência do índice e apostilamento assinado
  protected evidencia: File | null = null;
  protected apostilamento: File | null = null;

  /** Carrega o contrato e o painel de reajuste em paralelo. */
  ngOnInit(): void {
    forkJoin({ contrato: this.contratos.consultar(this.id()), painel: this.api.reajustes(this.id()) }).subscribe({
      next: ({ contrato, painel }) => {
        this.contrato.set(contrato);
        this.aplicar(painel);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o reajuste'),
    });
  }

  /** Guarda o painel e preenche os campos da memória com os valores salvos. */
  private aplicar(painel: PainelReajuste): void {
    this.painel.set(painel);
    const r = painel.em_andamento;
    // Sugere a vigência mais recente ainda não reajustada
    this.vigencia = painel.vigencias_disponiveis.at(-1)?.sequencia ?? null;
    if (r) {
      this.indices = Object.fromEntries(r.itens.map((i) => [i.item_id, paraDecimalTela(i.indice_percentual)]));
      this.referenciais = Object.fromEntries(r.itens.map((i) => [i.item_id, paraDecimalTela(i.valor_referencial)]));
    }
  }

  /** Executa a chamada (com "Executando…" se houver mensagem) e aplica o painel devolvido. */
  private tratar(requisicao: ReturnType<AlteracoesApiService['reajustes']>, titulo: string, processando?: string): void {
    (processando ? this.dialogos.executar(requisicao, processando) : requisicao).subscribe({
      next: (p) => this.aplicar(p),
      error: (e) => this.dialogos.mostrarErro(e, titulo),
    });
  }

  /** Abre o reajuste para a vigência e o mês escolhidos (enviado como dia 1). */
  protected abrir(): void {
    if (!this.vigencia || !this.mesReferencia) return;
    this.tratar(this.api.abrirReajuste(this.id(), this.vigencia, `${this.mesReferencia}-01`), 'Não foi possível abrir o reajuste');
  }

  /** Anexa a evidência do índice. */
  protected anexarEvidencia(r: Reajuste): void {
    if (this.evidencia) this.tratar(this.api.enviarReajuste(this.id(), r.id, 'evidencia', this.evidencia), 'Não foi possível anexar a evidência', 'Enviando a evidência…');
  }

  /** Grava índice e teto de cada item (teto vazio = sem teto). */
  protected salvarMemoria(r: Reajuste): void {
    const itens = r.itens.map((i) => ({
      item_id: i.item_id,
      indice_percentual: paraDecimalApi(this.indices[i.item_id] || '0'),
      valor_referencial: this.referenciais[i.item_id] ? paraDecimalApi(this.referenciais[i.item_id]) : null,
    }));
    this.tratar(this.api.salvarMemoriaReajuste(this.id(), r.id, itens), 'Não foi possível salvar a memória');
  }

  /** Gera a memória em PDF e XLSX e já baixa o PDF da versão mais recente. */
  protected gerarArquivos(r: Reajuste): void {
    this.dialogos.executar(this.api.acaoReajuste(this.id(), r.id, 'memoria/arquivos'), 'Gerando a memória em PDF e XLSX…').subscribe({
      next: (p) => {
        this.aplicar(p);
        const ultima = p.em_andamento?.memorias.at(-1);
        if (ultima) this.baixar(r, ultima.pdf.anexo_id);
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  /** Confirma (mostrando o efeito do reajuste) e conclui com o apostilamento. */
  protected async concluir(r: Reajuste): Promise<void> {
    if (!this.apostilamento) return;
    const ok = await this.dialogos.confirmar({
      titulo: 'Concluir e aplicar o reajuste?',
      mensagem: `Os preços reajustados passam a valer a partir de ${r.mes_referencia.slice(5, 7)}/${r.mes_referencia.slice(0, 4)}, em ${r.competencias_recalculadas} competência(s) ainda não medida(s)${r.competencias_com_diferenca ? `; a diferença de ${r.competencias_com_diferenca} competência(s) já medida(s) vira uma competência complementar` : ''}, e o valor global passa a ${Number(r.valor_global_reajustado).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}.`,
      rotuloConfirmar: 'Concluir e aplicar',
      segundos: 5,
    });
    if (ok) this.tratar(this.api.enviarReajuste(this.id(), r.id, 'concluir', this.apostilamento), 'Não foi possível concluir o reajuste', 'Aplicando o reajuste…');
  }

  /** Pede confirmação e cancela o reajuste em elaboração. */
  protected async cancelar(r: Reajuste): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Cancelar o reajuste?', mensagem: 'O reajuste em elaboração será cancelado.', rotuloConfirmar: 'Cancelar reajuste', segundos: 3 });
    if (ok) this.tratar(this.api.acaoReajuste(this.id(), r.id, 'cancelar'), 'Não foi possível cancelar o reajuste');
  }

  /** Baixa um arquivo do reajuste. */
  protected baixar(r: Reajuste, anexoId: string): void {
    this.api.baixarReajuste(this.id(), r.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
