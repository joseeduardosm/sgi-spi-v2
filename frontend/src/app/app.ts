// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir o componente raiz, que só reserva o espaço onde as telas são exibidas.

import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/**
 * Componente raiz da aplicação. O `<router-outlet />` é o lugar onde o roteador desenha a tela
 * correspondente ao endereço atual (login, layout autenticado etc.).
 */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: `<router-outlet />`,
})
export class Aplicacao {}
