// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de aditamento/supressão (justificativa, quantitativos, ciências e formalização).

import { DatePipe } from '@angular/common';
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { EnvioPdfComponent } from '../../../shared/componentes/envio-pdf/envio-pdf.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { AlteracoesApiService } from '../compartilhado/alteracoes-api.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { Alteracao, DetalheContrato, PainelAlteracao } from '../compartilhado/contratos.models';
import { paraDecimalApi, paraDecimalTela, ROTULOS_PAPEL, ROTULOS_TIPO_ITEM } from '../compartilhado/rotulos';

/** Abas do processo, na ordem do fluxo. */
type Aba = 'justificativa' | 'quantitativos' | 'memoria' | 'formalizacao';
/** Documentos que podem ser anexados na alteração. */
type Documento = 'justificativa' | 'autorizacao' | 'de_acordo' | 'termo';

/** Tela 7: aditamento ou supressão (justificativa → quantitativos → memória e ciências → formalização). */
@Component({
  selector: 'app-alteracao',
  imports: [FormsModule, RouterLink, DatePipe, CabecalhoModuloComponent, EnvioPdfComponent, ...PIPES_FORMATACAO],
  templateUrl: './alteracao.component.html',
})
export class AlteracaoComponent implements OnInit {
  readonly id = input.required<string>();

  private readonly api = inject(AlteracoesApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);
  // A mesma tela atende aditamento e supressão; o tipo vem do `data` da rota
  protected readonly tipo = inject(ActivatedRoute).snapshot.data['tipo'] as 'aditamento' | 'supressao';

  protected readonly rotuloTipo = this.tipo === 'aditamento' ? 'Aditamento' : 'Supressão';
  protected readonly papeis = ROTULOS_PAPEL;
  protected readonly rotulosItem = ROTULOS_TIPO_ITEM;
  // Dados carregados e a aba aberta
  protected readonly contrato = signal<DetalheContrato | null>(null);
  protected readonly painel = signal<PainelAlteracao | null>(null);
  protected readonly aba = signal<Aba>('justificativa');
  // Campos da abertura, novas quantidades por item e PDFs escolhidos por tipo de documento
  protected vigencia: number | null = null;
  protected mesEfeito = '';
  protected novas: Record<string, string> = {};
  protected arquivos: Partial<Record<Documento, File | null>> = {};

  // Alteração em andamento (se houver)
  protected readonly andamento = computed(() => this.painel()?.em_andamento ?? null);
  /** Outra alteração (do outro tipo) em andamento bloqueia esta tela. */
  protected readonly outroTipo = computed(() => {
    const a = this.andamento();
    return !!a && a.tipo !== this.tipo;
  });
  // O usuário logado já deu ciência?
  protected readonly jaRegistrei = computed(() => (this.andamento()?.ciencias ?? []).some((c) => c.usuario_id === this.autenticacao.usuario()?.id));

  /** Carrega o contrato e o painel da alteração em paralelo. */
  ngOnInit(): void {
    forkJoin({ contrato: this.contratos.consultar(this.id()), painel: this.api.alteracoes(this.id()) }).subscribe({
      next: ({ contrato, painel }) => {
        this.contrato.set(contrato);
        this.aplicar(painel);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a alteração'),
    });
  }

  /** Guarda o painel, preenche as novas quantidades e abre a aba da fase atual. */
  private aplicar(painel: PainelAlteracao): void {
    this.painel.set(painel);
    this.vigencia = painel.vigencias.at(-1)?.sequencia ?? null;
    const a = painel.em_andamento;
    if (!a) return;
    this.novas = Object.fromEntries(a.itens.map((i) => [i.item_id, paraDecimalTela(i.quantidade_nova)]));
    this.arquivos = {};
    // Abre na aba em que o processo está
    this.aba.set(!a.justificativa ? 'justificativa' : a.situacao === 'rascunho' ? 'quantitativos' : a.ciencias.length < a.ciencias_minimas ? 'memoria' : 'formalizacao');
  }

  /** Executa a chamada (com "Executando…" se houver mensagem) e aplica o painel devolvido. */
  private tratar(requisicao: ReturnType<AlteracoesApiService['alteracoes']>, titulo: string, processando?: string): void {
    (processando ? this.dialogos.executar(requisicao, processando) : requisicao).subscribe({ next: (p) => this.aplicar(p), error: (e) => this.dialogos.mostrarErro(e, titulo) });
  }

  /** Inicia a alteração para a vigência e o mês de efeito (enviado como dia 1). */
  protected abrir(): void {
    if (this.vigencia && this.mesEfeito) this.tratar(this.api.abrirAlteracao(this.id(), this.tipo, this.vigencia, `${this.mesEfeito}-01`), `Não foi possível iniciar ${this.rotuloTipo.toLowerCase()}`);
  }

  /** Anexa o documento escolhido para o tipo informado. */
  protected enviar(a: Alteracao, documento: Documento): void {
    const arquivo = this.arquivos[documento];
    if (arquivo) this.tratar(this.api.enviarDocumentoAlteracao(this.id(), a.id, documento, arquivo), 'Não foi possível anexar o documento', 'Enviando o documento…');
  }

  /** Texto digitado (formato brasileiro) como número. */
  protected numero(valor: string): number {
    return Number(paraDecimalApi(valor)) || 0;
  }

  /** Supressão de item sob demanda abaixo do já executado (a tela avisa; a API recusa). */
  protected abaixoDoExecutado(a: Alteracao, itemId: string): boolean {
    const item = a.itens.find((i) => i.item_id === itemId)!;
    return this.tipo === 'supressao' && item.tipo === 'sob_demanda' && this.numero(this.novas[itemId]) < Number(item.quantidade_executada);
  }

  /** Impacto estimado do item: diferença × preço × meses restantes (contínuo) ou × 1 (sob demanda). */
  protected impacto(a: Alteracao, itemId: string): number {
    const item = a.itens.find((i) => i.item_id === itemId)!;
    const diferenca = this.numero(this.novas[itemId]) - Number(item.quantidade_original);
    return diferenca * Number(item.valor_unitario) * (item.tipo === 'continuo' ? Number(a.meses_restantes) : 1);
  }

  /** Impacto total estimado da alteração. */
  protected impactoTotal(a: Alteracao): number {
    return a.itens.reduce((t, i) => t + this.impacto(a, i.item_id), 0);
  }

  /** Impacto em % do valor global original da vigência. */
  protected impactoPercentual(a: Alteracao): number {
    return Number(a.valor_global_original) ? (this.impactoTotal(a) * 100) / Number(a.valor_global_original) : 0;
  }

  /** Grava as novas quantidades; se já houver ciências, avisa que serão apagadas. */
  protected async salvarQuantitativos(a: Alteracao): Promise<void> {
    if (a.ciencias.length) {
      const ok = await this.dialogos.confirmar({ titulo: 'Reenviar para ciência?', mensagem: `As ${a.ciencias.length} ciências registradas serão apagadas.`, rotuloConfirmar: 'Salvar e reenviar' });
      if (!ok) return;
    }
    const itens = a.itens.map((i) => ({ item_id: i.item_id, quantidade_nova: paraDecimalApi(this.novas[i.item_id]) }));
    this.tratar(this.api.salvarQuantitativos(this.id(), a.id, itens), 'Não foi possível salvar os quantitativos');
  }

  /** Ações simples: registrar ciência, gerar memória ou gerar consolidado. */
  protected acao(a: Alteracao, acao: 'ciencia' | 'memoria' | 'consolidado', processando?: string): void {
    this.tratar(this.api.acaoAlteracao(this.id(), a.id, acao), 'Não foi possível concluir a ação', processando);
  }

  /** Confirma e conclui a alteração (aplica as quantidades ao contrato). */
  protected async concluir(a: Alteracao): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Concluir ${this.rotuloTipo.toLowerCase()}?`,
      mensagem: 'As novas quantidades serão aplicadas ao contrato a partir do mês de efeito.',
      rotuloConfirmar: 'Concluir e aplicar alteração',
      segundos: 5,
    });
    if (ok) this.tratar(this.api.acaoAlteracao(this.id(), a.id, 'concluir'), 'Não foi possível concluir a alteração');
  }

  /** Pede confirmação e cancela a alteração em andamento. */
  protected async cancelar(a: Alteracao): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Cancelar ${this.rotuloTipo.toLowerCase()}?`, mensagem: 'A alteração em andamento será cancelada.', rotuloConfirmar: 'Cancelar alteração', segundos: 3 });
    if (ok) this.tratar(this.api.acaoAlteracao(this.id(), a.id, 'cancelar'), 'Não foi possível cancelar');
  }

  /** Baixa um arquivo da alteração. */
  protected baixar(a: Alteracao, anexoId: string): void {
    this.api.baixarAlteracao(this.id(), a.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
