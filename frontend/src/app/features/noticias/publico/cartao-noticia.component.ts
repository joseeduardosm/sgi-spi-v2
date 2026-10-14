// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir uma notícia em cartão (capa 2:1, categoria, título e data) ou no formato Tweet Card (autor, texto e mídia).

import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { dataCurta, NoticiaCartao, srcsetCapa } from '../noticias.models';

@Component({
  selector: 'app-cartao-noticia',
  imports: [RouterLink],
  template: `
    @let n = noticia();
    @if (formato() === 'tweet') {
      <a class="cartao-tweet" [routerLink]="['/noticias', n.slug]">
        <span class="tweet-cabecalho">
          <span class="tweet-avatar" aria-hidden="true">SPI</span>
          <span class="tweet-autor">
            <span class="tweet-nome">SGI SPI
              <svg class="tweet-selo" viewBox="0 0 22 22" aria-label="Fonte oficial" role="img"><path fill="currentColor" d="M20.4 11c0-.9-.5-1.7-1.2-2.2.3-.8.2-1.8-.4-2.5s-1.5-1-2.4-.9c-.4-.8-1.2-1.3-2.1-1.3-.8-.2-1.6.1-2.3.6-.7-.5-1.5-.8-2.3-.6-.9 0-1.7.6-2.1 1.300-.9-.1-1.8.2-2.400.9s-.7 1.7-.4 2.500C3.100 9.300 2.600 10.100 2.600 11s.5 1.7 1.2 2.2c-.3.8-.2 1.8.4 2.500s1.5 1 2.400.9c.4.8 1.2 1.300 2.1 1.300.8.2 1.6-.1 2.3-.6.7.5 1.5.8 2.3.6.9 0 1.7-.6 2.1-1.300.9.1 1.8-.2 2.400-.9s.7-1.7.4-2.500c.7-.5 1.2-1.300 1.2-2.2Z"/><path fill="#fff" d="m9.900 14.500-2.600-2.600 1-1 1.6 1.6 3.700-3.8 1 1z"/></svg>
            </span>
            <span class="tweet-usuario">{{ n.categoria ? '@' + n.categoria.nome : '@spi' }} · {{ data(n.publicada_em) }}</span>
          </span>
        </span>
        <span class="tweet-texto"><strong>{{ n.titulo }}</strong>@if (n.linha_fina) { <span class="linha-fina">{{ n.linha_fina }}</span> }</span>
        @if (n.capa['800']) {
          <span class="tweet-midia"><img [src]="n.capa['800']" [srcset]="srcset(n)" sizes="(max-width: 700px) 100vw, 360px" [alt]="n.capa_alt" loading="lazy" /></span>
        }
      </a>
    } @else {
    <a class="cartao-noticia" [class.horizontal]="horizontal()" [routerLink]="['/noticias', n.slug]">
      <span class="capa-cartao">
        @if (n.capa['800']) { <img [src]="n.capa['800']" [srcset]="srcset(n)" sizes="(max-width: 700px) 100vw, 360px" [alt]="n.capa_alt" loading="lazy" /> }
      </span>
      <span class="texto-cartao">
        @if (n.categoria) { <span class="chip-categoria" [style.--cor]="n.categoria.cor">{{ n.categoria.nome }}</span> }
        <strong>{{ n.titulo }}</strong>
        @if (mostrarLinhaFina() && n.linha_fina) { <span class="linha-fina">{{ n.linha_fina }}</span> }
        <small>{{ data(n.publicada_em) }}</small>
      </span>
    </a>
    }
  `,
})
export class CartaoNoticiaComponent {
  readonly noticia = input.required<NoticiaCartao>();
  readonly horizontal = input(false);
  /** `tweet` mostra a notícia no formato do Tweet Card do MagicUI (autor, texto e mídia). */
  readonly formato = input<'cartao' | 'tweet'>('cartao');
  readonly mostrarLinhaFina = input(true);
  protected readonly data = dataCurta;
  protected readonly srcset = (n: NoticiaCartao) => srcsetCapa(n.capa);
}
