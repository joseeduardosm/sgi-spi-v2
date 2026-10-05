// Criado por José Eduardo Santana Martins
// Este arquivo serve para transformar endereços http/https digitados em campos de texto em links clicáveis.

import { inject, Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

// Endereço http(s) até o primeiro espaço, aspas ou sinal de marcação
const PADRAO_LINK = /https?:\/\/[^\s<>"']+/gi;
// Pontuação que costuma vir colada ao fim do link no meio de uma frase, e não faz parte dele
const PONTUACAO_FINAL = /[.,;:!?)\]}]+$/;

/** Escapa o texto para HTML: o que o usuário digitou nunca vira marcação. */
function escapar(texto: string): string {
  return texto.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/**
 * Devolve o texto com os endereços http/https como links (abrem em outra aba). Todo o resto é escapado,
 * então é seguro usar com `[innerHTML]`. Uso: `<p [innerHTML]="texto | linkificar"></p>`.
 * As quebras de linha continuam como estavam (use `white-space: pre-line` no elemento quando precisar delas).
 */
export function linkificarTexto(valor: string | null | undefined): string {
  const texto = valor ?? '';
  let saida = '';
  let ultimo = 0;
  for (const achado of texto.matchAll(PADRAO_LINK)) {
    const inicio = achado.index ?? 0;
    const endereco = achado[0].replace(PONTUACAO_FINAL, '');
    // Só endereço com algo depois do "://" vira link (evita "http://" solto)
    if (!/^https?:\/\/[^/\s]+/i.test(endereco)) continue;
    const seguro = escapar(endereco);
    saida += escapar(texto.slice(ultimo, inicio)) + `<a class="link-texto" href="${seguro}" target="_blank" rel="noopener noreferrer">${seguro}</a>`;
    ultimo = inicio + endereco.length;
  }
  return saida + escapar(texto.slice(ultimo));
}

@Pipe({ name: 'linkificar' })
export class LinkificarPipe implements PipeTransform {
  private readonly sanitizador = inject(DomSanitizer);

  transform(valor: string | null | undefined): SafeHtml {
    // O HTML é todo gerado por `linkificarTexto` (texto escapado + links http/https), por isso pode ser marcado como confiável
    return this.sanitizador.bypassSecurityTrustHtml(linkificarTexto(valor));
  }
}
