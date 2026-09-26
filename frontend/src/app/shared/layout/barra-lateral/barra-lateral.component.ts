// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a barra lateral de navegação e controlar os grupos abertos e fechados.

import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { filter } from 'rxjs';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { ItemNavegacao } from '../../../core/navegacao/navegacao.model';
import { NavegacaoService } from '../../../core/navegacao/navegacao.service';
import { IconeComponent } from '../../componentes/icone/icone.component';
import { LayoutService } from '../layout.service';

/**
 * Barra lateral do layout autenticado. Recolhida, mostra só os ícones; expande ao passar o mouse,
 * ao receber o foco do teclado ou quando fixada pelo usuário (estado no `LayoutService`).
 */
@Component({
  selector: 'app-barra-lateral',
  imports: [RouterLink, RouterLinkActive, IconeComponent],
  templateUrl: './barra-lateral.component.html',
  styleUrl: './barra-lateral.component.scss',
  // Eventos da própria barra: mouse ou foco dentro dela a mantêm expandida
  host: {
    '(mouseenter)': 'layout.barraSobMouse.set(true)',
    '(mouseleave)': 'layout.barraSobMouse.set(false)',
    '(focusin)': 'layout.barraSobMouse.set(true)',
    '(focusout)': 'layout.barraSobMouse.set(false)',
  },
})
export class BarraLateralComponent {
  protected readonly layout = inject(LayoutService);
  protected readonly navegacao = inject(NavegacaoService);
  protected readonly autenticacao = inject(AutenticacaoService);
  private readonly roteador = inject(Router);

  /** URL atual, atualizada a cada navegação (faz o destaque dos itens do submenu reagir). */
  private readonly urlAtual = signal(this.roteador.url);

  /** Grupos fechados. Todos começam abertos. */
  private readonly gruposFechados = signal<ReadonlySet<string>>(new Set());

  constructor() {
    // Garante que o grupo da página atual esteja aberto após cada navegação
    this.roteador.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => {
        this.urlAtual.set(this.roteador.url);
        this.abrirGruposAtivos();
      });
  }

  /** Indica se o grupo (submenu) está aberto. */
  protected estaAberto(id: string): boolean {
    return !this.gruposFechados().has(id);
  }

  /** Abre ou fecha um grupo; cria um conjunto novo para o signal perceber a mudança. */
  protected alternarGrupo(id: string): void {
    this.gruposFechados.update((conjunto) => {
      const novo = new Set(conjunto);
      if (novo.has(id)) novo.delete(id);
      else novo.add(id);
      return novo;
    });
  }

  /** Letra inicial do nome do usuário, exibida no avatar. */
  protected inicial(): string {
    const usuario = this.autenticacao.usuario();
    return (usuario?.nome_completo || usuario?.login || '?').charAt(0).toUpperCase();
  }

  /** Reabre os grupos que contêm a página atual (o usuário sempre vê onde está). */
  private abrirGruposAtivos(): void {
    const grupos = this.navegacao.secoes().flatMap((s) => s.itens).filter((i) => i.filhos?.length);
    const ativos = grupos.filter((g) => g.filhos!.some((f) => this.rotaAtiva(f)));
    if (ativos.length) {
      this.gruposFechados.update((conjunto) => new Set([...conjunto].filter((id) => !ativos.some((g) => g.id === id))));
    }
  }

  /** Item do submenu ativo: compara com `rota` (e não com `destino`), relendo a URL atual. */
  protected filhoAtivo(item: ItemNavegacao): boolean {
    this.urlAtual();
    return this.rotaAtiva(item);
  }

  /** Indica se o item corresponde à rota atual (exata ou como prefixo, conforme o item). */
  private rotaAtiva(item: ItemNavegacao): boolean {
    return (
      !!item.rota &&
      this.roteador.isActive(item.rota, {
        paths: item.exata ? 'exact' : 'subset',
        queryParams: 'ignored',
        fragment: 'ignored',
        matrixParams: 'ignored',
      })
    );
  }
}
