// Criado por José Eduardo Santana Martins
// Este arquivo serve para escolher os marcadores de uma tarefa como no Odoo: pílulas com ×, lista dos mais usados, busca ao digitar,
// criação na hora e janelinha de cores (com renomear e excluir para a liderança).

import { Component, ElementRef, HostListener, inject, input, OnDestroy, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { debounceTime, Subject, Subscription } from 'rxjs';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { PALETA_MARCADORES, classeMarcador, semAcento } from './marcadores.paleta';
import { TarefasApiService } from './tarefas-api.service';
import { Marcador } from './tarefas.models';

@Component({
  selector: 'app-seletor-marcadores',
  imports: [FormsModule],
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
        @if (!opcoes().length && !podeCriarNovo()) { <li class="vazia">{{ carregando() ? 'Buscando…' : 'Nenhum marcador encontrado.' }}</li> }
      </ul>
    }

    @if (editando(); as e) {
      <div class="janela-cor-marcador" role="dialog" aria-label="Cor do marcador" (click)="$event.stopPropagation()">
        @if (podeGerir()) {
          <div class="cores">
            @for (c of paleta; track $index; let i = $index) {
              <button type="button" class="cor" [class.atual]="i === e.cor_indice" [style.background]="c.fundo" [style.border-color]="c.borda"
                      [attr.aria-label]="'Cor ' + (i + 1)" (click)="trocarCor(e, i)"></button>
            }
          </div>
          <div class="renomear">
            <input type="text" maxlength="120" [(ngModel)]="novoNome" name="nome-marcador" aria-label="Nome do marcador" (keydown.enter)="renomear(e)" />
            <button type="button" class="acao-secundaria acao-pequena" [disabled]="!novoNome.trim() || novoNome.trim() === e.nome" (click)="renomear(e)">Renomear</button>
          </div>
          <button type="button" class="link-simples perigo" (click)="excluir(e)">Excluir marcador</button>
        }
        <button type="button" class="link-simples" (click)="editando.set(null)">Fechar</button>
      </div>
    }
  `,
})
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
  private readonly eu = inject<ElementRef<HTMLElement>>(ElementRef);

  protected readonly paleta = PALETA_MARCADORES;
  protected readonly aberta = signal(false);
  protected readonly carregando = signal(false);
  protected readonly lista = signal<Marcador[]>([]);
  protected readonly indice = signal(0);
  protected readonly editando = signal<Marcador | null>(null);
  protected busca = '';
  protected novoNome = '';
  private readonly digitacao = new Subject<string>();
  private readonly assinatura: Subscription = this.digitacao.pipe(debounceTime(150)).subscribe(() => this.buscar());

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

  ngOnDestroy(): void {
    this.assinatura.unsubscribe();
  }

  @HostListener('document:click', ['$event'])
  protected fora(evento: Event): void {
    if (!this.eu.nativeElement.contains(evento.target as Node)) { this.aberta.set(false); this.editando.set(null); }
  }

  protected focar(): void {
    this.eu.nativeElement.querySelector('input')?.focus();
  }

  protected abrir(): void {
    this.aberta.set(true);
    this.buscar();
  }

  protected digitar(texto: string): void {
    this.busca = texto;
    this.aberta.set(true);
    this.digitacao.next(texto);
  }

  private buscar(): void {
    this.carregando.set(true);
    this.api.marcadores(this.equipeId(), this.busca.trim(), 50).subscribe({
      next: (l) => { this.lista.set(l); this.indice.set(0); this.carregando.set(false); },
      error: () => this.carregando.set(false),
    });
  }

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

  protected escolher(m: Marcador): void {
    this.valorChange.emit([...this.valor(), m]);
    this.busca = '';
    this.buscar();
  }

  protected tirar(m: Marcador): void {
    this.valorChange.emit(this.valor().filter((x) => x.id !== m.id));
  }

  protected criar(): void {
    const nome = this.busca.trim();
    if (!nome) return;
    this.api.criarMarcador(this.equipeId(), nome).subscribe({
      next: (m) => { this.escolher(m); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar o marcador'),
    });
  }

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

  protected trocarCor(m: Marcador, indice: number): void {
    this.api.alterarMarcador(this.equipeId(), m.id, m.nome, indice).subscribe({
      next: (n) => this.aplicar(n), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível trocar a cor'),
    });
  }

  protected renomear(m: Marcador): void {
    const nome = this.novoNome.trim();
    if (!nome || nome === m.nome) return;
    this.api.alterarMarcador(this.equipeId(), m.id, nome, m.cor_indice).subscribe({
      next: (n) => this.aplicar(n), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível renomear o marcador'),
    });
  }

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
