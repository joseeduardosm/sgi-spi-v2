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
  host: { '(document:click)': 'aoClicarDocumento($event)' },
})
export class SeletorUsuariosComponent {
  readonly selecionados = model<OpcaoUsuario[]>([]);
  readonly fonte = input.required<(busca: string) => Observable<OpcaoUsuario[]>>();
  readonly multiplo = input(true);
  readonly textoAjuda = input('Pesquisar por nome, login ou cargo');
  readonly idCampo = input<string>();

  protected readonly resultados = signal<OpcaoUsuario[]>([]);
  protected readonly aberto = signal(false);
  protected readonly carregando = signal(false);
  protected termo = '';

  private readonly busca$ = new Subject<string>();
  private readonly elemento = inject(ElementRef<HTMLElement>);

  constructor() {
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
        next: (itens) => {
          const escolhidos = new Set(this.selecionados().map((u) => u.id));
          this.resultados.set(itens.filter((u) => !escolhidos.has(u.id)));
          this.carregando.set(false);
        },
        error: () => this.carregando.set(false),
      });
  }

  protected aoDigitar(valor: string): void {
    this.termo = valor;
    this.aberto.set(true);
    this.busca$.next(valor.trim());
  }

  protected aoFocar(): void {
    this.aberto.set(true);
    this.busca$.next(this.termo.trim());
  }

  protected adicionar(usuario: OpcaoUsuario): void {
    this.selecionados.set(this.multiplo() ? [...this.selecionados(), usuario] : [usuario]);
    this.resultados.update((r) => r.filter((u) => u.id !== usuario.id));
    this.termo = '';
    if (!this.multiplo()) this.aberto.set(false);
  }

  protected remover(usuario: OpcaoUsuario): void {
    this.selecionados.set(this.selecionados().filter((u) => u.id !== usuario.id));
  }

  protected aoClicarDocumento(evento: MouseEvent): void {
    if (!(this.elemento.nativeElement as HTMLElement).contains(evento.target as Node)) this.aberto.set(false);
  }
}
