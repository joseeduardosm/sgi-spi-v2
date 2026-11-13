/**
 * =============================================================================
 * ARQUIVO: ferias.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Tela do próprio servidor para agendar férias e licença-prêmio (LP) clicando
 * no primeiro e no último dia do período num calendário do exercício (ano).
 *
 * RESUMO TÉCNICO:
 * Componente standalone com signals: carrega "meus afastamentos" do exercício
 * (saldos, parâmetros da CGP, feriados e pedidos), monta os 12 meses da grade,
 * controla a seleção em dois cliques, pergunta o tipo num modal e chama a API
 * para agendar, alterar ou cancelar. O template fica em ferias.component.html.
 *
 * FINALIDADE DE NEGÓCIO:
 * Substitui o pedido em papel: o servidor vê o saldo, as datas vedadas e os
 * feriados, faz o pedido e acompanha o ciente do superior imediato e a
 * aprovação da CGP (Coordenação de Gestão de Pessoas) pela trilha de etapas.
 *
 * CONTEXTO NO SISTEMA:
 * Rota do Módulo RH (rh.routes.ts). Usa RhApiService (/api/rh), os tipos de
 * rh.models.ts, a trilha de trilha-afastamento.ts e o DialogosService para
 * avisos e confirmações. A aprovação acontece no painel-afastamentos.
 *
 * =============================================================================
 */

import { TrilhaEtapasComponent } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { trilhaAfastamento } from './trilha-afastamento';
import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhApiService } from './rh-api.service';
import { Afastamento, DIAS_SEMANA, Feriado, MeusAfastamentos, ROTULOS_STATUS, ROTULOS_TIPO, SIGLAS_TIPO, TipoAfastamento } from './rh.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/** Um dia do calendário (null = casa vazia antes do dia 1º). */
interface Dia {
  data: string;
  numero: number;
  semana: number;
}

/** AAAA-MM-DD sem fuso. */
function iso(ano: number, mes: number, dia: number): string {
  return `${ano}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
}

/** Converte "AAAA-MM-DD" em "DD/MM/AAAA" (só inverte as partes do texto, sem Date). */
function dataBr(texto: string): string {
  return texto.split('-').reverse().join('/');
}

/**
 * Férias e licença-prêmio do usuário: calendário mês a mês do exercício (ano civil). Clique no primeiro e no
 * último dia; o sistema pergunta "férias ou licença-prêmio?" e valida as regras da CGP e o saldo.
 */
@Component({
  selector: 'app-ferias',
  imports: [TrilhaEtapasComponent, EsqueletoComponent, LinkificarPipe, FormsModule, DatePipe, CabecalhoRhComponent],
  templateUrl: './ferias.component.html',
  host: { '(document:keydown.escape)': 'limparSelecao()' },
})
export class FeriasComponent implements OnInit {
  // inject() pede ao Angular a instância do serviço (injeção de dependência) sem precisar de construtor.
  protected readonly trilha = trilhaAfastamento;
  private readonly api = inject(RhApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tipos = ROTULOS_TIPO;
  protected readonly siglas = SIGLAS_TIPO;
  protected readonly status = ROTULOS_STATUS;
  protected readonly semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
  protected readonly nomesMeses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];

  protected exercicio = new Date().getFullYear();
  // signal() guarda um valor reativo: quando muda com set(), a tela que o lê é redesenhada.
  protected readonly dados = signal<MeusAfastamentos | null>(null);
  // Seleção: primeiro clique = início; segundo = fim (o intervalo é ordenado)
  protected readonly inicio = signal<string | null>(null);
  protected readonly fim = signal<string | null>(null);
  protected readonly passando = signal<string | null>(null);
  protected readonly perguntaTipo = signal(false);
  // Pedido em alteração (a nova seleção substitui as datas dele)
  protected readonly alterando = signal<Afastamento | null>(null);
  protected readonly hoje = iso(new Date().getFullYear(), new Date().getMonth() + 1, new Date().getDate());

  /**
   * Meses do exercício com as casas vazias do início (semana começando na segunda).
   * computed() é um signal derivado: recalcula sozinho quando os signals lidos dentro dele mudam.
   */
  protected readonly meses = computed(() => {
    const ano = this.dados()?.exercicio ?? this.exercicio;
    return Array.from({ length: 12 }, (_, m) => {
      const primeiro = new Date(Date.UTC(ano, m, 1));
      // getUTCDay() devolve 0 = domingo; somar 6 e tirar o resto por 7 faz a segunda virar 0 (coluna 1 da grade)
      const vazias = (primeiro.getUTCDay() + 6) % 7;
      const total = new Date(Date.UTC(ano, m + 1, 0)).getUTCDate();
      const dias: (Dia | null)[] = [...Array(vazias).fill(null)];
      for (let d = 1; d <= total; d++) dias.push({ data: iso(ano, m + 1, d), numero: d, semana: (vazias + d - 1) % 7 });
      return { nome: this.nomesMeses[m], dias };
    });
  });

  /** Afastamentos que aparecem no calendário (pendentes, aprovados e gozados), por dia. */
  private readonly porDia = computed(() => {
    const mapa = new Map<string, Afastamento>();
    for (const a of this.dados()?.afastamentos ?? []) {
      // Recusados e cancelados não ocupam o dia; o pedido em alteração some para que o usuário possa reaproveitar as datas dele
      if (!['pendente', 'aprovado', 'gozado'].includes(a.status) || a.id === this.alterando()?.id) continue;
      for (let d = new Date(`${a.inicio}T00:00:00Z`); d <= new Date(`${a.fim}T00:00:00Z`); d.setUTCDate(d.getUTCDate() + 1)) {
        mapa.set(d.toISOString().slice(0, 10), a);
      }
    }
    return mapa;
  });

  /** Feriados e pontos facultativos do exercício, por data. */
  private readonly feriadosPorDia = computed(() => new Map((this.dados()?.feriados ?? []).map((f) => [f.data, f] as [string, Feriado])));

  /** Feriado ou ponto facultativo da data (AAAA-MM-DD), se houver. */
  protected feriadoDo(dia: string): Feriado | undefined {
    return this.feriadosPorDia().get(dia);
  }

  ngOnInit(): void {
    this.carregar();
  }

  /**
   * Busca na API os saldos, parâmetros, feriados e pedidos do exercício escolhido.
   * subscribe() dispara a requisição HTTP (o Observable só executa quando alguém se inscreve).
   */
  protected carregar(): void {
    this.api.meus(this.exercicio).subscribe({
      next: (d) => this.dados.set(d),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar suas férias e licenças'),
    });
  }

  /** Vai para o ano anterior (-1) ou seguinte (+1), descartando a seleção em andamento. */
  protected mudarExercicio(delta: number): void {
    this.exercicio += delta;
    this.limparSelecao();
    this.carregar();
  }

  /** Pedido que ocupa a data no calendário (usado para colorir e bloquear o dia). */
  protected afastamentoDo(dia: string): Afastamento | undefined {
    return this.porDia().get(dia);
  }

  /** Intervalo selecionado (ou em seleção, acompanhando o mouse). */
  private intervalo(): [string, string] | null {
    const a = this.inicio();
    const b = this.fim() ?? this.passando();
    if (!a) return null;
    if (!b) return [a, a];
    return a <= b ? [a, b] : [b, a];
  }

  /** Indica se o dia está dentro do intervalo selecionado (pinta a seleção). */
  protected selecionado(dia: string): boolean {
    const i = this.intervalo();
    return !!i && dia >= i[0] && dia <= i[1];
  }

  /** Quantidade de dias corridos do intervalo, contando o primeiro e o último. */
  protected dias(): number {
    const i = this.intervalo();
    if (!i) return 0;
    return Math.round((Date.parse(`${i[1]}T00:00:00Z`) - Date.parse(`${i[0]}T00:00:00Z`)) / 86_400_000) + 1;
  }

  /** Texto do intervalo para o sobretítulo do modal, ex.: "01/07/2026 a 15/07/2026 (15 dias)". */
  protected textoIntervalo(): string {
    const i = this.intervalo();
    return i ? `${dataBr(i[0])} a ${dataBr(i[1])} (${this.dias()} dias)` : '';
  }

  /** Início vedado para algum tipo (só dica visual; a API confere). */
  protected inicioVedado(dia: Dia): boolean {
    const p = this.dados()?.parametros;
    if (p?.inicio_vedado_feriado && this.feriadoDo(dia.data)) return true;
    return !!p && p.inicio_vedado_ferias.includes(dia.semana) && p.inicio_vedado_lp.includes(dia.semana);
  }

  /**
   * Trata o clique num dia: o 1º clique marca o início; o 2º marca o fim (em qualquer ordem)
   * e abre a pergunta "férias ou licença-prêmio?". Dias ocupados ou passados são ignorados.
   */
  protected clicar(dia: Dia): void {
    if (this.afastamentoDo(dia.data) || dia.data < this.hoje) return;
    // Sem início, ou com um intervalo já completo: o clique recomeça a seleção
    if (!this.inicio() || this.fim()) {
      this.inicio.set(dia.data);
      this.fim.set(null);
      return;
    }
    const [a, b] = this.inicio()! <= dia.data ? [this.inicio()!, dia.data] : [dia.data, this.inicio()!];
    this.inicio.set(a);
    this.fim.set(b);
    this.perguntaTipo.set(true);
  }

  /** Desfaz a seleção e fecha o modal (também chamado pela tecla Esc, ver "host" acima). */
  protected limparSelecao(): void {
    this.inicio.set(null);
    this.fim.set(null);
    this.passando.set(null);
    this.perguntaTipo.set(false);
  }

  /**
   * "Deseja agendar férias ou licença-prêmio?" → envia (ou altera o pedido em alteração).
   * Efeito: cria um pedido novo (ou a alteração de um existente) na API; o backend valida as regras
   * e o saldo e manda e-mail ao superior imediato. Depois recarrega a tela.
   */
  protected agendar(tipo: TipoAfastamento): void {
    const [inicio, fim] = this.intervalo()!;
    const alterando = this.alterando();
    const chamada = alterando ? this.api.alterar(alterando.id, tipo, inicio, fim) : this.api.agendar(tipo, inicio, fim);
    this.perguntaTipo.set(false);
    this.dialogos.executar(chamada, alterando ? 'Enviando a alteração…' : 'Agendando…').subscribe({
      next: () => {
        this.dialogos.avisar(
          alterando ? 'Alteração enviada' : 'Pedido enviado',
          `${ROTULOS_TIPO[tipo]} de ${dataBr(inicio)} a ${dataBr(fim)} segue para o ciente e de acordo do seu superior imediato e, depois, para a aprovação (sem superior, vai direto à aprovação). Você receberá um e-mail a cada mudança de status.`,
        );
        this.alterando.set(null);
        this.limparSelecao();
        this.carregar();
      },
      error: (e) => {
        this.limparSelecao();
        this.dialogos.mostrarErro(e, 'Não foi possível agendar');
      },
    });
  }

  /** Entra no modo de alteração: a próxima seleção no calendário substitui as datas do pedido `a`. */
  protected iniciarAlteracao(a: Afastamento): void {
    this.alterando.set(a);
    this.limparSelecao();
    this.dialogos.avisar('Alterar período', 'Selecione no calendário o novo primeiro e o novo último dia. Uma alteração exige nova aprovação.');
  }

  /** Pede confirmação e cancela o pedido na API (sem justificativa, por isso o `null`). */
  protected async cancelar(a: Afastamento): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Cancelar este pedido?',
      mensagem: `${ROTULOS_TIPO[a.tipo]} de ${dataBr(a.inicio)} a ${dataBr(a.fim)} (${ROTULOS_STATUS[a.status].toLowerCase()}) será cancelado(a).`,
      rotuloConfirmar: 'Cancelar pedido',
    });
    if (!ok) return;
    this.dialogos.executar(this.api.cancelar(a.id, null), 'Cancelando…').subscribe({
      next: () => this.carregar(),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível cancelar'),
    });
  }

  /** A seleção começa no ano seguinte e o agendamento antecipado já abriu (vale o limite de dias, sem exigir saldo). */
  protected antecipadoDoPedido(d: MeusAfastamentos): boolean {
    const i = this.intervalo();
    const a = d.agendamento_antecipado;
    // Só vale o limite por ano para quem não tem o início do período informado; com ele, o saldo normal da janela já abate o pedido
    return !!i && !!a && a.inicio === null && a.aberto && Number(i[0].slice(0, 4)) === a.exercicio;
  }

  /** Saldo de férias do período em que a seleção começa: o vigente ou o próximo (ou o limite do ano seguinte, se aberto). */
  protected saldoFeriasDoPedido(d: MeusAfastamentos): number {
    const i = this.intervalo();
    if (this.antecipadoDoPedido(d)) return d.agendamento_antecipado!.limite_dias - d.agendamento_antecipado!.agendados;
    const pv = d.periodo_vigente;
    if (!pv) return 0;
    // Seleção que começa depois do fim do período vigente usa o saldo previsto do próximo período
    if (i && d.proximo_periodo && i[0] > pv.fim) return d.proximo_periodo.dias_creditados_previstos - d.proximo_periodo.usado;
    return pv.disponivel;
  }

  /** Atalho para o template formatar AAAA-MM-DD como DD/MM/AAAA. */
  protected data(texto: string): string {
    return dataBr(texto);
  }

  /** Lista os dias da semana vedados (0 = segunda) por extenso, ou "nenhum". */
  protected diasSemana(lista: number[]): string {
    return lista.length ? lista.map((d) => DIAS_SEMANA[d].toLowerCase()).join(', ') : 'nenhum';
  }
}
