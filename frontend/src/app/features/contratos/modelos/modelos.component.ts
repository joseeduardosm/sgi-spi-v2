import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DefinicaoFormulario, Modelo } from '../compartilhado/contratos.models';
import { definicaoVazia, EditorFormularioComponent } from '../detalhe/editor-formulario.component';

/** Modelos globais (SuperRoot): checklists e formulários clonados nos contratos. */
@Component({
  selector: 'app-modelos',
  imports: [FormsModule, DatePipe, CabecalhoModuloComponent, EditorFormularioComponent],
  host: { '(document:keydown.escape)': 'checklistAberto.set(false)' },
  template: `
    <app-cabecalho-modulo titulo="Modelos globais" [trilha]="['Modelos']" descricao="Checklists e formulários de avaliação que as equipes copiam para os contratos. As cópias não mudam quando o modelo muda." />
    <div class="duas-colunas">
      @for (tipo of tipos; track tipo.id) {
        <section class="cartao-dados" [attr.aria-labelledby]="'titulo-modelos-' + tipo.id">
          <header>
            <h2 [id]="'titulo-modelos-' + tipo.id">{{ tipo.rotulo }}</h2>
            <button type="button" class="acao-primaria acao-pequena" (click)="abrir(tipo.id)">+ Novo</button>
          </header>
          <div class="corpo">
            @for (m of doTipo(tipo.id); track m.id) {
              <article class="indicador" style="margin-bottom: 10px">
                <div style="display: flex; justify-content: space-between; gap: 8px">
                  <strong style="font-size: 14px">{{ m.nome }}</strong>
                  <span class="selo-situacao" [class.inativo]="!m.ativo">{{ m.ativo ? 'Ativo' : 'Inativo' }}</span>
                </div>
                <small>{{ m.tipo === 'checklist' ? (m.conteudo.itens?.length ?? 0) + ' documento(s)' : (m.conteudo.grupos?.length ?? 0) + ' grupo(s)' }} · atualizado em {{ m.atualizado_em | date: 'dd/MM/yyyy' }}</small>
                <div class="acoes-cartao esquerda">
                  <button type="button" class="acao-secundaria acao-pequena" (click)="abrir(m.tipo, m)">Editar</button>
                  <button type="button" class="acao-perigo acao-pequena" (click)="excluir(m)">Excluir</button>
                </div>
              </article>
            } @empty { <p class="estado-vazio">Nenhum modelo.</p> }
          </div>
        </section>
      }
    </div>

    @if (checklistAberto()) {
      <div class="fundo-modal" role="presentation" (click)="checklistAberto.set(false)"></div>
      <section class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-modelo-checklist">
        <header><div><span class="modal-sobretitulo">Modelo global</span><h2 id="titulo-modelo-checklist">Checklist</h2></div>
          <button type="button" aria-label="Fechar" (click)="checklistAberto.set(false)">×</button></header>
        <form (ngSubmit)="salvarChecklist()">
          <div class="grade-formulario">
            <div><label for="modelo-nome">Nome *</label><input id="modelo-nome" name="nome" required [(ngModel)]="nome" /></div>
            <div class="linha-caixas" style="align-self: end"><label><input type="checkbox" name="ativo" [(ngModel)]="ativo" /> Ativo</label></div>
          </div>
          @for (i of itens; track $index) {
            <div class="grade-formulario" style="grid-template-columns: 2fr 2fr 1fr auto">
              <div><label [for]="'modelo-doc-' + $index">Documento</label><input [id]="'modelo-doc-' + $index" [name]="'doc' + $index" [(ngModel)]="i.nome" /></div>
              <div><label [for]="'modelo-obs-' + $index">Observação</label><input [id]="'modelo-obs-' + $index" [name]="'obs' + $index" [(ngModel)]="i.observacao" /></div>
              <div><label [for]="'modelo-obr-' + $index">Tipo</label>
                <select [id]="'modelo-obr-' + $index" [name]="'obr' + $index" [(ngModel)]="i.obrigatorio">
                  <option [ngValue]="true">Obrigatório</option><option [ngValue]="false">Opcional</option>
                </select></div>
              <div style="align-self: center"><button type="button" class="link-arquivo" (click)="itens.splice($index, 1)">remover</button></div>
            </div>
          }
          <button type="button" class="acao-secundaria acao-pequena" (click)="itens.push({ nome: '', observacao: '', obrigatorio: true })">+ Documento</button>
          <footer style="margin-top: 16px">
            <button type="button" class="acao-secundaria" (click)="checklistAberto.set(false)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!nome.trim() || !itens.length || itens.some(i => !i.nome.trim())">Salvar modelo</button>
          </footer>
        </form>
      </section>
    }

    @if (formularioAberto()) {
      <app-editor-formulario titulo="Modelo de formulário" [nomeInicial]="emEdicao?.nome ?? ''" [definicaoInicial]="definicaoInicial()"
                             rotuloSalvar="Salvar modelo" (salvar)="salvarFormulario($event)" (fechar)="formularioAberto.set(false)" />
    }
  `,
})
export class ModelosComponent implements OnInit {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tipos = [{ id: 'checklist' as const, rotulo: 'Checklists' }, { id: 'formulario' as const, rotulo: 'Formulários de avaliação' }];
  protected readonly modelos = signal<Modelo[]>([]);
  protected readonly checklistAberto = signal(false);
  protected readonly formularioAberto = signal(false);
  protected emEdicao: Modelo | null = null;
  protected nome = '';
  protected ativo = true;
  protected itens: { nome: string; observacao: string; obrigatorio: boolean }[] = [];

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.modelos(undefined, false).subscribe({ next: (m) => this.modelos.set(m), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected doTipo(tipo: string): Modelo[] {
    return this.modelos().filter((m) => m.tipo === tipo);
  }

  protected definicaoInicial(): DefinicaoFormulario {
    const c = this.emEdicao?.conteudo;
    return c?.grupos ? { escala: c.escala ?? [], faixas: c.faixas ?? [], grupos: c.grupos } : definicaoVazia();
  }

  protected abrir(tipo: 'checklist' | 'formulario', modelo?: Modelo): void {
    this.emEdicao = modelo ?? null;
    this.nome = modelo?.nome ?? '';
    this.ativo = modelo?.ativo ?? true;
    if (tipo === 'checklist') {
      this.itens = (modelo?.conteudo.itens ?? []).map((i) => ({ nome: i.nome, observacao: i.observacao ?? '', obrigatorio: i.obrigatorio ?? true }));
      this.checklistAberto.set(true);
    } else {
      this.formularioAberto.set(true);
    }
  }

  protected salvarChecklist(): void {
    const dados = { tipo: 'checklist', nome: this.nome.trim(), ativo: this.ativo, itens: this.itens.map((i) => ({ nome: i.nome.trim(), observacao: i.observacao.trim(), obrigatorio: i.obrigatorio })) };
    this.api.salvarModelo(dados, this.emEdicao?.id).subscribe({
      next: () => {
        this.checklistAberto.set(false);
        this.carregar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o modelo'),
    });
  }

  protected salvarFormulario(evento: { nome: string; definicao: DefinicaoFormulario }): void {
    this.api.salvarModelo({ tipo: 'formulario', nome: evento.nome, ativo: this.emEdicao?.ativo ?? true, definicao: evento.definicao }, this.emEdicao?.id).subscribe({
      next: () => {
        this.formularioAberto.set(false);
        this.carregar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o modelo'),
    });
  }

  protected async excluir(modelo: Modelo): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: `Excluir o modelo "${modelo.nome}"?`, mensagem: 'As cópias já feitas nos contratos não mudam.', rotuloConfirmar: 'Excluir' });
    if (ok) this.api.excluirModelo(modelo.id).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
