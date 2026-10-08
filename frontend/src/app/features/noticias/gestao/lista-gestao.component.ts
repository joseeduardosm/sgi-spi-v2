// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar as notícias na gestão, com abas por situação (a de aprovação mostra o total pendente).

import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { NoticiasApiService } from '../noticias-api.service';
import { NoticiaGestaoResumo, PapelNoticias, ROTULOS_SITUACAO, SituacaoNoticia } from '../noticias.models';
import { CabecalhoNoticiasComponent } from './cabecalho-noticias.component';
import { ImagemAutenticadaDirective } from './imagem-autenticada.directive';

type ColunaOrdem = 'titulo' | 'situacao' | 'publicar_em' | 'autor_nome' | 'atualizado_em';

const ABAS: { valor: '' | SituacaoNoticia; rotulo: string }[] = [
  { valor: '', rotulo: 'Todas' }, { valor: 'em_revisao', rotulo: 'Aguardando aprovação' }, { valor: 'rascunho', rotulo: 'Rascunhos' },
  { valor: 'devolvida', rotulo: 'Devolvidas' }, { valor: 'aprovada', rotulo: 'Aprovadas' }, { valor: 'arquivada', rotulo: 'Arquivadas' },
];

@Component({
  selector: 'app-lista-gestao',
  imports: [FormsModule, RouterLink, DatePipe, CabecalhoNoticiasComponent, ImagemAutenticadaDirective],
  template: `
    <app-cabecalho-noticias titulo="Notícias" descricao="Escreva, envie para aprovação e acompanhe as notícias do portal." />
    @if (semAcesso()) {
      <div class="aviso-admin erro">Você não tem acesso à gestão de notícias. Peça ao administrador para incluir você como redator (MODIFICAÇÃO) ou aprovador (CONTROLE TOTAL) no recurso "Notícias" da ACL.</div>
    } @else {
      <div class="abas" role="tablist">
        @for (a of abas; track a.valor) {
          <button type="button" role="tab" [class.ativa]="situacao() === a.valor" [attr.aria-selected]="situacao() === a.valor" (click)="navegar(a.valor)">
            {{ a.rotulo }} @if (a.valor && papel()?.contagem?.[a.valor]) { <span class="contador-aba" [class.destaque]="a.valor === 'em_revisao'">{{ papel()!.contagem[a.valor] }}</span> }
          </button>
        }
      </div>
      <section class="painel-gestao">
        <div class="filtros-gestao">
          <input type="search" aria-label="Buscar pelo título" placeholder="Buscar pelo título" [ngModel]="busca" (ngModelChange)="digitar($event)" />
        </div>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao tabela-noticias">
            <thead><tr><th>Capa</th><th [attr.aria-sort]="sentido('titulo')"><button type="button" class="ordenar-coluna" [class.ativa]="ordenarPor() === 'titulo'" (click)="ordenar('titulo')" title="Ordenar por notícia">Notícia<span aria-hidden="true">{{ ordenarPor() === 'titulo' ? (direcao() === 'asc' ? '▲' : '▼') : '↕' }}</span></button></th><th [attr.aria-sort]="sentido('situacao')"><button type="button" class="ordenar-coluna" [class.ativa]="ordenarPor() === 'situacao'" (click)="ordenar('situacao')" title="Ordenar por situação">Situação<span aria-hidden="true">{{ ordenarPor() === 'situacao' ? (direcao() === 'asc' ? '▲' : '▼') : '↕' }}</span></button></th><th [attr.aria-sort]="sentido('publicar_em')"><button type="button" class="ordenar-coluna" [class.ativa]="ordenarPor() === 'publicar_em'" (click)="ordenar('publicar_em')" title="Ordenar por publicação">Publicação<span aria-hidden="true">{{ ordenarPor() === 'publicar_em' ? (direcao() === 'asc' ? '▲' : '▼') : '↕' }}</span></button></th><th [attr.aria-sort]="sentido('autor_nome')"><button type="button" class="ordenar-coluna" [class.ativa]="ordenarPor() === 'autor_nome'" (click)="ordenar('autor_nome')" title="Ordenar por autor">Autor<span aria-hidden="true">{{ ordenarPor() === 'autor_nome' ? (direcao() === 'asc' ? '▲' : '▼') : '↕' }}</span></button></th><th [attr.aria-sort]="sentido('atualizado_em')"><button type="button" class="ordenar-coluna" [class.ativa]="ordenarPor() === 'atualizado_em'" (click)="ordenar('atualizado_em')" title="Ordenar por atualizada">Atualizada<span aria-hidden="true">{{ ordenarPor() === 'atualizado_em' ? (direcao() === 'asc' ? '▲' : '▼') : '↕' }}</span></button></th></tr></thead>
            <tbody>
              @for (n of ordenados(); track n.id) {
                <tr>
                  <td class="coluna-capa"><a [routerLink]="['/noticias/gestao', n.id]">
                    @if (n.capa['400']) { <img [appImagemAutenticada]="n.capa['400']" [alt]="n.titulo" /> } @else { <span class="sem-capa">sem capa</span> }
                  </a></td>
                  <td><a [routerLink]="['/noticias/gestao', n.id]"><strong>{{ n.titulo }}</strong></a>
                    <small>@if (n.categoria) { {{ n.categoria.nome }} } @if (n.fixada) { · fixada }</small></td>
                  <td><span class="selo-noticia" [attr.data-situacao]="n.situacao">{{ rotulos[n.situacao] }}</span>
                    @if (n.situacao === 'aprovada' && !n.visivel) { <small>agendada</small> }</td>
                  <td>{{ n.publicar_em ? (n.publicar_em | date: 'dd/MM/yyyy HH:mm') : 'imediata' }}</td>
                  <td>{{ n.autor_nome }}</td>
                  <td>{{ n.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}</td>
                </tr>
              } @empty {
                <tr><td class="estado-vazio" colspan="6">{{ carregando() ? 'Carregando…' : 'Nenhuma notícia aqui.' }}</td></tr>
              }
            </tbody>
          </table>
        </div>
      </section>
    }
  `,
})
export class ListaGestaoComponent implements OnInit {
  private readonly api = inject(NoticiasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly destruir = inject(DestroyRef);
  protected readonly abas = ABAS;
  protected readonly rotulos = ROTULOS_SITUACAO;
  protected readonly situacao = signal<'' | SituacaoNoticia>('');
  protected readonly itens = signal<NoticiaGestaoResumo[]>([]);
  protected readonly papel = signal<PapelNoticias | null>(null);
  protected readonly carregando = signal(true);
  protected readonly semAcesso = signal(false);
  protected busca = '';
  // Ordenação das colunas (feita aqui: a lista não é paginada). Padrão: a mais recentemente atualizada primeiro
  protected readonly ordenarPor = signal<ColunaOrdem>('atualizado_em');
  protected readonly direcao = signal<'asc' | 'desc'>('desc');
  protected readonly ordenados = computed(() => {
    const coluna = this.ordenarPor();
    const sinal = this.direcao() === 'asc' ? 1 : -1;
    const valor = (n: NoticiaGestaoResumo): string => {
      // Sem data de publicação = publicação imediata: ordena pela atualização
      if (coluna === 'publicar_em') return n.publicar_em ?? n.atualizado_em;
      if (coluna === 'situacao') return this.rotulos[n.situacao];
      return String(n[coluna] ?? '');
    };
    return [...this.itens()].sort((a, b) => sinal * valor(a).localeCompare(valor(b), 'pt-BR', { numeric: true, sensitivity: 'base' }));
  });
  private readonly digitacao = new Subject<string>();

  ngOnInit(): void {
    this.api.papel().subscribe({ next: (p) => { this.papel.set(p); this.semAcesso.set(!p.redator); }, error: () => undefined });
    this.rota.queryParamMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((q) => {
      this.situacao.set((q.get('situacao') ?? '') as '' | SituacaoNoticia);
      this.busca = q.get('busca') ?? '';
      this.carregar();
    });
    this.digitacao.pipe(debounceTime(300), takeUntilDestroyed(this.destruir)).subscribe((b) =>
      void this.roteador.navigate([], { queryParams: { busca: b.trim() || null }, queryParamsHandling: 'merge', replaceUrl: true }));
  }

  protected navegar(s: string): void {
    void this.roteador.navigate([], { queryParams: { situacao: s || null }, queryParamsHandling: 'merge', replaceUrl: true });
  }

  protected digitar(v: string): void { this.digitacao.next(v); }

  /** Clique no título da coluna: ordena por ela; de novo, inverte o sentido. */
  protected ordenar(coluna: ColunaOrdem): void {
    if (this.ordenarPor() === coluna) this.direcao.update((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      this.ordenarPor.set(coluna);
      this.direcao.set(coluna === 'atualizado_em' || coluna === 'publicar_em' ? 'desc' : 'asc');
    }
  }

  protected sentido(coluna: ColunaOrdem): 'ascending' | 'descending' | 'none' {
    return this.ordenarPor() !== coluna ? 'none' : this.direcao() === 'asc' ? 'ascending' : 'descending';
  }

  private carregar(): void {
    this.carregando.set(true);
    this.api.listar(this.situacao(), this.busca).subscribe({
      next: (l) => { this.itens.set(l); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); if (e?.status === 403) this.semAcesso.set(true); else this.dialogos.mostrarErro(e); },
    });
  }
}
