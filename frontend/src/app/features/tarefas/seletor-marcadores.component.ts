/**
 * =============================================================================
 * ARQUIVO: seletor-marcadores.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Escolher os marcadores (etiquetas) de uma tarefa como no Odoo: pílulas com
 * ×, lista dos mais usados, busca ao digitar, criação na hora e janelinha de
 * cores (com renomear e excluir para a liderança).
 *
 * RESUMO TÉCNICO:
 * Componente de entrada/saída (input valor + output valorChange). A busca usa
 * um Subject com debounceTime(150) para não chamar a API a cada tecla. Navega
 * por setas, Enter, Esc e Backspace; fecha ao clicar fora (HostListener em
 * document:click). A janela de cor usa o SeletorCorComponent e a paleta de
 * marcadores.paleta.ts.
 *
 * FINALIDADE DE NEGÓCIO:
 * Marcadores organizam as tarefas da equipe por assunto (ex.: "Rede",
 * "Urgente") e permitem filtrar o quadro. Qualquer editor da tarefa pode
 * criar um marcador; trocar a cor, renomear e excluir ficam com a liderança,
 * porque afetam todas as tarefas da equipe.
 *
 * CONTEXTO NO SISTEMA:
 * Usado nos formulários de tarefa e recorrência do Módulo Tarefas. Chama
 * TarefasApiService (marcadores da equipe em /api/tarefas) e DialogosService
 * para confirmações e erros.
 *
 * =============================================================================
 */

import { SeletorCorComponent } from '../../shared/componentes/seletor-cor/seletor-cor.component';
import { Component, ElementRef, HostListener, inject, input, OnDestroy, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { debounceTime, Subject, Subscription } from 'rxjs';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { PALETA_MARCADORES, classeMarcador, semAcento } from './marcadores.paleta';
import { TarefasApiService } from './tarefas-api.service';
import { Marcador } from './tarefas.models';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
@Component({
  selector: 'app-seletor-marcadores',
  imports: [SeletorCorComponent, EsqueletoComponent, FormsModule],
  template: `
    <div class="campo-marcadores" [class.desabilitado]="desabilitado()" (click)="focar()">
      @for (m of valor(); track m.id) {
        <span class="pilula-marcador">
          <button type="button" [class]="classe(m.cor_indice)" [title]="podeGerir() ? 'Mudar a cor' : m.nome" [attr.aria-label]="'Marcador ' + m.nome"
                  (click)="$event.stopPropagation(); abrirCor(m)">{{ m.nome }}</button>
          @if (!desabilitado()) { <button type="button" class="tirar" [attr.aria-label]="'Tirar ' + m.nome" (click)="$event.stopPropagation(); tirar(m)">×</button> }
        </span>
      }
      @if (!desabilitado()) {
        <input #entrada type="text" role="combobox" aria-autocomplete="list" [attr.aria-expanded]="aberta()" autocomplete="off" maxlength="120"
               [placeholder]="valor().length ? '' : placeholder()" [ngModel]="busca" (ngModelChange)="digitar($event)" (focus)="abrir()"
               (keydown)="teclar($event)" name="busca-marcador" aria-label="Adicionar marcador" />
      }
    </div>

    @if (aberta()) {
      <ul class="lista-opcoes-marcador" role="listbox">
        @for (m of opcoes(); track m.id; let i = $index) {
          <li role="option" [class.ativa]="i === indice()" (mousedown)="$event.preventDefault()" (click)="escolher(m)" (mouseenter)="indice.set(i)">
            <span [class]="classe(m.cor_indice)">{{ m.nome }}</span>@if (m.usos) { <small>{{ m.usos }} uso(s)</small> }
          </li>
        }
        @if (podeCriarNovo()) {
          <li role="option" class="criar" [class.ativa]="indice() === opcoes().length" (mousedown)="$event.preventDefault()" (click)="criar()"
              (mouseenter)="indice.set(opcoes().length)">Criar "<b>{{ busca.trim() }}</b>"</li>
        }
        @if (!opcoes().length && !podeCriarNovo()) { <li class="vazia">@if (carregando()) { <app-esqueleto tipo="texto" [linhas]="2" /> } @else { {{ 'Nenhum marcador encontrado.' }} }</li> }
      </ul>
    }

    @if (editando(); as e) {
      <div class="janela-cor-marcador" role="dialog" aria-label="Cor do marcador" (click)="$event.stopPropagation()">
        @if (podeGerir()) {
          <app-seletor-cor tamanho="pequeno" [cores]="coresSeletor" [valor]="e.cor_indice" rotulo="Cor do marcador" (escolher)="trocarCor(e, $event)" />
          <div class="renomear">
            <input type="text" maxlength="120" [(ngModel)]="novoNome" name="nome-marcador" aria-label="Nome do marcador" (keydown.enter)="renomear(e)" />
            <button type="button" class="acao-secundaria acao-pequena" [disabled]="!novoNome.trim() || novoNome.trim() === e.nome" (click)="renomear(e)">Renomear</button>
          </div>
          <div class="acoes-janela-cor">
            <button type="button" class="acao-recusar acao-pequena" (click)="excluir(e)">Excluir marcador</button>
            <button type="button" class="acao-secundaria acao-pequena" (click)="editando.set(null)">Fechar</button>
          </div>
        } @else {
          <button type="button" class="acao-secundaria acao-pequena" (click)="editando.set(null)">Fechar</button>
        }
      </div>
    }
  `,
})
/**
 * Campo de marcadores com busca. `input()` declara uma propriedade que o
 * componente pai preenche no template; `output()` declara um evento que o
 * pai escuta. O par `valor`/`valorChange` permite usar `[(valor)]` no pai.
 */
export class SeletorMarcadoresComponent implements OnDestroy {
  /** Equipe dona dos marcadores. */
  readonly equipeId = input.required<string>();
  /** Marcadores já atribuídos. */
  readonly valor = input<Marcador[]>([]);
  readonly valorChange = output<Marcador[]>();
  readonly placeholder = input('Adicionar marcador…');
  readonly desabilitado = input(false);
  /** Liderança: troca cor, renomeia e exclui. */
  readonly podeGerir = input(false);
  /** Quem edita a tarefa cria marcadores na hora. */
  readonly podeCriar = input(true);

  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  // Elemento do próprio componente, usado para saber se um clique foi fora dele.
  private readonly eu = inject<ElementRef<HTMLElement>>(ElementRef);

  protected readonly coresSeletor = PALETA_MARCADORES.map((c, i) => ({ cor: c.borda, rotulo: `Cor ${i + 1}` }));
  protected readonly paleta = PALETA_MARCADORES;
  protected readonly aberta = signal(false);
  protected readonly carregando = signal(false);
  protected readonly lista = signal<Marcador[]>([]);
  protected readonly indice = signal(0);
  protected readonly editando = signal<Marcador | null>(null);
  protected busca = '';
  protected novoNome = '';
  // Subject: um Observable em que o próprio código "empurra" valores com next().
  // debounceTime(150) espera 150 ms sem novas teclas antes de buscar na API.
  private readonly digitacao = new Subject<string>();
  private readonly assinatura: Subscription = this.digitacao.pipe(debounceTime(150)).subscribe(() => this.buscar());

  /** Função que devolve a classe CSS da cor do marcador (exposta ao template). */
  protected classe = classeMarcador;

  /** Opções: os que combinam com o texto e ainda não estão na tarefa. */
  protected opcoes(): Marcador[] {
    const usados = new Set(this.valor().map((m) => m.id));
    return this.lista().filter((m) => !usados.has(m.id));
  }

  /** Mostra "Criar" quando o texto não é igual a nenhum marcador (nem aos já atribuídos). */
  protected podeCriarNovo(): boolean {
    const nome = semAcento(this.busca.trim());
    if (!nome || !this.podeCriar()) return false;
    return ![...this.lista(), ...this.valor()].some((m) => semAcento(m.nome) === nome);
  }

  /** Cancela a inscrição da busca ao destruir o componente, para não vazar memória. */
  ngOnDestroy(): void {
    this.assinatura.unsubscribe();
  }

  /** Fecha a lista e a janela de cor quando o clique acontece fora do componente. */
  @HostListener('document:click', ['$event'])
  protected fora(evento: Event): void {
    if (!this.eu.nativeElement.contains(evento.target as Node)) { this.aberta.set(false); this.editando.set(null); }
  }

  /** Clicar em qualquer ponto do campo coloca o cursor na caixa de digitação. */
  protected focar(): void {
    this.eu.nativeElement.querySelector('input')?.focus();
  }

  /** Abre a lista de opções e busca os marcadores (mais usados, sem texto). */
  protected abrir(): void {
    this.aberta.set(true);
    this.buscar();
  }

  /** Guarda o texto e agenda a busca (o debounce evita uma chamada por tecla). */
  protected digitar(texto: string): void {
    this.busca = texto;
    this.aberta.set(true);
    this.digitacao.next(texto);
  }

  /** Busca até 50 marcadores da equipe que combinam com o texto digitado. */
  private buscar(): void {
    this.carregando.set(true);
    this.api.marcadores(this.equipeId(), this.busca.trim(), 50).subscribe({
      next: (l) => { this.lista.set(l); this.indice.set(0); this.carregando.set(false); },
      error: () => this.carregando.set(false),
    });
  }

  /**
   * Teclado do campo: setas movem o destaque (a opção "Criar" conta como a
   * última), Enter escolhe ou cria, Esc fecha e Backspace com o campo vazio
   * tira o último marcador atribuído.
   */
  protected teclar(e: KeyboardEvent): void {
    const total = this.opcoes().length + (this.podeCriarNovo() ? 1 : 0);
    if (e.key === 'ArrowDown') { e.preventDefault(); this.aberta.set(true); this.indice.update((i) => Math.min(i + 1, Math.max(total - 1, 0))); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); this.indice.update((i) => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter') {
      e.preventDefault();
      const opcoes = this.opcoes();
      if (this.indice() < opcoes.length) this.escolher(opcoes[this.indice()]);
      else if (this.podeCriarNovo()) this.criar();
    } else if (e.key === 'Escape') { this.aberta.set(false); }
    else if (e.key === 'Backspace' && !this.busca && this.valor().length) this.tirar(this.valor()[this.valor().length - 1]);
  }

  /** Acrescenta o marcador à tarefa (avisa o pai) e limpa a busca. */
  protected escolher(m: Marcador): void {
    this.valorChange.emit([...this.valor(), m]);
    this.busca = '';
    this.buscar();
  }

  /** Remove o marcador da tarefa (o marcador continua existindo na equipe). */
  protected tirar(m: Marcador): void {
    this.valorChange.emit(this.valor().filter((x) => x.id !== m.id));
  }

  /** Cria um marcador novo na equipe com o texto digitado e já o atribui à tarefa. */
  protected criar(): void {
    const nome = this.busca.trim();
    if (!nome) return;
    this.api.criarMarcador(this.equipeId(), nome).subscribe({
      next: (m) => { this.escolher(m); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar o marcador'),
    });
  }

  /** Abre a janelinha de cor/renomear/excluir; só para a liderança e com o campo habilitado. */
  protected abrirCor(m: Marcador): void {
    if (!this.podeGerir() || this.desabilitado()) return;
    this.novoNome = m.nome;
    this.editando.set(m);
    this.aberta.set(false);
  }

  /** Atualiza o marcador editado na lista da tarefa e na lista de opções. */
  private aplicar(novo: Marcador): void {
    this.editando.set(novo);
    this.lista.update((l) => l.map((x) => (x.id === novo.id ? { ...x, ...novo } : x)));
    this.valorChange.emit(this.valor().map((x) => (x.id === novo.id ? { ...x, ...novo } : x)));
  }

  /** Troca a cor do marcador na equipe (vale para todas as tarefas que o usam). */
  protected trocarCor(m: Marcador, indice: number): void {
    this.api.alterarMarcador(this.equipeId(), m.id, m.nome, indice).subscribe({
      next: (n) => this.aplicar(n), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível trocar a cor'),
    });
  }

  /** Renomeia o marcador na equipe; ignora nome vazio ou igual ao atual. */
  protected renomear(m: Marcador): void {
    const nome = this.novoNome.trim();
    if (!nome || nome === m.nome) return;
    this.api.alterarMarcador(this.equipeId(), m.id, nome, m.cor_indice).subscribe({
      next: (n) => this.aplicar(n), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível renomear o marcador'),
    });
  }

  /** Exclui o marcador da equipe após confirmação; ele some de todas as tarefas. */
  protected async excluir(m: Marcador): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Excluir este marcador?', mensagem: `"${m.nome}" será removido de todas as tarefas da equipe.`, rotuloConfirmar: 'Excluir', segundos: 3, perigo: true,
    });
    if (!ok) return;
    this.api.excluirMarcador(m.id).subscribe({
      next: () => {
        this.editando.set(null);
        this.lista.update((l) => l.filter((x) => x.id !== m.id));
        this.valorChange.emit(this.valor().filter((x) => x.id !== m.id));
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível excluir o marcador'),
    });
  }
}
