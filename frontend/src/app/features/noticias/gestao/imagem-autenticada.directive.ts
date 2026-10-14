// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir em <img> um arquivo que exige token (baixa como blob e usa o endereço local), só quando a imagem chega perto da tela.

import { DestroyRef, Directive, effect, ElementRef, inject, input } from '@angular/core';

import { NoticiasApiService } from '../noticias-api.service';

/**
 * Imagem autenticada com carregamento preguiçoso: a requisição só sai quando a imagem está a ~200 px de aparecer (IntersectionObserver), e até
 * lá ela mostra o esqueleto (`data-carregando`). Ao chegar, aparece com fade (opacidade). Sem IntersectionObserver, carrega na hora.
 */
@Directive({ selector: 'img[appImagemAutenticada]', host: { loading: 'lazy', decoding: 'async' } })
export class ImagemAutenticadaDirective {
  readonly appImagemAutenticada = input<string | null | undefined>();
  private readonly api = inject(NoticiasApiService);
  private readonly elemento = inject<ElementRef<HTMLImageElement>>(ElementRef);
  private local: string | null = null;
  private observador: IntersectionObserver | null = null;

  constructor() {
    effect(() => {
      const url = this.appImagemAutenticada();
      this.liberar();
      const img = this.elemento.nativeElement;
      if (!url) { img.removeAttribute('src'); img.removeAttribute('data-carregando'); return; }
      img.setAttribute('data-carregando', '');
      img.addEventListener('load', () => img.removeAttribute('data-carregando'), { once: true });
      const buscar = () => this.api.blob(url).subscribe({ next: (b) => { this.local = b; img.src = b; }, error: () => img.removeAttribute('data-carregando') });
      if (typeof IntersectionObserver === 'undefined') { buscar(); return; }
      this.observador = new IntersectionObserver((entradas) => {
        if (entradas.some((e) => e.isIntersecting)) { this.observador?.disconnect(); this.observador = null; buscar(); }
      }, { rootMargin: '200px' });
      this.observador.observe(img);
    });
    inject(DestroyRef).onDestroy(() => this.liberar());
  }

  private liberar(): void {
    this.observador?.disconnect();
    this.observador = null;
    if (this.local) URL.revokeObjectURL(this.local);
    this.local = null;
  }
}
