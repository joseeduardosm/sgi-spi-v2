/**
 * =============================================================================
 * ARQUIVO: aba-eventos.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Aba "Eventos" do contrato: tudo o que aconteceu nele (lido da auditoria), com
 * chips por categoria, busca, colunas ordenáveis, "Mostrar mais" e o botão
 * "Tornar sem efeito" nas conclusões que podem ser desfeitas.
 *
 * RESUMO TÉCNICO:
 * Componente standalone (OnPush) com template embutido, na estrutura da lista
 * de Chamados (.chips-filtro, .barra-protocolo + .campo, tabela com
 * th[aria-sort] + button.ordenar-coluna). A API pagina e ordena
 * (GET /contratos/{id}/eventos); a tela acumula as páginas no signal `itens`.
 * <app-esqueleto> na primeira carga; app-tornar-sem-efeito na coluna Ação.
 *
 * FINALIDADE DE NEGÓCIO:
 * Decisão do usuário (13/11/2026): quem tem Controle total em Contratos vê a
 * história completa do contrato e pode tornar sem efeito o que for permitido.
 *
 * CONTEXTO NO SISTEMA:
 * Aberta pela tela de detalhe do contrato (aba visível só com
 * `permissoes.pode_administrar`); dados de AlteracoesApiService.eventos.
 *
 * =============================================================================
 */

import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { AlteracoesApiService } from '../compartilhado/alteracoes-api.service';
import { CategoriaEvento, EventoContrato } from '../compartilhado/contratos.models';
import { TornarSemEfeitoComponent } from '../compartilhado/tornar-sem-efeito.component';

/** Colunas ordenáveis (a API ordena; "ação" não ordena por ser um botão, não um dado). */
type ColunaEvento = 'ocorrido_em' | 'evento' | 'autor' | 'detalhe';

/** Chips de categoria, na ordem da tela ("Todos" = sem filtro). */
const CHIPS: { valor: CategoriaEvento | null; rotulo: string }[] = [
  { valor: 'altera_contrato', rotulo: 'Alteram o contrato' },
  { valor: 'execucao', rotulo: 'Execução' },
  { valor: 'documentos', rotulo: 'Documentos' },
  { valor: 'equipe_cadastro', rotulo: 'Equipe e cadastro' },
  { valor: 'sem_efeito', rotulo: 'Sem efeito' },
  { valor: null, rotulo: 'Todos' },
];

/**
 * Recursos do Angular usados aqui: `input()` (entrada do pai, lida como função), `output()` (evento para o pai) e
 * `signal()` (estado que, ao mudar, atualiza a tela).
 */
@Component({
  selector: 'app-aba-eventos',
  imports: [FormsModule, DatePipe, EsqueletoComponent, TornarSemEfeitoComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="painel-gestao protocolo" aria-labelledby="titulo-eventos-contrato">
      <h2 id="titulo-eventos-contrato" class="somente-leitor-tela">Eventos do contrato</h2>
      <div class="chips-filtro" role="group" aria-label="Categorias de evento">
        @for (c of chips; track c.rotulo) {
          <button type="button" [class.ativo]="categoria() === c.valor" [attr.aria-pressed]="categoria() === c.valor" (click)="trocarCategoria(c.valor)">
            {{ c.rotulo }}@if (c.valor && contagem()[c.valor] !== undefined) { ({{ contagem()[c.valor] }}) }</button>
        }
      </div>
      <div class="barra-protocolo">
        <div class="campo"><label for="eventos-busca">Busca</label>
          <input id="eventos-busca" type="search" placeholder="Evento, pessoa, motivo ou valor" [(ngModel)]="busca" (keyup.enter)="recarregar()" /></div>
        <button type="button" class="acao-secundaria" (click)="recarregar()">Buscar</button>
        <span class="espacador"></span>
        <span class="resumo-protocolo">{{ total() }} evento(s)</span>
      </div>
      @if (carregando()) {
        <app-esqueleto tipo="tabela" [linhas]="6" [colunas]="5" />
      } @else {
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr>
              @for (col of colunas; track col.chave) {
                <th scope="col" [attr.aria-sort]="sentidoAria(col.chave)">
                  <button type="button" class="ordenar-coluna" [class.ativa]="ordem() === col.chave" (click)="ordenar(col.chave)" [title]="'Ordenar por ' + col.rotulo.toLowerCase()">
                    {{ col.rotulo }}<span aria-hidden="true">{{ ordem() === col.chave ? (sentido() === 'asc' ? '▲' : '▼') : '↕' }}</span></button>
                </th>
              }
              <th scope="col">Ação</th>
            </tr></thead>
            <tbody>
              @for (e of itens(); track e.id) {
                <tr>
                  <td data-rotulo="Data e hora" class="texto-codigo">{{ e.ocorrido_em | date: 'dd/MM/yyyy HH:mm' }}</td>
                  <td data-rotulo="Evento"><span><strong>{{ e.evento }}</strong>
                    @if (e.sem_efeito) { <span class="selo-situacao perigo">Sem efeito</span> }</span></td>
                  <td data-rotulo="Por">{{ e.autor }}</td>
                  <td data-rotulo="Detalhe"><small>{{ e.detalhe || '—' }}</small></td>
                  <td data-rotulo="Ação">
                    @if (e.registro_tipo && e.registro_id && !e.sem_efeito) {
                      <app-tornar-sem-efeito [contratoId]="contratoId()" [tipo]="e.registro_tipo" [registroId]="e.registro_id" [pode]="e.pode_tornar_sem_efeito"
                                             [motivoBloqueio]="e.motivo_bloqueio" [titulo]="'Tornar sem efeito: ' + e.evento + '?'" (concluido)="aposSemEfeito()" />
                    } @else { — }
                  </td>
                </tr>
              } @empty {
                <tr><td colspan="5" class="estado-vazio">Nenhum evento com este filtro.</td></tr>
              }
            </tbody>
          </table>
        </div>
        @if (total() > itens().length) {
          <div class="acoes-formulario"><button type="button" class="acao-secundaria" [class.carregando]="carregandoMais()" [disabled]="carregandoMais()" (click)="carregarMais()">Mostrar mais</button></div>
        }
      }
    </section>
  `,
})
export class AbaEventosComponent implements OnInit {
  private readonly api = inject(AlteracoesApiService);
  private readonly dialogos = inject(DialogosService);

  readonly contratoId = input.required<string>();
  /** Emitido depois de tornar um evento sem efeito: a tela do contrato recarrega (preços, vigência…). */
  readonly alterado = output<void>();

  protected readonly chips = CHIPS;
  protected readonly colunas: { chave: ColunaEvento; rotulo: string }[] = [
    { chave: 'ocorrido_em', rotulo: 'Data e hora' }, { chave: 'evento', rotulo: 'Evento' }, { chave: 'autor', rotulo: 'Por' }, { chave: 'detalhe', rotulo: 'Detalhe' },
  ];
  protected readonly categoria = signal<CategoriaEvento | null>('altera_contrato');
  protected readonly ordem = signal<ColunaEvento>('ocorrido_em');
  protected readonly sentido = signal<'asc' | 'desc'>('desc');
  protected readonly itens = signal<EventoContrato[]>([]);
  protected readonly total = signal(0);
  protected readonly contagem = signal<Record<string, number>>({});
  protected readonly carregando = signal(true);
  protected readonly carregandoMais = signal(false);
  protected busca = '';
  private pagina = 1;

  ngOnInit(): void {
    this.recarregar();
  }

  protected trocarCategoria(valor: CategoriaEvento | null): void {
    this.categoria.set(valor);
    this.recarregar();
  }

  /** Clicar na coluna ativa inverte o sentido; outra coluna começa crescente (a data começa pela mais recente). */
  protected ordenar(coluna: ColunaEvento): void {
    if (this.ordem() === coluna) {
      this.sentido.set(this.sentido() === 'asc' ? 'desc' : 'asc');
    } else {
      this.ordem.set(coluna);
      this.sentido.set(coluna === 'ocorrido_em' ? 'desc' : 'asc');
    }
    this.recarregar();
  }

  protected sentidoAria(coluna: ColunaEvento): 'ascending' | 'descending' | 'none' {
    return this.ordem() !== coluna ? 'none' : this.sentido() === 'asc' ? 'ascending' : 'descending';
  }

  protected recarregar(): void {
    this.pagina = 1;
    this.carregando.set(true);
    this.buscar(false);
  }

  protected carregarMais(): void {
    this.pagina += 1;
    this.carregandoMais.set(true);
    this.buscar(true);
  }

  /** Depois de tornar um evento sem efeito: recarrega a lista e avisa a tela do contrato. */
  protected aposSemEfeito(): void {
    this.recarregar();
    this.alterado.emit();
  }

  private buscar(acumular: boolean): void {
    this.api.eventos(this.contratoId(), { categoria: this.categoria(), busca: this.busca, ordem: this.ordem(), sentido: this.sentido(), pagina: this.pagina }).subscribe({
      next: (p) => {
        this.itens.set(acumular ? [...this.itens(), ...p.itens] : p.itens);
        this.total.set(p.total);
        this.contagem.set(p.por_categoria);
        this.carregando.set(false);
        this.carregandoMais.set(false);
      },
      error: (e) => {
        this.carregando.set(false);
        this.carregandoMais.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível carregar os eventos');
      },
    });
  }
}
