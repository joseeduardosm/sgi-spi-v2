// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a leitura de uma página dos Manuais (HTML do BookStack, imagens e links do portal).

import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { Component, ElementRef, Injector, OnDestroy, afterNextRender, effect, inject, input, signal, viewChild } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Router, RouterLink } from '@angular/router';

import { DetalheLivro, DetalhePagina, ManuaisService } from '../../core/manuais/manuais.service';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { erroExibivel } from '../../shared/utilitarios/erros-api';

/** Página de manual: sumário do livro ao lado e o conteúdo (já sanitizado pela API) no centro. */
@Component({
  selector: 'app-pagina-manual',
  imports: [RouterLink, DatePipe, NgTemplateOutlet, TrilhaComponent],
  template: `
    @if (pagina(); as p) {
      <div class="cabecalho-pagina">
        <div>
          <app-trilha [itens]="trilha(p)" />
          <h1>{{ p.nome }}</h1>
          @if (p.atualizado_em) { <small>Atualizado em {{ p.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}</small> }
        </div>
        <div class="acoes-formulario"><a class="acao-secundaria" [href]="p.url_origem" target="_blank" rel="noopener">Abrir no BookStack ↗</a></div>
      </div>

      <div class="manuais-leitura">
        <nav class="manuais-lateral" aria-label="Sumário do livro">
          <strong><a [routerLink]="['/manuais/livros', p.livro_id]">{{ p.livro_nome }}</a></strong>
          @if (livro(); as l) {
            <ul>
              @for (item of l.sumario; track item.tipo + item.id) { <ng-container [ngTemplateOutlet]="entrada" [ngTemplateOutletContext]="{ item, atual: p.id }" /> }
            </ul>
          }
        </nav>

        <article class="painel-gestao manuais-artigo">
          <div #conteudo class="conteudo-manual" [innerHTML]="html()" (click)="aoClicar($event)"></div>
          <div class="manuais-navegacao">
            @if (p.anterior) { <a class="acao-secundaria" [routerLink]="['/manuais/paginas', p.anterior.id]">← {{ p.anterior.nome }}</a> } @else { <span></span> }
            @if (p.proxima) { <a class="acao-secundaria" [routerLink]="['/manuais/paginas', p.proxima.id]">{{ p.proxima.nome }} →</a> }
          </div>
        </article>
      </div>
    } @else if (erro()) {
      <p class="aviso-admin erro" role="alert">{{ erro() }}</p>
    } @else {
      <p class="estado-vazio">Carregando…</p>
    }

    <ng-template #entrada let-item="item" let-atual="atual">
      @if (item.tipo === 'capitulo') {
        <li><span class="manuais-capitulo">{{ item.nome }}</span>
          <ul>@for (filha of item.paginas; track filha.id) { <ng-container [ngTemplateOutlet]="entrada" [ngTemplateOutletContext]="{ item: filha, atual }" /> }</ul>
        </li>
      } @else {
        <li><a [routerLink]="['/manuais/paginas', item.id]" [class.ativo]="item.id === atual" [attr.aria-current]="item.id === atual ? 'page' : null">{{ item.nome }}</a></li>
      }
    </ng-template>
  `,
})
export class PaginaComponent implements OnDestroy {
  private readonly api = inject(ManuaisService);
  private readonly sanitizador = inject(DomSanitizer);
  private readonly roteador = inject(Router);
  private readonly injetor = inject(Injector);

  /** Id da página (parâmetro da rota). */
  readonly id = input.required<string>();
  protected readonly pagina = signal<DetalhePagina | null>(null);
  protected readonly livro = signal<DetalheLivro | null>(null);
  protected readonly erro = signal('');
  /** HTML já sanitizado no servidor (nh3): pode ser confiado ao `innerHTML`, que perderia o atributo `data-caminho` das imagens. */
  protected readonly html = signal<SafeHtml>('');
  private readonly conteudo = viewChild<ElementRef<HTMLElement>>('conteudo');
  private readonly enderecos: string[] = [];

  constructor() {
    effect(() => {
      const id = Number(this.id());
      this.pagina.set(null);
      this.erro.set('');
      this.api.pagina(id).subscribe({
        next: (p) => {
          this.pagina.set(p);
          this.html.set(this.sanitizador.bypassSecurityTrustHtml(p.html));
          // Só depois de o HTML ser desenhado dá para achar as <img>
          afterNextRender(() => this.carregarImagens(), { injector: this.injetor });
          // Sumário lateral: o do livro da página (já em cache na API)
          if (this.livro()?.id !== p.livro_id) this.api.livro(p.livro_id).subscribe({ next: (l) => this.livro.set(l) });
        },
        error: (e) => this.erro.set(erroExibivel(e).mensagem),
      });
    });
  }

  /** Baixa as imagens pela API (com o token) e as mostra como endereços locais; o `<img src>` comum não leva o token. */
  private carregarImagens(): void {
    const raiz = this.conteudo()?.nativeElement;
    raiz?.querySelectorAll<HTMLImageElement>('img[data-caminho]').forEach((img) => {
      this.api.imagem(img.dataset['caminho']!).subscribe({
        next: (blob) => {
          const endereco = URL.createObjectURL(blob);
          this.enderecos.push(endereco);
          img.src = endereco;
        },
        // Imagem indisponível: mantém o texto alternativo
        error: () => img.classList.add('imagem-indisponivel'),
      });
    });
  }

  ngOnDestroy(): void {
    this.enderecos.forEach((e) => URL.revokeObjectURL(e));
  }

  /** Links internos (`/manuais/...`) navegam pelo roteador; âncoras (`#...`) rolam até o título. */
  protected aoClicar(evento: MouseEvent): void {
    const link = (evento.target as HTMLElement).closest('a');
    const destino = link?.getAttribute('href') ?? '';
    if (!link || evento.ctrlKey || evento.metaKey || evento.shiftKey) return;
    if (destino.startsWith('/manuais/')) {
      evento.preventDefault();
      void this.roteador.navigateByUrl(destino);
    } else if (destino.startsWith('#')) {
      evento.preventDefault();
      this.conteudo()?.nativeElement.querySelector(`[id="${CSS.escape(destino.slice(1))}"]`)?.scrollIntoView({ behavior: 'smooth' });
    }
  }

  protected trilha(p: DetalhePagina) {
    const passos = [{ rotulo: 'Manuais', rota: '/manuais' }, { rotulo: p.livro_nome, rota: `/manuais/livros/${p.livro_id}` }];
    return p.capitulo_nome ? [...passos, { rotulo: p.capitulo_nome, rota: `/manuais/livros/${p.livro_id}` }, { rotulo: p.nome }] : [...passos, { rotulo: p.nome }];
  }
}
