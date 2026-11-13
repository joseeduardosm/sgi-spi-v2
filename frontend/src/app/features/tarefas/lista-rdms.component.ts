// Criado por José Eduardo Santana Martins
// Este arquivo serve para a lista de RDMs (Requisições de Mudança) das tarefas que a pessoa enxerga, com filtro por situação e colunas ordenáveis.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { RdmListada, SITUACOES_RDM, SituacaoRdm } from './rdm.models';
import { TarefasApiService } from './tarefas-api.service';

type ColunaOrdem = 'numero' | 'titulo' | 'tarefa' | 'situacao' | 'enviada' | 'decidida';
interface Ordenacao { coluna: ColunaOrdem; direcao: 'asc' | 'desc' }

function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/** Valor de cada coluna para comparar (número "00012/2026" pelo ano e número; datas pelo instante; vazio vai para o fim). */
function valor(r: RdmListada, coluna: ColunaOrdem): string | number | null {
  switch (coluna) {
    case 'numero': { const [n, ano] = r.numero.split('/'); return Number(ano) * 100000 + Number(n); }
    case 'titulo': return normalizar(r.titulo);
    case 'tarefa': return r.tarefa_numero;
    case 'situacao': return Object.keys(SITUACOES_RDM).indexOf(r.situacao);
    case 'enviada': return r.enviada_em ? new Date(r.enviada_em).getTime() : null;
    case 'decidida': return r.decidida_em ? new Date(r.decidida_em).getTime() : null;
  }
}

@Component({
  selector: 'app-lista-rdms',
  imports: [DatePipe, EsqueletoComponent, RouterLink, CabecalhoTarefasComponent],
  template: `
    <app-cabecalho-tarefas titulo="RDMs" [trilha]="[{ rotulo: 'RDMs' }]"
      descricao="Requisições de Mudança das tarefas que você acompanha: amarela aguardando aprovação, vermelha reprovada, laranja aprovada e verde concluída e implantada." />
    <section class="painel-gestao protocolo">
      <div class="barra-protocolo">
        <div class="chips-filtro" role="group" aria-label="Situação">
          @for (s of filtros; track s[0]) {
            <button type="button" [class.ativo]="filtro() === s[0]" [attr.aria-pressed]="filtro() === s[0]" (click)="filtrar(s[0])">{{ s[1] }}</button>
          }
        </div>
      </div>
      @if (itens(); as lista) {
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <!-- Colunas ordenáveis (regra do SGI), com o botão da lista de Chamados -->
            <thead><tr>
              @for (col of colunas; track col.chave) {
                <th scope="col" [attr.aria-sort]="sentido(col.chave)">
                  <button type="button" class="ordenar-coluna" [class.ativa]="ordem().coluna === col.chave" (click)="ordenar(col.chave)" [title]="'Ordenar por ' + col.rotulo.toLowerCase()">
                    {{ col.rotulo }}<span aria-hidden="true">{{ ordem().coluna === col.chave ? (ordem().direcao === 'asc' ? '▲' : '▼') : '↕' }}</span></button>
                </th>
              }
            </tr></thead>
            <tbody>
              @for (r of ordenados(); track r.id) {
                <tr>
                  <td data-rotulo="RDM"><a [routerLink]="['/tarefas', r.tarefa_numero, 'rdm']"><span class="texto-codigo">RDM SGI {{ r.numero }}</span></a></td>
                  <td data-rotulo="Título">{{ r.titulo }}</td>
                  <td data-rotulo="Tarefa"><a [routerLink]="['/tarefas', r.tarefa_numero]"><span class="texto-codigo">#{{ r.tarefa_numero }}</span> {{ r.tarefa_titulo }}</a>
                    @if (r.equipe) { <br /><small>{{ r.equipe }}</small> }</td>
                  <td data-rotulo="Situação"><span class="selo-status" [attr.data-chamado]="situacoes[r.situacao].cor">{{ situacoes[r.situacao].rotulo }}</span></td>
                  <td data-rotulo="Enviada">{{ r.enviada_por_nome }}@if (r.enviada_em) { <br /><small class="texto-codigo">{{ r.enviada_em | date: 'dd/MM/yyyy HH:mm' }}</small> }</td>
                  <td data-rotulo="Decidida">@if (r.decidida_em) { {{ r.decidida_por_nome }}<br /><small class="texto-codigo">{{ r.decidida_em | date: 'dd/MM/yyyy HH:mm' }}</small> } @else { — }</td>
                </tr>
              } @empty { <tr><td colspan="6" class="estado-vazio">Nenhuma RDM {{ filtro() ? 'nesta situação' : 'ainda' }}.</td></tr> }
            </tbody>
          </table>
        </div>
      } @else {
        <app-esqueleto tipo="tabela" />
      }
    </section>
  `,
})
export class ListaRdmsComponent implements OnInit {
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly situacoes = SITUACOES_RDM;
  protected readonly filtros: [SituacaoRdm | null, string][] = [[null, 'Todas'], ['pendente', 'Aguardando aprovação'], ['aprovada', 'Aprovadas'], ['reprovada', 'Reprovadas'], ['concluida', 'Concluídas']];
  protected readonly colunas: { chave: ColunaOrdem; rotulo: string }[] = [
    { chave: 'numero', rotulo: 'RDM' }, { chave: 'titulo', rotulo: 'Título' }, { chave: 'tarefa', rotulo: 'Tarefa' }, { chave: 'situacao', rotulo: 'Situação' },
    { chave: 'enviada', rotulo: 'Enviada' }, { chave: 'decidida', rotulo: 'Decidida' },
  ];
  protected readonly filtro = signal<SituacaoRdm | null>(null);
  protected readonly itens = signal<RdmListada[] | null>(null);
  protected readonly ordem = signal<Ordenacao>({ coluna: 'numero', direcao: 'desc' });
  protected readonly ordenados = computed(() => {
    const { coluna, direcao } = this.ordem();
    const sinal = direcao === 'asc' ? 1 : -1;
    return [...(this.itens() ?? [])].sort((a, b) => {
      const va = valor(a, coluna), vb = valor(b, coluna);
      if (va === null || vb === null) { if (va !== vb) return va === null ? 1 : -1; }
      else if (va !== vb) return (va < vb ? -1 : 1) * sinal;
      return valor(b, 'numero')! > valor(a, 'numero')! ? 1 : -1;
    });
  });

  ngOnInit(): void {
    this.carregar();
  }

  protected filtrar(situacao: SituacaoRdm | null): void {
    this.filtro.set(situacao);
    this.carregar();
  }

  private carregar(): void {
    this.itens.set(null);
    this.api.rdms(this.filtro()).subscribe({ next: (x) => this.itens.set(x), error: (e) => { this.itens.set([]); this.dialogos.mostrarErro(e, 'Não foi possível carregar as RDMs'); } });
  }

  protected ordenar(coluna: ColunaOrdem): void {
    const atual = this.ordem();
    this.ordem.set(atual.coluna === coluna ? { coluna, direcao: atual.direcao === 'asc' ? 'desc' : 'asc' }
      : { coluna, direcao: ['numero', 'enviada', 'decidida', 'tarefa'].includes(coluna) ? 'desc' : 'asc' });
  }

  protected sentido(coluna: ColunaOrdem): 'ascending' | 'descending' | 'none' {
    const atual = this.ordem();
    return atual.coluna !== coluna ? 'none' : atual.direcao === 'asc' ? 'ascending' : 'descending';
  }
}
