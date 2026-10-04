// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a página inicial do sistema: o portal de notícias (slider, cartões e atalhos).

import { Component, inject, input, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AcessoService } from '../../../core/acesso/acesso.service';
import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { NoticiasApiService } from '../noticias-api.service';
import { Portal } from '../noticias.models';
import { PainelExecutivoComponent } from '../../painel-executivo/painel-executivo.component';
import { AniversariantesComponent } from '../../diretorio/aniversariantes.component';
import { CartaoNoticiaComponent } from './cartao-noticia.component';
import { SliderNoticiasComponent } from './slider-noticias.component';

/** Página inicial (pública). Tudo o que aparece aqui é configurado em Notícias › Configurar portal. */
@Component({
  selector: 'app-portal',
  imports: [RouterLink, SliderNoticiasComponent, CartaoNoticiaComponent, AniversariantesComponent, PainelExecutivoComponent],
  template: `
    @if (acesso() === 'negado') {
      <div class="alert alert-warning" role="status">Você não possui acesso ao módulo solicitado. Solicite a revisão da ACL a um administrador do sistema.</div>
    }
    @if (portal(); as p) {
      <div class="cabecalho-portal">
        <div>
          @if (autenticacao.usuario(); as u) { <p class="saudacao-portal">Olá, {{ u.nome_completo }}</p> }
          <h1>{{ p.configuracao.titulo }}</h1>
          @if (p.configuracao.subtitulo) { <small>{{ p.configuracao.subtitulo }}</small> }
        </div>
      </div>
      @if (permissoes.painelExecutivo()) { <app-painel-executivo [compacto]="true" /> }
      @if (autenticacao.usuario()) { <app-aniversariantes /> }
      <div class="grade-portal" [class.sem-atalhos]="!p.atalhos.length">
        <div class="coluna-noticias">
          @if (p.slides.length) {
            <app-slider-noticias [slides]="p.slides" [segundos]="p.configuracao.segundos_por_slide"
                                 [automatico]="p.configuracao.passagem_automatica" [tituloSobreposto]="p.configuracao.titulo_sobreposto" />
          } @else {
            <p class="estado-vazio cartao-dados">Nenhuma notícia publicada ainda.</p>
          }
          @if (p.cartoes.length || p.configuracao.exibir_todas) {
            <div class="cartoes-portal">
              @for (n of p.cartoes; track n.id) { <app-cartao-noticia [noticia]="n" [mostrarLinhaFina]="false" /> }
              @if (p.configuracao.exibir_todas) {
                <a class="cartao-todas" routerLink="/noticias">Ver todas as notícias <span aria-hidden="true">→</span></a>
              }
            </div>
          }
        </div>
        @if (p.atalhos.length) {
          <aside class="atalhos-portal" aria-label="Atalhos">
            <h2>Atalhos</h2>
            <div class="grade-atalhos">
              @for (a of p.atalhos; track a.id) {
                <a class="atalho" [href]="a.url" [attr.target]="a.nova_aba ? '_blank' : null" [attr.rel]="a.nova_aba ? 'noopener' : null">
                  @if (a.imagem) { <img [src]="a.imagem" alt="" loading="lazy" /> }
                  <span>{{ a.titulo }}</span>
                </a>
              }
            </div>
          </aside>
        }
      </div>
    } @else if (erro()) {
      <p class="estado-vazio">Não foi possível carregar as notícias agora. Tente novamente em instantes.</p>
    } @else {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class PortalComponent implements OnInit {
  /** Preenchido pelo guardaAcl ao negar acesso a um módulo (?acesso=negado). */
  readonly acesso = input<string>();
  protected readonly autenticacao = inject(AutenticacaoService);
  protected readonly permissoes = inject(AcessoService);
  private readonly api = inject(NoticiasApiService);
  protected readonly portal = signal<Portal | null>(null);
  protected readonly erro = signal(false);

  ngOnInit(): void {
    this.api.portal().subscribe({ next: (p) => this.portal.set(p), error: () => this.erro.set(true) });
  }
}
