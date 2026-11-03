// Criado por José Eduardo Santana Martins
// Este arquivo serve para o campo único "bem do Patrimônio" da Rede: digita a chapa ou a descrição e escolhe na lista que aparece embaixo.

import { Component, DestroyRef, effect, inject, input, model, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, debounceTime, of, Subject, switchMap } from 'rxjs';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { RedeApiService } from './rede-api.service';
import { BemResumo } from './rede.models';

/**
 * Mesmo comportamento e classes do `app-busca-bem` do Patrimônio (um campo, a lista logo abaixo, setas, Enter e Esc), mas buscando pela
 * API da Rede (`/rede/bens`), que vale para quem tem acesso à Rede mesmo sem acesso ao Patrimônio.
 * Escolhido o bem, o campo mostra "chapa · descrição" e o "×" limpa; voltar a digitar desfaz a escolha.
 */
@Component({
  selector: 'app-busca-bem-rede',
  imports: [EsqueletoComponent],
  template: `
    <div class="pat-seletor-sala" role="combobox" [attr.aria-expanded]="aberto()" aria-haspopup="listbox">
      <input type="text" [id]="idCampo()" autocomplete="off" placeholder="Digite a chapa ou a descrição (ex.: 012345 ou impressora)"
             aria-autocomplete="list" [value]="texto()" (input)="digitou($any($event.target).value)" (blur)="fecharDepois()" (focus)="reabrir()" (keydown)="teclado($event)" />
      @if (bemId()) {
        <button type="button" class="pat-limpar-sala" aria-label="Limpar o bem escolhido" (mousedown)="$event.preventDefault()" (click)="limpar()">×</button>
      }
      @if (aberto()) {
        <ul class="pat-opcoes-sala pat-opcoes-bem" role="listbox">
          @for (b of sugestoes(); track b.id; let i = $index) {
            <li role="option" [attr.aria-selected]="i === destacado()" [class.destacada]="i === destacado()" (mousedown)="$event.preventDefault()" (click)="escolher(b)" (mouseenter)="destacado.set(i)">
              <strong class="texto-codigo">{{ b.chapa || 'sem chapa' }}</strong> <span>{{ b.descricao }}</span>
              @if (b.sala) { <small>{{ b.sala }}</small> }
            </li>
          } @empty { <li class="pat-sem-sala" role="presentation">@if (buscando()) { <app-esqueleto tipo="texto" [linhas]="2" /> } @else { Nenhum bem encontrado com este trecho. }</li> }
        </ul>
      }
    </div>
  `,
  // A lista encosta no campo (4px abaixo), descontando a margem que separa o campo do vizinho, como no campo de sala
  styles: [':host { display: block; } .pat-opcoes-bem { top: calc(100% - 10px); margin-top: 0; }'],
})
export class BuscaBemRedeComponent {
  private readonly api = inject(RedeApiService);
  private readonly busca$ = new Subject<string>();

  /** Bem escolhido (mão dupla): o pai lê para ligar e zera depois. */
  readonly bemId = model<string | null>(null);
  readonly idCampo = input('');

  protected readonly texto = signal('');
  protected readonly sugestoes = signal<BemResumo[]>([]);
  protected readonly aberto = signal(false);
  protected readonly buscando = signal(false);
  protected readonly destacado = signal(-1);
  /** Texto do bem escolhido: quando o pai zera `bemId` (depois de ligar), o campo se esvazia. */
  private rotuloEscolhido = '';

  constructor() {
    effect(() => {
      if (!this.bemId() && this.rotuloEscolhido) {
        this.rotuloEscolhido = '';
        this.texto.set('');
        this.sugestoes.set([]);
      }
    });
    this.busca$.pipe(
      debounceTime(250),
      switchMap((q) => {
        if (q.trim().length < 2) return of(null);
        this.buscando.set(true);
        return this.api.bens(q.trim()).pipe(catchError(() => of(null)));
      }),
      takeUntilDestroyed(inject(DestroyRef)),
    ).subscribe((lista) => {
      this.buscando.set(false);
      this.sugestoes.set(lista ?? []);
      this.destacado.set(-1);
      this.aberto.set(lista !== null && this.texto().trim().length >= 2 && !this.bemId());
    });
  }

  protected digitou(valor: string): void {
    this.rotuloEscolhido = '';
    this.texto.set(valor);
    this.bemId.set(null);
    if (valor.trim().length < 2) { this.aberto.set(false); this.sugestoes.set([]); }
    this.busca$.next(valor);
  }

  protected reabrir(): void {
    if (!this.bemId() && this.sugestoes().length && this.texto().trim().length >= 2) this.aberto.set(true);
  }

  protected fecharDepois(): void {
    setTimeout(() => this.aberto.set(false), 150);
  }

  protected escolher(b: BemResumo): void {
    this.aberto.set(false);
    this.rotuloEscolhido = `${b.chapa || 'sem chapa'} · ${b.descricao}`;
    this.texto.set(this.rotuloEscolhido);
    this.bemId.set(b.id);
  }

  protected limpar(): void {
    this.texto.set('');
    this.sugestoes.set([]);
    this.bemId.set(null);
  }

  protected teclado(evento: KeyboardEvent): void {
    const total = this.sugestoes().length;
    if (evento.key === 'ArrowDown' && total) { evento.preventDefault(); this.aberto.set(true); this.destacado.set((this.destacado() + 1) % total); }
    else if (evento.key === 'ArrowUp' && total) { evento.preventDefault(); this.destacado.set((this.destacado() - 1 + total) % total); }
    else if (evento.key === 'Escape') this.aberto.set(false);
    else if (evento.key === 'Enter' && this.aberto()) {
      // Enter escolhe o destacado (ou o único da lista); sem lista aberta, deixa o formulário seguir
      const alvo = this.sugestoes()[this.destacado()] ?? (total === 1 ? this.sugestoes()[0] : undefined);
      if (alvo) { evento.preventDefault(); this.escolher(alvo); }
    }
  }
}
