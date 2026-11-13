/**
 * =============================================================================
 * ARQUIVO: calendario-vencimentos.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Tela "Calendário de vencimentos" do módulo Contratos: reúne num só
 * calendário vigência, reajuste, pagamento e prazo da NF, validade de
 * documentos, medição atrasada, empenho insuficiente e tarefas dos contratos.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template embutido sobre o componente genérico
 * app-calendario-eventos. O calendário avisa o período visível (mês ou semana)
 * e a tela busca na API só os eventos desse intervalo, com filtros "só meus
 * contratos" e tipos de evento (chips). Um contador de pedidos descarta
 * respostas atrasadas. Exporta TIPOS_VENCIMENTO para legenda e filtros.
 *
 * FINALIDADE DE NEGÓCIO:
 * Dá ao gestor e ao fiscal uma visão de prazos: o que vence nos próximos dias
 * (cor de severidade), evitando perder vigência, reajuste ou pagamento de nota
 * fiscal. NF é a nota fiscal da empresa; empenho é a reserva orçamentária que
 * garante o pagamento; medição é a apuração mensal do serviço executado.
 *
 * CONTEXTO NO SISTEMA:
 * Rota do módulo Contratos. Usa ContratosApiService.calendario, os tipos
 * EventoVencimento e TipoEventoCalendario de contratos.models e o
 * CalendarioEventosComponent compartilhado. Clicar num evento navega para a
 * rota que a própria API informa (evento.rota).
 *
 * =============================================================================
 */

import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { CalendarioEventosComponent, EventoCalendarioGenerico, PeriodoCalendario } from '../../../shared/componentes/calendario-eventos/calendario-eventos.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { EventoVencimento, TipoEventoCalendario } from '../compartilhado/contratos.models';

import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
/** Tipos de evento e o texto de cada um (a legenda e o filtro usam esta lista). */
export const TIPOS_VENCIMENTO: { tipo: TipoEventoCalendario; rotulo: string }[] = [
  { tipo: 'vigencia_fim', rotulo: 'Fim da vigência' },
  { tipo: 'vigencia_maxima', rotulo: 'Vigência máxima' },
  { tipo: 'reajuste', rotulo: 'Reajuste' },
  { tipo: 'pagamento_nf', rotulo: 'Pagamento da NF' },
  { tipo: 'prazo_nf_48h', rotulo: 'Prazo da NF (contestação)' },
  { tipo: 'validade_documento', rotulo: 'Validade de documentos' },
  { tipo: 'medicao_atrasada', rotulo: 'Medição atrasada' },
  { tipo: 'empenho_insuficiente', rotulo: 'Empenho insuficiente' },
  { tipo: 'tarefa_contrato', rotulo: 'Tarefas dos contratos' },
];

/** Calendário de vencimentos dos contratos: o período vem do calendário (mês ou semana) e os dados são buscados só para ele. */
@Component({
  selector: 'app-calendario-vencimentos',
  imports: [EsqueletoComponent, FormsModule, CabecalhoModuloComponent, CalendarioEventosComponent],
  template: `
    <app-cabecalho-modulo titulo="Calendário de vencimentos" [trilha]="['Calendário de vencimentos']"
                          descricao="Vigência, reajuste, pagamento e prazo da nota fiscal, validade de documentos, empenho e tarefas dos contratos." />

    <form class="filtros-gestao painel-gestao" style="margin-bottom: 12px; border-bottom: 0" (submit)="$event.preventDefault()">
      <label class="opcao-meus"><input type="checkbox" name="meus" [ngModel]="meus()" (ngModelChange)="mudarMeus($event)" /> Só meus contratos</label>
      <div class="chips-tipos" role="group" aria-label="Tipos de vencimento">
        @for (t of tipos; track t.tipo) {
          <button type="button" class="chip-tipo" [class.ativo]="escolhidos().has(t.tipo)" [attr.aria-pressed]="escolhidos().has(t.tipo)" (click)="alternar(t.tipo)">{{ t.rotulo }}</button>
        }
        @if (escolhidos().size) { <button type="button" class="link-simples" (click)="limpar()">Todos os tipos</button> }
      </div>
    </form>

    <app-calendario-eventos [eventos]="eventosGenericos()" (periodoMudou)="periodo.set($event); carregar()" (abrir)="abrir($event)" />
    <p class="dica-formulario">
      <span class="legenda-evento" data-severidade="alta"></span> vencido ou em até 30 dias ·
      <span class="legenda-evento" data-severidade="media"></span> 31 a 60 dias ou perto ·
      <span class="legenda-evento" data-severidade="info"></span> informativo.
      @if (carregando()) { <app-esqueleto tipo="lista" [linhas]="3" /> } @else { {{ eventos().length + ' evento(s) no período.' }} }
    </p>
  `,
})
export class CalendarioVencimentosComponent {
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  protected readonly tipos = TIPOS_VENCIMENTO;
  protected readonly meus = signal(false);
  protected readonly escolhidos = signal<ReadonlySet<TipoEventoCalendario>>(new Set());
  protected readonly periodo = signal<PeriodoCalendario | null>(null);
  protected readonly eventos = signal<EventoVencimento[]>([]);
  protected readonly carregando = signal(false);
  /** Pedido em andamento: resposta de um período já trocado é descartada. */
  private pedido = 0;

  /** Eventos no formato do calendário genérico (o rótulo leva o número do contrato). */
  protected readonly eventosGenericos = computed<EventoCalendarioGenerico[]>(() => this.eventos().map((e) => ({
    data: e.data, hora: e.hora, rotulo: `${e.contrato_numero} · ${e.rotulo}`, detalhe: e.contrato_apelido, severidade: e.severidade,
  })));

  /** Liga ou desliga o filtro "Só meus contratos" e recarrega o período. */
  protected mudarMeus(valor: boolean): void {
    this.meus.set(valor);
    this.carregar();
  }

  /**
   * Marca ou desmarca um tipo de evento no filtro. Um novo Set é criado (em vez
   * de alterar o atual) para que o signal perceba a mudança e redesenhe os chips.
   * `delete` devolve false quando o tipo não estava marcado; aí ele é adicionado.
   */
  protected alternar(tipo: TipoEventoCalendario): void {
    const novo = new Set(this.escolhidos());
    if (!novo.delete(tipo)) novo.add(tipo);
    this.escolhidos.set(novo);
    this.carregar();
  }

  /** Remove todos os tipos escolhidos (sem filtro = todos os tipos) e recarrega. */
  protected limpar(): void {
    this.escolhidos.set(new Set());
    this.carregar();
  }

  /**
   * Busca os eventos do período visível com os filtros atuais.
   * Cada chamada ganha um número; se o usuário trocar de mês antes da resposta
   * chegar, a resposta antiga é ignorada (evita mostrar o mês errado).
   * Sem período ainda (o calendário não avisou), não faz nada.
   */
  protected carregar(): void {
    const periodo = this.periodo();
    if (!periodo) return;
    const numero = ++this.pedido;
    this.carregando.set(true);
    this.api.calendario(periodo.de, periodo.ate, this.meus(), [...this.escolhidos()]).subscribe({
      next: (r) => {
        if (numero !== this.pedido) return;
        this.eventos.set(r.eventos);
        this.carregando.set(false);
      },
      error: (e) => {
        if (numero !== this.pedido) return;
        this.carregando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível carregar o calendário de vencimentos');
      },
    });
  }

  /** Abre a tela ligada ao evento clicado (o índice vem do calendário genérico). */
  protected abrir(indice: number): void {
    const evento = this.eventos()[indice];
    if (evento) void this.roteador.navigateByUrl(evento.rota);
  }
}
