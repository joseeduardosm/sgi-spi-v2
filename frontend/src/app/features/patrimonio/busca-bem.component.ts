// Criado por José Eduardo Santana Martins
// Este arquivo serve para o campo "chapa ou número de série" com lista de sugestões (combobox): ao digitar um trecho, mostra os bens para clicar.

import { Component, DestroyRef, inject, input, model, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { catchError, debounceTime, of, Subject, switchMap } from 'rxjs';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { Bem } from './patrimonio.models';

/**
 * Combobox de bem. Conforme a pessoa digita (a partir de 2 caracteres), a lista mostra os bens cuja chapa, número de série ou descrição contêm o
 * trecho; clicar (ou Enter no destacado) emite `escolhido` com o bem. Enter sem escolher uma sugestão emite `enviar` com o texto digitado
 * (o servidor confere a chapa ou o número de série). Setas ↑ ↓ navegam e Esc fecha. Sem conexão não há sugestões e o campo segue como texto livre.
 */
@Component({
  selector: 'app-busca-bem',
  imports: [FormsModule, EsqueletoComponent],
  template: `
    <div class="pat-seletor-sala" role="combobox" [attr.aria-expanded]="aberto()" aria-haspopup="listbox">
      <input type="text" [name]="nome()" autocomplete="off" [placeholder]="placeholder()" [attr.aria-label]="rotulo()" aria-autocomplete="list"
             [ngModel]="texto()" (ngModelChange)="digitou($event)" (blur)="fecharDepois()" (focus)="reabrir()" (keydown)="teclado($event)" />
      @if (aberto()) {
        <ul class="pat-opcoes-sala pat-opcoes-bem" role="listbox">
          @for (b of sugestoes(); track b.id; let i = $index) {
            <li role="option" [attr.aria-selected]="i === destacado()" [class.destacada]="i === destacado()" (mousedown)="$event.preventDefault()" (click)="escolher(b)" (mouseenter)="destacado.set(i)">
              <strong>{{ b.rotulo }}</strong> <span>{{ b.descricao }}</span>
              <small>@if (b.chapa && b.numero_serie) { Série {{ b.numero_serie }} · }{{ b.sala_rotulo }}@if (b.situacao !== 'ativo') { · {{ situacoes[b.situacao] ?? b.situacao }} }</small>
            </li>
          } @empty { <li class="pat-sem-sala" role="presentation">@if (buscando()) { <app-esqueleto tipo="texto" [linhas]="2" /> } @else { Nenhum bem encontrado com este trecho. }</li> }
        </ul>
      }
    </div>
  `,
})
export class BuscaBemComponent {
  private readonly api = inject(PatrimonioApiService);
  private readonly busca$ = new Subject<string>();

  /** Texto digitado (mão dupla): o pai limpa o campo depois de incluir. */
  readonly texto = model('');
  readonly nome = input('busca-bem');
  readonly rotulo = input('Pesquisar bem');
  readonly placeholder = input('Pesquise por chapa, série, descrição, marca, modelo, local…');
  /** Restringe a busca a uma situação (ex.: só os inservíveis na baixa). */
  readonly situacao = input<string>('');
  readonly escolhido = output<Bem>();
  /** Enter com texto e sem sugestão destacada. */
  readonly enviar = output<string>();

  protected readonly sugestoes = signal<Bem[]>([]);
  protected readonly aberto = signal(false);
  protected readonly buscando = signal(false);
  protected readonly destacado = signal(-1);
  protected readonly situacoes: Record<string, string> = { inservivel: 'Inservível', extraviado: 'Extraviado', em_manutencao: 'Em manutenção', baixado: 'Baixado' };

  constructor() {
    this.busca$.pipe(
      debounceTime(250),
      switchMap((q) => {
        if (q.trim().length < 2) return of(null);
        this.buscando.set(true);
        return this.api.bens({ q: q.trim(), tamanho: 8, ordenar_por: 'chapa', direcao: 'asc', ...(this.situacao() ? { situacao: this.situacao() as never } : {}) })
          .pipe(catchError(() => of(null)));
      }),
      takeUntilDestroyed(inject(DestroyRef)),
    ).subscribe((resposta) => {
      this.buscando.set(false);
      this.sugestoes.set(resposta?.itens ?? []);
      this.destacado.set(-1);
      this.aberto.set(resposta !== null && this.texto().trim().length >= 2);
    });
  }

  protected digitou(valor: string): void {
    this.texto.set(valor);
    if (valor.trim().length < 2) { this.aberto.set(false); this.sugestoes.set([]); }
    this.busca$.next(valor);
  }

  protected reabrir(): void {
    if (this.sugestoes().length && this.texto().trim().length >= 2) this.aberto.set(true);
  }

  protected fecharDepois(): void {
    setTimeout(() => this.aberto.set(false), 150);
  }

  protected escolher(b: Bem): void {
    this.aberto.set(false);
    this.sugestoes.set([]);
    this.texto.set('');
    this.escolhido.emit(b);
  }

  protected teclado(evento: KeyboardEvent): void {
    const total = this.sugestoes().length;
    if (evento.key === 'ArrowDown' && total) { evento.preventDefault(); this.aberto.set(true); this.destacado.set((this.destacado() + 1) % total); }
    else if (evento.key === 'ArrowUp' && total) { evento.preventDefault(); this.destacado.set((this.destacado() - 1 + total) % total); }
    else if (evento.key === 'Escape') this.aberto.set(false);
    else if (evento.key === 'Enter') {
      evento.preventDefault();
      const alvo = this.sugestoes()[this.destacado()];
      if (this.aberto() && alvo) this.escolher(alvo);
      else if (this.texto().trim()) { this.aberto.set(false); this.enviar.emit(this.texto().trim()); }
    }
  }
}
