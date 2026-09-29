// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir a tarefa em página própria: etapas, resumo, ações, checklist, comentários e linha do tempo.

import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { nomeDoArquivo, salvarBlob } from '../../shared/utilitarios/download';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { JanelaTarefaComponent, ModoJanela } from './janela-tarefa.component';
import { TarefasApiService } from './tarefas-api.service';
import {
  AcaoPipeline, AnexoEvento, duracao, EventoTarefa, Marcador, prazoRelativo, PrioridadeTarefa, ROTULOS_PRIORIDADE, ROTULOS_STATUS, StatusTarefa,
  TarefaDetalhe, tamanhoLegivel,
} from './tarefas.models';

/** Filtros da linha do tempo (chips). */
const FILTROS = [
  { valor: '', rotulo: 'Tudo' },
  { valor: 'comentarios', rotulo: 'Comentários' },
  { valor: 'anexos', rotulo: 'Anexos' },
  { valor: 'status', rotulo: 'Situação' },
  { valor: 'prazos', rotulo: 'Prazos' },
  { valor: 'atribuicoes', rotulo: 'Atribuições' },
];

/** Traço SVG (24x24) do ícone de cada tipo de evento; a cor vem do CSS por `data-tipo`. */
const ICONES: Record<string, string> = {
  criada: 'M12 5v14M5 12h14',
  editada: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z',
  status: 'M5 12h14M13 6l6 6-6 6',
  entregue: 'M12 19V5M5 12l7-7 7 7',
  validada: 'M5 13l4 4L19 7',
  devolvida: 'M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-2',
  reaberta: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5',
  prazo: 'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  transferida: 'M4 7h14l-4-4M20 17H6l4 4',
  comentario: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z',
  checklist: 'M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11',
  removido: 'M18 6 6 18M6 6l12 12',
};
/** Clipe de anexo (SVG). */
export const CLIPE = 'M21.4 11.1l-9.2 9.2a6 6 0 0 1-8.5-8.5l9.2-9.2a4 4 0 0 1 5.7 5.7l-9.2 9.2a2 2 0 0 1-2.8-2.8l8.5-8.5';

/** Rótulos dos campos da edição ("dados.campos"). */
const CAMPOS: Record<string, string> = { titulo: 'Título', descricao: 'Descrição', prioridade: 'Prioridade', participantes: 'Participantes', marcadores: 'Marcadores' };

@Component({
  selector: 'app-detalhe-tarefa',
  imports: [FormsModule, RouterLink, DatePipe, DecimalPipe, SeletorUsuariosComponent, CabecalhoTarefasComponent, JanelaTarefaComponent],
  templateUrl: './detalhe-tarefa.component.html',
})
export class DetalheTarefaComponent implements OnInit {
  protected readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly destruir = inject(DestroyRef);
  private readonly autenticacao = inject(AutenticacaoService);

  protected readonly FILTROS = FILTROS;
  protected readonly CLIPE = CLIPE;
  protected readonly rotulosStatus = ROTULOS_STATUS;
  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly prioridades: PrioridadeTarefa[] = ['baixa', 'normal', 'alta', 'critica'];
  protected readonly prazoRelativo = prazoRelativo;
  protected readonly duracao = duracao;
  protected readonly tamanhoLegivel = tamanhoLegivel;

  protected readonly tarefa = signal<TarefaDetalhe | null>(null);
  protected readonly naoEncontrada = signal(false);
  protected readonly superRoot = computed(() => this.autenticacao.possuiPapel('SuperRoot'));
  protected readonly pode = (acao: string) => this.tarefa()?.acoes.includes(acao) ?? false;

  // Linha do tempo
  protected readonly filtro = signal('');
  protected readonly eventos = signal<EventoTarefa[]>([]);
  protected readonly totalEventos = signal(0);
  protected readonly temMais = signal(false);
  protected readonly carregandoEventos = signal(false);
  /** Eventos agrupados por dia ("Hoje", "Ontem", "segunda-feira, 28/09/2026"). */
  protected readonly dias = computed(() => {
    const grupos: { dia: string; itens: EventoTarefa[] }[] = [];
    for (const e of this.eventos()) {
      const dia = this.rotuloDia(e.criado_em);
      const ultimo = grupos[grupos.length - 1];
      if (ultimo?.dia === dia) ultimo.itens.push(e);
      else grupos.push({ dia, itens: [e] });
    }
    return grupos;
  });

  // Comentário
  protected textoComentario = '';
  protected readonly arquivos = signal<File[]>([]);
  protected readonly enviando = signal(false);

  // Checklist
  protected novoItem = '';

  // Edição
  protected readonly editando = signal(false);
  protected edicao = { titulo: '', descricao: '', prioridade: 'normal' as PrioridadeTarefa };
  protected participantes: OpcaoUsuario[] = [];
  protected readonly marcadoresEquipe = signal<Marcador[]>([]);
  protected readonly marcadoresIds = signal<string[]>([]);

  // Janelas
  protected readonly modoJanela = signal<ModoJanela | null>(null);

  ngOnInit(): void {
    this.rota.paramMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((p) => {
      const numero = Number(p.get('numero'));
      this.tarefa.set(null);
      this.naoEncontrada.set(false);
      this.api.detalhe(numero).subscribe({
        next: (t) => { this.tarefa.set(t); this.carregarEventos(true); },
        error: (e) => { if (e?.status === 404) this.naoEncontrada.set(true); else this.dialogos.mostrarErro(e); },
      });
    });
  }

  private numero(): number {
    return this.tarefa()!.numero;
  }

  /** Atualiza a tarefa (depois de uma ação) e recarrega a linha do tempo. */
  protected atualizar(t: TarefaDetalhe): void {
    this.tarefa.set(t);
    this.carregarEventos(true);
  }

  // --- Pipeline -------------------------------------------------------------------------------------

  protected executar(acao: AcaoPipeline): void {
    // Entregar, devolver e reabrir abrem a janela (comentário ou motivo); as demais vão direto
    if (acao === 'entregar' || acao === 'devolver' || acao === 'reabrir') {
      this.modoJanela.set(acao);
      return;
    }
    const t = this.tarefa()!;
    this.dialogos.executar(this.api.mover(t.numero, acao, '', t.versao)).subscribe({
      next: (n) => this.atualizar(n),
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected async excluir(): Promise<void> {
    const t = this.tarefa()!;
    if (!(await this.dialogos.confirmar({ titulo: 'Excluir tarefa', mensagem: `A tarefa #${t.numero} e todo o histórico serão apagados. Não há como desfazer.`, rotuloConfirmar: 'Excluir', segundos: 3 }))) return;
    this.dialogos.executar(this.api.excluir(t.numero)).subscribe({
      next: () => void this.roteador.navigate(['/tarefas']),
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  // --- Edição ---------------------------------------------------------------------------------------

  protected abrirEdicao(): void {
    const t = this.tarefa()!;
    this.edicao = { titulo: t.titulo, descricao: t.descricao, prioridade: t.prioridade };
    this.participantes = t.pessoas.filter((p) => p.id !== t.responsavel?.id)
      .map((p) => ({ id: p.id, login: p.login, nome_completo: p.nome, cargo: '', ativo: true }));
    this.marcadoresIds.set(t.marcadores.map((m) => m.id));
    this.marcadoresEquipe.set([]);
    if (t.equipe) this.api.marcadores(t.equipe.id).subscribe({ next: (m) => this.marcadoresEquipe.set(m), error: () => undefined });
    this.editando.set(true);
  }

  protected alternarMarcador(id: string): void {
    this.marcadoresIds.update((l) => (l.includes(id) ? l.filter((x) => x !== id) : [...l, id]));
  }

  protected salvarEdicao(): void {
    const t = this.tarefa()!;
    this.dialogos.executar(this.api.editar(t.numero, {
      ...this.edicao, titulo: this.edicao.titulo.trim(), participantes_ids: this.participantes.map((p) => p.id),
      marcadores_ids: this.marcadoresIds(), versao: t.versao,
    })).subscribe({
      next: (n) => { this.editando.set(false); this.atualizar(n); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  // --- Checklist ------------------------------------------------------------------------------------

  protected checklist(acao: 'incluir' | 'marcar' | 'remover', itemId: string | null = null): void {
    const texto = acao === 'incluir' ? this.novoItem.trim() : '';
    if (acao === 'incluir' && !texto) return;
    this.api.checklist(this.numero(), acao, texto, itemId).subscribe({
      next: (n) => { if (acao === 'incluir') this.novoItem = ''; this.atualizar(n); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  // --- Comentários e anexos -------------------------------------------------------------------------

  protected escolherArquivos(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    const novos = Array.from(campo.files ?? []);
    campo.value = '';
    const todos = [...this.arquivos(), ...novos];
    if (todos.length > 5) this.dialogos.avisar('Muitos arquivos', 'Envie no máximo 5 arquivos por comentário.');
    this.arquivos.set(todos.slice(0, 5));
  }

  protected removerArquivo(i: number): void {
    this.arquivos.update((l) => l.filter((_, j) => j !== i));
  }

  protected comentar(): void {
    if (!this.textoComentario.trim() && !this.arquivos().length) return;
    this.enviando.set(true);
    this.dialogos.executar(this.api.comentar(this.numero(), this.textoComentario.trim(), this.arquivos()), 'Enviando o comentário…').subscribe({
      next: () => {
        this.enviando.set(false);
        this.textoComentario = '';
        this.arquivos.set([]);
        this.carregarEventos(true);
      },
      error: (e) => { this.enviando.set(false); this.dialogos.mostrarErro(e); },
    });
  }

  protected baixar(anexo: AnexoEvento): void {
    this.api.baixarAnexo(this.numero(), anexo.id, anexo.nome).subscribe({
      next: (r) => salvarBlob(r.body!, nomeDoArquivo(r, anexo.nome)),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o arquivo'),
    });
  }

  // --- Linha do tempo -------------------------------------------------------------------------------

  protected trocarFiltro(valor: string): void {
    this.filtro.set(valor);
    this.carregarEventos(true);
  }

  protected carregarEventos(reiniciar: boolean): void {
    const ultimo = reiniciar ? null : this.eventos().at(-1)?.criado_em ?? null;
    this.carregandoEventos.set(true);
    this.api.linhaDoTempo(this.numero(), this.filtro(), ultimo).subscribe({
      next: (l) => {
        this.eventos.set(reiniciar ? l.itens : [...this.eventos(), ...l.itens]);
        this.totalEventos.set(l.total);
        this.temMais.set(l.tem_mais);
        this.carregandoEventos.set(false);
      },
      error: (e) => { this.carregandoEventos.set(false); this.dialogos.mostrarErro(e); },
    });
  }

  /** SuperRoot: remoção lógica de um item, com motivo (janela própria). */
  protected readonly eventoRemover = signal<EventoTarefa | null>(null);
  protected motivoRemocao = '';

  protected pedirRemocao(e: EventoTarefa): void {
    this.motivoRemocao = '';
    this.eventoRemover.set(e);
  }

  protected removerEvento(): void {
    const e = this.eventoRemover();
    const motivo = this.motivoRemocao.trim();
    if (!e || !motivo) return;
    this.dialogos.executar(this.api.removerEvento(this.numero(), e.id, motivo)).subscribe({
      next: () => { this.eventoRemover.set(null); this.carregarEventos(true); },
      error: (erro) => this.dialogos.mostrarErro(erro),
    });
  }

  protected icone(tipo: string): string {
    return ICONES[tipo] ?? 'M12 12h.01';
  }

  protected rotuloStatus(valor: unknown): string {
    return ROTULOS_STATUS[valor as StatusTarefa] ?? String(valor ?? '');
  }

  /** Mudanças da edição em texto: "Prioridade: Normal → Alta", "Participantes: entrou Ana". */
  protected camposEditados(e: EventoTarefa): string[] {
    const campos = (e.dados['campos'] ?? {}) as Record<string, Record<string, unknown>>;
    return Object.entries(campos).map(([nome, v]) => {
      const rotulo = CAMPOS[nome] ?? nome;
      if (nome === 'descricao') return `${rotulo} alterada`;
      if (nome === 'participantes') {
        const entraram = (v['entraram'] as string[]) ?? [];
        const sairam = (v['sairam'] as string[]) ?? [];
        return `${rotulo}: ${[entraram.length ? `entrou ${entraram.join(', ')}` : '', sairam.length ? `saiu ${sairam.join(', ')}` : ''].filter(Boolean).join('; ')}`;
      }
      const texto = (x: unknown) => (Array.isArray(x) ? x.join(', ') || '—' : nome === 'prioridade' ? ROTULOS_PRIORIDADE[x as PrioridadeTarefa] ?? String(x) : String(x ?? '—'));
      return `${rotulo}: ${texto(v['de'])} → ${texto(v['para'])}`;
    });
  }

  protected texto(valor: unknown): string {
    return String(valor ?? '');
  }

  private rotuloDia(iso: string): string {
    const d = new Date(iso);
    const hoje = new Date();
    const ontem = new Date();
    ontem.setDate(hoje.getDate() - 1);
    if (d.toDateString() === hoje.toDateString()) return 'Hoje';
    if (d.toDateString() === ontem.toDateString()) return 'Ontem';
    return d.toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' });
  }
}
