// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o rodapé institucional das páginas públicas.

import { Component } from '@angular/core';

/** Rodapé com o nome do governo e da secretaria; conteúdo fixo, sem lógica. */
@Component({
  selector: 'app-rodape',
  template: `<footer class="rodape">Governo do Estado de São Paulo · Secretaria de Parcerias em Investimentos</footer>`,
  styles: `
    .rodape {
      display: block;
      color: #7b8490;
      font-size: 0.76rem;
      text-align: center;
      padding: 20px 14px 27px;
    }
  `,
})
export class RodapeComponent {}
