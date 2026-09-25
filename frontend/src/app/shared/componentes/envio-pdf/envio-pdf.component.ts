import { ChangeDetectionStrategy, Component, ElementRef, input, output, signal, viewChild } from '@angular/core';

import { formatarTamanho } from '../../utilitarios/formatadores';

/** Mesmo limite padrão da API (ANEXOS_TAMANHO_MAXIMO_MB); a API continua sendo quem decide. */
export const TAMANHO_MAXIMO_PDF_MB = 25;

/**
 * Botão "Selecionar documento" para um PDF. Faz a checagem rápida no navegador (extensão,
 * arquivo vazio e tamanho) e emite o arquivo escolhido; o envio fica com a tela.
 */
@Component({
  selector: 'app-envio-pdf',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <input #campo type="file" accept="application/pdf,.pdf" hidden (change)="aoEscolher(campo)" />
    <button type="button" class="acao-secundaria" [disabled]="desabilitado()" (click)="campo.click()">{{ rotulo() }}</button>
    @if (arquivo(); as escolhido) {
      <span class="arquivo-escolhido">{{ escolhido.name }} · {{ tamanho(escolhido.size) }}</span>
    }
    @if (erro()) { <span class="erro-arquivo" role="alert">{{ erro() }}</span> }
  `,
  styles: `
    :host { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    .arquivo-escolhido { color: var(--spi-apagado); font-size: 12px; }
    .erro-arquivo { color: var(--spi-vermelho); font-size: 12px; }
  `,
})
export class EnvioPdfComponent {
  readonly rotulo = input('Selecionar documento');
  readonly desabilitado = input(false);
  readonly selecionado = output<File | null>();

  protected readonly arquivo = signal<File | null>(null);
  protected readonly erro = signal<string | null>(null);
  private readonly campo = viewChild<ElementRef<HTMLInputElement>>('campo');

  protected readonly tamanho = formatarTamanho;

  protected aoEscolher(campo: HTMLInputElement): void {
    const escolhido = campo.files?.[0] ?? null;
    const problema = escolhido ? validarPdf(escolhido) : null;
    this.erro.set(problema);
    this.arquivo.set(problema ? null : escolhido);
    this.selecionado.emit(problema ? null : escolhido);
    // Permite escolher de novo o mesmo arquivo depois de limpar
    campo.value = '';
  }

  /** Volta ao estado inicial (ex.: depois de um envio concluído). */
  limpar(): void {
    this.arquivo.set(null);
    this.erro.set(null);
    const elemento = this.campo()?.nativeElement;
    if (elemento) elemento.value = '';
  }
}

export function validarPdf(arquivo: File): string | null {
  if (!/\.pdf$/i.test(arquivo.name) && arquivo.type !== 'application/pdf') return 'Selecione um arquivo PDF.';
  if (arquivo.size === 0) return 'O arquivo está vazio.';
  if (arquivo.size > TAMANHO_MAXIMO_PDF_MB * 1024 * 1024) return `O arquivo excede o limite de ${TAMANHO_MAXIMO_PDF_MB} MB.`;
  return null;
}
