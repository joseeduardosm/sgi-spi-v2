/**
 * =============================================================================
 * ARQUIVO: movimentacoes.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Lista de movimentações de bens do Patrimônio, com filtros por status e
 * período, exportação em Excel/PDF e atalho para solicitar uma nova.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template inline. Os filtros usam ngModel e
 * recarregam a lista a cada mudança; a API filtra no servidor. A exportação
 * usa DialogosService.executar para mostrar o andamento enquanto o arquivo é
 * gerado.
 *
 * FINALIDADE DE NEGÓCIO:
 * Acompanha as trocas de sala dos bens (solicitação, autorização,
 * recebimento e conclusão), mostrando quantos bens já chegaram nas
 * movimentações autorizadas.
 *
 * CONTEXTO NO SISTEMA:
 * Rota /patrimonio/movimentacoes (patrimonio.routes.ts). Cada cartão abre
 * detalhe-movimentacao.component.ts; o botão abre nova-movimentacao.
 *
 * =============================================================================
 */
import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { COR_STATUS, Movimentacao, ROTULOS_STATUS } from './patrimonio.models';

@Component({
  selector: 'app-movimentacoes',
  imports: [FormsModule, RouterLink, DatePipe, CabecalhoPatrimonioComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Movimentações" descricao="Troca de sala dos bens: solicitação, autorização, recebimento e conclusão." />
    <section class="painel-gestao patrimonio">
      <div class="pat-barra">
        <div class="campo"><label for="mv-status">Status</label>
          <select id="mv-status" name="status" [(ngModel)]="status" (ngModelChange)="carregar()"><option value="">Todos</option>@for (s of statusLista; track s[0]) { <option [value]="s[0]">{{ s[1] }}</option> }</select></div>
        <div class="campo"><label for="mv-de">De</label><input id="mv-de" name="de" type="date" [(ngModel)]="de" (ngModelChange)="carregar()" /></div>
        <div class="campo"><label for="mv-ate">Até</label><input id="mv-ate" name="ate" type="date" [(ngModel)]="ate" (ngModelChange)="carregar()" /></div>
        <span class="espacador"></span>
        <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('xlsx')">Excel</button>
        <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('pdf')">PDF</button>
        @if (estado.podeOperar()) { <a class="acao-primaria pat-botao-grande" routerLink="/patrimonio/movimentacoes/nova">+ Solicitar movimentação</a> }
      </div>
      <div class="pat-lista-bens">
        @for (m of movimentacoes(); track m.id) {
          <a class="pat-cartao-bem" [routerLink]="['/patrimonio/movimentacoes', m.id]">
            <span class="pat-chapa">Para {{ m.destino_codigo }}</span>
            <span class="pat-descricao">{{ m.itens.length }} bem(ns) · {{ m.motivo }}</span>
            <small class="pat-sala">{{ m.solicitante_nome }} · {{ m.solicitada_em | date: 'dd/MM/yyyy HH:mm' }}</small>
            <span class="pat-marcadores"><span [class]="marcador(cores[m.status])">{{ rotulos[m.status] }}</span>
              @if (m.status === 'autorizada') { <span [class]="marcador(4)">{{ recebidos(m) }}/{{ m.itens.length }} recebidos</span> }</span>
          </a>
        } @empty { <p class="estado-vazio">Nenhuma movimentação encontrada.</p> }
      </div>
    </section>
  `,
})
/** Lista filtrável de movimentações. */
export class MovimentacoesComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);
  /** Movimentações exibidas. */
  protected readonly movimentacoes = signal<Movimentacao[]>([]);
  /** Filtros da barra (status e período), ligados por ngModel. */
  protected status = '';
  protected de = '';
  protected ate = '';
  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_STATUS;
  protected readonly rotulos = ROTULOS_STATUS;
  /** Pares [valor, rótulo] para as opções do filtro de status. */
  protected readonly statusLista = ['pendente', 'autorizada', 'concluida', 'recusada', 'cancelada'].map((s) => [s, ROTULOS_STATUS[s]]);

  ngOnInit(): void {
    this.carregar();
  }

  /** Quantos bens da movimentação já tiveram o recebimento confirmado. */
  protected recebidos(m: Movimentacao): number {
    return m.itens.filter((i) => i.recebido_em).length;
  }

  /** Busca as movimentações com os filtros atuais. */
  protected carregar(): void {
    this.api.movimentacoes({ status: this.status, de: this.de, ate: this.ate }).subscribe({
      next: (x) => this.movimentacoes.set(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as movimentações'),
    });
  }

  /** Gera o relatório das movimentações filtradas em Excel ou PDF. */
  protected exportar(formato: 'xlsx' | 'pdf'): void {
    this.dialogos.executar(this.api.exportar('movimentacoes', formato, { status: this.status, de: this.de, ate: this.ate }), 'Gerando o relatório…')
      .subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório') });
  }
}
