// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o HTML dos itens (já sanitizado pela API) sem o Angular remover cores, realces e alinhamento.

import { inject, Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/**
 * O HTML dos itens e das diferenças entre versões é sanitizado no servidor (nh3 com lista de tags e estilos permitidos) antes de ser
 * gravado ou devolvido; por isso é seguro exibi-lo como confiável. O sanitizador padrão do Angular removeria `style` (cor, realce).
 */
@Pipe({ name: 'htmlConfiavel' })
export class HtmlConfiavelPipe implements PipeTransform {
  private readonly sanitizador = inject(DomSanitizer);

  transform(valor: string | null | undefined): SafeHtml {
    return this.sanitizador.bypassSecurityTrustHtml(valor ?? '');
  }
}
