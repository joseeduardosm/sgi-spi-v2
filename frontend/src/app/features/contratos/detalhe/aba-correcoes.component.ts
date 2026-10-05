// Criado por José Eduardo Santana Martins
// Este arquivo serve para a aba "Correções de itens": corrigir preço e quantidades depois de geradas as competências (proposta, prévia e confirmação por outra pessoa).

import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { CorrecaoItens, HistoricoItemContrato, ItemContrato, PreviaCorrecao } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { LinkificarPipe } from '../../../shared/utilitarios/linkificar.pipe';

const ROTULOS_CAMPO: Record<string, string> = {
  valor_unitario: 'Valor unitário', quantidade_mensal: 'Quantidade mensal', quantidade_total: 'Quantidade total (teto)', unidade_fornecimento: 'Unidade',
  codigo_classe: 'Classe', codigo_natureza_despesa: 'Natureza da despesa', codigo_siafisico: 'Siafísico', codigo_catmat_catser: 'CATMAT/CATSER',
};
const ROTULOS_SITUACAO = { pendente: 'Aguardando confirmação', aplicada: 'Aplicada', recusada: 'Recusada', cancelada: 'Cancelada' };

interface LinhaEdicao {
  item: ItemContrato;
  valor_unitario: string;
  quantidade_mensal: string;
  quantidade_total: string;
}

/**
 * Corrigir erro de cadastro dos itens com as competências já geradas. As competências abertas (medição não concluída) seguem o cadastro;
 * as concluídas nunca mudam. O gestor propõe e **outra pessoa confirma** (dois olhos).
 */
@Component({
  selector: 'app-aba-correcoes',
  imports: [LinkificarPipe, FormsModule, DatePipe],
  template: `
    <section class="cartao-dados" aria-labelledby="titulo-correcoes">
      <header>
        <div><h2 id="titulo-correcoes">Correções de itens</h2>
          <small>As competências ainda sem medição concluída seguem o cadastro; as concluídas não mudam. Toda correção precisa da confirmação de outra pessoa.</small></div>
        @if (lista()?.pode_propor) { <button type="button" class="acao-primaria" (click)="abrir()"><span>+</span> Corrigir itens</button> }
      </header>
      <div class="corpo">
        <p class="dica-formulario">Para uma <b>mudança contratual a partir de um mês</b> (repactuação de preço, aditamento ou supressão), use as telas de Reajuste e de Aditamento/Supressão.</p>
        @for (c of lista()?.itens ?? []; track c.id) {
          <article class="indicador cartao-dobravel" style="margin-bottom: 12px">
            <button type="button" class="cabecalho-dobravel" [attr.aria-expanded]="aberta(c)" (click)="alternar(c)">
              <span class="seta" [class.aberta]="aberta(c)" aria-hidden="true">▸</span>
              <strong style="font-size: 14px">{{ c.mudancas.length }} item(ns) · proposta de {{ c.autor_nome }}</strong>
              <small>{{ c.criado_em | date: 'dd/MM/yyyy HH:mm' }}</small>
              <span class="selo-situacao" [class.inativo]="c.situacao !== 'pendente' && c.situacao !== 'aplicada'">{{ situacoes[c.situacao] }}</span>
            </button>
            @if (aberta(c)) {
              <p style="margin: 8px 0 4px; font-size: 13px"><b>Justificativa:</b> <span [innerHTML]="c.justificativa | linkificar"></span></p>
              @for (m of c.mudancas; track m.item_id) {
                <div style="font-size: 12.5px; margin: 6px 0"><b>{{ m.descricao }}</b>
                  <ul style="margin: 2px 0 0; padding-left: 20px">
                    @for (campo of chaves(m.campos); track campo) { <li>{{ rotulos[campo] }}: <s>{{ m.campos[campo].de }}</s> → <b>{{ m.campos[campo].para }}</b></li> }
                  </ul></div>
              }
              @if (c.previa.competencias_abertas.length) {
                <details style="margin: 8px 0"><summary>Competências abertas afetadas ({{ c.previa.competencias_abertas.length }}) · variação {{ c.previa.variacao_total }}</summary>
                  <ul style="font-size: 12px">@for (p of c.previa.competencias_abertas; track p.identificador) { <li>{{ p.competencia }}: {{ p.valor_antes }} → {{ p.valor_depois }} ({{ p.variacao }})@if (p.ciencias_invalidadas) { · ciências invalidadas }</li> }</ul></details>
              }
              @if (c.decidido_por_nome) { <small>{{ situacoes[c.situacao] }} por {{ c.decidido_por_nome }} em {{ c.decidido_em | date: 'dd/MM/yyyy HH:mm' }}@if (c.motivo_decisao) { · {{ c.motivo_decisao }} }</small> }
              <div class="acoes-cartao esquerda">
                @if (c.pode_decidir) {
                  <button type="button" class="acao-positiva acao-pequena" (click)="decidir(c, 'confirmar')">Confirmar correção</button>
                  <button type="button" class="acao-recusar acao-pequena" (click)="recusar(c)">Recusar</button>
                }
                @if (c.pode_cancelar) { <button type="button" class="acao-secundaria acao-pequena" (click)="decidir(c, 'cancelar')">Cancelar proposta</button> }
              </div>
            }
          </article>
        } @empty {
          <p class="estado-vazio">Nenhuma correção proposta.</p>
        }

        @if (historico().length) {
          <h3 style="margin: 18px 0 6px; font-size: 14px">Histórico dos itens</h3>
          <div class="tabela-gestao-envoltorio"><table class="tabela-gestao">
            <thead><tr><th>Quando</th><th>Item</th><th>O que mudou</th><th>Quem</th><th>Versão</th></tr></thead>
            <tbody>@for (h of historico(); track h.id) {
              <tr><td>{{ h.criado_em | date: 'dd/MM/yyyy HH:mm' }}</td><td>{{ h.descricao_item }}</td>
                <td>@for (campo of chaves(h.campos); track campo) { <div>{{ rotulos[campo] ?? campo }}: <s>{{ h.campos[campo].de }}</s> → <b>{{ h.campos[campo].para }}</b></div> }</td>
                <td>{{ h.autor_nome }}<small style="display:block" [innerHTML]="h.motivo | linkificar"></small></td><td>{{ h.versao_cadastro }}</td></tr> }</tbody></table></div>
        }
      </div>
    </section>

    @if (aberto()) {
      <div class="fundo-modal" role="presentation" (click)="aberto.set(false)"></div>
      <section class="modal-portal modal-largo modal-checklist" role="dialog" aria-modal="true" aria-labelledby="titulo-corrigir">
        <header>
          <div><span class="modal-sobretitulo">Contrato</span><h2 id="titulo-corrigir">Corrigir itens</h2></div>
          <button type="button" aria-label="Fechar" (click)="aberto.set(false)">×</button>
        </header>
        <form (ngSubmit)="propor()">
          <p class="dica-formulario" style="margin: 0 0 8px">Altere só o que está errado. Preço de item já reajustado e quantidade de item já aditado ou suprimido não podem ser corrigidos aqui.</p>
          <div class="tabela-gestao-envoltorio lista-documentos-checklist">
            <table class="tabela-gestao">
              <thead><tr><th>Item</th><th>Valor unitário</th><th>Qtd. mensal</th><th>Qtd. total (sob demanda)</th></tr></thead>
              <tbody>
                @for (l of linhas; track l.item.id; let i = $index) {
                  <tr><td><strong>{{ l.item.descricao }}</strong><small style="display:block">{{ l.item.tipo === 'continuo' ? 'Contínuo' : 'Sob demanda' }}</small></td>
                    <td><input class="campo-correcao" [name]="'v' + i" inputmode="decimal" [(ngModel)]="l.valor_unitario" /></td>
                    <td><input class="campo-correcao" [name]="'m' + i" inputmode="decimal" [(ngModel)]="l.quantidade_mensal" /></td>
                    <td><input class="campo-correcao" [name]="'t' + i" inputmode="decimal" [(ngModel)]="l.quantidade_total" [disabled]="l.item.tipo !== 'sob_demanda'" /></td></tr>
                }
              </tbody>
            </table>
          </div>
          <div class="grade-formulario uma-coluna" style="margin-top: 12px">
            <div><label for="corr-just">Justificativa * (mínimo 20 caracteres)</label>
              <textarea id="corr-just" name="justificativa" rows="3" maxlength="4000" [(ngModel)]="justificativa" placeholder="Por que o cadastro está errado?"></textarea></div>
          </div>
          @if (previa(); as p) {
            <div class="avisos-importacao" style="margin-top: 10px">
              <strong>Prévia</strong>: {{ p.competencias_abertas.length }} competência(s) aberta(s) mudam · variação do valor previsto {{ p.variacao_total }} · {{ p.congeladas }} concluída(s) não mudam.
              <ul>@for (a of p.avisos; track a) { <li>{{ a }}</li> }</ul>
            </div>
          }
          <footer>
            <small class="dica-formulario resumo-checklist">A correção só vale depois que outra pessoa da equipe confirmar.</small>
            <button type="button" class="acao-secundaria" (click)="aberto.set(false)">Cancelar</button>
            <button type="button" class="acao-secundaria" [disabled]="!podeEnviar() || ocupado()" (click)="verPrevia()">Ver prévia</button>
            <button type="submit" class="acao-primaria" [disabled]="!podeEnviar() || ocupado()">Propor correção</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class AbaCorrecoesComponent implements OnInit {
  readonly contratoId = input.required<string>();
  readonly itens = input.required<ItemContrato[]>();
  /** Avisa a tela quando uma correção foi aplicada (para recarregar os itens do contrato). */
  readonly aplicada = output<void>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly lista = signal<{ pode_propor: boolean; itens: CorrecaoItens[] } | null>(null);
  protected readonly historico = signal<HistoricoItemContrato[]>([]);
  protected readonly aberto = signal(false);
  protected readonly ocupado = signal(false);
  protected readonly previa = signal<PreviaCorrecao | null>(null);
  private readonly abertas = signal<Record<string, boolean>>({});
  protected readonly rotulos = ROTULOS_CAMPO;
  protected readonly situacoes = ROTULOS_SITUACAO;
  protected linhas: LinhaEdicao[] = [];
  protected justificativa = '';

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.correcoes(this.contratoId()).subscribe({ next: (l) => this.lista.set(l), error: (e) => this.dialogos.mostrarErro(e) });
    this.api.historicoItens(this.contratoId()).subscribe({ next: (h) => this.historico.set(h), error: () => this.historico.set([]) });
  }

  protected chaves(campos: Record<string, unknown>): string[] {
    return Object.keys(campos);
  }

  protected aberta(c: CorrecaoItens): boolean {
    return this.abertas()[c.id] ?? c.situacao === 'pendente';
  }

  protected alternar(c: CorrecaoItens): void {
    this.abertas.update((a) => ({ ...a, [c.id]: !this.aberta(c) }));
  }

  protected abrir(): void {
    this.linhas = this.itens().map((item) => ({ item, valor_unitario: item.valor_unitario, quantidade_mensal: item.quantidade_mensal, quantidade_total: item.quantidade_total }));
    this.justificativa = '';
    this.previa.set(null);
    this.aberto.set(true);
  }

  /** Só os campos que mudaram em relação ao cadastro vão para a API. */
  private corpo(): { justificativa: string; itens: Record<string, string>[] } {
    const itens = this.linhas.flatMap((l) => {
      const mudou: Record<string, string> = {};
      for (const c of ['valor_unitario', 'quantidade_mensal', 'quantidade_total'] as const) {
        const novo = String(l[c]).trim().replace(',', '.');
        if (novo !== '' && Number(novo) !== Number(l.item[c])) mudou[c] = novo;
      }
      return Object.keys(mudou).length ? [{ id: l.item.id, ...mudou }] : [];
    });
    return { justificativa: this.justificativa.trim(), itens };
  }

  protected podeEnviar(): boolean {
    const c = this.corpo();
    return c.itens.length > 0 && c.justificativa.length >= 20;
  }

  protected verPrevia(): void {
    this.ocupado.set(true);
    this.api.previaCorrecao(this.contratoId(), this.corpo()).subscribe({
      next: (p) => { this.ocupado.set(false); this.previa.set(p); },
      error: (e) => { this.ocupado.set(false); this.dialogos.mostrarErro(e, 'Não foi possível calcular a prévia'); },
    });
  }

  protected propor(): void {
    if (!this.podeEnviar()) return;
    this.ocupado.set(true);
    this.api.proporCorrecao(this.contratoId(), this.corpo()).subscribe({
      next: () => { this.ocupado.set(false); this.aberto.set(false); this.carregar(); this.dialogos.avisar('Proposta registrada', 'A equipe foi avisada. A correção só vale depois que outra pessoa confirmar.'); },
      error: (e) => { this.ocupado.set(false); this.dialogos.mostrarErro(e, 'Não foi possível propor a correção'); },
    });
  }

  protected async decidir(c: CorrecaoItens, acao: 'confirmar' | 'cancelar'): Promise<void> {
    const confirmar = acao === 'confirmar';
    const ok = await this.dialogos.confirmar({
      titulo: confirmar ? 'Confirmar a correção?' : 'Cancelar a proposta?',
      mensagem: confirmar ? `O cadastro dos itens muda e ${c.previa.competencias_abertas.length} competência(s) aberta(s) serão atualizadas (ciências invalidadas onde os valores mudarem). Competências concluídas não mudam.` : 'A proposta deixa de valer.',
      rotuloConfirmar: confirmar ? 'Confirmar correção' : 'Cancelar proposta',
      segundos: confirmar ? 3 : 0,
    });
    if (!ok) return;
    this.api.decidirCorrecao(this.contratoId(), c.id, acao).subscribe({
      next: () => { this.carregar(); if (confirmar) this.aplicada.emit(); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível concluir a ação'),
    });
  }

  protected recusar(c: CorrecaoItens): void {
    const motivo = window.prompt('Motivo da recusa:', '');
    if (!motivo?.trim()) return;
    this.api.decidirCorrecao(this.contratoId(), c.id, 'recusar', motivo.trim()).subscribe({ next: () => this.carregar(), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível recusar') });
  }
}
