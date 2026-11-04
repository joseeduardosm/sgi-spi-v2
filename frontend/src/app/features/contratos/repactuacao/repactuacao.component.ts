// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de repactuação pela CCT: cadastro das linhas e vínculos, memória, retroativo, checklist,
// consolidado e finalização com o apostilamento.

import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, input, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { debounceTime, forkJoin, Observable, Subject, switchMap } from 'rxjs';

import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
import { EtapaTrilha, TrilhaEtapasComponent } from '../../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { LinkificarPipe } from '../../../shared/utilitarios/linkificar.pipe';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { AlteracoesApiService } from '../compartilhado/alteracoes-api.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import {
  CalculoMesQuebrado, DetalheContrato, DocumentoProrrogacao, GravacaoLinhaRepactuacao, PainelRepactuacao, Repactuacao,
} from '../compartilhado/contratos.models';
import { paraDecimalApi, paraDecimalTela } from '../compartilhado/rotulos';

/** Valor digitado aceito (R$ com vírgula ou ponto, até 4 casas). */
const VALOR = /^\d{1,14}([.,]\d{1,4})?$/;

/** Linha em edição na tela: valores como texto (como se digita) e os itens vinculados. */
interface LinhaEdicao { descricao: string; vigente: string; repactuado: string; itens: Set<string> }

/**
 * Repactuação: a CCT muda componentes de custo (ex.: vale-transporte de R$ 198 para R$ 220 por posto/mês) e a diferença de cada um soma
 * no preço dos itens do contrato vinculados a ele, a partir da data de vigência. Mesma estrutura da tela de reajuste (cartão, trilha,
 * memória, mês quebrado) e o checklist da prorrogação.
 */
@Component({
  selector: 'app-repactuacao',
  imports: [TrilhaEtapasComponent, EsqueletoComponent, FormsModule, RouterLink, DatePipe, CabecalhoModuloComponent, EnvioPdfComponent, LinkificarPipe,
    ...PIPES_FORMATACAO],
  templateUrl: './repactuacao.component.html',
})
export class RepactuacaoComponent implements OnInit {
  readonly id = input.required<string>();
  private readonly api = inject(AlteracoesApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly destruir = inject(DestroyRef);

  protected readonly contrato = signal<DetalheContrato | null>(null);
  protected readonly painel = signal<PainelRepactuacao | null>(null);
  /** Cálculo ao vivo enquanto se digita (null = vale o gravado). */
  protected readonly previa = signal<Repactuacao | null>(null);
  protected readonly salvando = signal(false);
  protected readonly escolhendo = signal<CalculoMesQuebrado | null>(null);
  protected readonly incluindoDocumento = signal(false);
  protected readonly enviandoInclusao = signal(false);
  protected readonly calculos: CalculoMesQuebrado[] = ['pro_rata', 'integral'];
  protected readonly rotulosCalculo: Record<CalculoMesQuebrado, string> = { pro_rata: 'Opção 1 · Pro rata', integral: 'Opção 2 · Integral' };

  // Abertura
  protected dataBaseCct = '';
  protected dataEfeito = '';
  protected cct: File | null = null;
  // Linhas em edição
  protected linhas: LinhaEdicao[] = [];
  private alterado = false;
  private readonly mudou$ = new Subject<void>();
  // Apostilamento e inclusão de documento no checklist
  protected apostilamento: File | null = null;
  protected novoDocumentoNome = '';
  protected novoDocumentoDescricao = '';
  protected novoDocumentoArquivo: File | null = null;

  constructor() {
    // Prévia: recalcula 350 ms depois da última digitação, descartando respostas antigas
    this.mudou$.pipe(
      debounceTime(350),
      switchMap(() => {
        const r = this.painel()?.em_andamento;
        return r && this.linhasValidas() ? this.api.previaRepactuacao(this.id(), r.id, this.gravacao()) : new Observable<null>((o) => o.next(null));
      }),
      takeUntilDestroyed(this.destruir),
    ).subscribe({ next: (r) => this.previa.set(r), error: () => this.previa.set(null) });
  }

  ngOnInit(): void {
    forkJoin({ contrato: this.contratos.consultar(this.id()), painel: this.api.repactuacoes(this.id()) }).subscribe({
      next: ({ contrato, painel }) => {
        this.contrato.set(contrato);
        this.aplicar(painel);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a repactuação'),
    });
  }

  /** Guarda o painel e preenche as linhas em edição com as gravadas (uma linha vazia quando não há nenhuma). */
  private aplicar(painel: PainelRepactuacao): void {
    this.painel.set(painel);
    this.previa.set(null);
    this.alterado = false;
    this.apostilamento = null;
    const r = painel.em_andamento;
    this.linhas = r?.linhas.length
      ? r.linhas.map((l) => ({ descricao: l.descricao, vigente: paraDecimalTela(l.valor_vigente), repactuado: paraDecimalTela(l.valor_repactuado), itens: new Set(l.itens_ids) }))
      : [this.linhaVazia()];
  }

  private linhaVazia(): LinhaEdicao {
    return { descricao: '', vigente: '', repactuado: '', itens: new Set() };
  }

  /** O que a tela mostra: a prévia (se houver) ou o gravado. */
  protected vis(r: Repactuacao): Repactuacao {
    return this.previa() ?? r;
  }

  protected trilha(r: Repactuacao): EtapaTrilha[] {
    const estado = (feito: boolean, liberado: boolean) => (feito ? 'concluida' : liberado ? 'atual' : 'aguardando') as EtapaTrilha['estado'];
    return [
      { id: 'cadastro', rotulo: 'Cadastro', estado: estado(r.cadastro_concluido, true) },
      { id: 'memoria', rotulo: 'Memória de cálculo', estado: estado(r.memoria_atualizada, r.cadastro_concluido) },
      { id: 'checklist', rotulo: 'Checklist', estado: estado(r.obrigatorios_pendentes === 0 && r.cadastro_concluido, r.cadastro_concluido) },
      { id: 'consolidado', rotulo: 'Consolidado', estado: estado(r.consolidado_atualizado, r.memoria_atualizada) },
      { id: 'finalizacao', rotulo: 'Apostilamento e finalização', estado: estado(false, r.consolidado_atualizado) },
    ];
  }

  // --- Abertura ---
  protected abrir(): void {
    if (!this.dataBaseCct || !this.dataEfeito || !this.cct) return;
    this.tratar(this.api.abrirRepactuacao(this.id(), `${this.dataBaseCct}-01`, this.dataEfeito, this.cct), 'Não foi possível abrir a repactuação', 'Abrindo a repactuação…');
  }

  // --- Linhas ---
  protected adicionarLinha(): void {
    this.linhas.push(this.linhaVazia());
  }

  protected removerLinha(indice: number): void {
    this.linhas.splice(indice, 1);
    if (!this.linhas.length) this.linhas.push(this.linhaVazia());
    this.mudar();
  }

  protected alternarItem(linha: LinhaEdicao, itemId: string): void {
    if (linha.itens.has(itemId)) linha.itens.delete(itemId);
    else linha.itens.add(itemId);
    this.mudar();
  }

  /** Marca a tela como alterada e pede a prévia. */
  protected mudar(): void {
    this.alterado = true;
    this.mudou$.next();
  }

  protected alteradoSemSalvar(): boolean {
    return this.alterado;
  }

  protected valorValido(texto: string): boolean {
    return VALOR.test((texto || '').trim());
  }

  protected linhasValidas(): boolean {
    return this.linhas.length > 0 && this.linhas.every((l) => l.descricao.trim() && this.valorValido(l.vigente) && this.valorValido(l.repactuado) && l.itens.size > 0);
  }

  /** Diferença da linha em R$, para mostrar enquanto se digita. */
  protected diferencaLinha(l: LinhaEdicao): number | null {
    if (!this.valorValido(l.vigente) || !this.valorValido(l.repactuado)) return null;
    return Number(paraDecimalApi(l.repactuado)) - Number(paraDecimalApi(l.vigente));
  }

  private gravacao(): GravacaoLinhaRepactuacao[] {
    return this.linhas.map((l) => ({
      descricao: l.descricao.trim(), valor_vigente: paraDecimalApi(l.vigente), valor_repactuado: paraDecimalApi(l.repactuado), itens_ids: [...l.itens],
    }));
  }

  protected salvarLinhas(r: Repactuacao, finalizar = false): void {
    if (!this.linhasValidas()) return;
    this.tratar(this.api.salvarLinhasRepactuacao(this.id(), r.id, this.gravacao(), finalizar), 'Não foi possível salvar os itens',
      finalizar ? 'Finalizando o cadastro…' : 'Salvando os itens…');
  }

  // --- Memória e mês quebrado ---
  protected escolherCalculo(r: Repactuacao, calculo: CalculoMesQuebrado): void {
    this.escolhendo.set(calculo);
    this.api.mesQuebradoRepactuacao(this.id(), r.id, calculo).subscribe({
      next: (p) => { this.escolhendo.set(null); this.aplicar(p); },
      error: (e) => { this.escolhendo.set(null); this.dialogos.mostrarErro(e); },
    });
  }

  /** Gera a memória em PDF e XLSX e já baixa o PDF da versão mais recente. */
  protected gerarMemoria(r: Repactuacao): void {
    this.dialogos.executar(this.api.acaoRepactuacao(this.id(), r.id, 'memoria'), 'Gerando a memória em PDF e XLSX…').subscribe({
      next: (p) => {
        this.aplicar(p);
        const ultima = p.em_andamento?.memorias.at(-1);
        if (ultima) this.baixar(r, ultima.pdf.anexo_id);
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  // --- Checklist ---
  protected anexarDocumento(r: Repactuacao, documento: DocumentoProrrogacao, arquivo: File | null): void {
    if (!arquivo) return;
    this.tratar(this.api.anexarDocumentoRepactuacao(this.id(), r.id, documento.id, arquivo), 'Não foi possível anexar o documento', 'Enviando o documento…');
  }

  protected abrirInclusao(): void {
    this.novoDocumentoNome = '';
    this.novoDocumentoDescricao = '';
    this.novoDocumentoArquivo = null;
    this.incluindoDocumento.set(true);
  }

  protected incluirDocumento(r: Repactuacao): void {
    if (!this.novoDocumentoNome.trim() || !this.novoDocumentoArquivo) return;
    this.enviandoInclusao.set(true);
    this.api.incluirDocumentoRepactuacao(this.id(), r.id, this.novoDocumentoNome.trim(), this.novoDocumentoDescricao.trim(), this.novoDocumentoArquivo).subscribe({
      next: (p) => { this.enviandoInclusao.set(false); this.incluindoDocumento.set(false); this.aplicar(p); },
      error: (e) => { this.enviandoInclusao.set(false); this.dialogos.mostrarErro(e, 'Não foi possível incluir o documento'); },
    });
  }

  protected async excluirDocumento(r: Repactuacao, documento: DocumentoProrrogacao): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir "${documento.nome}"?`, mensagem: 'O documento sai do checklist desta repactuação e o arquivo é descartado.', rotuloConfirmar: 'Excluir documento' });
    if (ok) this.tratar(this.api.excluirDocumentoRepactuacao(this.id(), r.id, documento.id), 'Não foi possível excluir o documento');
  }

  // --- Consolidado e finalização ---
  protected gerarConsolidado(r: Repactuacao): void {
    this.dialogos.executar(this.api.acaoRepactuacao(this.id(), r.id, 'consolidado'), 'Gerando o documento consolidado…').subscribe({
      next: (p) => {
        this.aplicar(p);
        const c = p.em_andamento?.consolidado;
        if (c) this.baixar(r, c.anexo_id);
      },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected async finalizar(r: Repactuacao): Promise<void> {
    if (!this.apostilamento) return;
    const dif = Number(r.total_retroativo);
    const retro = dif > 0 ? `; a diferença de ${reais(dif)} das competências já medidas vira uma competência de diferença a pagar`
      : dif < 0 ? `; o crédito de ${reais(-dif)} das competências já medidas será abatido na próxima medição` : '';
    const ok = await this.dialogos.confirmar({
      titulo: 'Finalizar e aplicar a repactuação?',
      mensagem: `Os preços dos ${r.itens.length} item(ns) vinculados passam a valer a partir de ${dataBr(r.data_efeito)} e a base mensal vai de ${reais(r.base_atual)} para ${reais(r.base_repactuada)}${retro}.`,
      rotuloConfirmar: 'Finalizar e aplicar',
      segundos: 5,
    });
    if (ok) this.tratar(this.api.finalizarRepactuacao(this.id(), r.id, this.apostilamento), 'Não foi possível finalizar a repactuação', 'Aplicando a repactuação…');
  }

  protected async cancelar(r: Repactuacao): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Cancelar a repactuação?', mensagem: 'A repactuação em elaboração será cancelada; os preços não mudam e a CCT continua nos Documentos importantes.', rotuloConfirmar: 'Cancelar repactuação', segundos: 3 });
    if (ok) this.tratar(this.api.acaoRepactuacao(this.id(), r.id, 'cancelar'), 'Não foi possível cancelar a repactuação');
  }

  protected baixar(r: Repactuacao, anexoId: string): void {
    this.api.baixarRepactuacao(this.id(), r.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected nomeItem(itemId: string): string {
    const i = this.painel()?.itens_contrato.find((x) => x.id === itemId);
    return i ? `${i.ordem}. ${i.descricao}` : '';
  }

  /** Executa uma gravação com a mensagem de andamento e aplica o painel devolvido. */
  private tratar(pedido: Observable<PainelRepactuacao>, erro: string, andamento = 'Salvando…'): void {
    this.salvando.set(true);
    this.dialogos.executar(pedido, andamento).subscribe({
      next: (p) => { this.salvando.set(false); this.aplicar(p); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, erro); },
    });
  }
}

function reais(valor: string | number): string {
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

function dataBr(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}
