// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar as sugestões do usuário logado, com a situação, a resposta da equipe e os prints.

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { ImagemAutenticadaDirective } from '../noticias/gestao/imagem-autenticada.directive';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoMelhoriasComponent } from './cabecalho-melhorias.component';
import { MelhoriasApiService } from './melhorias-api.service';
import { PrintSugestao, ROTULOS_MODULO, ROTULOS_SITUACAO, SugestaoAutor } from './melhorias.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

@Component({
  selector: 'app-minhas-sugestoes',
  imports: [LinkificarPipe, DatePipe, CabecalhoMelhoriasComponent, ImagemAutenticadaDirective],
  template: `
    <app-cabecalho-melhorias titulo="Minhas sugestões"
      descricao="Sugestões que você enviou pelo botão &quot;Sugerir melhoria&quot;, com a situação e a resposta da equipe." />
    <section class="painel-gestao lista-sugestoes">
      @for (s of itens(); track s.id) {
        <article class="cartao-sugestao" [class.destacada]="s.numero === destaque()" [attr.id]="'sugestao-' + s.numero">
          <header>
            <strong>#{{ s.numero }}</strong>
            <span class="selo-sugestao" [attr.data-situacao]="s.situacao">{{ rotulos[s.situacao] }}</span>
            <span class="modulo-sugestao">{{ modulos[s.modulo] ?? s.modulo }}</span>
            <time [attr.datetime]="s.criado_em">{{ s.criado_em | date: 'dd/MM/yyyy HH:mm' }}</time>
          </header>
          <p class="texto-sugestao" [innerHTML]="s.texto | linkificar"></p>
          @if (s.prints.length) {
            <div class="prints-sugestao">
              @for (p of s.prints; track p.id) {
                <button type="button" [title]="'Baixar ' + p.nome" (click)="baixar(p)"><img [appImagemAutenticada]="p.url" [alt]="p.nome" /></button>
              }
            </div>
          }
          @if (s.resposta_publica) {
            <div class="resposta-sugestao"><span>Resposta da equipe</span><p>{{ s.resposta_publica }}</p>
              @if (s.atualizado_em) { <small>{{ s.atualizado_em | date: 'dd/MM/yyyy HH:mm' }}</small> }</div>
          }
        </article>
      } @empty {
        <p class="estado-vazio">{{ carregando() ? 'Carregando…' : 'Você ainda não enviou sugestões. Use o botão "Sugerir melhoria", no canto da tela.' }}</p>
      }
      @if (total() > itens().length) {
        <div class="acoes-cartao"><button type="button" class="acao-secundaria" (click)="carregar(pagina() + 1)">Carregar mais</button></div>
      }
    </section>
  `,
})
export class MinhasSugestoesComponent implements OnInit {
  private readonly api = inject(MelhoriasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  protected readonly rotulos = ROTULOS_SITUACAO;
  protected readonly modulos = ROTULOS_MODULO;
  protected readonly itens = signal<SugestaoAutor[]>([]);
  protected readonly total = signal(0);
  protected readonly pagina = signal(1);
  protected readonly carregando = signal(true);
  // Link do aviso (?sugestao=N) destaca a sugestão
  protected readonly destaque = signal<number | null>(null);

  ngOnInit(): void {
    const n = Number(this.rota.snapshot.queryParamMap.get('sugestao'));
    if (n) this.destaque.set(n);
    this.carregar(1);
  }

  protected carregar(pagina: number): void {
    this.carregando.set(true);
    this.api.minhas(pagina).subscribe({
      next: (p) => {
        this.itens.update((l) => (pagina === 1 ? p.itens : [...l, ...p.itens]));
        this.total.set(p.total);
        this.pagina.set(pagina);
        this.carregando.set(false);
        if (this.destaque()) setTimeout(() => document.getElementById(`sugestao-${this.destaque()}`)?.scrollIntoView({ block: 'center' }));
      },
      error: (e) => {
        this.carregando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível carregar as suas sugestões');
      },
    });
  }

  protected baixar(p: PrintSugestao): void {
    this.api.baixarPrint(p.url, p.nome).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }
}
