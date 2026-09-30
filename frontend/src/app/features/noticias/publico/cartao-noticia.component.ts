// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir uma notícia em cartão (capa 2:1, categoria, título e data).

import { Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { dataCurta, NoticiaCartao, srcsetCapa } from '../noticias.models';

@Component({
  selector: 'app-cartao-noticia',
  imports: [RouterLink],
  template: `
    @let n = noticia();
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
  `,
})
export class CartaoNoticiaComponent {
  readonly noticia = input.required<NoticiaCartao>();
  readonly horizontal = input(false);
  readonly mostrarLinhaFina = input(true);
  protected readonly data = dataCurta;
  protected readonly srcset = (n: NoticiaCartao) => srcsetCapa(n.capa);
}
