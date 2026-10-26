// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cartão executivo do orçamento do exercício: saldo remanescente dos meses concluídos e as decisões de empenho.

import { Component, computed, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';

import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { OrcamentoCarteira, OrcamentoExecutivo } from './contratos.models';

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

/** `AAAA-MM-DD` → `nov/2026`. */
function mesAno(data: string | null): string {
  return data ? `${MESES[Number(data.slice(5, 7)) - 1]}/${data.slice(0, 4)}` : '';
}

/**
 * Orçamento do exercício em respostas diretas: quanto sobrou dos meses concluídos (previsto − NF) e, do empenho, por quantos meses ele cobre,
 * quanto falta de reforço (e até quando pedir) e quanto pode ser cancelado ou transferido. Serve ao detalhe do contrato (`contrato`) e ao painel (`carteira`).
 */
@Component({
  selector: 'app-orcamento-executivo',
  imports: [RouterLink, ...PIPES_FORMATACAO],
  template: `
    @if (dados(); as d) {
      <section class="cartao-dados orcamento-executivo" aria-labelledby="titulo-orcamento-executivo">
        <header>
          <div><h2 id="titulo-orcamento-executivo">Orçamento do exercício {{ d.exercicio }}</h2>
            <small>{{ carteira() ? 'Soma dos contratos ativos visíveis (mesmos filtros do painel).' : 'Saldo dos meses concluídos e o que fazer com o empenho.' }}</small></div>
          @if (contrato()) { <button type="button" class="acao-secundaria acao-pequena" (click)="verNotas.emit()">Ver Notas de Empenho</button> }
        </header>
        <div class="corpo">
          <div class="orcamento-remanescente" [class.negativo]="+d.remanescente < 0">
            <span>Saldo remanescente · {{ textoConcluidos() }}</span>
            <strong>{{ d.remanescente | moeda }}</strong>
            <small>previsto {{ d.previsto_concluido | moeda }} · pago (NF bruta) {{ d.pago_concluido | moeda }}{{ +d.remanescente < 0 ? ' · pago acima do previsto' : '' }}</small>
          </div>
          <ul class="orcamento-decisoes">
            <li><span class="selo-situacao" [class.alerta]="!coberturaTotal()">{{ coberturaTotal() ? 'Cobertura' : 'Cobertura parcial' }}</span>{{ textoCobertura() }}</li>
            <li>
              @if (+d.reforco > 0) {
                <span class="selo-situacao" [class.alerta]="!reforcoAtrasado()" [class.vermelho]="reforcoAtrasado()">Reforço</span>
                <span>Falta empenhar <strong>{{ d.reforco | moeda }}</strong>@if (pedirAte(); as ate) { · pedir até <strong>{{ ate | dataBr }}</strong>{{ reforcoAtrasado() ? ' (prazo vencido)' : '' }} }</span>
              } @else {
                <span class="selo-situacao">Reforço</span><span>Não precisa de reforço neste exercício.</span>
              }
            </li>
            <li><span class="selo-situacao" [class.inativo]="!(+d.disponivel_cancelar > 0)">Cancelar/transferir</span>
              <span>@if (+d.disponivel_cancelar > 0) { Pode cancelar ou transferir <strong>{{ d.disponivel_cancelar | moeda }}</strong> sem faltar para os meses restantes. } @else { Nada a cancelar: o saldo livre é todo necessário. }</span></li>
          </ul>
          @if (carteira(); as c) {
            @if (c.precisam_reforco.length || c.com_sobra.length) {
              <div class="orcamento-listas">
                @if (c.precisam_reforco.length) {
                  <div><h3>Precisam de reforço ({{ c.precisam_reforco.length }})</h3>
                    <ul>@for (l of c.precisam_reforco.slice(0, 6); track l.contrato_id) {
                      <li><a [routerLink]="['/contratos', l.contrato_id]">{{ l.rotulo }}</a><span>{{ l.reforco | moeda }}@if (l.pedir_reforco_ate) { · até {{ l.pedir_reforco_ate | dataBr }} }</span></li>
                    }</ul></div>
                }
                @if (c.com_sobra.length) {
                  <div><h3>Empenho sobrando ({{ c.com_sobra.length }})</h3>
                    <ul>@for (l of c.com_sobra.slice(0, 6); track l.contrato_id) {
                      <li><a [routerLink]="['/contratos', l.contrato_id]">{{ l.rotulo }}</a><span>{{ l.disponivel_cancelar | moeda }}</span></li>
                    }</ul></div>
                }
              </div>
            }
          }
        </div>
      </section>
    }
  `,
})
export class OrcamentoExecutivoComponent {
  readonly contrato = input<OrcamentoExecutivo | null>(null);
  readonly carteira = input<OrcamentoCarteira | null>(null);
  /** Data de hoje (AAAA-MM-DD), para saber se o prazo do reforço já passou. */
  readonly hoje = input<string>(new Date().toISOString().slice(0, 10));
  readonly verNotas = output<void>();

  protected readonly dados = computed(() => this.contrato() ?? this.carteira());
  protected readonly pedirAte = computed(() => this.contrato()?.pedir_reforco_ate ?? this.carteira()?.precisam_reforco[0]?.pedir_reforco_ate ?? null);
  protected readonly reforcoAtrasado = computed(() => !!this.pedirAte() && this.pedirAte()! < this.hoje());
  protected readonly coberturaTotal = computed(() => Number(this.dados()?.reforco ?? 0) <= 0);

  protected textoConcluidos(): string {
    const c = this.contrato();
    if (!c) return 'meses concluídos';
    const meses = c.meses_concluidos;
    if (!meses.length) return 'nenhum mês concluído ainda';
    return meses.length === 1 ? `mês concluído: ${mesAno(meses[0].competencia)}` : `meses concluídos: ${mesAno(meses[0].competencia)} a ${mesAno(meses[meses.length - 1].competencia)}`;
  }

  protected textoCobertura(): string {
    const c = this.contrato();
    const d = this.dados();
    if (!d) return '';
    if (!c) {
      return Number(d.reforco) > 0
        ? `Saldo livre de ${moeda(d.livre)} para ${moeda(d.necessidade)} previstos nos meses restantes.`
        : `O saldo livre (${moeda(d.livre)}) cobre os ${moeda(d.necessidade)} previstos nos meses restantes.`;
    }
    if (!c.meses_restantes) return 'Não há meses a empenhar no restante do exercício.';
    if (c.meses_cobertos === c.meses_restantes) return `O empenho cobre todo o exercício (até ${mesAno(c.coberto_ate)}).`;
    if (!c.meses_cobertos) return `O saldo livre não cobre nem ${mesAno(c.primeiro_descoberto)}.`;
    return `O empenho cobre até ${mesAno(c.coberto_ate)} (${c.meses_cobertos} de ${c.meses_restantes} meses).`;
  }
}

function moeda(valor: string): string {
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
