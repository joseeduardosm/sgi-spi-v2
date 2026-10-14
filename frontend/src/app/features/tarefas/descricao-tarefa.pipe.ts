// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a descrição da tarefa: HTML do editor rico (já sanitizado na API) ou texto simples antigo com links.

import { inject, Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

import { linkificarTexto } from '../../shared/utilitarios/linkificar.pipe';

/** A descrição foi gravada pelo editor rico (começa com uma tag)? As antigas são texto simples. */
export function descricaoEhHtml(valor: string | null | undefined): boolean {
  return /^\s*<[a-z][\s\S]*>/i.test(valor ?? '');
}

/** Descrição para o editor: o texto simples antigo vira parágrafos (uma linha por parágrafo); HTML segue como está. */
export function descricaoParaEditor(valor: string | null | undefined): string {
  const texto = valor ?? '';
  if (!texto || descricaoEhHtml(texto)) return texto;
  const escapar = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return texto.replace(/\r\n?/g, '\n').split('\n').map((linha) => `<p>${escapar(linha)}</p>`).join('');
}

@Pipe({ name: 'descricaoTarefa' })
export class DescricaoTarefaPipe implements PipeTransform {
  private readonly sanitizador = inject(DomSanitizer);

  transform(valor: string | null | undefined): SafeHtml {
    // HTML: sanitizado na API (nh3), igual aos itens de Contratações; texto simples: escapado por `linkificarTexto`
    return this.sanitizador.bypassSecurityTrustHtml(descricaoEhHtml(valor) ? (valor ?? '') : linkificarTexto(valor));
  }
}
