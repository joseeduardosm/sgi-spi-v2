// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar chamados: "Meus chamados" (quem pediu) e a "Fila de atendimento" (quem atende), com filtros e busca.

import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, tap } from 'rxjs';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoChamadosComponent } from './cabecalho-chamados.component';
import { ChamadosApiService } from './chamados-api.service';
import { ChamadosTempoRealService } from './chamados-tempo-real.service';
import {
  ChamadoResumo, ColunaOrdem, COR_STATUS, dataHora, FiltroFila, FiltroMeus, nivelPrazo, Ordenacao, ROTULOS_PRIORIDADE, ROTULOS_STATUS, rotuloStatusSolicitante, textoPrazo,
} from './chamados.models';

const FILTROS_FILA: { valor: FiltroFila; rotulo: string }[] = [
  { valor: 'abertos', rotulo: 'Abertos' },
  { valor: 'meus', rotulo: 'Comigo' },
  { valor: 'sem_responsavel', rotulo: 'Sem responsável' },
  { valor: 'novos', rotulo: 'Novos' },
  { valor: 'setor', rotulo: 'Do meu setor' },
  { valor: 'sem_itil', rotulo: 'Sem categoria ITIL' },
  { valor: 'solucionados', rotulo: 'Resolvidos' },
  { valor: 'todos', rotulo: 'Todos' },
];
const FILTROS_MEUS: { valor: FiltroMeus; rotulo: string }[] = [
  { valor: 'abertos', rotulo: 'Abertos' },
  { valor: 'aguardando', rotulo: 'Aguardando você' },
  { valor: 'resolvidos', rotulo: 'Resolvidos' },
  { valor: 'todos', rotulo: 'Todos' },
];
const TAMANHO = 50;

@Component({
  selector: 'app-lista-chamados',
  imports: [FormsModule, RouterLink, CabecalhoChamadosComponent, EsqueletoComponent],
  template: `
    <div class="modulo-chamados">
      <app-cabecalho-chamados [titulo]="fila ? 'Fila de atendimento' : 'Meus chamados'"
        [descricao]="fila ? 'Chamados dos seus setores, do mais urgente para o menos urgente.' : 'Chamados que você abriu ou que foram abertos em nome do seu setor.'" />
      <section class="painel-gestao protocolo">
        <div class="chips-filtro" role="group" aria-label="Filtros rápidos">
          @for (f of filtros; track f.valor) {
            <button type="button" [class.ativo]="filtro() === f.valor" [attr.aria-pressed]="filtro() === f.valor" (click)="trocarFiltro(f.valor)">{{ f.rotulo }}</button>
          }
        </div>
        @if (tituloRecorte()) {
          <p class="aviso-formulario" role="status">Recorte do relatório: <strong>{{ tituloRecorte() }}</strong>.
            <button type="button" class="acao-secundaria acao-pequena" (click)="limparRecorte()">Limpar recorte</button>
            <a class="acao-secundaria acao-pequena" routerLink="/chamados/relatorios">Voltar aos relatórios</a></p>
        }
        @if (mudancasPendentes()) {
          <p class="aviso-formulario" role="status">Há chamados novos ou alterados desde que você carregou a lista.
            <button type="button" class="acao-secundaria acao-pequena" (click)="recarregar()">Atualizar a lista</button></p>
        }
        <p class="somente-leitor-tela" aria-live="polite">{{ anuncio() }}</p>
        <div class="barra-protocolo">
          <div class="campo"><label for="lc-busca">Busca</label>
            <input id="lc-busca" type="search" placeholder="Número, título ou solicitante" [(ngModel)]="busca" (keyup.enter)="recarregar()" /></div>
          <button type="button" class="acao-secundaria" (click)="recarregar()">Buscar</button>
          <span class="espacador"></span>
          <span class="resumo-protocolo">{{ total() }} chamado(s)</span>
        </div>
        @if (carregando()) {
          <app-esqueleto tipo="tabela" [linhas]="6" [colunas]="6" />
        } @else {
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao tabela-chamados">
              <thead><tr>
                @for (col of colunas; track col.chave) {
                  <th scope="col" [attr.aria-sort]="sentido(col.chave)">
                    <button type="button" class="ordenar-coluna" [class.ativa]="ordem()?.coluna === col.chave" (click)="ordenar(col.chave)" [title]="'Ordenar por ' + col.rotulo.toLowerCase()">
                      {{ col.rotulo }}<span aria-hidden="true">{{ ordem()?.coluna === col.chave ? (ordem()!.direcao === 'asc' ? '▲' : '▼') : '↕' }}</span></button>
                  </th>
                }
              </tr></thead>
              <tbody>
                @for (c of itens(); track c.id) {
                  <tr>
                    <td data-rotulo="Nº"><a class="numero-chamado" [routerLink]="['/chamados', c.numero]">#{{ c.numero }}</a></td>
                    <td data-rotulo="Chamado"><span><a [routerLink]="['/chamados', c.numero]"><strong>{{ c.titulo }}</strong></a><br /><small>{{ c.categoria_caminho }}</small></span></td>
                    <td [attr.data-rotulo]="fila ? 'Solicitante' : 'Setor'"><span>{{ fila ? c.solicitante_nome : c.setor_nome }}@if (fila && c.responsavel_nome) { <br /><small>Com {{ c.responsavel_nome }}</small> }</span></td>
                    <td data-rotulo="Situação"><span><span class="selo-status" [attr.data-chamado]="cor(c)">{{ status(c) }}</span>
                      @if (c.importado) { <span class="selo-status" data-chamado="neutro">Importado do GLPI</span> }</span></td>
                    <td data-rotulo="Prioridade"><span class="selo-prioridade" [attr.data-prioridade-chamado]="c.prioridade"
                      [title]="c.prioridade_origem === 'sla' ? 'Urgente: prazo estourado' : ''">{{ prioridade(c) }}</span></td>
                    <td data-rotulo="Prazo"><span class="selo-situacao" [attr.data-prazo]="nivel(c)">{{ prazo(c) }}</span></td>
                    <td data-rotulo="Aberto em">{{ data(c.aberto_em) }}</td>
                  </tr>
                } @empty {
                  <tr><td colspan="7" class="estado-vazio">{{ fila ? 'Nenhum chamado com este filtro.' : 'Você não tem chamados com este filtro.' }}
                    @if (!fila) { <a class="acao-primaria acao-pequena" routerLink="/chamados">Abrir chamado</a> }</td></tr>
                }
              </tbody>
            </table>
          </div>
          @if (total() > itens().length) {
            <div class="acoes-formulario"><button type="button" class="acao-secundaria" (click)="carregarMais()">Mostrar mais</button></div>
          }
        }
      </section>
    </div>
  `,
})
export class ListaChamadosComponent implements OnInit {
  private readonly api = inject(ChamadosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  protected readonly fila = this.rota.snapshot.data['modo'] === 'fila';
  /** Clique num número dos Relatórios: os parâmetros do recorte (vão para a API como vieram) e o texto que explica o que está na lista. */
  private recorte: Record<string, string> = this.fila ? this.lerRecorte() : {};
  private readonly roteador = inject(Router);
  protected readonly tituloRecorte = signal(this.fila ? this.rota.snapshot.queryParamMap.get('titulo') ?? '' : '');

  protected readonly filtros: { valor: string; rotulo: string }[] = this.fila ? FILTROS_FILA : FILTROS_MEUS;
  protected readonly filtro = signal<string>(this.rota.snapshot.queryParamMap.get('filtro') ?? 'abertos');
  protected readonly ordem = signal<Ordenacao | null>(null);
  // Colunas da tabela, na ordem em que aparecem (a 3ª muda conforme a lista)
  protected readonly colunas: { chave: ColunaOrdem; rotulo: string }[] = [
    { chave: 'numero', rotulo: 'Nº' }, { chave: 'titulo', rotulo: 'Chamado' },
    this.fila ? { chave: 'solicitante', rotulo: 'Solicitante' } : { chave: 'setor', rotulo: 'Setor' },
    { chave: 'situacao', rotulo: 'Situação' }, { chave: 'prioridade', rotulo: 'Prioridade' }, { chave: 'prazo', rotulo: 'Prazo de solução' },
    { chave: 'aberto_em', rotulo: 'Aberto em' },
  ];
  protected readonly itens = signal<ChamadoResumo[]>([]);
  protected readonly total = signal(0);
  protected readonly carregando = signal(true);
  protected busca = '';
  private pagina = 1;
  protected data = dataHora;

  private readonly tempoReal = inject(ChamadosTempoRealService);
  private readonly destruir = inject(DestroyRef);
  /** Chegou mudança enquanto a pessoa estava em outra página da lista (não recarrega sozinho para não tirar o que ela lê). */
  protected readonly mudancasPendentes = signal(false);
  protected readonly anuncio = signal('');
  private novosNaRajada = 0;

  ngOnInit(): void {
    this.recarregar();
    // Ao vivo: na primeira página, a lista se atualiza sozinha (vários eventos seguidos viram uma busca só)
    this.tempoReal.eventos$.pipe(
      tap((e) => { if (e.tipo === 'novo') this.novosNaRajada += 1; }),
      debounceTime(500),
      takeUntilDestroyed(this.destruir),
    ).subscribe(() => {
      const novos = this.novosNaRajada;
      this.novosNaRajada = 0;
      if (this.pagina > 1) {
        this.mudancasPendentes.set(true);
        return;
      }
      this.buscar((r) => this.itens.set(r));
      if (novos && this.fila) this.anuncio.set(novos === 1 ? '1 chamado novo na fila.' : `${novos} chamados novos na fila.`);
    });
  }

  /** Volta à fila completa: a tela é reaproveitada pelo Angular (mesma rota), então limpa aqui e tira os parâmetros da URL. */
  protected limparRecorte(): void {
    this.recorte = {};
    this.tituloRecorte.set('');
    this.filtro.set('abertos');
    this.roteador.navigate([], { relativeTo: this.rota, queryParams: {} });
    this.recarregar();
  }

  /** Parâmetros do recorte vindos da URL (só os que a API conhece; `filtro` e `titulo` são da tela). */
  private lerRecorte(): Record<string, string> {
    const chaves = ['escopo_relatorio', 'relatorio_setor_id', 'aberto_de', 'aberto_ate', 'resolvido_de', 'resolvido_ate', 'resolvido_por', 'assumido_por',
      'assumido_de', 'assumido_ate', 'categoria_id', 'setor_id', 'nota', 'reabertos'];
    const mapa = this.rota.snapshot.queryParamMap;
    return Object.fromEntries(chaves.filter((c) => mapa.has(c)).map((c) => [c, mapa.get(c)!]));
  }

  /** Clique no cabeçalho: a mesma coluna inverte o sentido; outra começa no sentido mais útil (data, prioridade e número: do maior para o menor). */
  protected ordenar(coluna: ColunaOrdem): void {
    const atual = this.ordem();
    if (atual?.coluna === coluna) this.ordem.set({ coluna, direcao: atual.direcao === 'asc' ? 'desc' : 'asc' });
    else this.ordem.set({ coluna, direcao: ['aberto_em', 'prioridade', 'numero'].includes(coluna) ? 'desc' : 'asc' });
    this.recarregar();
  }

  protected sentido(coluna: ColunaOrdem): 'ascending' | 'descending' | 'none' {
    const atual = this.ordem();
    return atual?.coluna !== coluna ? 'none' : atual.direcao === 'asc' ? 'ascending' : 'descending';
  }

  protected trocarFiltro(valor: string): void {
    this.filtro.set(valor);
    this.recarregar();
  }

  protected recarregar(): void {
    this.pagina = 1;
    this.mudancasPendentes.set(false);
    this.carregando.set(true);
    this.buscar((r) => this.itens.set(r));
  }

  protected carregarMais(): void {
    this.pagina += 1;
    this.buscar((r) => this.itens.update((atual) => [...atual, ...r]));
  }

  private buscar(aplicar: (itens: ChamadoResumo[]) => void): void {
    const pedido = this.fila
      ? this.api.fila(this.filtro() as FiltroFila, this.busca, this.pagina, TAMANHO, this.ordem(), this.recorte)
      : this.api.meus(this.filtro() as FiltroMeus, this.busca, this.pagina, this.ordem());
    pedido.subscribe({
      next: (r) => {
        aplicar(r.itens);
        this.total.set(r.total);
        this.carregando.set(false);
      },
      error: (e) => {
        this.carregando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível carregar os chamados');
      },
    });
  }

  protected status(c: ChamadoResumo): string {
    return this.fila ? c.status_nome || ROTULOS_STATUS[c.status_base] : rotuloStatusSolicitante(c);
  }

  protected cor(c: ChamadoResumo): string {
    return this.fila ? c.status_cor || COR_STATUS[c.status_base] : COR_STATUS[c.status_base];
  }

  protected prioridade(c: ChamadoResumo): string {
    return ROTULOS_PRIORIDADE[c.prioridade];
  }

  protected nivel(c: ChamadoResumo): string {
    return c.status_base === 'solucionado' ? 'cumprido' : nivelPrazo(c.solucao);
  }

  protected prazo(c: ChamadoResumo): string {
    return c.status_base === 'solucionado' ? 'Resolvido' : textoPrazo(c.solucao);
  }
}
