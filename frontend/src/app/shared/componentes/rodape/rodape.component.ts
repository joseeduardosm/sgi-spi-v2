import { Component } from '@angular/core';

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
