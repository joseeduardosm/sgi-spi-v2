// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a moldura das telas autenticadas (barra lateral, barra superior e conteúdo).

import { Component, ElementRef, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter, map, startWith, tap } from 'rxjs';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { DialogosComponent } from '../../componentes/dialogos/dialogos.component';
import { IconeComponent } from '../../componentes/icone/icone.component';
import { BarraLateralComponent } from '../barra-lateral/barra-lateral.component';
import { LayoutService } from '../layout.service';

/** Layout das rotas autenticadas: barra lateral, barra superior e área de conteúdo. */
@Component({
  selector: 'app-layout-autenticado',
  imports: [RouterOutlet, BarraLateralComponent, IconeComponent, DialogosComponent],
  templateUrl: './layout-autenticado.component.html',
  styleUrl: './layout-autenticado.component.scss',
  // Esc fecha menus abertos; clique fora do menu do usuário o fecha
  host: {
    '(document:keydown.escape)': 'layout.fecharSobreposicoes()',
    '(document:click)': 'aoClicarDocumento($event)',
  },
})
export class LayoutAutenticadoComponent {
  protected readonly layout = inject(LayoutService);
  protected readonly autenticacao = inject(AutenticacaoService);
  private readonly roteador = inject(Router);
  private readonly elemento = inject(ElementRef<HTMLElement>);

  /** Título da página atual, extraído do `title` da rota ("Início | Contratos SPI" → "Início"). */
  // `toSignal` transforma o fluxo de eventos do roteador em um signal que o template lê diretamente.
  // A cada navegação concluída: fecha menus abertos e recalcula o título.
  protected readonly tituloPagina = toSignal(
    this.roteador.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      tap(() => this.layout.fecharSobreposicoes()),
      startWith(null),
      map(() => this.tituloAtual()),
    ),
    { initialValue: '' },
  );

  /** Letra inicial do nome do usuário, exibida no avatar. */
  protected inicial(): string {
    const usuario = this.autenticacao.usuario();
    return (usuario?.nome_completo || usuario?.login || '?').charAt(0).toUpperCase();
  }

  /** Abre a página "Meu perfil" a partir do menu do usuário. */
  protected abrirPerfil(): void {
    this.layout.fecharSobreposicoes();
    void this.roteador.navigate(['/perfil']);
  }

  /** Encerra a sessão a partir do menu do usuário. */
  protected sair(): void {
    this.layout.fecharSobreposicoes();
    this.autenticacao.sair();
  }

  /** Fecha o menu do usuário quando o clique acontece fora dele. */
  protected aoClicarDocumento(evento: MouseEvent): void {
    const menu = (this.elemento.nativeElement as HTMLElement).querySelector('.menu-usuario');
    if (this.layout.menuUsuarioAberto() && menu && !menu.contains(evento.target as Node)) {
      this.layout.menuUsuarioAberto.set(false);
    }
  }

  /** Título da rota mais interna ativa (a tela aberta de fato). */
  private tituloAtual(): string {
    let rota = this.roteador.routerState.snapshot.root;
    // Desce até a última rota filha, que é a tela exibida
    while (rota.firstChild) rota = rota.firstChild;
    return (rota.title ?? '').split(' | ')[0] || 'Início';
  }
}
