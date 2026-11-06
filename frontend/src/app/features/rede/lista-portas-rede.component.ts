// Criado por José Eduardo Santana Martins
// Este arquivo serve para a lista aberta pelos cards do topo da Rede: portas alteradas nos últimos 7 dias ou portas ativas sem descrição,
// com equipamento | porta | descrição | quem alterou e quando (a última alteração da porta).

import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRedeComponent } from './cabecalho-rede.component';
import { RedeApiService } from './rede-api.service';
import { PortaListada } from './rede.models';

type FiltroLista = 'alteradas' | 'sem-descricao';
type ColunaOrdem = 'equipamento' | 'porta' | 'descricao' | 'alterado';
interface Ordenacao { coluna: ColunaOrdem; direcao: 'asc' | 'desc' }

/** Valor de cada coluna para comparar: texto sem acento, número da porta e o instante da alteração (sem alteração vai para o fim). */
function valorDaColuna(p: PortaListada, coluna: ColunaOrdem): string | number | null {
  switch (coluna) {
    case 'equipamento': return normalizar(p.equipamento_nome);
    case 'porta': return p.numero_logico;
    case 'descricao': return p.descricao ? normalizar(p.descricao) : null;
    case 'alterado': return p.alterado_em ? new Date(p.alterado_em).getTime() : null;
  }
}

/** Título e explicação de cada lista (o mesmo critério do card). */
const TEXTOS: Record<FiltroLista, { titulo: string; descricao: string; vazio: string }> = {
  alteradas: {
    titulo: 'Portas alteradas nos últimos 7 dias',
    descricao: 'Qualquer alteração na porta: configuração, ligação, dispositivo atrás, ponto de rede ou carga LLDP. Mostra a última de cada porta.',
    vazio: 'Nenhuma porta alterada nos últimos 7 dias.',
  },
  'sem-descricao': {
    titulo: 'Portas ativas sem descrição',
    descricao: 'Portas ligadas sem descrição, com a última alteração de cada uma (se houver). Abra a porta para descrevê-la.',
    vazio: 'Nenhuma porta ligada sem descrição.',
  },
};

/** Texto sem acento e em minúsculas, para a busca. */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

@Component({
  selector: 'app-lista-portas-rede',
  imports: [DatePipe, FormsModule, RouterLink, CabecalhoRedeComponent, EsqueletoComponent],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-rede [titulo]="textos().titulo" [descricao]="textos().descricao" [trilha]="[{ rotulo: textos().titulo }]" />
      <section class="painel-gestao protocolo">
        <!-- Mesma barra de busca da lista de equipamentos -->
        <div class="barra-protocolo">
          <div class="campo"><label for="lp-busca">Busca</label>
            <input id="lp-busca" type="search" placeholder="Equipamento, porta, descrição ou quem alterou" [ngModel]="busca()" (ngModelChange)="busca.set($event)" /></div>
          <span class="espacador"></span>
          @if (itens(); as lista) { <small>{{ filtrados().length }} de {{ lista.length }} porta(s)</small> }
        </div>
        @if (itens()) {
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <!-- Colunas ordenáveis (regra do SGI), com o mesmo botão da lista de Chamados: clicar de novo inverte o sentido -->
              <thead><tr>
                @for (col of colunas; track col.chave) {
                  <th scope="col" [attr.aria-sort]="sentido(col.chave)">
                    <button type="button" class="ordenar-coluna" [class.ativa]="ordem().coluna === col.chave" (click)="ordenar(col.chave)" [title]="'Ordenar por ' + col.rotulo.toLowerCase()">
                      {{ col.rotulo }}<span aria-hidden="true">{{ ordem().coluna === col.chave ? (ordem().direcao === 'asc' ? '▲' : '▼') : '↕' }}</span></button>
                  </th>
                }
              </tr></thead>
              <tbody>
                @for (p of filtrados(); track p.porta_id) {
                  <tr>
                    <td data-rotulo="Equipamento"><a [routerLink]="['/rede/equipamentos', p.equipamento_id]"><strong>{{ p.equipamento_nome }}</strong></a></td>
                    <td data-rotulo="Porta"><a [routerLink]="['/rede/portas', p.porta_id]"><span class="texto-codigo">{{ p.porta }}</span></a></td>
                    <td data-rotulo="Descrição">{{ p.descricao || '—' }}</td>
                    <td data-rotulo="Quem alterou">@if (p.alterado_em) { {{ p.alterado_por }} - <span class="texto-codigo">{{ p.alterado_em | date: 'dd/MM/yyyy HH:mm:ss' }}</span> } @else { — }</td>
                  </tr>
                } @empty { <tr><td colspan="4" class="estado-vazio">{{ busca() ? 'Nenhuma porta encontrada nesta busca.' : textos().vazio }}</td></tr> }
              </tbody>
            </table>
          </div>
        } @else {
          <app-esqueleto tipo="tabela" />
        }
      </section>
    </div>
  `,
})
export class ListaPortasRedeComponent implements OnInit {
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  /** Qual card abriu a lista (`alteradas` ou `sem-descricao`); outro valor cai em "alteradas". */
  protected readonly filtro: FiltroLista = inject(ActivatedRoute).snapshot.paramMap.get('filtro') === 'sem-descricao' ? 'sem-descricao' : 'alteradas';
  protected readonly textos = signal(TEXTOS[this.filtro]);
  protected readonly itens = signal<PortaListada[] | null>(null);
  protected readonly busca = signal('');
  protected readonly colunas: { chave: ColunaOrdem; rotulo: string }[] = [
    { chave: 'equipamento', rotulo: 'Equipamento' }, { chave: 'porta', rotulo: 'Porta' }, { chave: 'descricao', rotulo: 'Descrição' }, { chave: 'alterado', rotulo: 'Quem alterou' },
  ];
  /** Começa pela alteração mais recente (a ordem que a API já devolve). */
  protected readonly ordem = signal<Ordenacao>({ coluna: 'alterado', direcao: 'desc' });
  protected readonly filtrados = computed(() => {
    const termo = normalizar(this.busca().trim());
    const lista = this.itens() ?? [];
    const achados = termo ? lista.filter((p) => normalizar(`${p.equipamento_nome} ${p.porta} ${p.descricao} ${p.alterado_por ?? ''}`).includes(termo)) : lista;
    const { coluna, direcao } = this.ordem();
    const sinal = direcao === 'asc' ? 1 : -1;
    // Vazio (sem descrição, nunca alterada) fica sempre no fim; empate: equipamento e número da porta
    return [...achados].sort((a, b) => {
      const va = valorDaColuna(a, coluna), vb = valorDaColuna(b, coluna);
      if (va === null || vb === null) {
        if (va !== vb) return va === null ? 1 : -1;
      } else if (va !== vb) {
        return (va < vb ? -1 : 1) * sinal;
      }
      return normalizar(a.equipamento_nome).localeCompare(normalizar(b.equipamento_nome)) || a.numero_logico - b.numero_logico;
    });
  });

  protected ordenar(coluna: ColunaOrdem): void {
    const atual = this.ordem();
    // Mesma coluna inverte; outra coluna começa crescente (a data, do mais recente)
    this.ordem.set(atual.coluna === coluna ? { coluna, direcao: atual.direcao === 'asc' ? 'desc' : 'asc' } : { coluna, direcao: coluna === 'alterado' ? 'desc' : 'asc' });
  }

  protected sentido(coluna: ColunaOrdem): 'ascending' | 'descending' | 'none' {
    const atual = this.ordem();
    return atual.coluna !== coluna ? 'none' : atual.direcao === 'asc' ? 'ascending' : 'descending';
  }

  ngOnInit(): void {
    this.api.portasListadas(this.filtro).subscribe({
      next: (x) => this.itens.set(x),
      error: (e) => { this.itens.set([]); this.dialogos.mostrarErro(e, 'Não foi possível carregar a lista de portas'); },
    });
  }
}
