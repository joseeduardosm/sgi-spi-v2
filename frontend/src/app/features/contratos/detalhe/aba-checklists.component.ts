// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a aba "Checklists": versões do checklist mensal e a janela de edição.

import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { Checklist, Modelo } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ImportacaoModeloXlsxComponent } from '../compartilhado/importacao-modelo-xlsx.component';
import { LinkificarPipe } from '../../../shared/utilitarios/linkificar.pipe';

/** Aba "Checklists": versões do checklist de documentos mensais (etapa 5 da execução). */
@Component({
  selector: 'app-aba-checklists',
  imports: [LinkificarPipe, FormsModule, DatePipe, ImportacaoModeloXlsxComponent],
  templateUrl: './aba-checklists.component.html',
  // Esc fecha a janela de edição
  host: { '(document:keydown.escape)': 'aberto.set(false)' },
})
export class AbaChecklistsComponent implements OnInit {
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);

  private readonly api = inject(ExecucaoApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  // Versões carregadas, modelos globais disponíveis e o estado da janela
  protected readonly checklists = signal<Checklist[]>([]);
  protected readonly modelos = signal<Modelo[]>([]);
  protected readonly aberto = signal(false);
  protected emEdicao: Checklist | null = null;
  protected nome = '';
  // Documentos da versão em edição e os campos da linha "adicionar documento"
  protected itens: { nome: string; observacao: string; obrigatorio: boolean; com_validade: boolean; vale_outros_contratos: boolean }[] = [];
  protected novoDocumento = '';
  protected novaObservacao = '';
  protected novoObrigatorio = true;
  protected novoComValidade = false;
  protected novoValeOutros = false;
  // Versões abertas na lista: todas entram recolhidas e só abrem quando a pessoa clica
  private readonly abertas = signal<Record<string, boolean>>({});

  /** Carrega as versões do contrato e os modelos globais de checklist. */
  ngOnInit(): void {
    this.api.checklists(this.contratoId()).subscribe({ next: (c) => this.checklists.set(c), error: (e) => this.dialogos.mostrarErro(e) });
    this.contratos.modelos('checklist').subscribe({ next: (m) => this.modelos.set(m), error: () => this.modelos.set([]) });
  }

  /** Recarrega as versões (depois de importar uma planilha). */
  protected recarregar(): void {
    this.api.checklists(this.contratoId()).subscribe({ next: (c) => this.checklists.set(c), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** A versão está aberta? Sem escolha do usuário, só a ativa aparece aberta. */
  protected aberta(c: Checklist): boolean {
    return this.abertas()[c.id] ?? false;
  }

  protected alternar(c: Checklist): void {
    this.abertas.update((a) => ({ ...a, [c.id]: !this.aberta(c) }));
  }

  protected expandirTodos(abrir: boolean): void {
    this.abertas.set(Object.fromEntries(this.checklists().map((c) => [c.id, abrir])));
  }

  /** Abre a janela: vazia (nova versão) ou com a versão escolhida (edição). */
  protected abrir(checklist?: Checklist): void {
    this.emEdicao = checklist ?? null;
    this.nome = checklist?.nome ?? '';
    this.itens = checklist?.itens.map((i) => ({ nome: i.nome, observacao: i.observacao, obrigatorio: i.obrigatorio, com_validade: i.com_validade, vale_outros_contratos: i.vale_outros_contratos ?? false })) ?? [];
    this.novoDocumento = this.novaObservacao = '';
    this.novoObrigatorio = true;
    this.novoComValidade = false;
    this.novoValeOutros = false;
    this.aberto.set(true);
  }

  /** Copia os documentos de um modelo global para a janela (o nome só é preenchido se estiver vazio). */
  protected carregarModelo(id: string): void {
    const modelo = this.modelos().find((m) => m.id === id);
    if (!modelo) return;
    this.nome ||= modelo.nome;
    this.itens = (modelo.conteudo.itens ?? []).map((i) => ({ nome: i.nome, observacao: i.observacao ?? '', obrigatorio: i.obrigatorio ?? true, com_validade: i.com_validade ?? false, vale_outros_contratos: i.vale_outros_contratos ?? false }));
  }

  /** Acrescenta o documento digitado à lista (obrigatório por padrão). */
  protected adicionar(): void {
    if (!this.novoDocumento.trim()) return;
    this.itens = [...this.itens, { nome: this.novoDocumento.trim(), observacao: this.novaObservacao.trim(), obrigatorio: this.novoObrigatorio, com_validade: this.novoComValidade, vale_outros_contratos: this.novoComValidade && this.novoValeOutros }];
    this.novoDocumento = this.novaObservacao = '';
    this.novoObrigatorio = true;
    this.novoComValidade = false;
    this.novoValeOutros = false;
  }

  /** Sobe (−1) ou desce (+1) um documento, trocando-o de lugar com o vizinho (a ordem vale na competência). */
  protected mover(indice: number, deslocamento: number): void {
    const destino = indice + deslocamento;
    if (destino < 0 || destino >= this.itens.length) return;
    const lista = [...this.itens];
    [lista[indice], lista[destino]] = [lista[destino], lista[indice]];
    this.itens = lista;
  }

  /** Quantos documentos da lista são obrigatórios (resumo no rodapé da janela). */
  protected obrigatorios(): number {
    return this.itens.filter((i) => i.obrigatorio).length;
  }

  /** Remove um documento da lista. */
  protected remover(indice: number): void {
    this.itens = this.itens.filter((_, i) => i !== indice);
  }

  /** Salva a versão (sempre inativa); a API devolve a lista atualizada. */
  protected salvar(): void {
    this.api.salvarChecklist(this.contratoId(), { nome: this.nome.trim(), itens: this.itens }, this.emEdicao?.id).subscribe({
      next: (c) => {
        this.checklists.set(c);
        this.aberto.set(false);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o checklist'),
    });
  }

  /** Ativa a versão depois de confirmar (ela passa a valer nas competências abertas). */
  protected async ativar(checklist: Checklist): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Ativar a versão v${checklist.versao}?`,
      mensagem: 'A nova versão passa a valer para as competências que ainda não iniciaram o checklist (cada uma copia o checklist ativo ao concluir a nota fiscal). Checklists já copiados não mudam; para refazer um, reabra a nota fiscal da competência.',
      rotuloConfirmar: 'Ativar',
      segundos: 3,
    });
    if (ok) this.api.acaoChecklist(this.contratoId(), checklist.id, 'ativar').subscribe({ next: (c) => this.checklists.set(c), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Baixa a versão como planilha XLSX já preenchida. */
  protected baixarXlsx(checklist: Checklist): void {
    this.api.baixarModeloXlsx(this.contratoId(), 'checklists', checklist.id).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar a planilha') });
  }

  /** Cria uma cópia inativa da versão. */
  protected duplicar(checklist: Checklist): void {
    this.api.acaoChecklist(this.contratoId(), checklist.id, 'duplicar').subscribe({ next: (c) => this.checklists.set(c), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Pede confirmação e exclui a versão inativa. */
  protected async excluir(checklist: Checklist): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir a versão v${checklist.versao}?`, mensagem: 'A versão inativa deixa de aparecer na lista.', rotuloConfirmar: 'Excluir' });
    if (ok) this.api.excluirChecklist(this.contratoId(), checklist.id).subscribe({ next: (c) => this.checklists.set(c), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
