/**
 * =============================================================================
 * ARQUIVO: opcao-email.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Oferecer a caixa "Enviar por e-mail" (desmarcada por padrão) com a escolha,
 * agrupada, de quem recebe, nas etapas da execução que disparam e-mail.
 *
 * RESUMO TÉCNICO:
 * Componente standalone (OnPush) com template e estilos embutidos. Usa
 * model() para o estado "marcado" e para os ids escolhidos (ligação de mão
 * dupla com o pai). Um effect() carrega a lista de destinatários (função
 * "fonte" passada pelo pai) na primeira vez em que a caixa é marcada. Exporta
 * os tipos Destinatario e GrupoDestinatarios.
 *
 * FINALIDADE DE NEGÓCIO:
 * Evita e-mails disparados sem querer: o envio aos prepostos da empresa ou ao
 * Financeiro (DOF) só acontece quando o servidor marca a opção, e ele pode
 * escolher exatamente quem recebe. Em envios obrigatórios, só a escolha de
 * destinatários é mostrada.
 *
 * CONTEXTO NO SISTEMA:
 * Usado pelas etapas da competência (medição, avaliação, nota fiscal,
 * retenção, CADIN etc.). As listas vêm de ExecucaoApiService
 * (gruposPrepostos, gruposFinanceiro).
 *
 * =============================================================================
 */

import { ChangeDetectionStrategy, Component, computed, effect, input, model, signal } from '@angular/core';
import { Observable } from 'rxjs';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
/** Um destinatário possível (preposto = representante da empresa contratada; usuário do Financeiro…). */
export interface Destinatario {
  id: string | number;
  nome: string;
  email: string;
  cargo?: string;
}

/** Grupo de destinatários (ex.: um subsetor do Financeiro). */
export interface GrupoDestinatarios {
  titulo: string;
  itens: Destinatario[];
}

/**
 * Caixa "Enviar por e-mail". Fica **desmarcada** por padrão: a etapa só dispara o SMTP quando a pessoa marca.
 * Com `fonte`, ao marcar abre a lista de quem recebe (todos marcados), com "Selecionar todos", marcação por grupo e por pessoa.
 * `selecionados` devolve os ids escolhidos (lista vazia = ninguém dessa lista; `null` enquanto a lista não carregou = todos).
 *
 * `model()` é como um `input()` que o próprio componente também pode alterar: o pai usa `[(marcado)]` e recebe
 * a mudança de volta. `effect()` executa uma função sempre que algum signal lido dentro dela muda.
 */
@Component({
  imports: [EsqueletoComponent],
  selector: 'app-opcao-email',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="opcao-email-bloco">
      @if (obrigatorio()) {
        <!-- Envio obrigatório: sem caixa para desligar, só a escolha de quem recebe -->
        <div class="opcao-email"><span><b>{{ titulo() }}</b>@if (descricao()) { <small>{{ descricao() }}</small> }</span></div>
      } @else {
        <label class="opcao-email">
          <input type="checkbox" [checked]="marcado()" (change)="marcado.set($any($event.target).checked)" />
          <span>Enviar por e-mail@if (descricao()) { <small>{{ descricao() }}</small> }</span>
        </label>
      }
      @if ((marcado() || obrigatorio()) && fonte()) {
        <div class="seletor-destinatarios" role="group" [attr.aria-label]="rotuloLista()">
          <div class="cabecalho-seletor">
            <label><input type="checkbox" [checked]="todos()" [indeterminate]="alguns()" (change)="alternarTodos($any($event.target).checked)" /> <b>Selecionar todos</b></label>
            <small>{{ rotuloLista() }}: {{ escolhidos().size }} de {{ total() }}</small>
          </div>
          @if (carregando()) {
            <app-esqueleto tipo="lista" [linhas]="4" />
          } @else if (!total()) {
            <p class="dica-formulario">{{ vazio() }}</p>
          }
          @for (g of grupos(); track g.titulo) {
            <div class="grupo-destinatarios">
              <label class="titulo-grupo"><input type="checkbox" [checked]="grupoTodos(g)" [indeterminate]="grupoAlguns(g)" (change)="alternarGrupo(g, $any($event.target).checked)" /> {{ g.titulo }}</label>
              @for (d of g.itens; track d.id) {
                <label class="destinatario"><input type="checkbox" [checked]="escolhidos().has(d.id)" (change)="alternar(d, $any($event.target).checked)" />
                  <span>{{ d.nome }} <small>{{ d.email }}@if (d.cargo) { · {{ d.cargo }} }</small></span></label>
              }
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: `
    :host { display: inline-block; vertical-align: top; }
    .opcao-email-bloco { margin: 0 12px 6px 0; }
    .opcao-email { display: inline-flex; align-items: center; gap: 8px; color: var(--cor-464f5a); font-size: 13px; font-weight: 600; cursor: pointer; }
    input[type='checkbox'] { width: 16px; height: 16px; margin: 0; accent-color: #af3741; }
    small { display: block; color: var(--cor-6a7786); font-size: 11.5px; font-weight: 400; }
    .seletor-destinatarios { min-width: 340px; max-width: 520px; max-height: 260px; margin-top: 8px; padding: 10px 12px; overflow: auto; border: 1px solid var(--cor-e2e5e8); border-radius: var(--spi-raio-m); background: var(--cor-fbfbfc); }
    .cabecalho-seletor { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 6px; border-bottom: 1px solid var(--cor-eceef0); font-size: 12.5px; }
    .cabecalho-seletor label, .titulo-grupo, .destinatario { display: flex; align-items: center; gap: 8px; cursor: pointer; }
    .grupo-destinatarios { margin-top: 8px; }
    .titulo-grupo { color: var(--cor-361a1c); font-size: 12px; font-weight: 700; }
    .destinatario { padding: 3px 0 3px 24px; font-size: 12.5px; }
    .destinatario small { display: inline; }
    .dica-formulario { margin: 8px 0 0; color: var(--cor-6a7786); font-size: 12px; }
  `,
})
export class OpcaoEmailComponent {
  /** Marcada = envia o e-mail (mão dupla). */
  readonly marcado = model(false);
  /** Texto de apoio exibido sob a caixa (ex.: quem recebe e o que vai anexado). */
  readonly descricao = input('');
  /** Envio obrigatório: não há caixa para desligar; a lista de destinatários aparece sempre e o pai exige ao menos um escolhido. */
  readonly obrigatorio = input(false);
  /** Título mostrado no lugar da caixa quando `obrigatorio`. */
  readonly titulo = input('Enviar por e-mail');
  /** Carrega os destinatários possíveis (chamada na primeira vez que a caixa é marcada). Sem ela, só a caixa aparece. */
  readonly fonte = input<(() => Observable<GrupoDestinatarios[]>) | null>(null);
  /** Rótulo da lista (acessibilidade e contador "x de y"). */
  readonly rotuloLista = input('Destinatários');
  /** Mensagem quando a fonte não traz ninguém com e-mail. */
  readonly vazio = input('Ninguém com e-mail cadastrado para esta lista.');
  /** Ids escolhidos (mão dupla). `null` até a lista carregar. */
  readonly selecionados = model<(string | number)[] | null>(null);

  // Estado interno: grupos carregados, carregamento em curso e o conjunto de ids marcados.
  // `carregado` é campo comum (não signal) porque só controla a carga única e não aparece na tela.
  protected readonly grupos = signal<GrupoDestinatarios[]>([]);
  protected readonly carregando = signal(false);
  protected readonly escolhidos = signal<Set<string | number>>(new Set());
  private carregado = false;

  // Totais para o "Selecionar todos" (marcado, desmarcado ou indeterminado)
  protected readonly total = computed(() => this.grupos().reduce((n, g) => n + g.itens.length, 0));
  protected readonly todos = computed(() => this.total() > 0 && this.escolhidos().size === this.total());
  protected readonly alguns = computed(() => this.escolhidos().size > 0 && this.escolhidos().size < this.total());

  constructor() {
    // Ao marcar pela primeira vez, carrega a lista e marca todos
    effect(() => {
      const fonte = this.fonte();
      if ((this.marcado() || this.obrigatorio()) && fonte && !this.carregado) {
        this.carregado = true;
        this.carregando.set(true);
        fonte().subscribe({
          next: (g) => {
            this.grupos.set(g);
            this.escolher(new Set(g.flatMap((x) => x.itens.map((d) => d.id))));
            this.carregando.set(false);
          },
          // Em erro, libera nova tentativa na próxima vez que a caixa for marcada
          error: () => { this.carregando.set(false); this.carregado = false; },
        });
      }
    });
  }

  /** Atualiza o conjunto interno e devolve ao pai os ids escolhidos (model `selecionados`). */
  private escolher(conjunto: Set<string | number>): void {
    this.escolhidos.set(conjunto);
    this.selecionados.set([...conjunto]);
  }

  /** Marca ou desmarca todos os destinatários de todos os grupos. */
  protected alternarTodos(marcar: boolean): void {
    this.escolher(marcar ? new Set(this.grupos().flatMap((g) => g.itens.map((d) => d.id))) : new Set());
  }

  /** Marca ou desmarca todas as pessoas de um grupo; sempre cria um Set novo para o signal notar a mudança. */
  protected alternarGrupo(g: GrupoDestinatarios, marcar: boolean): void {
    const novo = new Set(this.escolhidos());
    for (const d of g.itens) marcar ? novo.add(d.id) : novo.delete(d.id);
    this.escolher(novo);
  }

  /** Marca ou desmarca uma pessoa. */
  protected alternar(d: Destinatario, marcar: boolean): void {
    const novo = new Set(this.escolhidos());
    marcar ? novo.add(d.id) : novo.delete(d.id);
    this.escolher(novo);
  }

  /** Caixa do grupo marcada: todas as pessoas dele escolhidas. */
  protected grupoTodos(g: GrupoDestinatarios): boolean {
    return g.itens.length > 0 && g.itens.every((d) => this.escolhidos().has(d.id));
  }

  /** Caixa do grupo indeterminada (traço): só parte das pessoas escolhidas. */
  protected grupoAlguns(g: GrupoDestinatarios): boolean {
    const n = g.itens.filter((d) => this.escolhidos().has(d.id)).length;
    return n > 0 && n < g.itens.length;
  }
}
