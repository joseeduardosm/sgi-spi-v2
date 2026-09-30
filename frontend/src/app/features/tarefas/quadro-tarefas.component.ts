// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o quadro de tarefas (estilo Trello): colunas do pipeline, raias por pessoa, arraste e criação rápida.

import { DecimalPipe } from '@angular/common';
import { Component, computed, ElementRef, input, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AvataresComponent } from './avatares.component';
import { CartaoTarefaComponent } from './cartao-tarefa.component';
import { agruparRaias, Pessoa, PessoaCarga, STATUS, StatusTarefa, TarefaResumo } from './tarefas.models';

/** Quantas concluídas a coluna mostra antes do "ver todas". */
const LIMITE_CONCLUIDAS = 10;
/** Chave (localStorage) da coluna Concluída recolhida. */
const CHAVE_RECOLHIDA = 'tarefas.quadro.concluida-recolhida';

/** Movimento pedido pelo quadro (arraste ou menu do cartão); o espaço decide a ação do pipeline. */
export interface MovimentoQuadro { tarefa: TarefaResumo; para: StatusTarefa }

/** Opção do menu "⋯" do cartão. */
interface OpcaoMenu { rotulo: string; para: StatusTarefa }

@Component({
  selector: 'app-quadro-tarefas',
  imports: [FormsModule, DecimalPipe, CartaoTarefaComponent, AvataresComponent],
  // Clique fora do menu "⋯" o fecha (o botão do menu interrompe a propagação do próprio clique)
  host: { '(document:click)': 'menuAberto.set(null)' },
  template: `
    @for (raia of raias(); track raia.chave) {
      @if (comRaias()) {
        <!-- Cabeçalho da raia: a pessoa, a carga e quantas tarefas tem no quadro -->
        <div class="cabecalho-raia">
          @if (raia.pessoa; as p) { <app-avatares [pessoas]="[p]" /> <strong>{{ p.nome }}</strong> } @else { <strong>Sem responsável</strong> }
          <small>{{ raia.total }} tarefa{{ raia.total === 1 ? '' : 's' }}</small>
          @if (raia.carga; as c) {
            <span class="faixa-carga" [attr.data-faixa]="c.faixa" title="Carga de todas as tarefas da pessoa">{{ c.faixa }} · {{ c.carga | number: '1.0-1' }} pts</span>
          }
        </div>
      }
      <div class="quadro" [class.com-raias]="comRaias()">
        @for (c of raia.colunas; track c.valor) {
          <section class="lista-quadro" [attr.data-status]="c.valor" [class.alvo]="alvo() === raia.chave + c.valor"
                   [class.recolhida]="c.valor === 'concluida' && recolhida()" [attr.aria-label]="c.rotulo"
                   (dragover)="$event.preventDefault(); alvo.set(raia.chave + c.valor)" (dragleave)="alvo.set(null)" (drop)="soltar($event, c.valor)">
            <header>
              <h3>{{ c.rotulo }}</h3><span class="contagem">{{ c.total }}</span>
              @if (c.valor === 'concluida') {
                <button type="button" class="botao-icone" [attr.aria-label]="recolhida() ? 'Expandir Concluída' : 'Recolher Concluída'"
                        [title]="recolhida() ? 'Expandir' : 'Recolher'" (click)="alternarRecolhida()">{{ recolhida() ? '⟩' : '⟨' }}</button>
              }
            </header>
            @if (!(c.valor === 'concluida' && recolhida())) {
              <div class="cartoes">
                @for (t of c.itens; track t.numero) {
                  <div class="envoltorio-cartao" draggable="true" [class.arrastando]="arrastando()?.numero === t.numero"
                       (dragstart)="iniciarArraste($event, t)" (dragend)="terminarArraste()">
                    <app-cartao-tarefa [tarefa]="t" [destacado]="destacado() === t.numero" (abrir)="abrir.emit($event)" />
                    @if (opcoes(t).length) {
                      <button type="button" class="menu-cartao" [attr.aria-label]="'Ações da tarefa ' + t.numero" [attr.aria-expanded]="menuAberto() === t.numero"
                              (click)="$event.stopPropagation(); menuAberto.set(menuAberto() === t.numero ? null : t.numero)">⋯</button>
                      @if (menuAberto() === t.numero) {
                        <div class="menu-suspenso" role="menu">
                          @for (o of opcoes(t); track o.rotulo) {
                            <button type="button" role="menuitem" (click)="menuAberto.set(null); mover.emit({ tarefa: t, para: o.para })">{{ o.rotulo }}</button>
                          }
                        </div>
                      }
                    }
                  </div>
                } @empty { <p class="lista-vazia">{{ c.valor === 'a_fazer' && podeCriar() ? 'Nada a fazer por aqui.' : 'Nenhuma tarefa' }}</p> }
                @if (c.valor === 'concluida' && c.total > c.itens.length) {
                  <button type="button" class="link-simples ver-todas-concluidas" (click)="todasConcluidas.set(true)">Ver todas as {{ c.total }}</button>
                }
              </div>
              <!-- Criação rápida: só o título; o restante segue os padrões e pode ser ajustado na tarefa -->
              @if (c.valor === 'a_fazer' && podeCriar() && !comRaias()) {
                @if (criando()) {
                  <form class="criacao-rapida" (submit)="$event.preventDefault(); confirmarCriacao()">
                    <textarea #campoCriacao name="titulo" rows="2" maxlength="200" placeholder="Título da tarefa" aria-label="Título da nova tarefa"
                              [(ngModel)]="novoTitulo" (keydown.enter)="$event.preventDefault(); confirmarCriacao()" (keydown.escape)="cancelarCriacao()"></textarea>
                    <small>Enter cria · responsável: você · prazo em 7 dias, 18:00 · Esc cancela</small>
                    <div class="acoes-criacao">
                      <button type="submit" class="acao-primaria" [disabled]="!novoTitulo.trim()">Adicionar</button>
                      <button type="button" class="botao-icone" aria-label="Cancelar" (click)="cancelarCriacao()">×</button>
                    </div>
                  </form>
                } @else {
                  <button type="button" class="adicionar-cartao" (click)="abrirCriacao()">+ Adicionar tarefa</button>
                }
              }
            }
          </section>
        }
      </div>
    }
  `,
})
export class QuadroTarefasComponent {
  /** Tarefas já filtradas pelo espaço. */
  readonly itens = input<TarefaResumo[]>([]);
  /** Agrupar em raias por responsável. */
  readonly comRaias = input(false);
  /** Carga das pessoas (cabeçalho das raias), quando disponível. */
  readonly cargas = input<PessoaCarga[]>([]);
  /** O usuário lidera o contexto (vê "Validar" e "Devolver" no menu). */
  readonly lider = input(false);
  /** Mostrar a criação rápida na coluna A fazer. */
  readonly podeCriar = input(false);
  /** Tarefa em destaque (recém-criada). */
  readonly destacado = input<number | null>(null);

  readonly abrir = output<number>();
  readonly mover = output<MovimentoQuadro>();
  readonly criar = output<string>();

  // Estado do arraste, do menu e da criação rápida
  protected readonly arrastando = signal<TarefaResumo | null>(null);
  protected readonly alvo = signal<string | null>(null);
  protected readonly menuAberto = signal<number | null>(null);
  protected readonly criando = signal(false);
  protected readonly todasConcluidas = signal(false);
  protected readonly recolhida = signal(lerRecolhida());
  protected novoTitulo = '';
  private readonly campoCriacao = viewChild<ElementRef<HTMLTextAreaElement>>('campoCriacao');

  /** Raias (uma só, sem cabeçalho, quando não agrupa), cada uma com as quatro colunas. */
  protected readonly raias = computed(() => {
    const cargas = new Map(this.cargas().map((c) => [c.id, c]));
    const grupos: { pessoa: Pessoa | null; itens: TarefaResumo[] }[] = this.comRaias() ? agruparRaias(this.itens()) : [{ pessoa: null, itens: this.itens() }];
    return grupos.map((g) => ({
      chave: g.pessoa ? `p${g.pessoa.id}-` : 'sem-',
      pessoa: g.pessoa,
      total: g.itens.length,
      carga: g.pessoa ? cargas.get(g.pessoa.id) ?? null : null,
      colunas: STATUS.map((s) => {
        const todos = g.itens.filter((t) => t.status === s.valor);
        if (s.valor !== 'concluida') return { ...s, itens: [...todos].sort((a, b) => a.ordem - b.ordem), total: todos.length };
        // Concluídas: as mais recentes primeiro, limitadas até o "ver todas"
        const recentes = [...todos].sort((a, b) => (b.concluida_em ?? b.atualizado_em).localeCompare(a.concluida_em ?? a.atualizado_em));
        return { ...s, itens: this.todasConcluidas() ? recentes : recentes.slice(0, LIMITE_CONCLUIDAS), total: todos.length };
      }),
    }));
  });

  /** Movimentos oferecidos no menu "⋯" (a API confere a permissão; em recusa, nada muda). */
  protected opcoes(t: TarefaResumo): OpcaoMenu[] {
    switch (t.status) {
      case 'a_fazer': return [{ rotulo: 'Iniciar', para: 'em_andamento' }, ...(this.lider() ? [{ rotulo: 'Concluir', para: 'concluida' as StatusTarefa }] : [])];
      case 'em_andamento': return [
        { rotulo: t.equipe ? 'Entregar para validação' : 'Concluir', para: t.equipe ? 'em_validacao' : 'concluida' },
        { rotulo: 'Voltar para A fazer', para: 'a_fazer' },
      ];
      case 'em_validacao': return this.lider() ? [{ rotulo: 'Validar', para: 'concluida' }, { rotulo: 'Devolver', para: 'em_andamento' }] : [];
      default: return this.lider() ? [{ rotulo: 'Reabrir', para: 'em_andamento' }] : [];
    }
  }

  // --- Arraste entre colunas --------------------------------------------------------------------------

  protected iniciarArraste(evento: DragEvent, t: TarefaResumo): void {
    this.arrastando.set(t);
    evento.dataTransfer?.setData('text/plain', String(t.numero));
    if (evento.dataTransfer) evento.dataTransfer.effectAllowed = 'move';
  }

  protected terminarArraste(): void {
    this.arrastando.set(null);
    this.alvo.set(null);
  }

  protected soltar(evento: DragEvent, para: StatusTarefa): void {
    evento.preventDefault();
    const t = this.arrastando();
    this.terminarArraste();
    if (t && t.status !== para) this.mover.emit({ tarefa: t, para });
  }

  // --- Coluna Concluída recolhível (preferência guardada no navegador) --------------------------------

  protected alternarRecolhida(): void {
    this.recolhida.update((v) => !v);
    try {
      localStorage.setItem(CHAVE_RECOLHIDA, this.recolhida() ? '1' : '0');
    } catch {
      // Navegador sem armazenamento (janela privada): a preferência só vale nesta visita
    }
  }

  // --- Criação rápida ---------------------------------------------------------------------------------

  protected abrirCriacao(): void {
    this.novoTitulo = '';
    this.criando.set(true);
    // Foco no campo depois que ele aparece
    setTimeout(() => this.campoCriacao()?.nativeElement.focus());
  }

  protected cancelarCriacao(): void {
    this.criando.set(false);
    this.novoTitulo = '';
  }

  protected confirmarCriacao(): void {
    const titulo = this.novoTitulo.trim();
    if (!titulo) return;
    this.criar.emit(titulo);
    // Mantém o campo aberto e vazio, para criar várias em sequência (como no Trello)
    this.novoTitulo = '';
    setTimeout(() => this.campoCriacao()?.nativeElement.focus());
  }
}

/** Lê a preferência da coluna Concluída; sem armazenamento disponível, começa expandida. */
function lerRecolhida(): boolean {
  try {
    return localStorage.getItem(CHAVE_RECOLHIDA) === '1';
  } catch {
    return false;
  }
}
