// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a aba "Formulários de avaliação": versões do formulário e a janela de edição.

import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DefinicaoFormulario, Formulario, Modelo } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ImportacaoModeloXlsxComponent } from '../compartilhado/importacao-modelo-xlsx.component';
import { EditorFormularioComponent, definicaoVazia } from './editor-formulario.component';

/** Aba "Formulários de avaliação": versões do formulário usado na etapa 2 (opcional). */
@Component({
  selector: 'app-aba-formularios',
  imports: [FormsModule, DatePipe, EditorFormularioComponent, ImportacaoModeloXlsxComponent],
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-formularios">
      <header>
        <div><h2 id="titulo-formularios">Formulários de avaliação</h2><small>Opcional. Sem formulário ativo, a competência vai da medição direto para a nota fiscal.</small></div>
        @if (podeEditar()) {
          <div class="acoes-cartao">
            <app-importacao-modelo-xlsx tipo="formulario" [contratoId]="contratoId()" (importado)="recarregar()" />
            <button type="button" class="acao-primaria" (click)="abrir()"><span>+</span> Gerar formulário</button>
          </div>
        }
      </header>
      <div class="corpo">
        @if (formularios().length > 1) {
          <div class="barra-dobrar"><button type="button" class="link-arquivo" (click)="expandirTodos(true)">Expandir todos</button><button type="button" class="link-arquivo" (click)="expandirTodos(false)">Recolher todos</button></div>
        }
        @for (f of formularios(); track f.id) {
          <article class="indicador cartao-dobravel" style="margin-bottom: 12px">
            <button type="button" class="cabecalho-dobravel" [attr.aria-expanded]="aberta(f)" [attr.aria-controls]="'formulario-' + f.id" (click)="alternar(f)">
              <span class="seta" [class.aberta]="aberta(f)" aria-hidden="true">▸</span>
              <strong style="font-size: 14px">v{{ f.versao }} · {{ f.nome }}</strong>
              <small>{{ f.definicao.escala.length }} notas · {{ f.definicao.grupos.length }} grupos · {{ f.definicao.faixas.length }} faixas</small>
              <span class="selo-situacao" [class.inativo]="!f.ativo">{{ f.ativo ? 'Ativo' : 'Inativo' }}</span>
            </button>
            @if (aberta(f)) {
            <div [id]="'formulario-' + f.id" class="detalhe-formulario">
              <div class="bloco-formulario"><b>Escala de notas</b>
                <ul>@for (n of f.definicao.escala; track $index) { <li>{{ n.valor }} — {{ n.legenda }}</li> }</ul></div>
              @for (g of f.definicao.grupos; track $index) {
                <div class="bloco-formulario"><b>{{ g.nome }}</b>
                  <ul>@for (i of g.itens; track $index) { <li>{{ i.nome }} <span class="etiqueta">peso {{ i.peso }}%</span>@if (i.descricao) { <small style="display: inline; color: #8e99a6"> — {{ i.descricao }}</small> }</li> }</ul></div>
              }
              <div class="bloco-formulario"><b>Faixas de liberação do pagamento</b>
                <ul>@for (x of f.definicao.faixas; track $index) { <li>{{ x.minimo }} a {{ x.maximo ?? '…' }} → {{ x.percentual }}% liberado</li> }</ul></div>
            </div>
            }
            <small>Criado por {{ f.criado_por_nome }} em {{ f.criado_em | date: 'dd/MM/yyyy HH:mm' }}</small>
            @if (podeEditar()) {
              <div class="acoes-cartao esquerda">
                @if (!f.ativo) {
                  <button type="button" class="acao-primaria acao-pequena" (click)="ativar(f)">Ativar</button>
                  <button type="button" class="acao-secundaria acao-pequena" (click)="abrir(f)">Editar</button>
                  <button type="button" class="acao-perigo acao-pequena" (click)="excluir(f)">Excluir</button>
                }
                <button type="button" class="acao-secundaria acao-pequena" (click)="duplicar(f)">Duplicar</button>
              </div>
            }
          </article>
        } @empty {
          <p class="estado-vazio">Nenhum formulário cadastrado.</p>
        }
      </div>
    </section>

    @if (aberto()) {
      <app-editor-formulario [titulo]="emEdicao ? 'Editar formulário v' + emEdicao.versao : 'Gerar formulário'" [nomeInicial]="emEdicao?.nome ?? ''"
                             [definicaoInicial]="emEdicao?.definicao ?? definicaoVazia()" [modelos]="modelos()" rotuloSalvar="Salvar versão inativa"
                             (salvar)="salvar($event)" (fechar)="aberto.set(false)" />
    }
  `,
})
export class AbaFormulariosComponent implements OnInit {
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);

  private readonly api = inject(ExecucaoApiService);
  private readonly contratos = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  // Versões, modelos globais e o estado da janela do editor
  protected readonly formularios = signal<Formulario[]>([]);
  protected readonly modelos = signal<Modelo[]>([]);
  protected readonly aberto = signal(false);
  // Função exposta ao template para iniciar um formulário novo com valores de exemplo
  protected readonly definicaoVazia = definicaoVazia;
  protected emEdicao: Formulario | null = null;
  // Versões abertas na lista: todas entram recolhidas e só abrem quando a pessoa clica
  private readonly abertas = signal<Record<string, boolean>>({});

  protected aberta(f: Formulario): boolean {
    return this.abertas()[f.id] ?? false;
  }

  protected alternar(f: Formulario): void {
    this.abertas.update((a) => ({ ...a, [f.id]: !this.aberta(f) }));
  }

  protected expandirTodos(abrir: boolean): void {
    this.abertas.set(Object.fromEntries(this.formularios().map((f) => [f.id, abrir])));
  }

  /** Carrega as versões do contrato e os modelos globais de formulário. */
  ngOnInit(): void {
    this.api.formularios(this.contratoId()).subscribe({ next: (f) => this.formularios.set(f), error: (e) => this.dialogos.mostrarErro(e) });
    this.contratos.modelos('formulario').subscribe({ next: (m) => this.modelos.set(m), error: () => this.modelos.set([]) });
  }

  /** Recarrega as versões (depois de importar uma planilha). */
  protected recarregar(): void {
    this.api.formularios(this.contratoId()).subscribe({ next: (f) => this.formularios.set(f), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Abre o editor: vazio (nova versão) ou com a versão escolhida. */
  protected abrir(formulario?: Formulario): void {
    this.emEdicao = formulario ?? null;
    this.aberto.set(true);
  }

  /** Salva a versão (sempre inativa) com o que veio do editor. */
  protected salvar(evento: { nome: string; definicao: DefinicaoFormulario }): void {
    this.api.salvarFormulario(this.contratoId(), evento, this.emEdicao?.id).subscribe({
      next: (f) => {
        this.formularios.set(f);
        this.aberto.set(false);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o formulário'),
    });
  }

  /** Ativa a versão depois de confirmar. */
  /** Pede confirmação e exclui a versão inativa (as avaliações que já a usaram guardam a própria cópia). */
  protected async excluir(formulario: Formulario): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Excluir a versão v${formulario.versao}?`, mensagem: 'A versão inativa deixa de aparecer na lista. As avaliações que já usaram esta versão não mudam.', rotuloConfirmar: 'Excluir',
    });
    if (ok) this.api.excluirFormulario(this.contratoId(), formulario.id).subscribe({ next: (l) => this.formularios.set(l), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected async ativar(formulario: Formulario): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: `Ativar o formulário v${formulario.versao}?`,
      mensagem: 'Ele passa a valer para as competências geradas daqui em diante e para as que ainda estão na medição.',
      rotuloConfirmar: 'Ativar',
      segundos: 3,
    });
    if (ok) this.api.acaoFormulario(this.contratoId(), formulario.id, 'ativar').subscribe({ next: (f) => this.formularios.set(f), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Cria uma cópia inativa da versão. */
  protected duplicar(formulario: Formulario): void {
    this.api.acaoFormulario(this.contratoId(), formulario.id, 'duplicar').subscribe({ next: (f) => this.formularios.set(f), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
