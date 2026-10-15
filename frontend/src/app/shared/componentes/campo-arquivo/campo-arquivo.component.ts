// Criado por José Eduardo Santana Martins
// Este arquivo serve para escolher um arquivo (PDF ou XML) numa área de arrastar e soltar, com colar (Ctrl+V) e validação rápida.

import { ChangeDetectionStrategy, Component, input, output, signal } from '@angular/core';

import { formatarTamanho } from '../../utilitarios/formatadores';
import { validarPdf } from '../envio-pdf/envio-pdf.component';

/**
 * Área de envio de um arquivo: clique, arraste e solte ou cole (Ctrl+V) com ela em foco. Confere extensão e tamanho no navegador
 * (a API continua sendo quem decide) e mostra o nome e o tamanho do arquivo escolhido, com × para trocar.
 */
@Component({
  selector: 'app-campo-arquivo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <input #campo type="file" hidden [accept]="tipo() === 'pdf' ? 'application/pdf,.pdf' : '.xml,application/xml,text/xml'" (change)="aoEscolher(campo.files?.[0] ?? null); campo.value = ''" />
    <div class="zona" [class.sobre]="sobre()" [class.cheia]="!!arquivo() || !!jaEnviado()" [class.erro]="!!erro()" [attr.tabindex]="desabilitado() ? -1 : 0" role="button"
         [attr.aria-disabled]="desabilitado()" [attr.aria-label]="rotulo() + (obrigatorio() ? ' (obrigatório)' : ' (opcional)')"
         (click)="!desabilitado() && campo.click()" (keydown.enter)="!desabilitado() && campo.click()" (keydown.space)="$event.preventDefault(); !desabilitado() && campo.click()"
         (dragover)="arrastando($event, true)" (dragleave)="arrastando($event, false)" (drop)="soltar($event)" (paste)="colar($event)">
      <span class="titulo">{{ rotulo() }} <em>{{ obrigatorio() ? 'obrigatório' : 'opcional' }}</em></span>
      @if (arquivo(); as a) {
        <span class="nome"><b>{{ a.name }}</b> · {{ tamanho(a.size) }}</span>
        <button type="button" class="remover" aria-label="Remover o arquivo escolhido" (click)="$event.stopPropagation(); limpar()">×</button>
      } @else if (jaEnviado()) {
        <span class="nome"><b>{{ jaEnviado() }}</b> · já enviado; escolha outro para substituir</span>
      } @else {
        <span class="dica">{{ desabilitado() ? 'Indisponível' : 'Clique, arraste e solte ou cole (Ctrl+V)' }}</span>
      }
    </div>
    @if (erro()) { <span class="msg-erro" role="alert">{{ erro() }}</span> }
  `,
  styles: `
    :host { display: block; min-width: 0; }
    .zona { position: relative; display: flex; flex-direction: column; gap: 4px; min-height: 76px; padding: 12px 40px 12px 14px; border: 1.5px dashed var(--spi-borda-campo); border-radius: var(--spi-raio-g);
      background: var(--spi-superficie); color: var(--spi-texto); cursor: pointer; transition: border-color 150ms ease-out, background-color 150ms ease-out; }
    .zona:hover:not([aria-disabled='true']), .zona:focus-visible, .zona.sobre { border-color: var(--spi-vermelho); background: var(--spi-vermelho-suave); outline: none; }
    .zona.cheia { border-style: solid; background: var(--spi-superficie-alt); }
    .zona.erro { border-color: var(--spi-perigo); }
    .zona[aria-disabled='true'] { cursor: default; opacity: 0.7; }
    .titulo { font-size: var(--spi-texto-compacto); font-weight: 600; }
    .titulo em { margin-left: 6px; color: var(--spi-apagado); font-size: var(--spi-texto-legenda); font-style: normal; font-weight: 400; }
    .dica, .nome { color: var(--spi-apagado); font-size: var(--spi-texto-legenda); overflow-wrap: anywhere; }
    .nome b { color: var(--spi-texto); font-weight: 600; }
    .remover { position: absolute; top: 8px; right: 8px; width: 26px; height: 26px; border: 0; border-radius: 50%; background: transparent; color: var(--spi-apagado); font-size: 18px; line-height: 1; cursor: pointer; }
    .remover:hover { background: var(--spi-perigo-suave); color: var(--spi-perigo); }
    .msg-erro { display: block; margin-top: 4px; color: var(--spi-perigo); font-size: var(--spi-texto-legenda); }
    @media (prefers-reduced-motion: reduce) { .zona { transition: none; } }
  `,
})
export class CampoArquivoComponent {
  readonly tipo = input<'pdf' | 'xml'>('pdf');
  readonly rotulo = input.required<string>();
  readonly obrigatorio = input(false);
  readonly desabilitado = input(false);
  /** Nome do arquivo que já está salvo (aparece enquanto nada novo foi escolhido). */
  readonly jaEnviado = input<string | null>(null);
  readonly selecionado = output<File | null>();

  protected readonly arquivo = signal<File | null>(null);
  protected readonly erro = signal<string | null>(null);
  protected readonly sobre = signal(false);
  protected readonly tamanho = formatarTamanho;

  protected arrastando(evento: DragEvent, sobre: boolean): void {
    if (this.desabilitado()) return;
    evento.preventDefault();
    this.sobre.set(sobre);
  }

  protected soltar(evento: DragEvent): void {
    evento.preventDefault();
    this.sobre.set(false);
    if (!this.desabilitado()) this.aoEscolher(evento.dataTransfer?.files?.[0] ?? null);
  }

  protected colar(evento: ClipboardEvent): void {
    const arquivo = evento.clipboardData?.files?.[0];
    if (!arquivo || this.desabilitado()) return;
    evento.preventDefault();
    this.aoEscolher(arquivo);
  }

  protected aoEscolher(arquivo: File | null): void {
    if (!arquivo) return;
    const problema = this.tipo() === 'pdf' ? validarPdf(arquivo) : validarXml(arquivo);
    this.erro.set(problema);
    this.arquivo.set(problema ? null : arquivo);
    this.selecionado.emit(problema ? null : arquivo);
  }

  limpar(): void {
    this.arquivo.set(null);
    this.erro.set(null);
    this.selecionado.emit(null);
  }
}

/** Confere se é um XML (extensão) e se não está vazio nem grande demais (5 MB). */
function validarXml(arquivo: File): string | null {
  if (!/\.xml$/i.test(arquivo.name)) return 'Selecione o XML da nota fiscal (arquivo .xml).';
  if (arquivo.size === 0) return 'O arquivo está vazio.';
  if (arquivo.size > 5 * 1024 * 1024) return 'O XML excede o limite de 5 MB.';
  return null;
}
