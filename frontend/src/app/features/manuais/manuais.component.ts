// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela inicial dos Manuais: estantes com seus livros e a busca.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ListaManuais, ManuaisService, ResultadoBuscaManual } from '../../core/manuais/manuais.service';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../shared/utilitarios/erros-api';

/** Manuais do BookStack: estantes e livros; a busca pesquisa o conteúdo de todas as páginas. */
@Component({
  selector: 'app-manuais',
  imports: [FormsModule, RouterLink, TrilhaComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Manuais' }]" />
        <h1>Manuais</h1>
        <small>Instruções e procedimentos do SPI. O conteúdo é mantido no BookStack e exibido aqui.</small>
      </div>
    </div>

    <form class="manuais-busca" role="search" (ngSubmit)="buscar()">
      <input type="search" name="q" class="form-control" placeholder="Pesquisar nos manuais…" aria-label="Pesquisar nos manuais" maxlength="100" [(ngModel)]="termo" />
      <button type="submit" class="acao-primaria" [disabled]="termo.trim().length < 2">Pesquisar</button>
      @if (resultados() !== null) { <button type="button" class="acao-secundaria" (click)="limpar()">Limpar</button> }
    </form>

    @if (erro()) { <p class="aviso-admin erro" role="alert">{{ erro() }}</p> }

    @if (resultados(); as lista) {
      <section class="painel-gestao manuais-painel" aria-label="Resultados da pesquisa">
        <div class="barra-ferramentas"><div><h2>Resultados</h2><p>{{ lista.length }} encontrado(s) para "{{ ultimaBusca }}"</p></div></div>
        @for (r of lista; track r.tipo + r.id) {
          <a class="manuais-resultado" [routerLink]="r.rota">
            <strong>{{ r.nome }}</strong>
            <small>{{ r.tipo === 'pagina' ? 'Página' : r.tipo === 'capitulo' ? 'Capítulo' : 'Livro' }}@if (r.livro_nome && r.tipo !== 'livro') { · {{ r.livro_nome }} }</small>
            @if (r.trecho) { <span class="manuais-trecho" [innerHTML]="r.trecho"></span> }
          </a>
        } @empty { <p class="estado-vazio">Nada encontrado.</p> }
      </section>
    } @else if (lista(); as l) {
      @for (e of l.estantes; track e.id) {
        <section class="painel-gestao manuais-painel" [attr.aria-label]="e.nome">
          <div class="barra-ferramentas"><div><h2>{{ e.nome }}</h2>@if (e.descricao) { <p>{{ e.descricao }}</p> }</div></div>
          <div class="manuais-grade">
            @for (livro of e.livros; track livro.id) {
              <a class="manuais-livro" [routerLink]="['/manuais/livros', livro.id]"><strong>{{ livro.nome }}</strong>@if (livro.descricao) { <small>{{ livro.descricao }}</small> }</a>
            } @empty { <p class="estado-vazio">Nenhum livro nesta estante.</p> }
          </div>
        </section>
      }
      @if (l.livros_avulsos.length) {
        <section class="painel-gestao manuais-painel" aria-label="Outros livros">
          <div class="barra-ferramentas"><div><h2>Outros livros</h2></div></div>
          <div class="manuais-grade">
            @for (livro of l.livros_avulsos; track livro.id) {
              <a class="manuais-livro" [routerLink]="['/manuais/livros', livro.id]"><strong>{{ livro.nome }}</strong>@if (livro.descricao) { <small>{{ livro.descricao }}</small> }</a>
            }
          </div>
        </section>
      }
      @if (!l.estantes.length && !l.livros_avulsos.length) { <p class="estado-vazio">Nenhum manual disponível ainda.</p> }
    } @else if (!erro()) {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class ManuaisComponent implements OnInit {
  private readonly api = inject(ManuaisService);
  private readonly roteador = inject(Router);

  protected readonly lista = signal<ListaManuais | null>(null);
  protected readonly resultados = signal<ResultadoBuscaManual[] | null>(null);
  protected readonly erro = signal('');
  protected termo = '';
  protected ultimaBusca = '';

  ngOnInit(): void {
    this.api.listar().subscribe({
      next: (l) => {
        // Com um único livro disponível (ex.: só o SGI SPI), não há o que escolher: abre direto nele
        const livros = [...l.estantes.flatMap((e) => e.livros), ...l.livros_avulsos];
        if (livros.length === 1) void this.roteador.navigate(['/manuais/livros', livros[0].id], { replaceUrl: true });
        else this.lista.set(l);
      }, error: (e) => this.erro.set(erroExibivel(e).mensagem) });
  }

  protected buscar(): void {
    const termo = this.termo.trim();
    if (termo.length < 2) return;
    this.erro.set('');
    this.api.buscar(termo).subscribe({
      next: (r) => { this.ultimaBusca = termo; this.resultados.set(r.itens); },
      error: (e) => this.erro.set(erroExibivel(e).mensagem),
    });
  }

  protected limpar(): void {
    this.termo = '';
    this.resultados.set(null);
  }
}
