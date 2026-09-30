// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar as notícias na gestão, com abas por situação (a de aprovação mostra o total pendente).

import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { debounceTime, Subject } from 'rxjs';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { NoticiasApiService } from '../noticias-api.service';
import { NoticiaGestaoResumo, PapelNoticias, ROTULOS_SITUACAO, SituacaoNoticia } from '../noticias.models';
import { CabecalhoNoticiasComponent } from './cabecalho-noticias.component';
import { ImagemAutenticadaDirective } from './imagem-autenticada.directive';

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
            <thead><tr><th>Capa</th><th>Notícia</th><th>Situação</th><th>Publicação</th><th>Autor</th><th>Atualizada</th></tr></thead>
            <tbody>
              @for (n of itens(); track n.id) {
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

  private carregar(): void {
    this.carregando.set(true);
    this.api.listar(this.situacao(), this.busca).subscribe({
      next: (l) => { this.itens.set(l); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); if (e?.status === 403) this.semAcesso.set(true); else this.dialogos.mostrarErro(e); },
    });
  }
}
