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
  protected readonly tituloPagina = toSignal(
    this.roteador.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      tap(() => this.layout.fecharSobreposicoes()),
      startWith(null),
      map(() => this.tituloAtual()),
    ),
    { initialValue: '' },
  );

  protected inicial(): string {
    const usuario = this.autenticacao.usuario();
    return (usuario?.nome_completo || usuario?.login || '?').charAt(0).toUpperCase();
  }

  protected abrirPerfil(): void {
    this.layout.fecharSobreposicoes();
    void this.roteador.navigate(['/perfil']);
  }

  protected sair(): void {
    this.layout.fecharSobreposicoes();
    this.autenticacao.sair();
  }

  protected aoClicarDocumento(evento: MouseEvent): void {
    const menu = (this.elemento.nativeElement as HTMLElement).querySelector('.menu-usuario');
    if (this.layout.menuUsuarioAberto() && menu && !menu.contains(evento.target as Node)) {
      this.layout.menuUsuarioAberto.set(false);
    }
  }

  private tituloAtual(): string {
    let rota = this.roteador.routerState.snapshot.root;
    while (rota.firstChild) rota = rota.firstChild;
    return (rota.title ?? '').split(' | ')[0] || 'Início';
  }
}
