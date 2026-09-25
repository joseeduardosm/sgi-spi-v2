import { Component, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { filter } from 'rxjs';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { ItemNavegacao } from '../../../core/navegacao/navegacao.model';
import { NavegacaoService } from '../../../core/navegacao/navegacao.service';
import { IconeComponent } from '../../componentes/icone/icone.component';
import { LayoutService } from '../layout.service';

@Component({
  selector: 'app-barra-lateral',
  imports: [RouterLink, RouterLinkActive, IconeComponent],
  templateUrl: './barra-lateral.component.html',
  styleUrl: './barra-lateral.component.scss',
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

  /** Grupos fechados. Todos começam abertos. */
  private readonly gruposFechados = signal<ReadonlySet<string>>(new Set());

  constructor() {
    // Garante que o grupo da página atual esteja aberto após cada navegação
    this.roteador.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.abrirGruposAtivos());
  }

  protected estaAberto(id: string): boolean {
    return !this.gruposFechados().has(id);
  }

  protected alternarGrupo(id: string): void {
    this.gruposFechados.update((conjunto) => {
      const novo = new Set(conjunto);
      if (novo.has(id)) novo.delete(id);
      else novo.add(id);
      return novo;
    });
  }

  protected inicial(): string {
    const usuario = this.autenticacao.usuario();
    return (usuario?.nome_completo || usuario?.login || '?').charAt(0).toUpperCase();
  }

  private abrirGruposAtivos(): void {
    const grupos = this.navegacao.secoes().flatMap((s) => s.itens).filter((i) => i.filhos?.length);
    const ativos = grupos.filter((g) => g.filhos!.some((f) => this.rotaAtiva(f)));
    if (ativos.length) {
      this.gruposFechados.update((conjunto) => new Set([...conjunto].filter((id) => !ativos.some((g) => g.id === id))));
    }
  }

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
