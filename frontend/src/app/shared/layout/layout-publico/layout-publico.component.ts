// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a moldura das páginas públicas (hoje, só a tela de login).

import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { CabecalhoComponent } from '../../componentes/cabecalho/cabecalho.component';
import { RodapeComponent } from '../../componentes/rodape/rodape.component';

/** Layout das páginas públicas (login): cabeçalho institucional, conteúdo centralizado e rodapé. */
@Component({
  selector: 'app-layout-publico',
  imports: [RouterOutlet, CabecalhoComponent, RodapeComponent],
  template: `
    <div class="pagina">
      <app-cabecalho />
      <main class="container-fluid largura-portal conteudo-principal">
        <router-outlet />
      </main>
      <app-rodape />
    </div>
  `,
  styles: `
    .pagina {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .conteudo-principal {
      flex: 1;
      padding-top: clamp(48px, 8vh, 90px);
      padding-bottom: 70px;
    }
  `,
})
// Sem lógica: estrutura e estilo estão no template acima
export class LayoutPublicoComponent {}
