// Criado por José Eduardo Santana Martins
// Este arquivo serve para a paleta de comandos (Ctrl+K): ações de criar, telas do menu, favoritos, recentes e resultados da busca global.

import { HttpClient, HttpParams } from '@angular/common/http';
import { Component, computed, effect, ElementRef, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { catchError, debounceTime, distinctUntilChanged, map, of, Subject, switchMap } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { AcessoService } from '../../../core/acesso/acesso.service';
import { ChamadoService } from '../../../core/chamados/chamado.service';
import { AtalhosService } from '../../../core/navegacao/atalhos.service';
import { NavegacaoService } from '../../../core/navegacao/navegacao.service';
import { normalizarTexto, telasDoMenu } from '../../../core/navegacao/telas-menu';
import { TemaService } from '../../../core/tema/tema.service';
import { MelhoriasJanelaService } from '../botao-melhorias/melhorias-janela.service';
import { ResultadoBusca } from '../busca-global/busca-global.component';
import { COMANDOS, ComandoPaleta, filtrarComandos } from './paleta-comandos.registro';
import { PaletaComandosService } from './paleta-comandos.service';

/** Linha da paleta: o que mostra e o que faz ao escolher. */
interface Entrada {
  chave: string;
  grupo: string;
  rotulo: string;
  descricao: string;
  executar: () => void;
}

/**
 * Paleta de comandos, aberta por Ctrl/Cmd+K. Vazia, mostra as ações, os favoritos e as telas recentes; com texto, as ações que combinam,
 * as telas do menu (já filtradas pela ACL) e os resultados da busca global (contratos, tarefas, pessoas…).
 * Teclado: setas escolhem, Enter executa, Esc fecha (só a paleta), Tab também fecha.
 */
@Component({
  selector: 'app-paleta-comandos',
  imports: [FormsModule],
  template: `
    @if (paleta.aberta()) {
      <div class="paleta-fundo" role="presentation" (click)="paleta.fechar()"></div>
      <section class="paleta" role="dialog" aria-modal="true" aria-label="Paleta de comandos" (keydown.escape)="$event.stopPropagation(); paleta.fechar()">
        <input #campo type="text" class="paleta-campo" name="paleta" autocomplete="off" placeholder="Digite um comando, uma tela ou algo para buscar…"
               aria-label="Paleta de comandos" role="combobox" aria-expanded="true" aria-controls="lista-paleta" [attr.aria-activedescendant]="'paleta-' + indice()"
               [ngModel]="termo()" (ngModelChange)="digitou($event)" (keydown)="teclado($event)" />
        <div class="paleta-lista" id="lista-paleta" role="listbox">
          @for (e of entradas(); track e.chave; let i = $index) {
            @if (i === 0 || entradas()[i - 1].grupo !== e.grupo) { <p class="titulo-grupo-busca">{{ e.grupo }}</p> }
            <button type="button" role="option" class="resultado-busca" [id]="'paleta-' + i" [class.ativo]="i === indice()" [attr.aria-selected]="i === indice()"
                    (mouseenter)="indice.set(i)" (click)="escolher(e)">
              <strong>{{ e.rotulo }}</strong>@if (e.descricao) { <small>{{ e.descricao }}</small> }
            </button>
          } @empty {
            <p class="sem-resultado-busca">{{ carregando() ? 'Buscando…' : 'Nada encontrado para "' + termo().trim() + '".' }}</p>
          }
        </div>
        <footer class="paleta-rodape"><span>↑↓ escolher</span><span>Enter abrir</span><span>Esc fechar</span></footer>
      </section>
    }
  `,
})
export class PaletaComandosComponent {
  protected readonly paleta = inject(PaletaComandosService);
  private readonly roteador = inject(Router);
  private readonly http = inject(HttpClient);
  private readonly acesso = inject(AcessoService);
  private readonly navegacao = inject(NavegacaoService);
  private readonly atalhos = inject(AtalhosService);
  private readonly chamado = inject(ChamadoService);
  private readonly melhorias = inject(MelhoriasJanelaService);
  private readonly tema = inject(TemaService);
  private readonly campo = viewChild<ElementRef<HTMLInputElement>>('campo');

  protected readonly termo = signal('');
  protected readonly indice = signal(0);
  protected readonly carregando = signal(false);
  private readonly remotos = signal<ResultadoBusca[]>([]);
  private readonly digitado$ = new Subject<string>();

  /** Linhas da paleta, na ordem em que aparecem (a escolha por setas anda nesta lista). */
  protected readonly entradas = computed<Entrada[]>(() => {
    const texto = this.termo().trim();
    const pode = (acl: string, nivel: Parameters<AcessoService['pode']>[1]) => this.acesso.pode(acl, nivel);
    const acoes = filtrarComandos(COMANDOS, texto, pode).map((c) => this.deComando(c));
    if (!texto) {
      const guardadas = (lista: { rota: string; rotulo: string }[], grupo: string): Entrada[] =>
        lista.map((a) => ({ chave: `${grupo}:${a.rota}`, grupo, rotulo: a.rotulo, descricao: a.rota, executar: () => void this.roteador.navigateByUrl(a.rota) }));
      return [...acoes, ...guardadas(this.atalhos.favoritos(), 'Favoritos'), ...guardadas(this.atalhos.recentes(), 'Recentes')];
    }
    const alvo = normalizarTexto(texto);
    const telas = telasDoMenu(this.navegacao.secoes()).filter((t) => normalizarTexto(t.titulo).includes(alvo))
      .map<Entrada>((t) => ({ chave: `tela:${t.id}`, grupo: 'Ir para', rotulo: t.titulo, descricao: '', executar: () => void this.roteador.navigateByUrl(t.rota) }));
    const resultados = this.remotos().map<Entrada>((r) => ({
      chave: `busca:${r.tipo}:${r.id}`, grupo: ROTULO_TIPO[r.tipo] ?? 'Resultados', rotulo: r.titulo, descricao: r.subtitulo, executar: () => void this.roteador.navigateByUrl(r.rota),
    }));
    return [...acoes, ...telas, ...resultados];
  });

  constructor() {
    // Ao abrir: limpa, foca o campo e marca a primeira linha
    effect(() => {
      if (!this.paleta.aberta()) return;
      this.termo.set('');
      this.remotos.set([]);
      this.indice.set(0);
      setTimeout(() => this.campo()?.nativeElement.focus());
    });
    // Busca remota 250 ms depois da última tecla; resposta velha é descartada pelo switchMap
    this.digitado$.pipe(
      debounceTime(250), distinctUntilChanged(),
      switchMap((q) => {
        if (q.trim().length < 2) return of<ResultadoBusca[]>([]);
        this.carregando.set(true);
        return this.http.get<{ itens: ResultadoBusca[] }>(`${ambiente.urlApi}/busca`, { params: new HttpParams().set('q', q.trim()) }).pipe(
          map((r) => r.itens), catchError(() => of<ResultadoBusca[]>([])),
        );
      }),
      takeUntilDestroyed(),
    ).subscribe((itens) => {
      this.carregando.set(false);
      this.remotos.set(itens);
    });
  }

  protected digitou(valor: string): void {
    this.termo.set(valor);
    this.indice.set(0);
    this.digitado$.next(valor);
  }

  protected teclado(evento: KeyboardEvent): void {
    const total = this.entradas().length;
    if (evento.key === 'ArrowDown' && total) {
      evento.preventDefault();
      this.indice.set((this.indice() + 1) % total);
      this.rolarParaAtiva();
    } else if (evento.key === 'ArrowUp' && total) {
      evento.preventDefault();
      this.indice.set((this.indice() - 1 + total) % total);
      this.rolarParaAtiva();
    } else if (evento.key === 'Enter' && total) {
      evento.preventDefault();
      this.escolher(this.entradas()[Math.min(this.indice(), total - 1)]);
    } else if (evento.key === 'Tab') {
      this.paleta.fechar();
    }
  }

  protected escolher(entrada: Entrada): void {
    this.paleta.fechar();
    entrada.executar();
  }

  /** Mantém a linha escolhida à vista quando a lista rola. */
  private rolarParaAtiva(): void {
    setTimeout(() => document.getElementById(`paleta-${this.indice()}`)?.scrollIntoView({ block: 'nearest' }));
  }

  private deComando(c: ComandoPaleta): Entrada {
    const executar = (): void => {
      switch (c.acao) {
        case 'abrir-chamado': this.chamado.abrirModal(); break;
        case 'sugerir-melhoria': this.melhorias.pedirAbertura(); break;
        case 'alternar-tema': this.tema.escolher(this.tema.preferencia() === 'escuro' ? 'claro' : 'escuro'); break;
        default: if (c.rota) void this.roteador.navigateByUrl(c.rota);
      }
    };
    return { chave: `acao:${c.id}`, grupo: 'Ações', rotulo: c.rotulo, descricao: c.descricao ?? '', executar };
  }
}

/** Título do grupo de cada tipo de resultado da busca. */
const ROTULO_TIPO: Record<string, string> = {
  contrato: 'Contratos', empresa: 'Empresas', contratacao: 'Contratações', tarefa: 'Tarefas', pessoa: 'Pessoas', setor: 'Setores',
};
