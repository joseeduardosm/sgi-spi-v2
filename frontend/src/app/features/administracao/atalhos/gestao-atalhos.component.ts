// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de Administração › Atalhos (CRUD de categorias e atalhos fixos).

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AtalhosFixosService, CategoriaAtalho, GravacaoAtalho } from '../../../core/navegacao/atalhos-fixos.service';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../../shared/utilitarios/erros-api';

/** Cadastro dos atalhos fixos que aparecem para todos na barra lateral, agrupados por categoria. */
@Component({
  selector: 'app-gestao-atalhos',
  imports: [FormsModule, TrilhaComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Administração' }, { rotulo: 'Atalhos' }]" />
        <h1>Atalhos</h1>
        <small>Links fixos da barra lateral, para todos os usuários (internos e externos), divididos em categorias.</small>
      </div>
    </div>

    @if (aviso(); as a) { <p class="aviso-admin" [class.erro]="a.erro" role="status">{{ a.texto }}</p> }

    <section class="painel-gestao" aria-labelledby="titulo-categoria">
      <div class="barra-ferramentas"><div><h2 id="titulo-categoria">{{ categoriaId ? 'Alterar categoria' : 'Nova categoria' }}</h2></div></div>
      <form class="grade-formulario" style="grid-template-columns: 2fr 1fr auto" (ngSubmit)="salvarCategoria()">
        <div><label for="cat-nome">Nome *</label>
          <input id="cat-nome" name="nome" class="form-control" required maxlength="80" [(ngModel)]="catNome" /></div>
        <div><label for="cat-ordem">Ordem</label>
          <input id="cat-ordem" name="ordem" type="number" min="0" max="9999" class="form-control" [(ngModel)]="catOrdem" /></div>
        <div><label class="opcao-meus"><input type="checkbox" name="ativo" [(ngModel)]="catAtivo" /> Ativa</label></div>
        <div class="ocupa-duas acoes-formulario" style="grid-column: 1 / -1">
          @if (categoriaId) { <button type="button" class="acao-secundaria" (click)="limparCategoria()">Cancelar</button> }
          <button type="submit" class="acao-primaria" [disabled]="!catNome.trim()">Salvar categoria</button>
        </div>
      </form>
    </section>

    <section class="painel-gestao" aria-labelledby="titulo-atalho">
      <div class="barra-ferramentas"><div><h2 id="titulo-atalho">{{ atalhoId ? 'Alterar atalho' : 'Novo atalho' }}</h2>
        <p>Destino: rota do SGI (<code>/contratos</code>) ou endereço externo (<code>https://…</code>).</p></div></div>
      <form class="grade-formulario" style="grid-template-columns: 1fr 1fr" (ngSubmit)="salvarAtalho()">
        <div><label for="at-cat">Categoria *</label>
          <select id="at-cat" name="cat" class="form-control" required [(ngModel)]="atCategoria">
            <option [ngValue]="0" disabled>Selecione…</option>
            @for (c of categorias(); track c.id) { <option [ngValue]="c.id">{{ c.nome }}</option> }
          </select></div>
        <div><label for="at-titulo">Título *</label>
          <input id="at-titulo" name="titulo" class="form-control" required maxlength="80" [(ngModel)]="atTitulo" /></div>
        <div class="ocupa-duas"><label for="at-url">Destino *</label>
          <input id="at-url" name="url" class="form-control" required maxlength="500" placeholder="/ramais ou https://exemplo.gov.br" [(ngModel)]="atUrl" /></div>
        <div><label for="at-ordem">Ordem</label>
          <input id="at-ordem" name="ordem" type="number" min="0" max="9999" class="form-control" [(ngModel)]="atOrdem" /></div>
        <div><label for="at-aba">Abrir em</label>
          <select id="at-aba" name="aba" class="form-control" [(ngModel)]="atAba">
            <option value="auto">Automático (externos em nova aba)</option>
            <option value="nova">Nova aba</option>
            <option value="mesma">Mesma aba</option>
          </select></div>
        <div class="ocupa-duas"><label class="opcao-meus"><input type="checkbox" name="atativo" [(ngModel)]="atAtivo" /> Ativo</label></div>
        <div class="ocupa-duas acoes-formulario">
          @if (atalhoId) { <button type="button" class="acao-secundaria" (click)="limparAtalho()">Cancelar</button> }
          <button type="submit" class="acao-primaria" [disabled]="!atTitulo.trim() || !atUrl.trim() || !atCategoria">Salvar atalho</button>
        </div>
      </form>
    </section>

    <section class="painel-gestao" aria-labelledby="titulo-lista">
      <div class="barra-ferramentas"><div><h2 id="titulo-lista">Cadastrados</h2></div></div>
      @for (c of categorias(); track c.id) {
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <caption style="text-align:left;padding:10px 15px">
              <strong>{{ c.nome }}</strong> · ordem {{ c.ordem }}@if (!c.ativo) { · <em>inativa</em> }
              <button type="button" class="acao-secundaria" (click)="editarCategoria(c)">Editar</button>
              <button type="button" class="acao-secundaria" (click)="excluirCategoria(c)">Excluir</button>
            </caption>
            <thead><tr><th>Título</th><th>Destino</th><th>Ordem</th><th>Situação</th><th></th></tr></thead>
            <tbody>
              @for (a of c.atalhos; track a.id) {
                <tr>
                  <td><strong>{{ a.titulo }}</strong></td>
                  <td>{{ a.url }} @if (a.nova_aba) { <span aria-label="nova aba">↗</span> }</td>
                  <td>{{ a.ordem }}</td>
                  <td>{{ a.ativo ? 'Ativo' : 'Inativo' }}</td>
                  <td>
                    <button type="button" class="acao-secundaria" (click)="editarAtalho(a)">Editar</button>
                    <button type="button" class="acao-secundaria" (click)="excluirAtalho(a.id, a.titulo)">Excluir</button>
                  </td>
                </tr>
              } @empty {
                <tr><td colspan="5" class="estado-vazio">Nenhum atalho nesta categoria.</td></tr>
              }
            </tbody>
          </table>
        </div>
      } @empty {
        <p class="estado-vazio">Nenhuma categoria cadastrada.</p>
      }
    </section>
  `,
})
export class GestaoAtalhosComponent implements OnInit {
  private readonly servico = inject(AtalhosFixosService);

  protected readonly categorias = signal<CategoriaAtalho[]>([]);
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);

  // Formulário da categoria
  protected categoriaId = 0;
  protected catNome = '';
  protected catOrdem = 0;
  protected catAtivo = true;

  // Formulário do atalho
  protected atalhoId = 0;
  protected atCategoria = 0;
  protected atTitulo = '';
  protected atUrl = '';
  protected atOrdem = 0;
  protected atAba: 'auto' | 'nova' | 'mesma' = 'auto';
  protected atAtivo = true;

  ngOnInit(): void {
    this.recarregar();
  }

  private recarregar(): void {
    this.servico.gestao().subscribe({
      next: (r) => this.categorias.set(r.categorias),
      error: (e) => this.avisar(erroExibivel(e).mensagem, true),
    });
  }

  private avisar(texto: string, erro = false): void {
    this.aviso.set({ texto, erro });
  }

  /** Executa a gravação, mostra o resultado e recarrega a lista. */
  private concluir(sucesso: string, aoTerminar?: () => void): { next: () => void; error: (e: unknown) => void } {
    return {
      next: () => {
        this.avisar(sucesso);
        aoTerminar?.();
        this.recarregar();
      },
      error: (e) => this.avisar(erroExibivel(e).mensagem, true),
    };
  }

  protected salvarCategoria(): void {
    const dados = { nome: this.catNome.trim(), ordem: this.catOrdem || 0, ativo: this.catAtivo };
    const chamada = this.categoriaId ? this.servico.alterarCategoria(this.categoriaId, dados) : this.servico.criarCategoria(dados);
    chamada.subscribe(this.concluir('Categoria salva.', () => this.limparCategoria()));
  }

  protected editarCategoria(c: CategoriaAtalho): void {
    this.categoriaId = c.id;
    this.catNome = c.nome;
    this.catOrdem = c.ordem;
    this.catAtivo = c.ativo;
  }

  protected limparCategoria(): void {
    this.categoriaId = 0;
    this.catNome = '';
    this.catOrdem = 0;
    this.catAtivo = true;
  }

  protected excluirCategoria(c: CategoriaAtalho): void {
    if (!confirm(`Excluir a categoria "${c.nome}" e os ${c.atalhos.length} atalho(s) dela?`)) return;
    this.servico.excluirCategoria(c.id).subscribe(this.concluir('Categoria excluída.'));
  }

  protected salvarAtalho(): void {
    const dados: GravacaoAtalho = {
      categoria_id: this.atCategoria,
      titulo: this.atTitulo.trim(),
      url: this.atUrl.trim(),
      nova_aba: this.atAba === 'auto' ? null : this.atAba === 'nova',
      ordem: this.atOrdem || 0,
      ativo: this.atAtivo,
    };
    const chamada = this.atalhoId ? this.servico.alterarAtalho(this.atalhoId, dados) : this.servico.criarAtalho(dados);
    chamada.subscribe(this.concluir('Atalho salvo.', () => this.limparAtalho()));
  }

  protected editarAtalho(a: CategoriaAtalho['atalhos'][number]): void {
    this.atalhoId = a.id;
    this.atCategoria = a.categoria_id;
    this.atTitulo = a.titulo;
    this.atUrl = a.url;
    this.atOrdem = a.ordem;
    this.atAba = a.nova_aba ? 'nova' : 'mesma';
    this.atAtivo = a.ativo;
  }

  protected limparAtalho(): void {
    this.atalhoId = 0;
    this.atTitulo = '';
    this.atUrl = '';
    this.atOrdem = 0;
    this.atAba = 'auto';
    this.atAtivo = true;
  }

  protected excluirAtalho(id: number, titulo: string): void {
    if (!confirm(`Excluir o atalho "${titulo}"?`)) return;
    this.servico.excluirAtalho(id).subscribe(this.concluir('Atalho excluído.'));
  }
}
