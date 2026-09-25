// Criado por José Eduardo Santana Martins
// Este arquivo serve para oferecer um campo de pesquisa e seleção de usuários (um ou vários).

import { Component, ElementRef, inject, input, model, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { debounceTime, Observable, Subject, switchMap } from 'rxjs';

import { OpcaoUsuario } from '../../../core/modelos/usuario.model';

/**
 * Seletor de usuários com pesquisa no servidor.
 * `multiplo=false` mantém no máximo um selecionado (gestor, líder).
 */
@Component({
  selector: 'app-seletor-usuarios',
  templateUrl: './seletor-usuarios.component.html',
  styleUrl: './seletor-usuarios.component.scss',
  // Clique em qualquer lugar do documento: usado para fechar a lista ao clicar fora do componente
  host: { '(document:click)': 'aoClicarDocumento($event)' },
})
export class SeletorUsuariosComponent {
  // `model`: valor de mão dupla ([(selecionados)]); a tela lê e altera a mesma lista
  readonly selecionados = model<OpcaoUsuario[]>([]);
  // Função que busca usuários na API; cada tela passa a sua (ex.: opções de gestor, opções da equipe)
  readonly fonte = input.required<(busca: string) => Observable<OpcaoUsuario[]>>();
  readonly multiplo = input(true);
  readonly textoAjuda = input('Pesquisar por nome, login ou cargo');
  readonly idCampo = input<string>();

  // Estado da lista de sugestões
  protected readonly resultados = signal<OpcaoUsuario[]>([]);
  protected readonly aberto = signal(false);
  protected readonly carregando = signal(false);
  protected termo = '';

  // Fluxo de termos digitados; o componente em si (para detectar cliques fora dele)
  private readonly busca$ = new Subject<string>();
  private readonly elemento = inject(ElementRef<HTMLElement>);

  constructor() {
    // Pesquisa enquanto o usuário digita:
    // - debounceTime: espera 250 ms sem digitação antes de pesquisar (evita uma chamada por tecla);
    // - switchMap: cancela a pesquisa anterior se chegar um termo novo;
    // - takeUntilDestroyed: encerra a assinatura quando o componente é destruído.
    this.busca$
      .pipe(
        debounceTime(250),
        switchMap((termo) => {
          this.carregando.set(true);
          return this.fonte()(termo);
        }),
        takeUntilDestroyed(),
      )
      .subscribe({
        // Mostra só quem ainda não está selecionado
        next: (itens) => {
          const escolhidos = new Set(this.selecionados().map((u) => u.id));
          this.resultados.set(itens.filter((u) => !escolhidos.has(u.id)));
          this.carregando.set(false);
        },
        error: () => this.carregando.set(false),
      });
  }

  /** A cada tecla: guarda o termo, abre a lista e agenda a pesquisa. */
  protected aoDigitar(valor: string): void {
    this.termo = valor;
    this.aberto.set(true);
    this.busca$.next(valor.trim());
  }

  /** Ao focar o campo, abre a lista com o termo atual. */
  protected aoFocar(): void {
    this.aberto.set(true);
    this.busca$.next(this.termo.trim());
  }

  /** Seleciona um usuário; no modo de seleção única, substitui o anterior e fecha a lista. */
  protected adicionar(usuario: OpcaoUsuario): void {
    this.selecionados.set(this.multiplo() ? [...this.selecionados(), usuario] : [usuario]);
    this.resultados.update((r) => r.filter((u) => u.id !== usuario.id));
    this.termo = '';
    if (!this.multiplo()) this.aberto.set(false);
  }

  /** Remove um usuário da seleção. */
  protected remover(usuario: OpcaoUsuario): void {
    this.selecionados.set(this.selecionados().filter((u) => u.id !== usuario.id));
  }

  /** Fecha a lista quando o clique foi fora do componente. */
  protected aoClicarDocumento(evento: MouseEvent): void {
    if (!(this.elemento.nativeElement as HTMLElement).contains(evento.target as Node)) this.aberto.set(false);
  }
}
