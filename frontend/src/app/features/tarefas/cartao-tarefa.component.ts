// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cartão compacto de uma tarefa no quadro (estilo Trello): etiquetas, título, prazo, contadores e avatares.

import { DatePipe } from '@angular/common';
import { classeMarcador } from './marcadores.paleta';
import { Component, computed, input, output } from '@angular/core';

import { AvataresComponent } from './avatares.component';
import { textoSla } from '../sla/sla.models';
import { ROTULOS_PRIORIDADE, situacaoPrazo, TarefaResumo } from './tarefas.models';

/** "Fabiana Tucilio Fanizzi de Morais" → "Fabiana Morais" (primeiro e último nome, sem partículas como "de"). */
export function nomeCurto(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  return partes.length <= 2 ? partes.join(' ') : `${partes[0]} ${partes[partes.length - 1]}`;
}

/**
 * Cartão do quadro. Clicar abre a tarefa (evento `abrir`); o arraste é controlado pela coluna.
 * - faixas coloridas no topo: os marcadores (o nome aparece ao passar o mouse);
 * - borda esquerda: a cor da prioridade (alta e crítica chamam atenção);
 * - nomes (até 2, com "+N") das pessoas envolvidas, abaixo do título;
 * - rodapé: chip do prazo colorido, checklist, comentários, anexos e os avatares dos responsaveis.
 */
@Component({
  selector: 'app-cartao-tarefa',
  imports: [DatePipe, AvataresComponent],
  template: `
    @let t = tarefa();
    <article class="cartao-quadro" [attr.data-prioridade]="t.prioridade" [class.destacado]="destacado()" tabindex="0" role="button"
             [attr.aria-label]="'Abrir tarefa ' + t.numero + ': ' + t.titulo" (click)="abrir.emit(t.numero)" (keydown.enter)="abrir.emit(t.numero)">
      <!-- Versão reduzida (só aparece quando o quadro entende que há cartões demais para a tela): #número · prazo · criticidade · marcadores -->
      <div class="mini-cartao" aria-hidden="true">
        <b class="mini-numero">#{{ t.numero }}</b>
        <span class="mini-prazo" [attr.data-situacao]="situacao()">{{ t.prazo | date: 'dd/MM' }}</span>
        <i class="mini-prioridade" [attr.data-prioridade]="t.prioridade">{{ siglaPrioridade() }}</i>
        @if (t.marcadores.length) {
          <span class="mini-marcadores">@for (m of t.marcadores; track m.id) { <i [class]="classeMarcador(m.cor_indice)"></i> }</span>
        }
      </div>
      @if (t.marcadores.length) {
        <div class="etiquetas">
          @for (m of t.marcadores; track m.id) { <span [class]="classeMarcador(m.cor_indice)" [title]="m.nome">{{ m.nome }}</span> }
        </div>
      }
      @if (t.tarefa_pai_numero) { <small class="rastro-subtarefa">↳ subtarefa de #{{ t.tarefa_pai_numero }}</small> }
      <p class="titulo-quadro" [title]="t.titulo">@if (t.controlada_externamente) { <span class="selo-origem" title="Controlada pelo módulo Contratos: anda sozinha conforme a etapa evolui" aria-label="Controlada pelo módulo Contratos">📄</span> }@if (t.bloqueada) { <span class="cadeado-tarefa" title="Bloqueada: há tarefa que precisa ser concluída antes" aria-label="Tarefa bloqueada">🔒</span> }{{ t.titulo }}</p>
      @if (t.subtarefas_total) {
        <div class="progresso-subtarefas" [title]="t.subtarefas_concluidas + ' de ' + t.subtarefas_total + ' subtarefas concluídas'"><span class="trilho"><i [style.width.%]="100 * t.subtarefas_concluidas / t.subtarefas_total"></i></span><small>{{ t.subtarefas_concluidas }}/{{ t.subtarefas_total }}</small></div>
      }
      @if (t.responsaveis.length) {
        <p class="nomes-quadro" [title]="nomesTodos()">{{ nomesCurtos() }}@if (outros()) { <b> +{{ outros() }}</b> }</p>
      }
      <div class="rodape-quadro">
        <span class="chip-prazo" [attr.data-situacao]="situacao()" [title]="'Prazo: ' + (t.prazo | date: 'dd/MM/yyyy HH:mm')">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" /></svg>
          {{ t.prazo | date: 'dd/MM' }}@if (t.prorrogacoes) { <b title="Prazo alterado">↻{{ t.prorrogacoes }}</b> }
        </span>
        @if (t.dias_em_aberto !== null) {
          <span class="contador dias-aberto" [title]="'Em aberto há ' + t.dias_em_aberto + (t.dias_em_aberto === 1 ? ' dia' : ' dias')">{{ t.dias_em_aberto }}d</span>
        }
        @if (t.checklist_total) {
          <span class="contador" [class.completo]="t.checklist_feitos === t.checklist_total" title="Checklist">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
            {{ t.checklist_feitos }}/{{ t.checklist_total }}</span>
        }
        @if (t.comentarios) {
          <span class="contador" title="Comentários">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" /></svg>{{ t.comentarios }}</span>
        }
        @if (t.anexos) {
          <span class="contador" title="Anexos">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.4 11.1l-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5" /></svg>{{ t.anexos }}</span>
        }
        @if (t.status !== 'concluida' && t.sla && (t.sla.situacao_resolucao === 'em_risco' || t.sla.situacao_resolucao === 'estourado')) {
          <span class="selo-sla" [attr.data-situacao]="t.sla.situacao_resolucao" [title]="textoSla(t.sla, 'resolucao')">SLA</span>
        }
        @if (t.prioridade === 'alta' || t.prioridade === 'critica') {
          <span class="selo-prioridade-tarefa" [attr.data-prioridade]="t.prioridade">{{ rotulosPrioridade[t.prioridade] }}</span>
        }
        <span class="numero-quadro">#{{ t.numero }}</span>
        <app-avatares [pessoas]="t.responsaveis" tamanho="pequeno" />
      </div>
    </article>
  `,
})
export class CartaoTarefaComponent {
  protected readonly classeMarcador = classeMarcador;
  readonly tarefa = input.required<TarefaResumo>();
  /** Destaque temporário (ex.: tarefa recém-criada pela criação rápida). */
  readonly destacado = input(false);
  readonly abrir = output<number>();

  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly textoSla = textoSla;
  protected readonly situacao = computed(() => situacaoPrazo(this.tarefa()));
  /** Sigla da criticidade para a versão reduzida: B, N, A ou C. */
  protected readonly siglaPrioridade = computed(() => ({ baixa: 'B', normal: 'N', alta: 'A', critica: 'C' })[this.tarefa().prioridade]);
  /** Quantos nomes aparecem no cartão antes do "+N" (os demais ficam na dica). */
  private readonly maximoNomes = 2;
  protected readonly nomesCurtos = computed(() => this.tarefa().responsaveis.slice(0, this.maximoNomes).map((p) => nomeCurto(p.nome)).join(', '));
  protected readonly outros = computed(() => Math.max(0, this.tarefa().responsaveis.length - this.maximoNomes));
  protected readonly nomesTodos = computed(() => this.tarefa().responsaveis.map((p) => p.nome).join(', '));
}
