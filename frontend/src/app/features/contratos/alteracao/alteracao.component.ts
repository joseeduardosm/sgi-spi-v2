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

type Aba = 'justificativa' | 'quantitativos' | 'memoria' | 'formalizacao';
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
  protected readonly tipo = inject(ActivatedRoute).snapshot.data['tipo'] as 'aditamento' | 'supressao';

  protected readonly rotuloTipo = this.tipo === 'aditamento' ? 'Aditamento' : 'Supressão';
  protected readonly papeis = ROTULOS_PAPEL;
  protected readonly rotulosItem = ROTULOS_TIPO_ITEM;
  protected readonly contrato = signal<DetalheContrato | null>(null);
  protected readonly painel = signal<PainelAlteracao | null>(null);
  protected readonly aba = signal<Aba>('justificativa');
  protected vigencia: number | null = null;
  protected mesEfeito = '';
  protected novas: Record<string, string> = {};
  protected arquivos: Partial<Record<Documento, File | null>> = {};

  protected readonly andamento = computed(() => this.painel()?.em_andamento ?? null);
  /** Outra alteração (do outro tipo) em andamento bloqueia esta tela. */
  protected readonly outroTipo = computed(() => {
    const a = this.andamento();
    return !!a && a.tipo !== this.tipo;
  });
  protected readonly jaRegistrei = computed(() => (this.andamento()?.ciencias ?? []).some((c) => c.usuario_id === this.autenticacao.usuario()?.id));

  ngOnInit(): void {
    forkJoin({ contrato: this.contratos.consultar(this.id()), painel: this.api.alteracoes(this.id()) }).subscribe({
      next: ({ contrato, painel }) => {
        this.contrato.set(contrato);
        this.aplicar(painel);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a alteração'),
    });
  }

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

  private tratar(requisicao: ReturnType<AlteracoesApiService['alteracoes']>, titulo: string, processando?: string): void {
    (processando ? this.dialogos.executar(requisicao, processando) : requisicao).subscribe({ next: (p) => this.aplicar(p), error: (e) => this.dialogos.mostrarErro(e, titulo) });
  }

  protected abrir(): void {
    if (this.vigencia && this.mesEfeito) this.tratar(this.api.abrirAlteracao(this.id(), this.tipo, this.vigencia, `${this.mesEfeito}-01`), `Não foi possível iniciar ${this.rotuloTipo.toLowerCase()}`);
  }

  protected enviar(a: Alteracao, documento: Documento): void {
    const arquivo = this.arquivos[documento];
    if (arquivo) this.tratar(this.api.enviarDocumentoAlteracao(this.id(), a.id, documento, arquivo), 'Não foi possível anexar o documento', 'Enviando o documento…');
  }

  protected numero(valor: string): number {
    return Number(paraDecimalApi(valor)) || 0;
  }

  protected abaixoDoExecutado(a: Alteracao, itemId: string): boolean {
    const item = a.itens.find((i) => i.item_id === itemId)!;
    return this.tipo === 'supressao' && item.tipo === 'sob_demanda' && this.numero(this.novas[itemId]) < Number(item.quantidade_executada);
  }

  protected impacto(a: Alteracao, itemId: string): number {
    const item = a.itens.find((i) => i.item_id === itemId)!;
    const diferenca = this.numero(this.novas[itemId]) - Number(item.quantidade_original);
    return diferenca * Number(item.valor_unitario) * (item.tipo === 'continuo' ? Number(a.meses_restantes) : 1);
  }

  protected impactoTotal(a: Alteracao): number {
    return a.itens.reduce((t, i) => t + this.impacto(a, i.item_id), 0);
  }

  protected impactoPercentual(a: Alteracao): number {
    return Number(a.valor_global_original) ? (this.impactoTotal(a) * 100) / Number(a.valor_global_original) : 0;
  }

  protected async salvarQuantitativos(a: Alteracao): Promise<void> {
    if (a.ciencias.length) {
      const ok = await this.dialogos.confirmar({ titulo: 'Reenviar para ciência?', mensagem: `As ${a.ciencias.length} ciências registradas serão apagadas.`, rotuloConfirmar: 'Salvar e reenviar' });
      if (!ok) return;
    }
    const itens = a.itens.map((i) => ({ item_id: i.item_id, quantidade_nova: paraDecimalApi(this.novas[i.item_id]) }));
    this.tratar(this.api.salvarQuantitativos(this.id(), a.id, itens), 'Não foi possível salvar os quantitativos');
  }

  protected acao(a: Alteracao, acao: 'ciencia' | 'memoria' | 'consolidado', processando?: string): void {
    this.tratar(this.api.acaoAlteracao(this.id(), a.id, acao), 'Não foi possível concluir a ação', processando);
  }

  protected async concluir(a: Alteracao): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Concluir ${this.rotuloTipo.toLowerCase()}?`,
      mensagem: 'As novas quantidades serão aplicadas ao contrato a partir do mês de efeito.',
      rotuloConfirmar: 'Concluir e aplicar alteração',
      segundos: 5,
    });
    if (ok) this.tratar(this.api.acaoAlteracao(this.id(), a.id, 'concluir'), 'Não foi possível concluir a alteração');
  }

  protected async cancelar(a: Alteracao): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Cancelar ${this.rotuloTipo.toLowerCase()}?`, mensagem: 'A alteração em andamento será cancelada.', rotuloConfirmar: 'Cancelar alteração', segundos: 3 });
    if (ok) this.tratar(this.api.acaoAlteracao(this.id(), a.id, 'cancelar'), 'Não foi possível cancelar');
  }

  protected baixar(a: Alteracao, anexoId: string): void {
    this.api.baixarAlteracao(this.id(), a.id, anexoId).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
