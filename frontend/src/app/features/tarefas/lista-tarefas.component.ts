// Criado por José Eduardo Santana Martins
// Este arquivo serve para listar tarefas (minhas, da equipe ou da pessoa) em tabela ou Kanban, com filtros guardados na URL.

import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Params, Router, RouterLink } from '@angular/router';
import { combineLatest, debounceTime, Subject } from 'rxjs';

import { ItemTrilha } from '../../shared/componentes/trilha/trilha.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { JanelaTarefaComponent, ModoJanela } from './janela-tarefa.component';
import { Escopo, TarefasApiService } from './tarefas-api.service';
import {
  AcaoPipeline, ListaTarefas, Marcador, Pessoa, prazoRelativo, PrioridadeTarefa, ROTULOS_PRIORIDADE, ROTULOS_STATUS, STATUS, StatusTarefa, TarefaResumo,
} from './tarefas.models';

type Visao = 'tabela' | 'kanban';
type Recorte = '' | 'atrasadas' | 'hoje';
type Ordem = 'manual' | 'prazo' | 'prioridade';

const ABERTAS: StatusTarefa[] = ['a_fazer', 'em_andamento', 'em_validacao'];
const PESO_PRIORIDADE: Record<PrioridadeTarefa, number> = { critica: 0, alta: 1, normal: 2, baixa: 3 };

/**
 * Movimento no Kanban: ação do pipeline para ir de uma coluna à outra.
 * Tarefa sem equipe "conclui" pela entrega; com equipe, só a liderança conclui direto (a API confere).
 */
function acaoEntre(de: StatusTarefa, para: StatusTarefa, semEquipe: boolean): AcaoPipeline | null {
  const mapa: Record<string, AcaoPipeline> = {
    'a_fazer>em_andamento': 'iniciar',
    'em_andamento>a_fazer': 'pausar',
    'em_andamento>em_validacao': 'entregar',
    'em_validacao>concluida': 'validar',
    'em_validacao>em_andamento': 'devolver',
    'concluida>em_andamento': 'reabrir',
    'a_fazer>concluida': 'concluir',
    'em_andamento>concluida': semEquipe ? 'entregar' : 'concluir',
  };
  return mapa[`${de}>${para}`] ?? null;
}

@Component({
  selector: 'app-lista-tarefas',
  imports: [FormsModule, RouterLink, DatePipe, DecimalPipe, CabecalhoTarefasComponent, JanelaTarefaComponent],
  templateUrl: './lista-tarefas.component.html',
})
export class ListaTarefasComponent implements OnInit {
  private readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly destruir = inject(DestroyRef);

  protected readonly STATUS = STATUS;
  protected readonly rotulosStatus = ROTULOS_STATUS;
  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly prioridades: PrioridadeTarefa[] = ['critica', 'alta', 'normal', 'baixa'];
  protected readonly prazoRelativo = prazoRelativo;

  protected readonly escopo = signal<Escopo>({ tipo: 'minhas' });
  protected readonly dados = signal<ListaTarefas | null>(null);
  protected readonly carregando = signal(true);

  // Estado vindo da URL
  protected readonly visao = signal<Visao>('tabela');
  protected readonly status = signal<StatusTarefa[]>(ABERTAS);
  protected readonly prioridade = signal<PrioridadeTarefa | ''>('');
  protected readonly marcador = signal('');
  protected readonly responsavel = signal<number | null>(null);
  protected readonly busca = signal('');
  protected readonly recorte = signal<Recorte>('');
  protected readonly ordem = signal<Ordem>('manual');
  private readonly digitacao = new Subject<string>();

  // Janela de ação (devolver/reabrir pelo Kanban)
  protected readonly modoJanela = signal<ModoJanela | null>(null);
  protected readonly tarefaJanela = signal<TarefaResumo | null>(null);

  // Arrastar
  protected readonly arrastando = signal<TarefaResumo | null>(null);
  protected readonly colunaAlvo = signal<StatusTarefa | null>(null);
  protected readonly linhaAlvo = signal<number | null>(null);

  protected readonly titulo = computed(() => this.dados()?.contexto.titulo ?? (this.escopo().tipo === 'minhas' ? 'Minhas tarefas' : 'Tarefas'));
  protected readonly trilha = computed<ItemTrilha[]>(() => {
    const e = this.escopo();
    if (e.tipo === 'minhas') return [];
    return [{ rotulo: this.dados()?.contexto.titulo ?? '…' }];
  });
  protected readonly lider = computed(() => !!this.dados()?.contexto.lider);

  /** Marcadores e responsáveis presentes na lista (opções dos filtros). */
  protected readonly marcadoresDisponiveis = computed(() => {
    const mapa = new Map<string, Marcador>();
    for (const t of this.dados()?.itens ?? []) for (const m of t.marcadores) mapa.set(m.id, m);
    return [...mapa.values()].sort((a, b) => a.nome.localeCompare(b.nome));
  });
  protected readonly responsaveisDisponiveis = computed(() => {
    const mapa = new Map<number, Pessoa>();
    for (const t of this.dados()?.itens ?? []) if (t.responsavel) mapa.set(t.responsavel.id, t.responsavel);
    return [...mapa.values()].sort((a, b) => a.nome.localeCompare(b.nome));
  });

  /** Itens filtrados sem o filtro de situação (o Kanban separa por coluna). */
  private readonly filtradosSemStatus = computed(() => {
    const termo = this.busca().trim().toLowerCase();
    const hoje = new Date().toDateString();
    return (this.dados()?.itens ?? []).filter((t) =>
      (!this.prioridade() || t.prioridade === this.prioridade())
      && (!this.marcador() || t.marcadores.some((m) => m.id === this.marcador()))
      && (!this.responsavel() || t.responsavel?.id === this.responsavel())
      && (this.recorte() !== 'atrasadas' || (t.atrasada && t.status !== 'concluida'))
      && (this.recorte() !== 'hoje' || (new Date(t.prazo).toDateString() === hoje && t.status !== 'concluida'))
      && (!termo || t.titulo.toLowerCase().includes(termo) || String(t.numero) === termo.replace('#', '')
          || (t.responsavel?.nome.toLowerCase().includes(termo) ?? false)),
    );
  });

  protected readonly itens = computed(() => this.ordenar(this.filtradosSemStatus().filter((t) => this.status().includes(t.status))));

  protected readonly colunas = computed(() => STATUS.map((s) => {
    const todos = this.ordenar(this.filtradosSemStatus().filter((t) => t.status === s.valor));
    // Concluídas: as 30 mais recentes (as antigas continuam na tabela com o filtro "Concluída")
    const itens = s.valor === 'concluida' ? [...todos].sort((a, b) => b.atualizado_em.localeCompare(a.atualizado_em)).slice(0, 30) : todos;
    return { ...s, itens, total: todos.length };
  }));

  /** Filtros ativos (chips removíveis). */
  protected readonly chips = computed(() => {
    const lista: { rotulo: string; limpar: Params }[] = [];
    if (this.recorte()) lista.push({ rotulo: this.recorte() === 'atrasadas' ? 'Atrasadas' : 'Vencem hoje', limpar: { recorte: null } });
    if (this.prioridade()) lista.push({ rotulo: `Prioridade: ${ROTULOS_PRIORIDADE[this.prioridade() as PrioridadeTarefa]}`, limpar: { prioridade: null } });
    const m = this.marcadoresDisponiveis().find((x) => x.id === this.marcador());
    if (this.marcador()) lista.push({ rotulo: `Marcador: ${m?.nome ?? '…'}`, limpar: { marcador: null } });
    const r = this.responsaveisDisponiveis().find((x) => x.id === this.responsavel());
    if (this.responsavel()) lista.push({ rotulo: `Responsável: ${r?.nome ?? '…'}`, limpar: { responsavel: null } });
    if (this.busca()) lista.push({ rotulo: `Busca: "${this.busca()}"`, limpar: { busca: null } });
    return lista;
  });

  ngOnInit(): void {
    combineLatest([this.rota.paramMap, this.rota.data]).pipe(takeUntilDestroyed(this.destruir)).subscribe(([p, d]) => {
      const tipo = (d['escopo'] ?? 'minhas') as Escopo['tipo'];
      this.escopo.set({ tipo, equipeId: p.get('equipeId'), login: p.get('login') });
      this.carregar();
    });
    this.rota.queryParamMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((q) => {
      this.visao.set(q.get('visao') === 'kanban' ? 'kanban' : 'tabela');
      const status = q.get('status');
      this.status.set(status === 'todas' ? STATUS.map((s) => s.valor) : status ? (status.split(',') as StatusTarefa[]) : ABERTAS);
      this.prioridade.set((q.get('prioridade') ?? '') as PrioridadeTarefa | '');
      this.marcador.set(q.get('marcador') ?? '');
      this.responsavel.set(q.get('responsavel') ? Number(q.get('responsavel')) : null);
      this.busca.set(q.get('busca') ?? '');
      this.recorte.set((q.get('recorte') ?? '') as Recorte);
      this.ordem.set((q.get('ordem') ?? 'manual') as Ordem);
    });
    // Busca com atraso: a URL muda 300 ms depois da última tecla
    this.digitacao.pipe(debounceTime(300), takeUntilDestroyed(this.destruir)).subscribe((b) => this.navegar({ busca: b.trim() || null }));
  }

  protected carregar(): void {
    this.carregando.set(true);
    const vazio = { status: [], prioridade: '' as const, marcador_id: '', responsavel_id: null, busca: '' };
    this.api.listar(this.escopo(), vazio).subscribe({
      next: (d) => { this.dados.set(d); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar as tarefas'); },
    });
  }

  /** Grava os filtros na URL (recarregar a página mantém o estado). */
  protected navegar(params: Params): void {
    void this.roteador.navigate([], { relativeTo: this.rota, queryParams: params, queryParamsHandling: 'merge', replaceUrl: true });
  }

  protected digitar(valor: string): void {
    this.digitacao.next(valor);
  }

  protected alternarStatus(s: StatusTarefa): void {
    const atual = this.status();
    const novo = atual.includes(s) ? atual.filter((x) => x !== s) : [...atual, s];
    const texto = novo.length === STATUS.length ? 'todas' : novo.length === 0 || this.iguais(novo, ABERTAS) ? null : novo.join(',');
    this.navegar({ status: texto });
  }

  /** Indicadores clicáveis: aplicam o filtro correspondente. */
  protected aplicarIndicador(tipo: 'abertas' | 'atrasadas' | 'hoje' | 'criticas' | 'validacao' | 'concluidas'): void {
    const limpo: Params = { recorte: null, prioridade: null, status: null };
    const extra: Record<typeof tipo, Params> = {
      abertas: {},
      atrasadas: { recorte: 'atrasadas' },
      hoje: { recorte: 'hoje' },
      criticas: { prioridade: 'critica' },
      validacao: { status: 'em_validacao' },
      concluidas: { status: 'concluida' },
    };
    this.navegar({ ...limpo, ...extra[tipo] });
  }

  protected limparFiltros(): void {
    this.navegar({ recorte: null, prioridade: null, marcador: null, responsavel: null, busca: null, status: null });
  }

  // --- Tabela: ordem manual por arrastar ------------------------------------------------------------

  protected iniciarArraste(evento: DragEvent, t: TarefaResumo): void {
    this.arrastando.set(t);
    evento.dataTransfer?.setData('text/plain', String(t.numero));
    if (evento.dataTransfer) evento.dataTransfer.effectAllowed = 'move';
  }

  protected terminarArraste(): void {
    this.arrastando.set(null);
    this.colunaAlvo.set(null);
    this.linhaAlvo.set(null);
  }

  protected soltarNaLinha(evento: DragEvent, alvo: TarefaResumo): void {
    evento.preventDefault();
    const movida = this.arrastando();
    this.terminarArraste();
    if (!movida || movida.numero === alvo.numero || this.ordem() !== 'manual') return;
    const lista = this.itens().filter((t) => t.numero !== movida.numero);
    lista.splice(lista.findIndex((t) => t.numero === alvo.numero), 0, movida);
    this.reordenar(lista.map((t) => t.numero));
  }

  /** Teclado: sobe ou desce a tarefa uma posição. */
  protected mover(t: TarefaResumo, passo: -1 | 1): void {
    const lista = [...this.itens()];
    const i = lista.findIndex((x) => x.numero === t.numero);
    const j = i + passo;
    if (j < 0 || j >= lista.length) return;
    [lista[i], lista[j]] = [lista[j], lista[i]];
    this.reordenar(lista.map((x) => x.numero));
  }

  private reordenar(numeros: number[]): void {
    // Aplica na tela na hora (posição 0 = topo, como no servidor) e grava
    this.dados.update((d) => d && { ...d, itens: d.itens.map((t) => {
      const i = numeros.indexOf(t.numero);
      return i < 0 ? t : { ...t, ordem: i };
    }) });
    this.api.ordenar(numeros).subscribe({ error: (e) => { this.dialogos.mostrarErro(e); this.carregar(); } });
  }

  // --- Kanban: arrastar entre colunas ---------------------------------------------------------------

  protected soltarNaColuna(evento: DragEvent, para: StatusTarefa): void {
    evento.preventDefault();
    const t = this.arrastando();
    this.terminarArraste();
    if (!t || t.status === para) return;
    this.moverPara(t, para);
  }

  protected moverPara(t: TarefaResumo, para: StatusTarefa): void {
    const acao = acaoEntre(t.status, para, !t.equipe);
    if (!acao) {
      this.dialogos.avisar('Movimento não permitido', `Não é possível ir de "${ROTULOS_STATUS[t.status]}" para "${ROTULOS_STATUS[para]}". `
        + 'Siga o caminho A fazer → Em andamento → Em validação → Concluída.');
      return;
    }
    if (acao === 'devolver' || acao === 'reabrir') {
      this.tarefaJanela.set(t);
      this.modoJanela.set(acao);
      return;
    }
    // Movimento otimista: o cartão muda de coluna e volta se a API recusar
    const anterior = t.status;
    this.trocarStatus(t.numero, acao === 'entregar' && !t.equipe ? 'concluida' : para);
    this.api.mover(t.numero, acao).subscribe({
      next: () => this.carregar(),
      error: (e) => { this.trocarStatus(t.numero, anterior); this.dialogos.mostrarErro(e, 'Movimento não realizado'); },
    });
  }

  /** Botões do cartão (alternativa ao arrastar). */
  protected proximos(t: TarefaResumo): { rotulo: string; para: StatusTarefa; classe: string }[] {
    switch (t.status) {
      case 'a_fazer': return [{ rotulo: 'Iniciar', para: 'em_andamento', classe: '' }];
      case 'em_andamento': return [{ rotulo: t.equipe ? 'Entregar' : 'Concluir', para: t.equipe ? 'em_validacao' : 'concluida', classe: 'acao-aprovar' }];
      case 'em_validacao': return this.lider()
        ? [{ rotulo: 'Validar', para: 'concluida', classe: 'acao-aprovar' }, { rotulo: 'Devolver', para: 'em_andamento', classe: '' }]
        : [];
      default: return [];
    }
  }

  protected aoConcluirJanela(): void {
    this.carregar();
  }

  private trocarStatus(numero: number, status: StatusTarefa): void {
    this.dados.update((d) => d && { ...d, itens: d.itens.map((t) => (t.numero === numero ? { ...t, status } : t)) });
  }

  private ordenar(lista: TarefaResumo[]): TarefaResumo[] {
    const copia = [...lista];
    const o = this.ordem();
    if (o === 'prazo') return copia.sort((a, b) => a.prazo.localeCompare(b.prazo));
    if (o === 'prioridade') return copia.sort((a, b) => PESO_PRIORIDADE[a.prioridade] - PESO_PRIORIDADE[b.prioridade] || a.prazo.localeCompare(b.prazo));
    return copia.sort((a, b) => a.ordem - b.ordem);
  }

  private iguais(a: StatusTarefa[], b: StatusTarefa[]): boolean {
    return a.length === b.length && a.every((x) => b.includes(x));
  }
}
