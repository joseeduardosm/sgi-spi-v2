// Criado por José Eduardo Santana Martins
// Este arquivo serve para a página /painel-executivo: cabeçalho do módulo e o carrossel em tamanho completo.

import { Component } from '@angular/core';

import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { PainelExecutivoComponent } from './painel-executivo.component';

@Component({
  selector: 'app-pagina-painel-executivo',
  imports: [TrilhaComponent, PainelExecutivoComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Painel Executivo', rota: '/painel-executivo' }]" />
        <h1>Painel Executivo</h1>
        <small>Contratos, RH e tarefas da organização, em painéis que giram sozinhos. Use "Tela cheia" para exibir em TV.</small>
      </div>
    </div>
    <app-painel-executivo />
  `,
})
export class PaginaPainelExecutivoComponent {}
