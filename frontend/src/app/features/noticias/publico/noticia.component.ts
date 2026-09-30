// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir uma notícia publicada: capa, texto, anexos (PDF incorporado) e "leia também".

import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { NoticiasApiService } from '../noticias-api.service';
import { dataCurta, NoticiaPublica, srcsetCapa, tamanhoLegivel } from '../noticias.models';
import { CartaoNoticiaComponent } from './cartao-noticia.component';

@Component({
  selector: 'app-noticia',
  imports: [RouterLink, CartaoNoticiaComponent],
  template: `
    @if (noticia(); as n) {
      <article class="noticia-publica">
        <p class="trilha-noticia"><a routerLink="/">Início</a> <span>/</span> <a routerLink="/noticias">Notícias</a></p>
        <header>
          @if (n.categoria) { <a class="chip-categoria" [style.--cor]="n.categoria.cor" routerLink="/noticias" [queryParams]="{ categoria: n.categoria.id }">{{ n.categoria.nome }}</a> }
          <h1>{{ n.titulo }}</h1>
          @if (n.linha_fina) { <p class="linha-fina-noticia">{{ n.linha_fina }}</p> }
          <div class="meta-noticia">
            <span>{{ data(n.publicada_em) }}</span>
            <button type="button" class="link-simples" (click)="copiarLink()">{{ copiado() ? 'Link copiado' : 'Copiar link' }}</button>
          </div>
        </header>
        @if (n.capa['1600']) {
          <img class="capa-noticia" [src]="n.capa['1600']" [srcset]="srcset(n)" sizes="(max-width: 1000px) 100vw, 960px" [alt]="n.capa_alt" />
        }
        <div class="corpo-noticia" [innerHTML]="n.corpo_html"></div>
        @if (n.anexos.length) {
          <section class="anexos-noticia" aria-label="Anexos">
            <h2>Anexos</h2>
            @for (a of n.anexos; track a.id) {
              <a class="anexo-noticia" [href]="a.url" target="_blank" rel="noopener">{{ a.nome }} <small>{{ tamanho(a.tamanho) }}</small></a>
            }
            @if (pdf(); as url) { <iframe class="pdf-noticia" [src]="url" title="Anexo em PDF"></iframe> }
          </section>
        }
      </article>
      @if (n.leia_tambem.length) {
        <section class="leia-tambem" aria-label="Leia também">
          <h2>Leia também</h2>
          <div class="grade-noticias">@for (x of n.leia_tambem; track x.id) { <app-cartao-noticia [noticia]="x" [mostrarLinhaFina]="false" /> }</div>
        </section>
      }
    } @else if (naoEncontrada()) {
      <div class="estado-vazio"><p>Notícia não encontrada ou ainda não publicada.</p><a routerLink="/noticias">Ver todas as notícias</a></div>
    } @else {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class NoticiaComponent implements OnInit {
  private readonly api = inject(NoticiasApiService);
  private readonly rota = inject(ActivatedRoute);
  private readonly destruir = inject(DestroyRef);
  private readonly sanitizador = inject(DomSanitizer);
  protected readonly noticia = signal<NoticiaPublica | null>(null);
  protected readonly naoEncontrada = signal(false);
  protected readonly copiado = signal(false);
  protected readonly data = dataCurta;
  protected readonly tamanho = tamanhoLegivel;
  protected readonly srcset = (n: NoticiaPublica) => srcsetCapa(n.capa);
  /** O primeiro PDF anexado aparece incorporado na página (a URL é da própria API). */
  protected readonly pdf = computed<SafeResourceUrl | null>(() => {
    const a = this.noticia()?.anexos.find((x) => x.tipo === 'application/pdf');
    return a ? this.sanitizador.bypassSecurityTrustResourceUrl(a.url) : null;
  });

  ngOnInit(): void {
    this.rota.paramMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((p) => {
      this.noticia.set(null);
      this.naoEncontrada.set(false);
      this.api.publica(p.get('slug') ?? '').subscribe({
        next: (n) => { this.noticia.set(n); document.title = `${n.titulo} | SGI SPI`; window.scrollTo(0, 0); },
        error: () => this.naoEncontrada.set(true),
      });
    });
  }

  protected copiarLink(): void {
    void navigator.clipboard?.writeText(location.href).then(() => { this.copiado.set(true); setTimeout(() => this.copiado.set(false), 2000); });
  }
}
