// Criado por José Eduardo Santana Martins
// Este arquivo serve para oferecer o editor de texto formatado (TipTap) dos itens de Contratações.

import { Component, effect, ElementRef, input, model, OnDestroy, viewChild, AfterViewInit } from '@angular/core';
import { Editor } from '@tiptap/core';
import Highlight from '@tiptap/extension-highlight';
import Link from '@tiptap/extension-link';
import { TableKit } from '@tiptap/extension-table';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyleKit } from '@tiptap/extension-text-style';
import Underline from '@tiptap/extension-underline';
import StarterKit from '@tiptap/starter-kit';

const CORES_TEXTO = [
  { nome: 'Preto', valor: '#000000' },
  { nome: 'Vermelho', valor: '#ff0000' },
  { nome: 'Azul escuro', valor: '#1f4e78' },
];
const CORES_REALCE = [
  { nome: 'Amarelo', valor: '#fff2cc' },
  { nome: 'Vermelho claro', valor: '#f4cccc' },
  { nome: 'Verde claro', valor: '#d9ead3' },
];

/**
 * Editor de um item. Emite só o HTML interno do item (o tipo, o pai e a ordem ficam fora do documento). A API sanitiza de novo.
 * A colagem usa só texto puro, para não trazer estilos de outras aplicações.
 */
@Component({
  selector: 'app-editor-rico',
  template: `
    <div class="editor-rico" [class.somente-leitura]="somenteLeitura()">
      @if (!somenteLeitura()) {
        <div class="barra-editor" role="toolbar" aria-label="Formatação">
          <button type="button" title="Negrito" [class.ativo]="ativo('bold')" (click)="comando('bold')"><b>N</b></button>
          <button type="button" title="Itálico" [class.ativo]="ativo('italic')" (click)="comando('italic')"><i>I</i></button>
          <button type="button" title="Sublinhado" [class.ativo]="ativo('underline')" (click)="comando('underline')"><u>S</u></button>
          <button type="button" title="Tachado" [class.ativo]="ativo('strike')" (click)="comando('strike')"><s>T</s></button>
          <span class="separador"></span>
          <button type="button" title="Lista com marcadores" [class.ativo]="ativo('bulletList')" (click)="comando('lista')">• Lista</button>
          <button type="button" title="Alinhar à esquerda" [class.ativo]="alinhado('left')" (click)="comando('left')">⇤</button>
          <button type="button" title="Centralizar" [class.ativo]="alinhado('center')" (click)="comando('center')">↔</button>
          <button type="button" title="Justificar" [class.ativo]="alinhado('justify')" (click)="comando('justify')">☰</button>
          <span class="separador"></span>
          @for (c of coresTexto; track c.valor) {
            <button type="button" [title]="'Texto ' + c.nome" class="cor" [style.color]="c.valor" (click)="cor(c.valor)">A</button>
          }
          @for (c of coresRealce; track c.valor) {
            <button type="button" [title]="'Realce ' + c.nome" class="cor realce" [style.background]="c.valor" (click)="realce(c.valor)">ab</button>
          }
          <span class="separador"></span>
          <button type="button" title="Inserir tabela 3×3" (click)="comando('tabela')">Tabela</button>
          @if (ativo('table')) {
            <button type="button" (click)="comando('linha')">+ linha</button>
            <button type="button" (click)="comando('coluna')">+ coluna</button>
            <button type="button" (click)="comando('mesclar')">Mesclar</button>
            <button type="button" (click)="comando('excluirTabela')">Excluir tabela</button>
          }
        </div>
      }
      <div #superficie></div>
    </div>
  `,
})
export class EditorRicoComponent implements AfterViewInit, OnDestroy {
  /** HTML do item (mão dupla). */
  readonly html = model('');
  readonly somenteLeitura = input(false);
  readonly rotulo = input('Editor de conteúdo formatado');
  protected readonly coresTexto = CORES_TEXTO;
  protected readonly coresRealce = CORES_REALCE;

  private readonly superficie = viewChild.required<ElementRef<HTMLElement>>('superficie');
  private editor?: Editor;

  constructor() {
    // Mudança vinda de fora (restaurar, trocar de item): atualiza o editor sem disparar nova gravação
    effect(() => {
      const novo = this.html() || '<p></p>';
      if (this.editor && this.editor.getHTML() !== novo) this.editor.commands.setContent(novo, { emitUpdate: false });
    });
    effect(() => this.editor?.setEditable(!this.somenteLeitura()));
  }

  ngAfterViewInit(): void {
    this.editor = new Editor({
      element: this.superficie().nativeElement,
      content: this.html() || '<p></p>',
      editable: !this.somenteLeitura(),
      extensions: [
        StarterKit.configure({ link: false, underline: false, heading: false, code: false, codeBlock: false, horizontalRule: false }),
        Underline,
        TextStyleKit,
        TextAlign.configure({ types: ['paragraph'] }),
        Link.configure({ openOnClick: false, autolink: false, defaultProtocol: 'https' }),
        Highlight.configure({ multicolor: true }),
        TableKit.configure({ table: { resizable: true } }),
      ],
      editorProps: {
        attributes: { class: 'superficie-editor', role: 'textbox', 'aria-multiline': 'true', 'aria-label': this.rotulo() },
        handlePaste: (_vista, evento) => {
          const texto = evento.clipboardData?.getData('text/plain');
          if (texto == null) return false;
          evento.preventDefault();
          this.editor?.commands.insertContent(this.paraHtml(texto));
          return true;
        },
      },
      onUpdate: ({ editor }) => this.html.set(editor.getHTML()),
    });
  }

  ngOnDestroy(): void {
    this.editor?.destroy();
  }

  /** Insere o texto na posição do cursor (usado, por exemplo, para os placeholders das máscaras). */
  inserir(texto: string): void {
    this.editor?.chain().focus().insertContent(texto).run();
  }

  protected ativo(nome: string): boolean {
    return this.editor?.isActive(nome) ?? false;
  }

  protected alinhado(valor: string): boolean {
    return this.editor?.isActive({ textAlign: valor }) ?? false;
  }

  protected cor(valor: string): void {
    this.editor?.chain().focus().setColor(valor).run();
  }

  protected realce(valor: string): void {
    this.editor?.chain().focus().toggleHighlight({ color: valor }).run();
  }

  protected comando(nome: string): void {
    const cadeia = this.editor?.chain().focus();
    if (!cadeia) return;
    switch (nome) {
      case 'bold': cadeia.toggleBold().run(); break;
      case 'italic': cadeia.toggleItalic().run(); break;
      case 'underline': cadeia.toggleUnderline().run(); break;
      case 'strike': cadeia.toggleStrike().run(); break;
      case 'lista': cadeia.toggleBulletList().run(); break;
      case 'left': cadeia.setTextAlign('left').run(); break;
      case 'center': cadeia.setTextAlign('center').run(); break;
      case 'justify': cadeia.setTextAlign('justify').run(); break;
      case 'tabela': cadeia.insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); break;
      case 'linha': cadeia.addRowAfter().run(); break;
      case 'coluna': cadeia.addColumnAfter().run(); break;
      case 'mesclar': cadeia.mergeCells().run(); break;
      case 'excluirTabela': cadeia.deleteTable().run(); break;
    }
  }

  private paraHtml(texto: string): string {
    const escapar = (t: string) => {
      const no = document.createElement('div');
      no.textContent = t;
      return no.innerHTML;
    };
    return texto.replace(/\r\n?/g, '\n').split('\n\n').map((p) => `<p>${escapar(p).replace(/\n/g, '<br>')}</p>`).join('');
  }
}
