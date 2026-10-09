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
import { DesempenhoTarefasComponent } from './desempenho-tarefas.component';
import { FaixaEquipeComponent } from './faixa-equipe.component';
import { JanelaTarefaComponent, ModoJanela } from './janela-tarefa.component';
import { ListaTarefasComponent, OrdemLista, SentidoOrdem } from './lista-tarefas.component';
import { MovimentoQuadro, QuadroTarefasComponent } from './quadro-tarefas.component';
import { Escopo, TarefasApiService } from './tarefas-api.service';
import {
  acaoEntre, corAvatar, Estagio, iniciais, ListaTarefas, Marcador, Pessoa, PessoaCarga, prazoPadrao, PrioridadeTarefa, ROTULOS_PRIORIDADE, ROTULOS_STATUS, StatusTarefa,
  TarefaResumo,
} from './tarefas.models';

type Visao = 'quadro' | 'lista' | 'calendario' | 'pessoas' | 'desempenho';
/** Recortes rápidos (linha de resumo e filtros): cada um vira um filtro na URL (`recorte`). */
type Recorte = '' | 'atrasadas' | 'hoje' | 'semana' | 'criticas' | 'validacao';

const ROTULOS_RECORTE: Record<Exclude<Recorte, ''>, string> = {
  atrasadas: 'Atrasadas', hoje: 'Vencem hoje', semana: 'Vencem nesta semana', criticas: 'Prioridade crítica', validacao: 'Em validação',
};
/** Quantos segundos o cartão recém-criado fica destacado. */
const SEGUNDOS_DESTAQUE = 4;
/** Chave (localStorage) da preferência pelo modo tela cheia. */
const CHAVE_TELA_CHEIA = 'tarefas.espaco.tela-cheia';

/**
 * Tela de trabalho do módulo, como um quadro do Trello:
 * - cabeçalho: título, visões (Quadro | Lista | Calendário | Pessoas), avatares que filtram por pessoa,
 *   busca, filtros e a linha de resumo (em aberto, atrasadas, vencem hoje…), tudo guardado na URL;
 * - a tarefa abre na tela própria (`/tarefas/123`).
 */
@Component({
  selector: 'app-espaco-tarefas',
  imports: [
    FormsModule, RouterLink, DecimalPipe, QuadroTarefasComponent, ListaTarefasComponent, CalendarioTarefasComponent,
    JanelaTarefaComponent, DesempenhoTarefasComponent, FaixaEquipeComponent,
  ],
  templateUrl: './espaco-tarefas.component.html',
  // Clique fora do popover de filtros o fecha
  host: {
    '(document:click)': 'filtrosAbertos.set(false)',
    '(document:fullscreenchange)': 'aoMudarFullscreen()',
    '(document:keydown)': 'aoTeclar($event)',
    '[class.tela-cheia]': 'telaCheia()',
    '[class.visao-quadro]': "visao() === 'quadro'",
  },
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
  /** Marco (milestone) usado como filtro. */
  protected readonly marco = signal('');
  /** Pessoas escolhidas nos avatares (ids). */
  protected readonly pessoasFiltro = signal<number[]>([]);
  protected readonly recorte = signal<Recorte>('');
  protected readonly raias = signal(false);
  protected readonly ordem = signal<OrdemLista>('manual');
  protected readonly sentido = signal<SentidoOrdem>('asc');
  /** Número da tarefa aberta na janela. */
  private readonly digitacao = new Subject<string>();

  // --- Estado da tela ---------------------------------------------------------------------------------
  protected readonly filtrosAbertos = signal(false);
  /** Modo tela cheia: o espaço cobre o portal (e pede o fullscreen do navegador) para usar o máximo da tela. */
  protected readonly telaCheia = signal(lerTelaCheia());
  /** O fullscreen do navegador foi entrado por este espaço (para sair dele junto com a tela cheia). */
  private pediuFullscreen = false;
  protected readonly destacado = signal<number | null>(null);
  protected readonly modoJanela = signal<ModoJanela | null>(null);
  protected readonly tarefaJanela = signal<TarefaResumo | null>(null);
  protected readonly prazoSugerido = signal<Date | null>(null);

  protected readonly titulo = computed(() => this.dados()?.contexto.titulo ?? (this.escopo().tipo === 'minhas' ? 'Minhas tarefas' : 'Tarefas'));
  protected readonly lider = computed(() => !!this.dados()?.contexto.lider);
  /** Pessoa do contexto (Minhas tarefas = eu; tela de pessoa = ela), para o Desempenho individual. */
  protected readonly pessoaDoEscopo = computed(() => this.dados()?.contexto.pessoa_id ?? null);
  /** Equipe do escopo (para "Configurar" e para a criação rápida). */
  protected readonly equipe = computed(() => this.estado.equipes().find((e) => e.id === this.escopo().equipeId) ?? null);
  /** Criação rápida: em Minhas (tarefa pessoal) e na equipe; na tela de outra pessoa, não. */
  protected readonly podeCriar = computed(() => this.escopo().tipo !== 'pessoa');

  /** Pessoas envolvidas nas tarefas do escopo (avatares do filtro), da que tem mais tarefas para a que tem menos. */
  protected readonly pessoasDoEscopo = computed(() => {
    const contagem = new Map<number, { pessoa: Pessoa; total: number }>();
    for (const t of this.dados()?.itens ?? []) {
      for (const p of t.responsaveis) contagem.set(p.id, { pessoa: p, total: (contagem.get(p.id)?.total ?? 0) + 1 });
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
        && (!this.marco() || t.marco_id === this.marco())
        && (!pessoas.size || t.responsaveis.some((p) => pessoas.has(p.id)))
        && (r !== 'atrasadas' || (t.atrasada && aberta))
        && (r !== 'hoje' || (aberta && new Date(t.prazo).toDateString() === hoje))
        && (r !== 'semana' || (aberta && new Date(t.prazo) < fimSemana))
        && (r !== 'criticas' || (aberta && t.prioridade === 'critica'))
        && (r !== 'validacao' || t.status === 'em_validacao')
        && (!termo || t.titulo.toLowerCase().includes(termo) || String(t.numero) === termo.replace('#', '')
          || t.responsaveis.some((p) => p.nome.toLowerCase().includes(termo)));
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
    if (this.marco()) lista.push({ rotulo: 'Marco', limpar: { marco: null } });
    for (const id of this.pessoasFiltro()) {
      const p = this.pessoasDoEscopo().find((x) => x.id === id);
      lista.push({ rotulo: `Pessoa: ${p?.nome ?? '…'}`, limpar: { pessoas: this.textoPessoas(this.pessoasFiltro().filter((x) => x !== id)) } });
    }
    if (this.busca()) lista.push({ rotulo: `Busca: "${this.busca()}"`, limpar: { busca: null } });
    return lista;
  });

  /** Entra ou sai da tela cheia; entrando, também pede o fullscreen do navegador (se negado, o espaço só cobre o portal). */
  protected alternarTelaCheia(): void {
    const ligar = !this.telaCheia();
    this.telaCheia.set(ligar);
    try {
      localStorage.setItem(CHAVE_TELA_CHEIA, ligar ? '1' : '0');
    } catch {
      // Navegador sem armazenamento: a preferência só vale nesta visita
    }
    if (ligar) document.documentElement.requestFullscreen?.().catch(() => undefined);
    else if (document.fullscreenElement) document.exitFullscreen?.().catch(() => undefined);
  }

  /** O navegador saiu do fullscreen (ex.: Esc): o modo tela cheia sai junto. */
  protected aoMudarFullscreen(): void {
    if (!document.fullscreenElement && this.telaCheia() && this.pediuFullscreen) this.alternarTelaCheia();
    this.pediuFullscreen = !!document.fullscreenElement;
  }

  /** Esc sai da tela cheia (sem atrapalhar quem está digitando ou com janela aberta); F alterna fora dos campos de texto. */
  protected aoTeclar(evento: KeyboardEvent): void {
    const alvo = evento.target as HTMLElement | null;
    const digitando = !!alvo && (['INPUT', 'TEXTAREA', 'SELECT'].includes(alvo.tagName) || alvo.isContentEditable);
    if (evento.key === 'Escape' && this.telaCheia() && !this.modoJanela() && !this.relatorioAberto() && !digitando) this.alternarTelaCheia();
    else if ((evento.key === 'f' || evento.key === 'F') && !digitando && !evento.ctrlKey && !evento.metaKey && !evento.altKey) this.alternarTelaCheia();
  }

  ngOnInit(): void {
    // Saindo do espaço, o fullscreen do navegador que ele pediu também termina
    this.destruir.onDestroy(() => {
      if (document.fullscreenElement && this.pediuFullscreen) document.exitFullscreen?.().catch(() => undefined);
    });
    // Escopo pela rota (minhas, equipe ou pessoa)
    combineLatest([this.rota.paramMap, this.rota.data]).pipe(takeUntilDestroyed(this.destruir)).subscribe(([p, d]) => {
      this.escopo.set({ tipo: (d['escopo'] ?? 'minhas') as Escopo['tipo'], equipeId: p.get('equipeId'), login: p.get('login'), tarefa: Number(p.get('numero')) || null });
      this.dados.set(null);
      this.pessoasCarga.set([]);
      this.estagios.set([]);
      this.carregarEstagios();
      this.carregar();
    });
    // Visão e filtros pela query string
    this.rota.queryParamMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((q) => {
      const visao = q.get('visao');
      // O quadro de subtarefas só tem as visões quadro e lista
      const soBasicas = this.escopo().tipo === 'subtarefas';
      this.visao.set(visao === 'lista' || (!soBasicas && (visao === 'calendario' || visao === 'pessoas' || visao === 'desempenho')) ? visao : 'quadro');
      this.busca.set(q.get('busca') ?? '');
      this.prioridade.set((q.get('prioridade') ?? '') as PrioridadeTarefa | '');
      this.marcador.set(q.get('marcador') ?? '');
      this.marco.set(q.get('marco') ?? '');
      this.pessoasFiltro.set((q.get('pessoas') ?? '').split(',').filter(Boolean).map(Number));
      this.recorte.set((q.get('recorte') ?? '') as Recorte);
      this.raias.set(q.get('raias') === 'pessoa');
      this.ordem.set((q.get('ordem') ?? 'manual') as OrdemLista);
      this.sentido.set(q.get('sentido') === 'desc' ? 'desc' : 'asc');
      // Links antigos (?tarefa=123) seguem para a tela própria da tarefa
      if (Number(q.get('tarefa')) > 0) void this.roteador.navigate(['/tarefas', Number(q.get('tarefa'))], { replaceUrl: true });
      if (this.visao() === 'pessoas' || this.raias()) this.carregarPessoas();
    });
    this.iniciarAtualizacaoAutomatica();
    // Busca com atraso: a URL muda 300 ms depois da última tecla
    this.digitacao.pipe(debounceTime(300), takeUntilDestroyed(this.destruir)).subscribe((b) => this.navegar({ busca: b.trim() || null }));
  }

  // --- Atualização automática ---------------------------------------------------------------------------

  /** Tarefa sendo arrastada no quadro: a atualização espera o arraste terminar (trocar a lista no meio cancelaria o gesto). */
  private arrastandoCartao = false;
  private buscando = false;

  /**
   * Mantém a tela em dia sem recarregar a página: a cada 15 s (e ao voltar para a aba) busca as tarefas em silêncio, para que
   * tarefas criadas ou alteradas por outras pessoas apareçam sozinhas. Pausa com a aba escondida ou durante um arraste.
   */
  private iniciarAtualizacaoAutomatica(): void {
    const atualizar = () => {
      if (document.hidden || this.arrastandoCartao || this.buscando) return;
      this.buscando = true;
      this.carregar(true, () => (this.buscando = false));
    };
    const marcar = (valor: boolean) => () => (this.arrastandoCartao = valor);
    const iniciouArraste = marcar(true), terminouArraste = marcar(false);
    document.addEventListener('dragstart', iniciouArraste);
    document.addEventListener('dragend', terminouArraste);
    document.addEventListener('visibilitychange', atualizar);
    const intervalo = setInterval(atualizar, 15000);
    this.destruir.onDestroy(() => {
      clearInterval(intervalo);
      document.removeEventListener('dragstart', iniciouArraste);
      document.removeEventListener('dragend', terminouArraste);
      document.removeEventListener('visibilitychange', atualizar);
    });
  }

  // --- Carga ------------------------------------------------------------------------------------------

  /** Busca as tarefas do escopo. `silenciosa`: sem o "Carregando…" (depois de uma ação); `aoFim` roda ao terminar (com sucesso ou erro). */
  protected carregar(silenciosa = false, aoFim?: () => void): void {
    if (!silenciosa) this.carregando.set(true);
    const vazio = { status: [], prioridade: '' as const, marcador_id: '', responsavel_id: null, busca: '' };
    this.api.listar(this.escopo(), vazio).subscribe({
      next: (d) => {
        this.dados.set(d);
        this.carregando.set(false);
        // Subtarefas usam as colunas da equipe da tarefa-mãe (só se conhece a equipe depois da primeira carga)
        if (this.escopo().tipo === 'subtarefas' && d.contexto.equipe_id && !this.estagios().length) {
          this.api.estagios(d.contexto.equipe_id).subscribe({ next: (l) => this.estagios.set(l), error: () => this.estagios.set([]) });
        }
        aoFim?.();
      },
      // Na atualização automática um erro passageiro (rede, API reiniciando) não abre aviso: a próxima tentativa corrige
      error: (e) => { this.carregando.set(false); aoFim?.(); if (!aoFim) this.dialogos.mostrarErro(e, 'Não foi possível carregar as tarefas'); },
    });
  }

  /** Carga de cada pessoa da equipe (visão Pessoas e cabeçalho das raias). */
  protected readonly pessoasCarga = signal<PessoaCarga[]>([]);
  /** Colunas da equipe (estágios); vazio nas visões que não são de uma equipe. */
  protected readonly estagios = signal<Estagio[]>([]);
  private carregarEstagios(): void {
    const id = this.escopo().equipeId;
    if (this.escopo().tipo !== 'equipe' || !id) { this.estagios.set([]); return; }
    this.api.estagios(id).subscribe({ next: (l) => this.estagios.set(l), error: () => this.estagios.set([]) });
  }

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
    this.navegar({ recorte: null, prioridade: null, marcador: null, marco: null, pessoas: null, busca: null });
  }

  // --- Tela da tarefa (/tarefas/123) ---------------------------------------------------------------------

  protected abrirTarefa(numero: number): void {
    void this.roteador.navigate(['/tarefas', numero]);
  }

  // --- Ações vindas das visões ----------------------------------------------------------------------------

  /** Quadro: arraste ou menu "⋯". Devolver e reabrir pedem o motivo; entregar sem equipe conclui. */
  protected mover(m: MovimentoQuadro): void {
    const { tarefa: t, para, estagioId } = m;
    // Mesma situação, outra coluna: só troca o estágio
    if (para === t.status && estagioId) {
      const anteriorEstagio = t.estagio_id;
      this.dados.update((d) => d && { ...d, itens: d.itens.map((x) => (x.numero === t.numero ? { ...x, estagio_id: estagioId } : x)) });
      this.api.mudarEstagio(t.numero, estagioId).subscribe({
        next: () => this.carregar(true),
        error: (e) => {
          this.dados.update((d) => d && { ...d, itens: d.itens.map((x) => (x.numero === t.numero ? { ...x, estagio_id: anteriorEstagio } : x)) });
          this.dialogos.mostrarErro(e, 'Movimento não realizado');
        },
      });
      return;
    }
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
    this.api.mover(t.numero, acao, '', undefined, estagioId).subscribe({
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
    // No quadro de subtarefas, a criação rápida cria uma subtarefa da tarefa-mãe
    if (escopo.tipo === 'subtarefas' && escopo.tarefa) {
      this.api.criarSubtarefa(escopo.tarefa, { titulo }).subscribe({
        next: (t) => {
          this.destacado.set(t.numero);
          setTimeout(() => { if (this.destacado() === t.numero) this.destacado.set(null); }, SEGUNDOS_DESTAQUE * 1000);
          this.carregar(true);
        },
        error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a subtarefa'),
      });
      return;
    }
    this.api.criar({
      titulo, descricao: '', prazo: prazoPadrao().toISOString(), prioridade: 'normal',
      equipe_id: escopo.tipo === 'equipe' ? escopo.equipeId ?? null : null, responsaveis_ids: [], marcadores_ids: [],
    }).subscribe({
      next: (t) => {
        this.destacado.set(t.numero);
        setTimeout(() => { if (this.destacado() === t.numero) this.destacado.set(null); }, SEGUNDOS_DESTAQUE * 1000);
        this.carregar(true);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível criar a tarefa'),
    });
  }

  /** Lista: clique no título de uma coluna (crescente → decrescente → ordem manual). */
  protected ordenarPor(coluna: OrdemLista): void {
    if (this.ordem() !== coluna) this.navegar({ ordem: coluna, sentido: null });
    else if (this.sentido() === 'asc') this.navegar({ ordem: coluna, sentido: 'desc' });
    else this.navegar({ ordem: null, sentido: null });
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

/** Lê a preferência pelo modo tela cheia; sem armazenamento disponível, começa no modo normal. */
function lerTelaCheia(): boolean {
  try {
    return localStorage.getItem(CHAVE_TELA_CHEIA) === '1';
  } catch {
    return false;
  }
}
