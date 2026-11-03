// Criado por José Eduardo Santana Martins
// Este arquivo serve para o campo de escolha com busca (combobox): substitui o <select> quando a lista é longa ou precisa de pesquisa.
// Mesmo padrão do campo de sala do Patrimônio: um campo só, a lista filtra enquanto se digita, setas/Enter/Esc e o "×" para limpar.

import { Component, computed, ElementRef, forwardRef, inject, input, signal, viewChild } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

/** Uma opção do campo: o valor gravado e o texto mostrado (e pesquisado). */
export interface OpcaoEscolha {
  valor: unknown;
  rotulo: string;
}

/** Texto sem acento e em minúsculas, para a busca ("Gestão" acha "gestao"). */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/**
 * Campo de escolha com busca. Funciona como um `<select>`: `[(ngModel)]` e `required` valem normalmente.
 * - `opcoes`: a lista ({valor, rotulo});
 * - `vazio`: com texto, acrescenta a opção vazia (valor `null`) com esse rótulo (ex.: "Herdar", "Sem categoria") e mostra o "×";
 * - `excluir`: um valor a esconder (ex.: a própria categoria no campo "Dentro de").
 */
@Component({
  selector: 'app-campo-escolha',
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => CampoEscolhaComponent), multi: true }],
  host: { '(document:click)': 'cliqueFora($event)' },
  template: `
    <div class="campo-escolha" role="combobox" [attr.aria-expanded]="aberto()" aria-haspopup="listbox" [attr.aria-owns]="idLista">
      <input #entrada type="text" [id]="idCampo()" autocomplete="off" [placeholder]="placeholder()" [attr.aria-label]="rotuloAcessivel() || null"
             aria-autocomplete="list" [attr.aria-controls]="idLista" [disabled]="desabilitado()" [value]="texto()"
             (input)="digitou($any($event.target).value)" (focus)="abrir()" (blur)="aoSair()" (keydown)="teclado($event)" />
      @if (vazio() !== null && valor() !== null && !desabilitado()) {
        <button type="button" class="limpar-escolha" [attr.aria-label]="'Limpar: ' + vazio()" (mousedown)="$event.preventDefault()" (click)="escolher(null)">×</button>
      }
      @if (aberto()) {
        <ul class="opcoes-escolha" role="listbox" [id]="idLista">
          @for (o of filtradas(); track $index) {
            <li role="option" [attr.aria-selected]="o.valor === valor()" [class.destacada]="$index === destacada()" [class.escolhida]="o.valor === valor()"
                [class.vazia]="o.valor === null" (mousedown)="$event.preventDefault()" (click)="escolher(o.valor)" (mouseenter)="destacada.set($index)">{{ o.rotulo }}</li>
          } @empty { <li class="sem-opcao" role="presentation">Nada encontrado.</li> }
        </ul>
      }
    </div>
  `,
  styles: `
    :host { display: block; }
    /* Num formulário em grade, o mesmo espaço que os campos nativos têm embaixo (a lista continua colada no campo) */
    :host-context(.grade-formulario) { margin-bottom: 16px; }
    .campo-escolha { position: relative; }
    input { width: 100%; margin: 0; padding-right: 36px; }
    .limpar-escolha { position: absolute; top: 50%; right: 6px; transform: translateY(-50%); width: 30px; height: 30px; padding: 0; border: 0;
      border-radius: var(--spi-raio-p); color: var(--spi-apagado); background: transparent; font-size: 20px; line-height: 1; cursor: pointer;
      &:hover { background: var(--spi-superficie-alt); color: var(--spi-texto); }
      &:focus-visible { outline: none; box-shadow: var(--spi-anel-foco); } }
    .opcoes-escolha { position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 30; max-height: 280px; margin: 0; padding: 4px 0; overflow-y: auto;
      border: 1px solid var(--spi-borda); border-radius: var(--spi-raio-m); background: var(--spi-superficie); box-shadow: var(--spi-sombra-flutuante); list-style: none;
      li { padding: 9px 12px; font-size: 13px; color: var(--spi-texto); cursor: pointer; }
      li.destacada { background: var(--spi-vermelho-suave); }
      li.escolhida { font-weight: 700; }
      li.vazia { color: var(--spi-apagado); }
      .sem-opcao { color: var(--spi-apagado); cursor: default; } }
  `,
})
export class CampoEscolhaComponent implements ControlValueAccessor {
  private static sequencia = 0;
  readonly opcoes = input.required<OpcaoEscolha[]>();
  readonly vazio = input<string | null>(null);
  readonly excluir = input<unknown>(undefined);
  readonly idCampo = input<string>('');
  readonly placeholder = input('Digite para buscar ou escolha');
  /** Rótulo para leitor de tela quando não há `<label for>` (ex.: campo dentro de tabela). */
  readonly rotuloAcessivel = input('');

  protected readonly idLista = `campo-escolha-${++CampoEscolhaComponent.sequencia}`;
  protected readonly valor = signal<unknown>(null);
  protected readonly aberto = signal(false);
  protected readonly desabilitado = signal(false);
  protected readonly destacada = signal(0);
  /** O que a pessoa digitou (vazio = mostra a lista inteira). */
  private readonly filtro = signal('');
  private readonly digitando = signal(false);
  private readonly entrada = viewChild<ElementRef<HTMLInputElement>>('entrada');
  private readonly elemento = inject(ElementRef<HTMLElement>);
  private aoMudar: (valor: unknown) => void = () => undefined;
  private aoTocar: () => void = () => undefined;

  /** Opções que valem (com a vazia no topo, sem a excluída). */
  private readonly todas = computed<OpcaoEscolha[]>(() => {
    const excluir = this.excluir();
    const lista = this.opcoes().filter((o) => excluir === undefined || o.valor !== excluir);
    return this.vazio() !== null ? [{ valor: null, rotulo: this.vazio()! }, ...lista] : lista;
  });
  protected readonly filtradas = computed(() => {
    const termo = normalizar(this.filtro().trim());
    return termo ? this.todas().filter((o) => normalizar(o.rotulo).includes(termo)) : this.todas();
  });
  /** No campo: o que se digita ou, parado, o rótulo da opção escolhida. */
  protected readonly texto = computed(() => {
    if (this.digitando()) return this.filtro();
    const atual = this.todas().find((o) => o.valor === this.valor());
    return atual && !(atual.valor === null && !this.vazio()) ? atual.rotulo : '';
  });

  writeValue(valor: unknown): void {
    this.valor.set(valor === undefined ? null : valor);
  }

  registerOnChange(fn: (valor: unknown) => void): void {
    this.aoMudar = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.aoTocar = fn;
  }

  setDisabledState(desabilitado: boolean): void {
    this.desabilitado.set(desabilitado);
  }

  protected abrir(): void {
    this.filtro.set('');
    this.aberto.set(true);
    this.destacada.set(Math.max(0, this.todas().findIndex((o) => o.valor === this.valor())));
  }

  protected digitou(texto: string): void {
    this.digitando.set(true);
    this.filtro.set(texto);
    this.aberto.set(true);
    this.destacada.set(0);
  }

  protected escolher(valor: unknown): void {
    this.valor.set(valor);
    this.aoMudar(valor);
    this.fechar();
  }

  protected aoSair(): void {
    this.fechar();
    this.aoTocar();
  }

  private fechar(): void {
    this.aberto.set(false);
    this.digitando.set(false);
    this.filtro.set('');
  }

  protected teclado(evento: KeyboardEvent): void {
    const total = this.filtradas().length;
    if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') {
      evento.preventDefault();
      if (!this.aberto()) { this.abrir(); return; }
      const passo = evento.key === 'ArrowDown' ? 1 : -1;
      this.destacada.set(total ? (this.destacada() + passo + total) % total : 0);
      this.rolarParaDestacada();
    } else if (evento.key === 'Enter') {
      if (!this.aberto()) return;
      evento.preventDefault();
      const opcao = this.filtradas()[this.destacada()];
      if (opcao) this.escolher(opcao.valor);
    } else if (evento.key === 'Escape' && this.aberto()) {
      evento.stopPropagation();
      this.fechar();
    }
  }

  private rolarParaDestacada(): void {
    setTimeout(() => (this.elemento.nativeElement as HTMLElement).querySelector('li.destacada')?.scrollIntoView({ block: 'nearest' }));
  }

  /** Clique fora do campo fecha a lista. */
  protected cliqueFora(evento: MouseEvent): void {
    if (this.aberto() && !(this.elemento.nativeElement as HTMLElement).contains(evento.target as Node)) this.fechar();
  }

  /** Para o `<label for>` focar o campo. */
  focar(): void {
    this.entrada()?.nativeElement.focus();
  }
}
