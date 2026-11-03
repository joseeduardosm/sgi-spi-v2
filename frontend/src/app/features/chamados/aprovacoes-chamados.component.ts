// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar as aprovações de chamados que aguardam a pessoa (ou um setor dela).

import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoChamadosComponent } from './cabecalho-chamados.component';
import { ChamadosApiService } from './chamados-api.service';
import { AprovacaoPendente, dataHora } from './chamados.models';

@Component({
  selector: 'app-aprovacoes-chamados',
  imports: [RouterLink, CabecalhoChamadosComponent, EsqueletoComponent],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-chamados titulo="Minhas aprovações" descricao="Chamados em que pediram a sua aprovação (ou a de um setor seu). Abra o chamado para aprovar ou não." />
      <section class="painel-gestao protocolo">
        @if (carregando()) {
          <app-esqueleto tipo="tabela" [linhas]="4" [colunas]="4" />
        } @else {
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao tabela-chamados">
              <thead><tr><th>Chamado</th><th>O que aprovar</th><th>Pedida por</th><th>Para</th><th>Em</th></tr></thead>
              <tbody>
                @for (a of itens(); track a.id) {
                  <tr>
                    <td data-rotulo="Chamado"><span><a class="numero-chamado" [routerLink]="['/chamados', a.chamado_numero]">#{{ a.chamado_numero }}</a><br /><small>{{ a.chamado_titulo }}</small></span></td>
                    <td data-rotulo="O que aprovar">{{ a.pedido }}</td>
                    <td data-rotulo="Pedida por">{{ a.solicitante_nome }}</td>
                    <td data-rotulo="Para">{{ a.alvo_nome }}</td>
                    <td data-rotulo="Em">{{ data(a.criado_em) }}</td>
                  </tr>
                } @empty { <tr><td colspan="5" class="estado-vazio">Nenhuma aprovação aguardando você.</td></tr> }
              </tbody>
            </table>
          </div>
        }
      </section>
    </div>
  `,
})
export class AprovacoesChamadosComponent implements OnInit {
  private readonly api = inject(ChamadosApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly itens = signal<AprovacaoPendente[]>([]);
  protected readonly carregando = signal(true);
  protected data = dataHora;

  ngOnInit(): void {
    this.api.minhasAprovacoes().subscribe({
      next: (r) => {
        this.itens.set(r);
        this.carregando.set(false);
      },
      error: (e) => {
        this.carregando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível carregar as aprovações');
      },
    });
  }
}
