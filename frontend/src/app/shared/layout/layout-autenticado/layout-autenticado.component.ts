// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar a moldura das telas autenticadas (barra lateral, barra superior e conteúdo).

import { Component, DestroyRef, ElementRef, inject, signal, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter, map, startWith, tap } from 'rxjs';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { AtalhosService } from '../../../core/navegacao/atalhos.service';
import { PreferenciaTema, TemaService } from '../../../core/tema/tema.service';
import { CaixaMensagensService } from '../../../core/mensagens/caixa-mensagens.service';
import { JanelaMensagemComponent } from '../../../features/mensagens/janela-mensagem.component';
import { FolhaPontoDialogoComponent } from '../../../features/rh/folha-ponto-dialogo.component';
import { DialogosComponent } from '../../componentes/dialogos/dialogos.component';
import { IconeComponent } from '../../componentes/icone/icone.component';
import { BotaoMelhoriasComponent } from '../../componentes/botao-melhorias/botao-melhorias.component';
import { AbrirChamadoComponent } from '../../componentes/abrir-chamado/abrir-chamado.component';
import { BuscaGlobalComponent } from '../../componentes/busca-global/busca-global.component';
import { BarraLateralComponent } from '../barra-lateral/barra-lateral.component';
import { LayoutService } from '../layout.service';

/** Layout das rotas autenticadas: barra lateral, barra superior e área de conteúdo. */
@Component({
  selector: 'app-layout-autenticado',
  imports: [
    RouterOutlet, RouterLink, BarraLateralComponent, IconeComponent, DialogosComponent, JanelaMensagemComponent, FolhaPontoDialogoComponent,
    BotaoMelhoriasComponent, BuscaGlobalComponent, AbrirChamadoComponent,
  ],
  templateUrl: './layout-autenticado.component.html',
  styleUrl: './layout-autenticado.component.scss',
  // Esc fecha menus abertos; clique fora do menu do usuário o fecha
  host: {
    '(document:keydown.escape)': 'layout.fecharSobreposicoes()',
    '(document:click)': 'aoClicarDocumento($event)',
    '(document:keydown)': 'aoTeclar($event)',
  },
})
export class LayoutAutenticadoComponent {
  protected readonly layout = inject(LayoutService);
  protected readonly autenticacao = inject(AutenticacaoService);
  // Seletor de tema do menu do usuário
  protected readonly tema = inject(TemaService);
  protected readonly opcoesTema: { valor: PreferenciaTema; rotulo: string }[] = [
    { valor: 'claro', rotulo: 'Claro' },
    { valor: 'escuro', rotulo: 'Escuro' },
    { valor: 'auto', rotulo: 'Auto' },
  ];
  private readonly roteador = inject(Router);
  protected readonly atalhos = inject(AtalhosService);
  private readonly busca = viewChild<BuscaGlobalComponent>('busca');
  private readonly elemento = inject(ElementRef<HTMLElement>);
  // Sino da mensageria (contador de pendentes) e janela de avisos
  protected readonly caixa = inject(CaixaMensagensService);

  constructor() {
    this.caixa.iniciar(inject(DestroyRef));
  }

  /** Título da página atual, extraído do `title` da rota ("Início | SGI SPI" → "Início"). */
  // `toSignal` transforma o fluxo de eventos do roteador em um signal que o template lê diretamente.
  // A cada navegação concluída: fecha menus abertos e recalcula o título.
  protected readonly tituloPagina = toSignal(
    this.roteador.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      tap(() => {
        this.layout.fecharSobreposicoes();
        this.caixa.atualizar();
        // A tela aberta entra nos recentes e passa a ser a "atual" (a estrela do topo age sobre ela)
        this.urlAtual.set(this.roteador.url);
        this.atalhos.registrar(this.roteador.url, this.tituloAtual());
      }),
      startWith(null),
      map(() => this.tituloAtual()),
    ),
    { initialValue: '' },
  );

  /** URL atual (com query string): é a que a estrela do topo fixa ou solta. */
  protected readonly urlAtual = signal(this.roteador.url);

  protected favorita(): boolean {
    return this.atalhos.ehFavorito(this.urlAtual());
  }

  /** Fixa ou solta a tela atual; o nome vem dos recentes, que a própria tela pode ter detalhado (ex.: "Contrato 004/2025"). */
  protected alternarFavorita(): void {
    const url = this.urlAtual();
    const rotulo = this.atalhos.recentes().find((r) => r.rota === url)?.rotulo ?? this.tituloAtual();
    this.atalhos.alternar(url, rotulo);
  }

  /** Atalhos de teclado: Ctrl+K (ou Cmd+K) e "/" levam à busca global, exceto quando a pessoa está digitando em um campo. */
  protected aoTeclar(evento: KeyboardEvent): void {
    const alvo = evento.target as HTMLElement | null;
    const digitando = !!alvo && (alvo.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo.tagName));
    if (((evento.ctrlKey || evento.metaKey) && evento.key.toLowerCase() === 'k') || (evento.key === '/' && !digitando && !evento.ctrlKey && !evento.metaKey)) {
      const busca = this.busca();
      if (!busca) return;
      evento.preventDefault();
      busca.focar();
    }
  }

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

  protected abrirAssinatura(): void {
    this.layout.fecharSobreposicoes();
    void this.roteador.navigate(['/assinatura-email']);
  }

  /** Janela da folha de ponto (criada ao abrir: a lista de competências é sempre a do mês atual). */
  protected readonly folhaPontoAberta = signal(false);

  protected abrirFolhaPonto(): void {
    this.layout.fecharSobreposicoes();
    this.folhaPontoAberta.set(true);
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
