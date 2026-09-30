// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar todas as notícias publicadas, com busca, categoria e mês guardados na URL.

import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { FiltrosArquivo, NoticiasApiService } from '../noticias-api.service';
import { Categoria, NoticiaCartao } from '../noticias.models';
import { CartaoNoticiaComponent } from './cartao-noticia.component';

const MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];

@Component({
  selector: 'app-arquivo-noticias',
  imports: [FormsModule, CartaoNoticiaComponent],
  template: `
    <div class="cabecalho-portal">
      <div><h1>Notícias</h1><small>Todas as notícias publicadas, da mais recente à mais antiga.</small></div>
    </div>
    <div class="filtros-noticias">
      <input type="search" aria-label="Buscar notícias" placeholder="Buscar por palavra" [ngModel]="filtros.busca" (ngModelChange)="digitar($event)" />
      <select aria-label="Mês" [ngModel]="mesAno()" (ngModelChange)="escolherMes($event)">
        <option value="">Qualquer data</option>
        @for (m of meses; track m.valor) { <option [value]="m.valor">{{ m.rotulo }}</option> }
      </select>
    </div>
    @if (categorias().length) {
      <div class="chips-categorias" role="group" aria-label="Categorias">
        <button type="button" [class.ativo]="!filtros.categoria" (click)="escolherCategoria(null)">Todas</button>
        @for (c of categorias(); track c.id) {
          <button type="button" [class.ativo]="filtros.categoria === c.id" [style.--cor]="c.cor" (click)="escolherCategoria(c.id)">{{ c.nome }}</button>
        }
      </div>
    }
    <p class="contagem-noticias" aria-live="polite">{{ carregando() && !itens().length ? 'Carregando…' : total() + ' notícia' + (total() === 1 ? '' : 's') }}</p>
    <div class="grade-noticias">
      @for (n of itens(); track n.id) { <app-cartao-noticia [noticia]="n" /> }
    </div>
    @if (!carregando() && !itens().length) { <p class="estado-vazio">Nenhuma notícia encontrada com esses filtros.</p> }
    @if (itens().length < total()) {
      <button type="button" class="acao-secundaria carregar-mais" [disabled]="carregando()" (click)="carregar(false)">Carregar mais</button>
    }
  `,
})
export class ArquivoNoticiasComponent implements OnInit {
  private readonly api = inject(NoticiasApiService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly destruir = inject(DestroyRef);
  protected filtros: FiltrosArquivo = { busca: '', categoria: null, ano: null, mes: null };
  protected readonly itens = signal<NoticiaCartao[]>([]);
  protected readonly total = signal(0);
  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly carregando = signal(false);
  protected readonly mesAno = signal('');
  private pagina = 1;
  private readonly digitacao = new Subject<string>();
  /** Os últimos 24 meses para o filtro de data. */
  protected readonly meses = Array.from({ length: 24 }, (_, i) => {
    const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - i);
    return { valor: `${d.getFullYear()}-${d.getMonth() + 1}`, rotulo: `${MESES[d.getMonth()]} de ${d.getFullYear()}` };
  });

  ngOnInit(): void {
    this.api.portal().subscribe({ next: (p) => this.categorias.set(p.categorias), error: () => undefined });
    this.rota.queryParamMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((q) => {
      this.filtros = { busca: q.get('busca') ?? '', categoria: q.get('categoria') ? Number(q.get('categoria')) : null,
                       ano: q.get('ano') ? Number(q.get('ano')) : null, mes: q.get('mes') ? Number(q.get('mes')) : null };
      this.mesAno.set(this.filtros.ano && this.filtros.mes ? `${this.filtros.ano}-${this.filtros.mes}` : '');
      this.carregar(true);
    });
    this.digitacao.pipe(debounceTime(350), takeUntilDestroyed(this.destruir)).subscribe((b) => this.navegar({ busca: b.trim() || null }));
  }

  protected carregar(reiniciar: boolean): void {
    this.pagina = reiniciar ? 1 : this.pagina + 1;
    this.carregando.set(true);
    this.api.publicas(this.filtros, this.pagina).subscribe({
      next: (p) => { this.itens.set(reiniciar ? p.itens : [...this.itens(), ...p.itens]); this.total.set(p.total); this.carregando.set(false); },
      error: () => this.carregando.set(false),
    });
  }

  protected digitar(v: string): void { this.digitacao.next(v); }

  protected escolherCategoria(id: number | null): void { this.navegar({ categoria: id }); }

  protected escolherMes(valor: string): void {
    const [ano, mes] = valor ? valor.split('-').map(Number) : [null, null];
    this.navegar({ ano, mes });
  }

  private navegar(params: Record<string, string | number | null>): void {
    void this.roteador.navigate([], { relativeTo: this.rota, queryParams: params, queryParamsHandling: 'merge', replaceUrl: true });
  }
}
