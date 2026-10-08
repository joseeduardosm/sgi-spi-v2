// Criado por José Eduardo Santana Martins
// Este arquivo serve para oferecer a caixa de busca global do topo (Ctrl+K ou "/"): telas do menu, contratos, tarefas, pessoas e mais.

import { HttpClient, HttpParams } from '@angular/common/http';
import { Component, computed, ElementRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { debounceTime, distinctUntilChanged, of, Subject, switchMap, catchError } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { ambiente } from '../../../../environments/ambiente';
import { NavegacaoService } from '../../../core/navegacao/navegacao.service';
import { normalizarTexto, telasDoMenu } from '../../../core/navegacao/telas-menu';

/** Resultado da busca (`ResultadoBusca` da API; as telas do menu usam o tipo `tela`). */
export interface ResultadoBusca {
  tipo: 'tela' | 'contrato' | 'empresa' | 'contratacao' | 'tarefa' | 'pessoa' | 'setor';
  id: string;
  titulo: string;
  subtitulo: string;
  rota: string;
}

/** Ordem e título de cada grupo na lista de resultados. */
export const GRUPOS_BUSCA: { tipo: ResultadoBusca['tipo']; titulo: string }[] = [
  { tipo: 'tela', titulo: 'Telas' },
  { tipo: 'contrato', titulo: 'Contratos' },
  { tipo: 'empresa', titulo: 'Empresas' },
  { tipo: 'contratacao', titulo: 'Contratações' },
  { tipo: 'tarefa', titulo: 'Tarefas' },
  { tipo: 'pessoa', titulo: 'Pessoas' },
  { tipo: 'setor', titulo: 'Setores' },
];

/** Minúsculas e sem acento, para comparar textos na busca. */
export const normalizar = normalizarTexto;

/**
 * Busca global do topo. Procura nas telas do menu (já filtradas pelo que o usuário pode ver) e, pela API, em contratos,
 * contratações, tarefas, pessoas e setores. Atalho: Ctrl+K ou "/" (tratado pelo layout, que chama `focar()`).
 * Teclado: setas escolhem, Enter abre, Esc fecha.
 */
@Component({
  selector: 'app-busca-global',
  imports: [FormsModule],
  host: { '(document:click)': 'aoClicarFora($event)' },
  template: `
    <div class="busca-global" role="search">
      <input #campo type="search" class="form-control" name="busca-global" autocomplete="off" placeholder="Buscar (Ctrl+K)"
             aria-label="Busca global" aria-autocomplete="list" [attr.aria-expanded]="aberta()" aria-controls="resultados-busca"
             [ngModel]="termo()" (ngModelChange)="digitou($event)" (focus)="aberta.set(true)" (keydown)="teclado($event)" />
      @if (aberta() && termo().trim().length >= 2) {
        <div class="resultados-busca" id="resultados-busca" role="listbox">
          @for (grupo of grupos(); track grupo.tipo) {
            <p class="titulo-grupo-busca">{{ grupo.titulo }}</p>
            @for (r of grupo.itens; track r.rota + r.id) {
              <button type="button" role="option" class="resultado-busca" [class.ativo]="r === ativo()" [attr.aria-selected]="r === ativo()"
                      (mouseenter)="ativo.set(r)" (click)="abrir(r)">
                <strong>{{ r.titulo }}</strong>@if (r.subtitulo) { <small>{{ r.subtitulo }}</small> }
              </button>
            }
          } @empty {
            <p class="sem-resultado-busca">{{ carregando() ? 'Buscando…' : 'Nenhum resultado para "' + termo().trim() + '".' }}</p>
          }
        </div>
      }
    </div>
  `,
})
export class BuscaGlobalComponent {
  private readonly http = inject(HttpClient);
  private readonly roteador = inject(Router);
  private readonly navegacao = inject(NavegacaoService);
  private readonly elemento = inject(ElementRef<HTMLElement>);
  private readonly campo = viewChild.required<ElementRef<HTMLInputElement>>('campo');

  protected readonly termo = signal('');
  protected readonly aberta = signal(false);
  protected readonly carregando = signal(false);
  private readonly remotos = signal<ResultadoBusca[]>([]);
  protected readonly ativo = signal<ResultadoBusca | null>(null);
  private readonly digitado$ = new Subject<string>();

  /** Telas do menu que combinam com o termo (o menu já vem filtrado por permissão). */
  private readonly telas = computed<ResultadoBusca[]>(() => {
    const alvo = normalizar(this.termo());
    if (alvo.length < 2) return [];
    return telasDoMenu(this.navegacao.secoes()).filter((t) => normalizar(t.titulo).includes(alvo)).map((t) => ({ tipo: 'tela' as const, id: t.id, titulo: t.titulo, subtitulo: '', rota: t.rota }));
  });

  /** Resultados agrupados, na ordem de `GRUPOS_BUSCA`, sem grupos vazios. */
  protected readonly grupos = computed(() => {
    const todos = [...this.telas(), ...this.remotos()];
    return GRUPOS_BUSCA.map((g) => ({ ...g, itens: todos.filter((r) => r.tipo === g.tipo) })).filter((g) => g.itens.length);
  });
  private readonly planos = computed(() => this.grupos().flatMap((g) => g.itens));

  constructor() {
    // Chama a API 250 ms depois da última tecla; resposta velha de uma busca anterior é descartada pelo switchMap
    this.digitado$
      .pipe(
        debounceTime(250),
        distinctUntilChanged(),
        switchMap((q) => {
          if (q.trim().length < 2) return of<ResultadoBusca[]>([]);
          this.carregando.set(true);
          return this.http.get<{ itens: ResultadoBusca[] }>(`${ambiente.urlApi}/busca`, { params: new HttpParams().set('q', q.trim()) }).pipe(
            switchMap((r) => of(r.itens)),
            catchError(() => of<ResultadoBusca[]>([])),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe((itens) => {
        this.carregando.set(false);
        this.remotos.set(itens);
        this.ativo.set(this.planos()[0] ?? null);
      });
  }

  /** Atalho global: leva o foco para a caixa e seleciona o texto. */
  focar(): void {
    this.campo().nativeElement.focus();
    this.campo().nativeElement.select();
    this.aberta.set(true);
  }

  protected digitou(valor: string): void {
    this.termo.set(valor);
    this.aberta.set(true);
    this.digitado$.next(valor);
    // Telas do menu já aparecem na hora; o primeiro resultado fica marcado
    queueMicrotask(() => this.ativo.set(this.planos()[0] ?? null));
  }

  protected teclado(evento: KeyboardEvent): void {
    const lista = this.planos();
    const posicao = this.ativo() ? lista.indexOf(this.ativo()!) : -1;
    if (evento.key === 'ArrowDown' && lista.length) {
      evento.preventDefault();
      this.ativo.set(lista[(posicao + 1) % lista.length]);
    } else if (evento.key === 'ArrowUp' && lista.length) {
      evento.preventDefault();
      this.ativo.set(lista[(posicao - 1 + lista.length) % lista.length]);
    } else if (evento.key === 'Enter' && this.ativo()) {
      evento.preventDefault();
      this.abrir(this.ativo()!);
    } else if (evento.key === 'Escape') {
      this.fechar();
    }
  }

  /** Abre o resultado e limpa a busca. */
  protected abrir(resultado: ResultadoBusca): void {
    void this.roteador.navigateByUrl(resultado.rota);
    this.fechar();
    this.termo.set('');
    this.remotos.set([]);
  }

  private fechar(): void {
    this.aberta.set(false);
    this.campo().nativeElement.blur();
  }

  protected aoClicarFora(evento: Event): void {
    if (!this.elemento.nativeElement.contains(evento.target as Node)) this.aberta.set(false);
  }
}
