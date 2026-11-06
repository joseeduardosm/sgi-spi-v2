// Criado por José Eduardo Santana Martins
// Este arquivo serve para escolher as VLANs de uma porta (com tag ou sem tag) como os marcadores das Tarefas: selos coloridos só com o número
// (o nome no "title" e na busca), busca ao digitar, "Todas"/"Limpar", resumo em faixas ("2469–2483 (15 VLANs)") e, para quem administra a
// rede, a janelinha de cor e nome do selo. A cor e o nome são da VLAN: trocar vale em todas as portas.

import { Component, computed, ElementRef, inject, input, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { SeletorCorComponent } from '../../shared/componentes/seletor-cor/seletor-cor.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador, PALETA_MARCADORES } from '../tarefas/marcadores.paleta';
import { RedeApiService } from './rede-api.service';
import { Vlan } from './rede.models';

/** Texto sem acento e em minúsculas, para a busca ("Câmeras" acha "cameras"). */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/** Números em faixas, como no switch: [2469, 2470, 2471, 2480] → "2469–2471, 2480". */
export function faixasDeVlans(numeros: number[]): string {
  const ordenados = [...new Set(numeros)].sort((a, b) => a - b);
  const faixas: string[] = [];
  for (let i = 0; i < ordenados.length; ) {
    let fim = i;
    while (fim + 1 < ordenados.length && ordenados[fim + 1] === ordenados[fim] + 1) fim++;
    faixas.push(fim > i ? `${ordenados[i]}–${ordenados[fim]}` : String(ordenados[i]));
    i = fim + 1;
  }
  return faixas.join(', ');
}

@Component({
  selector: 'app-seletor-vlans',
  imports: [FormsModule, SeletorCorComponent],
  // A lista de opções e a janelinha de cor são absolutas: o componente é a referência delas
  host: { style: 'display: block; position: relative', '(document:click)': 'cliqueFora($event)' },
  styles: [`
    .cabecalho-seletor-vlans { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 0 0 7px;
      label { margin: 0; } .espaco { flex: 1; } }
    /* O campo de digitar fica "invisível" dentro do campo de selos (o .grade-formulario input daria borda, altura e margem próprias) */
    .campo-marcadores input.busca-vlan { flex: 1; width: auto; min-width: 120px; height: 28px; margin: 0; padding: 0 4px; border: 0; border-radius: 0;
      outline: 0; box-shadow: none; background: transparent; font-size: 13px; }
    .pilula-marcador > button:first-child .texto-codigo { font-size: 12px; }
    .resumo-vlans { display: block; margin-top: 6px; }
  `],
  template: `
    <div class="cabecalho-seletor-vlans">
      <label [for]="idCampo()">{{ rotuloCampo() }} @if (detalheRotulo()) { <small>{{ detalheRotulo() }}</small> }</label>
      <span class="espaco"></span>
      @if (!desabilitado()) {
        <button type="button" class="acao-secundaria acao-pequena" [disabled]="!disponiveis().length" (click)="todas()">Todas</button>
        <button type="button" class="acao-secundaria acao-pequena" [disabled]="!valor().length" (click)="limpar()">Limpar</button>
      }
    </div>
    <!-- Mesmas classes globais do campo de marcadores das Tarefas (styles/_tarefas.scss) -->
    <div class="campo-marcadores" [class.desabilitado]="desabilitado()" (click)="focar()">
      @for (v of escolhidas(); track v.id) {
        <span class="pilula-marcador">
          <button type="button" [class]="classe(v.cor_indice)" [title]="v.nome + (podeGerir() && !desabilitado() ? ' · clique para mudar a cor ou o nome' : '')"
                  [attr.aria-label]="'VLAN ' + v.numero + ' · ' + v.nome" (click)="$event.stopPropagation(); abrirCor(v)"><span class="texto-codigo">{{ v.numero }}</span></button>
          @if (!desabilitado()) {
            <button type="button" class="tirar" [attr.aria-label]="'Tirar a VLAN ' + v.numero" (click)="$event.stopPropagation(); tirar(v.id)">×</button>
          }
        </span>
      }
      @if (!desabilitado()) {
        <input #entrada type="text" class="busca-vlan" role="combobox" aria-autocomplete="list" [attr.aria-expanded]="aberta()" [attr.aria-controls]="idLista"
               [id]="idCampo()" autocomplete="off" maxlength="60" [placeholder]="escolhidas().length ? '' : placeholder()" [value]="busca()"
               (input)="digitar($any($event.target).value)" (focus)="aberta.set(true)" (keydown)="teclar($event)" [attr.aria-label]="rotulo()" />
      } @else if (!escolhidas().length) {
        <span class="dica-formulario">Nenhuma</span>
      }
    </div>
    @if (escolhidas().length) {
      <small class="dica-formulario resumo-vlans">{{ prefixoResumo() }}: <span class="texto-codigo">{{ resumo() }}</span> ({{ escolhidas().length }} VLAN{{ escolhidas().length > 1 ? 's' : '' }})</small>
    }
    @if (aberta() && !desabilitado()) {
      <ul class="lista-opcoes-marcador" role="listbox" [id]="idLista">
        @for (v of opcoes(); track v.id; let i = $index) {
          <li role="option" [class.ativa]="i === indice()" [attr.aria-selected]="i === indice()" (mousedown)="$event.preventDefault()" (click)="escolher(v.id)"
              (mouseenter)="indice.set(i)">
            <span><span [class]="classe(v.cor_indice)"><span class="texto-codigo">{{ v.numero }}</span></span> {{ v.nome }}</span>
          </li>
        } @empty { <li class="vazia">Nenhuma VLAN encontrada.</li> }
      </ul>
    }

    <!-- Janelinha do selo (como a dos marcadores): cor e nome da VLAN, para quem administra a rede -->
    @if (editando(); as e) {
      <div class="janela-cor-marcador" role="dialog" [attr.aria-label]="'VLAN ' + e.numero" (click)="$event.stopPropagation()">
        <app-seletor-cor tamanho="pequeno" [cores]="coresSeletor" [valor]="e.cor_indice" rotulo="Cor da VLAN" (escolher)="trocarCor(e, $event)" />
        <div class="renomear">
          <input type="text" maxlength="120" [(ngModel)]="novoNome" name="nome-vlan" [attr.aria-label]="'Nome da VLAN ' + e.numero" (keydown.enter)="$event.preventDefault(); renomear(e)" />
          <button type="button" class="acao-secundaria acao-pequena" [disabled]="!novoNome.trim() || novoNome.trim() === e.nome" (click)="renomear(e)">Renomear</button>
        </div>
        <small class="dica-formulario">A cor e o nome valem para a VLAN {{ e.numero }} em todas as portas.</small>
        <div class="acoes-janela-cor"><span></span><button type="button" class="acao-secundaria acao-pequena" (click)="editando.set(null)">Fechar</button></div>
      </div>
    }
  `,
})
export class SeletorVlansComponent {
  private static sequencia = 0;
  private readonly elemento = inject(ElementRef<HTMLElement>);
  private readonly api = inject(RedeApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly entrada = viewChild<ElementRef<HTMLInputElement>>('entrada');

  /** Todas as VLANs cadastradas. */
  readonly vlans = input.required<Vlan[]>();
  /** IDs das VLANs escolhidas neste campo. */
  readonly valor = input<string[]>([]);
  readonly valorChange = output<string[]>();
  /** IDs usados no outro campo (a mesma VLAN não passa com e sem tag): não aparecem como opção nem entram em "Todas". */
  readonly excluir = input<string[]>([]);
  /** Rótulo do campo (ex.: "VLANs com tag") e o complemento menor (ex.: "(tagged)"). */
  readonly rotuloCampo = input('VLANs');
  readonly detalheRotulo = input('');
  /** Começo da linha de resumo (ex.: "Com tag" → "Com tag: 2469–2483 (15 VLANs)"). */
  readonly prefixoResumo = input('VLANs');
  readonly rotulo = input('Adicionar VLAN');
  readonly placeholder = input('Digite o número ou o nome da VLAN…');
  readonly desabilitado = input(false);
  /** Quem administra a rede troca a cor e o nome da VLAN pelo selo (mesma regra dos marcadores: só quem gere). */
  readonly podeGerir = input(false);
  /** VLAN com cor ou nome novos: a tela atualiza a lista dela (vale para os dois campos e as outras partes da tela). */
  readonly vlanAlterada = output<Vlan>();
  /** `id` do campo de texto, para o `<label for>`. */
  readonly idCampo = input<string>(`seletor-vlans-campo-${SeletorVlansComponent.sequencia + 1}`);

  protected readonly idLista = `seletor-vlans-${++SeletorVlansComponent.sequencia}`;
  protected readonly coresSeletor = PALETA_MARCADORES.map((c, i) => ({ cor: c.borda, rotulo: `Cor ${i + 1}` }));
  protected readonly busca = signal('');
  protected readonly aberta = signal(false);
  protected readonly indice = signal(0);
  protected readonly editando = signal<Vlan | null>(null);
  protected novoNome = '';

  /** As escolhidas, na ordem do número da VLAN. */
  protected readonly escolhidas = computed(() => {
    const ids = new Set(this.valor());
    return this.vlans().filter((v) => ids.has(v.id)).sort((a, b) => a.numero - b.numero);
  });

  /** As que ainda podem entrar (nem aqui nem no outro campo). */
  protected readonly disponiveis = computed(() => {
    const fora = new Set([...this.valor(), ...this.excluir()]);
    return this.vlans().filter((v) => !fora.has(v.id)).sort((a, b) => a.numero - b.numero);
  });

  /** As disponíveis filtradas pela busca: o número começa com o que foi digitado ou o nome o contém. */
  protected readonly opcoes = computed(() => {
    const termo = normalizar(this.busca().trim());
    return this.disponiveis().filter((v) => !termo || String(v.numero).startsWith(termo) || normalizar(v.nome).includes(termo));
  });

  /** "2469–2483, 2490" (como no display do switch). */
  protected readonly resumo = computed(() => faixasDeVlans(this.escolhidas().map((v) => v.numero)));

  protected classe(cor: number): string {
    return classeMarcador(cor);
  }

  protected focar(): void {
    this.entrada()?.nativeElement.focus();
  }

  protected digitar(texto: string): void {
    this.busca.set(texto);
    this.indice.set(0);
    this.aberta.set(true);
  }

  protected escolher(id: string): void {
    this.valorChange.emit([...this.valor(), id]);
    this.busca.set('');
    this.indice.set(0);
    this.focar();
  }

  protected tirar(id: string): void {
    this.valorChange.emit(this.valor().filter((x) => x !== id));
  }

  /** Todas as VLANs que ainda não estão em nenhum dos dois campos (uplink/trunk que leva tudo). */
  protected todas(): void {
    this.valorChange.emit([...this.valor(), ...this.disponiveis().map((v) => v.id)]);
  }

  protected limpar(): void {
    this.valorChange.emit([]);
  }

  protected abrirCor(v: Vlan): void {
    if (!this.podeGerir() || this.desabilitado()) return;
    this.novoNome = v.nome;
    this.aberta.set(false);
    this.editando.set(v);
  }

  /** Grava a cor ou o nome na VLAN (vale em todas as portas) e avisa a tela. */
  private salvar(v: Vlan, mudancas: Partial<Pick<Vlan, 'nome' | 'cor_indice'>>, erro: string): void {
    this.api.salvarVlan(v.id, { numero: v.numero, nome: mudancas.nome ?? v.nome, descricao: v.descricao, cor_indice: mudancas.cor_indice ?? v.cor_indice }).subscribe({
      next: (nova) => { this.editando.set(nova); this.vlanAlterada.emit(nova); },
      error: (e) => this.dialogos.mostrarErro(e, erro),
    });
  }

  protected trocarCor(v: Vlan, indice: number): void {
    this.salvar(v, { cor_indice: indice }, 'Não foi possível trocar a cor da VLAN');
  }

  protected renomear(v: Vlan): void {
    const nome = this.novoNome.trim();
    if (nome && nome !== v.nome) this.salvar(v, { nome }, 'Não foi possível renomear a VLAN');
  }

  /** Setas andam na lista, Enter escolhe, Esc fecha e Backspace com o campo vazio tira a última. */
  protected teclar(evento: KeyboardEvent): void {
    const opcoes = this.opcoes();
    if (evento.key === 'ArrowDown') {
      evento.preventDefault();
      this.aberta.set(true);
      this.indice.set(Math.min(this.indice() + 1, Math.max(opcoes.length - 1, 0)));
    } else if (evento.key === 'ArrowUp') {
      evento.preventDefault();
      this.indice.set(Math.max(this.indice() - 1, 0));
    } else if (evento.key === 'Enter') {
      // Enter não envia o formulário da porta enquanto se escolhe a VLAN
      evento.preventDefault();
      const escolhida = opcoes[this.indice()];
      if (escolhida) this.escolher(escolhida.id);
    } else if (evento.key === 'Escape') {
      this.aberta.set(false);
      this.editando.set(null);
    } else if (evento.key === 'Backspace' && !this.busca() && this.escolhidas().length) {
      this.tirar(this.escolhidas()[this.escolhidas().length - 1].id);
    }
  }

  protected cliqueFora(evento: MouseEvent): void {
    if (!this.elemento.nativeElement.contains(evento.target as Node)) {
      this.aberta.set(false);
      this.editando.set(null);
    }
  }
}
