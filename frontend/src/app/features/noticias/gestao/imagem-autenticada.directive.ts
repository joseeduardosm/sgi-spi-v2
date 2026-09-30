// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir em <img> um arquivo da gestão, que exige token (baixa como blob e usa o endereço local).

import { DestroyRef, Directive, effect, ElementRef, inject, input } from '@angular/core';

import { NoticiasApiService } from '../noticias-api.service';

@Directive({ selector: 'img[appImagemAutenticada]' })
export class ImagemAutenticadaDirective {
  readonly appImagemAutenticada = input<string | null | undefined>();
  private readonly api = inject(NoticiasApiService);
  private readonly elemento = inject<ElementRef<HTMLImageElement>>(ElementRef);
  private local: string | null = null;

  constructor() {
    effect(() => {
      const url = this.appImagemAutenticada();
      this.liberar();
      if (!url) { this.elemento.nativeElement.removeAttribute('src'); return; }
      this.api.blob(url).subscribe({ next: (b) => { this.local = b; this.elemento.nativeElement.src = b; }, error: () => undefined });
    });
    inject(DestroyRef).onDestroy(() => this.liberar());
  }

  private liberar(): void {
    if (this.local) URL.revokeObjectURL(this.local);
    this.local = null;
  }
}
