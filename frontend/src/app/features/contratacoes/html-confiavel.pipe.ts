/**
 * =============================================================================
 * ARQUIVO: html-confiavel.pipe.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Exibir o HTML dos itens (já sanitizado pela API) sem que o Angular remova
 * cores, realces e alinhamento do texto formatado.
 *
 * RESUMO TÉCNICO:
 * Pipe "htmlConfiavel" (um pipe transforma um valor dentro do template, como
 * em [innerHTML]="texto | htmlConfiavel"). Usa o DomSanitizer do Angular para
 * marcar a string como HTML confiável (bypassSecurityTrustHtml). Valor nulo
 * ou indefinido vira string vazia.
 *
 * FINALIDADE DE NEGÓCIO:
 * Os itens do ETP e do TR são escritos com formatação rica (cor, realce,
 * alinhamento). Sem este pipe a formatação sumiria na leitura e na
 * comparação entre versões, e o documento não pareceria o que foi escrito.
 *
 * CONTEXTO NO SISTEMA:
 * Usado nas telas de documento e de versões de Contratações. A segurança
 * depende da sanitização feita no backend (biblioteca nh3) antes de gravar.
 *
 * =============================================================================
 */

import { inject, Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/**
 * O HTML dos itens e das diferenças entre versões é sanitizado no servidor (nh3 com lista de tags e estilos permitidos) antes de ser
 * gravado ou devolvido; por isso é seguro exibi-lo como confiável. O sanitizador padrão do Angular removeria `style` (cor, realce).
 *
 * Atenção: só use este pipe com HTML que veio da API de Contratações. Aplicá-lo a texto digitado
 * no navegador e ainda não sanitizado abriria brecha para injeção de script (XSS).
 */
@Pipe({ name: 'htmlConfiavel' })
export class HtmlConfiavelPipe implements PipeTransform {
  /** `inject` pega um serviço do Angular sem precisar de construtor. */
  private readonly sanitizador = inject(DomSanitizer);

  /**
   * Marca o HTML como confiável para o binding `[innerHTML]`.
   * @param valor HTML vindo da API (pode ser nulo ou indefinido).
   * @returns Objeto SafeHtml que o Angular exibe sem filtrar; vazio quando não há valor.
   */
  transform(valor: string | null | undefined): SafeHtml {
    return this.sanitizador.bypassSecurityTrustHtml(valor ?? '');
  }
}
