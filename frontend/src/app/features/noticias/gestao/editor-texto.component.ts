// Criado por José Eduardo Santana Martins
// Este arquivo serve para editar o texto da notícia com formatação simples (o HTML é limpo de novo no servidor).

import { AfterViewInit, Component, ElementRef, model, viewChild } from '@angular/core';

/** Editor enxuto: negrito, itálico, sublinhado, títulos, listas, citação, link e limpar formatação. */
@Component({
  selector: 'app-editor-texto',
  template: `
    <div class="editor-texto">
      <div class="barra-editor" role="toolbar" aria-label="Formatação">
        <button type="button" title="Negrito (Ctrl+B)" aria-label="Negrito" (mousedown)="$event.preventDefault()" (click)="comando('bold')"><b>N</b></button>
        <button type="button" title="Itálico (Ctrl+I)" aria-label="Itálico" (mousedown)="$event.preventDefault()" (click)="comando('italic')"><i>I</i></button>
        <button type="button" title="Sublinhado (Ctrl+U)" aria-label="Sublinhado" (mousedown)="$event.preventDefault()" (click)="comando('underline')"><u>S</u></button>
        <span class="separador"></span>
        <button type="button" title="Título" (mousedown)="$event.preventDefault()" (click)="bloco('h2')">Título</button>
        <button type="button" title="Subtítulo" (mousedown)="$event.preventDefault()" (click)="bloco('h3')">Subtítulo</button>
        <button type="button" title="Parágrafo" (mousedown)="$event.preventDefault()" (click)="bloco('p')">Parágrafo</button>
        <span class="separador"></span>
        <button type="button" title="Lista" aria-label="Lista com marcadores" (mousedown)="$event.preventDefault()" (click)="comando('insertUnorderedList')">• Lista</button>
        <button type="button" title="Lista numerada" aria-label="Lista numerada" (mousedown)="$event.preventDefault()" (click)="comando('insertOrderedList')">1. Lista</button>
        <button type="button" title="Citação" (mousedown)="$event.preventDefault()" (click)="bloco('blockquote')">“ Citação</button>
        <button type="button" title="Link" (mousedown)="$event.preventDefault()" (click)="link()">Link</button>
        <button type="button" title="Limpar formatação" (mousedown)="$event.preventDefault()" (click)="comando('removeFormat')">Limpar</button>
      </div>
      <div #area class="area-editor corpo-noticia" contenteditable="true" role="textbox" aria-multiline="true" aria-label="Texto da notícia"
           (input)="atualizar()" (blur)="atualizar()"></div>
    </div>
  `,
})
export class EditorTextoComponent implements AfterViewInit {
  readonly html = model('');
  private readonly area = viewChild.required<ElementRef<HTMLDivElement>>('area');
  private ultimo = '';

  ngAfterViewInit(): void {
    this.area().nativeElement.innerHTML = this.html();
    this.ultimo = this.html();
  }

  /** Recebe um HTML novo de fora (ex.: notícia carregada depois). */
  definir(html: string): void {
    this.area().nativeElement.innerHTML = html;
    this.ultimo = html;
    this.html.set(html);
  }

  protected comando(nome: string, valor?: string): void {
    document.execCommand(nome, false, valor);
    this.atualizar();
  }

  protected bloco(tag: string): void {
    this.comando('formatBlock', tag);
  }

  protected link(): void {
    const url = prompt('Endereço do link (https://…):')?.trim();
    if (url && /^(https?:\/\/|mailto:)/i.test(url)) this.comando('createLink', url);
  }

  protected atualizar(): void {
    const atual = this.area().nativeElement.innerHTML;
    if (atual !== this.ultimo) { this.ultimo = atual; this.html.set(atual); }
  }
}
