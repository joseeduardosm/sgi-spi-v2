// Criado por José Eduardo Santana Martins
// Este arquivo serve para o espaço de tarefas (minhas, equipe ou pessoa): carrega as tarefas, guarda filtros e visão na URL e alterna quadro, lista, calendário e pessoas.

import { DecimalPipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Params, Router, RouterLink } from '@angular/router';
import { combineLatest, debounceTime, Subject } from 'rxjs';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CalendarioTarefasComponent, Reprogramacao } from './calendario-tarefas.component';
import { EstadoTarefasService } from './estado-tarefas.service';
import { JanelaDetalheTarefaComponent } from './janela-detalhe-tarefa.component';
import { JanelaTarefaComponent, ModoJanela } from './janela-tarefa.component';
import { ListaTarefasComponent, OrdemLista } from './lista-tarefas.component';
import { MovimentoQuadro, QuadroTarefasComponent } from './quadro-tarefas.component';
import { Escopo, TarefasApiService } from './tarefas-api.service';
import {
  acaoEntre, corAvatar, iniciais, ListaTarefas, Marcador, Pessoa, PessoaCarga, prazoPadrao, PrioridadeTarefa, ROTULOS_PRIORIDADE, ROTULOS_STATUS, StatusTarefa,
  TarefaResumo,
} from './tarefas.models';

type Visao = 'quadro' | 'lista' | 'calendario' | 'pessoas';
/** Recortes rápidos (linha de resumo e filtros): cada um vira um filtro na URL (`recorte`). */
type Recorte = '' | 'atrasadas' | 'hoje' | 'semana' | 'criticas' | 'validacao';

const ROTULOS_RECORTE: Record<Exclude<Recorte, ''>, string> = {
  atrasadas: 'Atrasadas', hoje: 'Vencem hoje', semana: 'Vencem nesta semana', criticas: 'Prioridade crítica', validacao: 'Em validação',
};
/** Quantos segundos o cartão recém-criado fica destacado. */
const SEGUNDOS_DESTAQUE = 4;

/**
 * Tela de trabalho do módulo, como um quadro do Trello:
 * - cabeçalho: título, visões (Quadro | Lista | Calendário | Pessoas), avatares que filtram por pessoa,
 *   busca, filtros e a linha de resumo (em aberto, atrasadas, vencem hoje…), tudo guardado na URL;
 * - a tarefa abre numa janela por cima (`?tarefa=123`), sem sair do quadro.
 */
@Component({
  selector: 'app-espaco-tarefas',
  imports: [
    FormsModule, RouterLink, DecimalPipe, QuadroTarefasComponent, ListaTarefasComponent, CalendarioTarefasComponent,
    JanelaDetalheTarefaComponent, JanelaTarefaComponent,
  ],
  templateUrl: './espaco-tarefas.component.html',
  // Clique fora do popover de filtros o fecha
  host: { '(document:click)': 'filtrosAbertos.set(false)' },
})
export class EspacoTarefasComponent implements OnInit {
  private readonly api = inject(TarefasApiService);
  private readonly estado = inject(EstadoTarefasService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly destruir = inject(DestroyRef);

  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly rotulosRecorte = ROTULOS_RECORTE;
  protected readonly prioridades: PrioridadeTarefa[] = ['critica', 'alta', 'normal', 'baixa'];
  protected readonly corAvatar = corAvatar;
  protected readonly iniciais = iniciais;

  protected readonly escopo = signal<Escopo>({ tipo: 'minhas' });
  protected readonly dados = signal<ListaTarefas | null>(null);
  protected readonly carregando = signal(true);

  // --- Estado vindo da URL ----------------------------------------------------------------------------
  protected readonly visao = signal<Visao>('quadro');
  protected readonly busca = signal('');
  protected readonly prioridade = signal<PrioridadeTarefa | ''>('');
  protected readonly marcador = signal('');
  /** Pessoas escolhidas nos avatares (ids). */
  protected readonly pessoasFiltro = signal<number[]>([]);
  protected readonly recorte = signal<Recorte>('');
  protected readonly raias = signal(false);
  protected readonly ordem = signal<OrdemLista>('manual');
  /** Número da tarefa aberta na janela. */
  protected readonly tarefaAberta = signal<number | null>(null);
  private readonly digitacao = new Subject<string>();

  // --- Estado da tela ---------------------------------------------------------------------------------
  protected readonly filtrosAbertos = signal(false);
  protected readonly destacado = signal<number | null>(null);
  protected readonly modoJanela = signal<ModoJanela | null>(null);
  protected readonly tarefaJanela = signal<TarefaResumo | null>(null);
  protected readonly prazoSugerido = signal<Date | null>(null);

  protected readonly titulo = computed(() => this.dados()?.contexto.titulo ?? (this.escopo().tipo === 'minhas' ? 'Minhas tarefas' : 'Tarefas'));
  protected readonly lider = computed(() => !!this.dados()?.contexto.lider);
  /** Equipe do escopo (para "Configurar" e para a criação rápida). */
  protected readonly equipe = computed(() => this.estado.equipes().find((e) => e.id === this.escopo().equipeId) ?? null);
  /** Criação rápida: em Minhas (tarefa pessoal) e na equipe; na tela de outra pessoa, não. */
  protected readonly podeCriar = computed(() => this.escopo().tipo !== 'pessoa');

  /** Pessoas envolvidas nas tarefas do escopo (avatares do filtro), da que tem mais tarefas para a que tem menos. */
  protected readonly pessoasDoEscopo = computed(() => {
    const contagem = new Map<number, { pessoa: Pessoa; total: number }>();
    for (const t of this.dados()?.itens ?? []) {
      for (const p of t.envolvidos) contagem.set(p.id, { pessoa: p, total: (contagem.get(p.id)?.total ?? 0) + 1 });
    }
    return [...contagem.values()].sort((a, b) => b.total - a.total || a.pessoa.nome.localeCompare(b.pessoa.nome)).map((c) => c.pessoa);
  });

  /** Marcadores presentes nas tarefas (opções do filtro). */
  protected readonly marcadoresDisponiveis = computed(() => {
    const mapa = new Map<string, Marcador>();
    for (const t of this.dados()?.itens ?? []) for (const m of t.marcadores) mapa.set(m.id, m);
    return [...mapa.values()].sort((a, b) => a.nome.localeCompare(b.nome));
  });

  /** Tarefas depois de todos os filtros (as visões recebem esta lista). */
  protected readonly filtradas = computed(() => {
    const termo = this.busca().trim().toLowerCase();
    const pessoas = new Set(this.pessoasFiltro());
    const agora = new Date();
    const hoje = agora.toDateString();
    const fimSemana = new Date(agora.getFullYear(), agora.getMonth(), agora.getDate() + (7 - agora.getDay()));
    const r = this.recorte();
    return (this.dados()?.itens ?? []).filter((t) => {
      const aberta = t.status !== 'concluida';
      return (!this.prioridade() || t.prioridade === this.prioridade())
        && (!this.marcador() || t.marcadores.some((m) => m.id === this.marcador()))
        && (!pessoas.size || t.envolvidos.some((p) => pessoas.has(p.id)))
        && (r !== 'atrasadas' || (t.atrasada && aberta))
        && (r !== 'hoje' || (aberta && new Date(t.prazo).toDateString() === hoje))
        && (r !== 'semana' || (aberta && new Date(t.prazo) < fimSemana))
        && (r !== 'criticas' || (aberta && t.prioridade === 'critica'))
        && (r !== 'validacao' || t.status === 'em_validacao')
        && (!termo || t.titulo.toLowerCase().includes(termo) || String(t.numero) === termo.replace('#', '')
          || t.envolvidos.some((p) => p.nome.toLowerCase().includes(termo)));
    });
  });

  /** Filtros ativos (chips removíveis). */
  protected readonly chips = computed(() => {
    const lista: { rotulo: string; limpar: Params }[] = [];
    const r = this.recorte();
    if (r) lista.push({ rotulo: ROTULOS_RECORTE[r], limpar: { recorte: null } });
    if (this.prioridade()) lista.push({ rotulo: `Prioridade: ${ROTULOS_PRIORIDADE[this.prioridade() as PrioridadeTarefa]}`, limpar: { prioridade: null } });
    const m = this.marcadoresDisponiveis().find((x) => x.id === this.marcador());
    if (this.marcador()) lista.push({ rotulo: `Marcador: ${m?.nome ?? '…'}`, limpar: { marcador: null } });
    for (const id of this.pessoasFiltro()) {
      const p = this.pessoasDoEscopo().find((x) => x.id === id);
      lista.push({ rotulo: `Pessoa: ${p?.nome ?? '…'}`, limpar: { pessoas: this.textoPessoas(this.pessoasFiltro().filter((x) => x !== id)) } });
    }
    if (this.busca()) lista.push({ rotulo: `Busca: "${this.busca()}"`, limpar: { busca: null } });
    return lista;
  });

  ngOnInit(): void {
    // Escopo pela rota (minhas, equipe ou pessoa)
    combineLatest([this.rota.paramMap, this.rota.data]).pipe(takeUntilDestroyed(this.destruir)).subscribe(([p, d]) => {
      this.escopo.set({ tipo: (d['escopo'] ?? 'minhas') as Escopo['tipo'], equipeId: p.get('equipeId'), login: p.get('login') });
      this.dados.set(null);
      this.pessoasCarga.set([]);
      this.carregar();
    });
    // Visão e filtros pela query string
    this.rota.queryParamMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((q) => {
      const visao = q.get('visao');
      this.visao.set(visao === 'lista' || visao === 'calendario' || visao === 'pessoas' ? visao : 'quadro');
      this.busca.set(q.get('busca') ?? '');
      this.prioridade.set((q.get('prioridade') ?? '') as PrioridadeTarefa | '');
      this.marcador.set(q.get('marcador') ?? '');
      this.pessoasFiltro.set((q.get('pessoas') ?? '').split(',').filter(Boolean).map(Number));
      this.recorte.set((q.get('recorte') ?? '') as Recorte);
      this.raias.set(q.get('raias') === 'pessoa');
      this.ordem.set((q.get('ordem') ?? 'manual') as OrdemLista);
      this.tarefaAberta.set(q.get('tarefa') ? Number(q.get('tarefa')) : null);
      if (this.visao() === 'pessoas' || this.raias()) this.carregarPessoas();
    });
    // Busca com atraso: a URL muda 300 ms depois da última tecla
    this.digitacao.pipe(debounceTime(300), takeUntilDestroyed(this.destruir)).subscribe((b) => this.navegar({ busca: b.trim() || null }));
  }

  // --- Carga ------------------------------------------------------------------------------------------

  /** Busca as tarefas do escopo. `silenciosa`: sem o "Carregando…" (depois de uma ação). */
  protected carregar(silenciosa = false): void {
    if (!silenciosa) this.carregando.set(true);
    const vazio = { status: [], prioridade: '' as const, marcador_id: '', responsavel_id: null, busca: '' };
    this.api.listar(this.escopo(), vazio).subscribe({
      next: (d) => { this.dados.set(d); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar as tarefas'); },
    });
  }

  /** Carga de cada pessoa da equipe (visão Pessoas e cabeçalho das raias). */
  protected readonly pessoasCarga = signal<PessoaCarga[]>([]);
  private carregarPessoas(): void {
    const id = this.escopo().equipeId;
    if (this.escopo().tipo !== 'equipe' || !id || this.pessoasCarga().length) return;
    this.api.pessoas(id).subscribe({ next: (l) => this.pessoasCarga.set(l), error: () => undefined });
  }

  /** Maior total de tarefas entre as pessoas (escala das barras empilhadas da visão Pessoas). */
  protected readonly maiorTotal = computed(() => Math.max(1, ...this.pessoasCarga().map((p) => {
    const e = p.na_equipe;
    return e ? e.a_fazer + e.em_andamento + e.em_validacao + e.concluidas : 0;
  })));

  protected largura(valor: number): number {
    return (valor / this.maiorTotal()) * 100;
  }

  // --- URL ----------------------------------------------------------------------------------------------

  /** Grava visão e filtros na URL (recarregar a página mantém o estado). */
  protected navegar(params: Params): void {
    void this.roteador.navigate([], { relativeTo: this.rota, queryParams: params, queryParamsHandling: 'merge', replaceUrl: true });
  }

  protected digitar(valor: string): void {
    this.digitacao.next(valor);
  }

  protected trocarVisao(visao: Visao): void {
    this.navegar({ visao: visao === 'quadro' ? null : visao });
  }

  /** Avatar do filtro: clique escolhe só a pessoa; com Shift (ou Ctrl), soma ou tira da seleção. */
  protected alternarPessoa(evento: MouseEvent, id: number): void {
    const atual = this.pessoasFiltro();
    const acumular = evento.shiftKey || evento.ctrlKey || evento.metaKey;
    let novo: number[];
    if (acumular) novo = atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id];
    else novo = atual.length === 1 && atual[0] === id ? [] : [id];
    this.navegar({ pessoas: this.textoPessoas(novo) });
  }

  private textoPessoas(ids: number[]): string | null {
    return ids.length ? ids.join(',') : null;
  }

  protected aplicarRecorte(r: Recorte): void {
    this.navegar({ recorte: this.recorte() === r ? null : r || null });
  }

  protected limparFiltros(): void {
    this.navegar({ recorte: null, prioridade: null, marcador: null, pessoas: null, busca: null });
  }

  // --- Janela da tarefa (?tarefa=123) -------------------------------------------------------------------

  protected abrirTarefa(numero: number): void {
    // Sem replaceUrl: o "voltar" do navegador fecha a janela
    void this.roteador.navigate([], { relativeTo: this.rota, queryParams: { tarefa: numero }, queryParamsHandling: 'merge' });
  }

  protected fecharTarefa(): void {
    this.navegar({ tarefa: null });
  }

  // --- Ações vindas das visões ----------------------------------------------------------------------------

  /** Quadro: arraste ou menu "⋯". Devolver e reabrir pedem o motivo; entregar sem equipe conclui. */
  protected mover(m: MovimentoQuadro): void {
    const { tarefa: t, para } = m;
    const acao = acaoEntre(t.status, para, !t.equipe);
    if (!acao) {
      this.dialogos.avisar('Movimento não permitido', `Não é possível ir de "${ROTULOS_STATUS[t.status]}" para "${ROTULOS_STATUS[para]}". `
        + 'Siga o caminho A fazer → Em andamento → Em validação → Concluída.');
      return;
    }
    if (acao === 'devolver' || acao === 'reabrir') {
      this.prazoSugerido.set(null);
      this.tarefaJanela.set(t);
      this.modoJanela.set(acao);
      return;
    }
    // Movimento otimista: o cartão muda de coluna na hora e volta se a API recusar
    const anterior = t.status;
    this.trocarStatus(t.numero, acao === 'entregar' && !t.equipe ? 'concluida' : para);
    this.api.mover(t.numero, acao).subscribe({
      next: () => this.carregar(true),
      error: (e) => { this.trocarStatus(t.numero, anterior); this.dialogos.mostrarErro(e, 'Movimento não realizado'); },
    });
  }

  private trocarStatus(numero: number, status: StatusTarefa): void {
    this.dados.update((d) => d && { ...d, itens: d.itens.map((t) => (t.numero === numero ? { ...t, status } : t)) });
  }

  /** Criação rápida (só o título): você como responsável, prioridade normal, prazo em 7 dias às 18:00. */
  protected criarRapida(titulo: string): void {
    const escopo = this.escopo();
    this.api.criar({
      titulo, descricao: '', prazo: prazoPadrao().toISOString(), prioridade: 'normal',
      equipe_id: escopo.tipo === 'equipe' ? escopo.equipeId ?? null : null, responsavel_id: null, participantes_ids: [], marcadores_ids: [],
    }).subscribe({
      next: (t) => {
        this.destacado.set(t.numero);
        setTimeout(() => { if (this.destacado() === t.numero) this.destacado.set(null); }, SEGUNDOS_DESTAQUE * 1000);
        this.carregar(true);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a tarefa'),
    });
  }

  /** Lista: nova ordem manual (aplica na tela e grava). */
  protected reordenar(numeros: number[]): void {
    this.dados.update((d) => d && { ...d, itens: d.itens.map((t) => {
      const i = numeros.indexOf(t.numero);
      return i < 0 ? t : { ...t, ordem: i };
    }) });
    this.api.ordenar(numeros).subscribe({ error: (e) => { this.dialogos.mostrarErro(e); this.carregar(true); } });
  }

  /** Calendário: tarefa solta em outro dia → janela "Alterar prazo" com o dia novo e o mesmo horário. */
  protected reprogramar(r: Reprogramacao): void {
    const antigo = new Date(r.tarefa.prazo);
    const novo = new Date(r.dia.getFullYear(), r.dia.getMonth(), r.dia.getDate(), antigo.getHours(), antigo.getMinutes());
    this.prazoSugerido.set(novo);
    this.tarefaJanela.set(r.tarefa);
    this.modoJanela.set('prazo');
  }

  // --- Relatório ------------------------------------------------------------------------------------------

  protected readonly relatorioAberto = signal(false);
  protected relatorio = { de: '', ate: '', marcador: '', formato: 'xlsx' as 'xlsx' | 'pdf' };

  protected abrirRelatorio(): void {
    const hoje = new Date();
    const z = (n: number) => String(n).padStart(2, '0');
    const texto = (d: Date) => `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
    this.relatorio = { de: texto(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), ate: texto(hoje), marcador: this.marcador(), formato: 'xlsx' };
    this.relatorioAberto.set(true);
  }

  protected gerarRelatorio(): void {
    const r = this.relatorio;
    this.dialogos.executar(this.api.relatorio(this.escopo(), r.formato, r.de, r.ate, r.marcador), 'Gerando o relatório…').subscribe({
      next: () => this.relatorioAberto.set(false),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório'),
    });
  }
}
