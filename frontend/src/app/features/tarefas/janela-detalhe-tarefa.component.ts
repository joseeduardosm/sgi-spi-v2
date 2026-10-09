// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o detalhe da tarefa (estilo Trello) na tela própria /tarefas/:numero: conteúdo à esquerda, propriedades e ações à direita.

import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, effect, ElementRef, inject, input, output, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorMarcadoresComponent } from './seletor-marcadores.component';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { textoSla } from '../sla/sla.models';
import { AgendaPessoaComponent } from './agenda-pessoa.component';
import { AvataresComponent } from './avatares.component';
import { JanelaTarefaComponent, ModoJanela } from './janela-tarefa.component';
import { TarefasApiService } from './tarefas-api.service';
import {
  AcaoPipeline, AnexoEvento, duracao, EventoTarefa, Marcador, Pessoa, TarefaResumo, Atividade, Marco, ICONES_TIPO_ATIVIDADE, ROTULOS_TIPO_ATIVIDADE, TipoAtividade, PessoaCarga, prazoRelativo, PrioridadeTarefa, ROTULOS_PRIORIDADE, ROTULOS_STATUS,
  situacaoPrazo, StatusTarefa, TarefaDetalhe, tamanhoLegivel,
} from './tarefas.models';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

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
  // Escalonamento por atraso: aviso à liderança (triângulo de alerta)
  escalonada: 'M12 3 2 20h20L12 3Zm0 6v5m0 3h.01',
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
const CAMPOS: Record<string, string> = { titulo: 'Título', descricao: 'Descrição', prioridade: 'Prioridade', responsaveis: 'Responsáveis', participantes: 'Participantes (antes)', marcadores: 'Marcadores' };

/** Campos que o `PUT /api/tarefas/{numero}` grava de uma vez (a janela altera um de cada vez). */
interface CamposEdicao { titulo: string; descricao: string; prioridade: PrioridadeTarefa; responsaveis_ids: number[]; marcadores_ids: string[] }

/**
 * Detalhe da tarefa, exibido na tela própria `/tarefas/:numero` (`pagina`) ou, se preciso, como janela.
 * - Esquerda: título (edita no lugar), descrição, checklist, comentário e a atividade (linha do tempo).
 * - Direita: etapa e ações do pipeline (só as permitidas em `acoes`), pessoas, prazo, prioridade,
 *   marcadores, equipe e dados da tarefa. Cada propriedade é salva sozinha, com `versao` (409 em conflito).
 * Emite `alterada` depois de cada gravação (o quadro recarrega) e `fechar` ao sair.
 */
@Component({
  selector: 'app-janela-detalhe-tarefa',
  imports: [LinkificarPipe, FormsModule, RouterLink, DatePipe, DecimalPipe, SeletorUsuariosComponent, SeletorMarcadoresComponent, JanelaTarefaComponent, AvataresComponent, AgendaPessoaComponent],
  templateUrl: './janela-detalhe-tarefa.component.html',
  // Esc fecha a janela, a menos que uma janela interna (prazo, motivo, remoção) esteja aberta: ela fecha primeiro
  host: { '(document:keydown.escape)': 'aoEsc()', '(window:focus)': 'recarregarAoVoltar()' },
})
export class JanelaDetalheTarefaComponent {
  /** Número da tarefa aberta (vazio: janela fechada). */
  readonly numeroTarefa = input<number | null>(null);
  /** Tela própria (`/tarefas/:numero`): sem fundo escurecido nem comportamento de janela modal. */
  readonly pagina = input(false);
  readonly fechar = output<void>();
  /** A tarefa mudou (o quadro recarrega); `null` quando foi excluída. */
  readonly alterada = output<TarefaDetalhe | null>();

  protected readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);

  protected readonly FILTROS = FILTROS;
  protected readonly CLIPE = CLIPE;
  protected readonly textoSla = textoSla;
  protected readonly rotulosStatus = ROTULOS_STATUS;
  protected readonly rotulosPrioridade = ROTULOS_PRIORIDADE;
  protected readonly prioridades: PrioridadeTarefa[] = ['baixa', 'normal', 'alta', 'critica'];
  protected readonly prazoRelativo = prazoRelativo;
  protected readonly duracao = duracao;
  protected readonly tamanhoLegivel = tamanhoLegivel;
  protected readonly situacao = situacaoPrazo;

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
  /** Comentário que está sendo respondido (a resposta o cita e entra no topo, como qualquer comentário novo). */
  protected readonly respondendoA = signal<EventoTarefa | null>(null);
  private readonly campoComentario = viewChild<ElementRef<HTMLTextAreaElement>>('campoComentario');
  protected readonly arquivos = signal<File[]>([]);
  protected readonly enviando = signal(false);

  // Checklist
  protected novoItem = '';

  // Edição no lugar: qual propriedade está aberta e os valores em edição
  protected readonly editandoCampo = signal<'titulo' | 'descricao' | 'responsaveis' | null>(null);
  protected edicaoTitulo = '';
  private readonly campoTitulo = viewChild<ElementRef<HTMLInputElement>>('campoTitulo');
  protected edicaoDescricao = '';
  protected responsaveis: OpcaoUsuario[] = [];
  // Atividades agendadas e menções
  protected readonly icones = ICONES_TIPO_ATIVIDADE;
  protected readonly tiposAtividade = ROTULOS_TIPO_ATIVIDADE;
  protected readonly tiposLista = Object.keys(ROTULOS_TIPO_ATIVIDADE) as TipoAtividade[];
  protected readonly atividades = signal<Atividade[]>([]);
  protected readonly concluindo = signal<string | null>(null);
  protected readonly pessoasMencao = signal<PessoaCarga[]>([]);
  protected feedbackAtividade = '';
  protected novaAtividade: { tipo: string; resumo: string; prazo: string; responsavel_id: number | null } = { tipo: 'fazer', resumo: '', prazo: '', responsavel_id: null };
  protected readonly marcosEquipe = signal<Marco[]>([]);
  // Subtarefas e dependências
  protected novaSubtarefa = '';
  protected buscaDependencia = '';
  private readonly equipeTarefas = signal<TarefaResumo[]>([]);
  /** Pessoa cuja agenda aparece ao escolher responsáveis (a última incluída). */
  protected readonly pessoaAgenda = signal<number | null>(null);

  // Janelas internas
  protected readonly modoJanela = signal<ModoJanela | null>(null);

  constructor() {
    // Abre (ou troca) a tarefa sempre que o número muda
    effect(() => {
      const numero = this.numeroTarefa();
      this.tarefa.set(null);
      this.naoEncontrada.set(false);
      this.editandoCampo.set(null);
      this.eventos.set([]);
      this.atividades.set([]);
      this.pessoasMencao.set([]);
      this.filtro.set('');
      if (!numero) return;
      this.api.detalhe(numero).subscribe({
        next: (t) => { this.tarefa.set(t); this.carregarEventos(true); this.carregarAtividades(); },
        error: (e) => { if (e?.status === 404) this.naoEncontrada.set(true); else this.dialogos.mostrarErro(e); },
      });
    });
  }

  /** Recarrega a tarefa e a linha do tempo (a tela pode estar desatualizada: outra pessoa pode ter mudado a tarefa). */
  protected recarregar(): void {
    const numero = this.numeroTarefa();
    if (!numero) return;
    this.api.detalhe(numero).subscribe({
      next: (t) => { this.tarefa.set(t); this.carregarEventos(true); this.carregarAtividades(); this.alterada.emit(t); },
      error: () => undefined,
    });
  }

  /** Ao voltar para a aba: se a tarefa mudou enquanto ela estava em segundo plano, a tela atualiza (sem atrapalhar quem edita). */
  protected recarregarAoVoltar(): void {
    if (this.numeroTarefa() && !this.modoJanela() && !this.editandoCampo() && !this.eventoRemover()) this.recarregar();
  }

  /** Erro numa ação: mostra a mensagem e, se for recusa ou conflito (tela desatualizada), atualiza a tarefa para mostrar as ações de agora. */
  protected falha(e: { status?: number }): void {
    this.dialogos.mostrarErro(e);
    if (e?.status === 403 || e?.status === 409) this.recarregar();
  }

  /** Esc: fecha primeiro as janelas internas; sem elas, fecha a tarefa. */
  protected aoEsc(): void {
    if (!this.numeroTarefa() || this.modoJanela() || this.eventoRemover()) return;
    if (this.editandoCampo()) { this.editandoCampo.set(null); return; }
    this.fechar.emit();
  }

  private numero(): number {
    return this.tarefa()!.numero;
  }

  /** Atualiza a tarefa (depois de uma ação), recarrega a linha do tempo e avisa o quadro. */
  protected atualizar(t: TarefaDetalhe): void {
    this.tarefa.set(t);
    this.carregarEventos(true);
    this.alterada.emit(t);
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
      error: (e) => this.falha(e),
    });
  }

  protected async excluir(): Promise<void> {
    const t = this.tarefa()!;
    if (!(await this.dialogos.confirmar({ titulo: 'Excluir tarefa', mensagem: `A tarefa #${t.numero} e todo o histórico serão apagados. Não há como desfazer.`, rotuloConfirmar: 'Excluir', segundos: 3 }))) return;
    this.dialogos.executar(this.api.excluir(t.numero)).subscribe({
      next: () => { this.alterada.emit(null); this.fechar.emit(); },
      error: (e) => this.falha(e),
    });
  }

  // --- Edição no lugar (uma propriedade por vez) -------------------------------------------------------

  /** Grava a tarefa trocando só os campos informados; os demais seguem como estão. */
  private salvarCampos(parcial: Partial<CamposEdicao>): void {
    const t = this.tarefa()!;
    const atual: CamposEdicao = {
      titulo: t.titulo, descricao: t.descricao, prioridade: t.prioridade,
      responsaveis_ids: t.responsaveis.map((p) => p.id), marcadores_ids: t.marcadores.map((m) => m.id),
    };
    this.dialogos.executar(this.api.editar(t.numero, { ...atual, ...parcial, versao: t.versao })).subscribe({
      next: (n) => { this.editandoCampo.set(null); this.atualizar(n); },
      error: (e) => this.falha(e),
    });
  }

  protected editarTitulo(): void {
    if (!this.pode('editar')) return;
    this.edicaoTitulo = this.tarefa()!.titulo;
    this.editandoCampo.set('titulo');
    // Foco e seleção no campo assim que ele aparece
    setTimeout(() => this.campoTitulo()?.nativeElement.select());
  }

  protected salvarTitulo(): void {
    const titulo = this.edicaoTitulo.trim();
    if (this.editandoCampo() !== 'titulo') return;
    // Fecha o campo já (Enter e a perda de foco chegam juntos; só a primeira grava)
    this.editandoCampo.set(null);
    if (titulo && titulo !== this.tarefa()!.titulo) this.salvarCampos({ titulo });
  }

  protected editarDescricao(): void {
    this.edicaoDescricao = this.tarefa()!.descricao;
    this.editandoCampo.set('descricao');
  }

  protected salvarDescricao(): void {
    this.salvarCampos({ descricao: this.edicaoDescricao });
  }

  protected trocarPrioridade(prioridade: PrioridadeTarefa): void {
    if (prioridade !== this.tarefa()!.prioridade) this.salvarCampos({ prioridade });
  }

  protected editarResponsaveis(): void {
    const t = this.tarefa()!;
    this.responsaveis = t.responsaveis
      .map((p) => ({ id: p.id, login: p.login, nome_completo: p.nome, cargo: '', ativo: true }));
    this.pessoaAgenda.set(null);
    this.editandoCampo.set('responsaveis');
  }

  /** Ao incluir alguém, a agenda dessa pessoa aparece ao lado (para ver a carga antes de salvar). */
  protected aoMudarResponsaveis(lista: OpcaoUsuario[]): void {
    const novo = lista.find((p) => !this.responsaveis.some((x) => x.id === p.id));
    this.responsaveis = lista;
    if (novo) this.pessoaAgenda.set(novo.id);
    else if (!lista.some((p) => p.id === this.pessoaAgenda())) this.pessoaAgenda.set(lista.at(-1)?.id ?? null);
  }

  protected salvarResponsaveis(): void {
    this.salvarCampos({ responsaveis_ids: this.responsaveis.map((p) => p.id) });
  }

  /** Marcadores gravam na hora, a cada pílula incluída ou tirada (sem botão Salvar). */
  protected salvarMarcadores(lista: Marcador[]): void {
    this.salvarCampos({ marcadores_ids: lista.map((m) => m.id) });
  }

  // --- Checklist ------------------------------------------------------------------------------------

  protected checklist(acao: 'incluir' | 'marcar' | 'remover', itemId: string | null = null): void {
    const texto = acao === 'incluir' ? this.novoItem.trim() : '';
    if (acao === 'incluir' && !texto) return;
    this.api.checklist(this.numero(), acao, texto, itemId).subscribe({
      next: (n) => { if (acao === 'incluir') this.novoItem = ''; this.atualizar(n); },
      error: (e) => this.falha(e),
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

  /** Escolhe o comentário a responder: mostra a citação acima do campo e leva o foco para ele. */
  protected responder(evento: EventoTarefa): void {
    this.respondendoA.set(evento);
    setTimeout(() => this.campoComentario()?.nativeElement.focus());
  }

  protected cancelarResposta(): void {
    this.respondendoA.set(null);
  }

  /** Trecho curto do comentário para a citação (a API já limita o que guarda nas respostas). */
  protected trecho(texto: string, limite = 140): string {
    return texto.length > limite ? texto.slice(0, limite).trimEnd() + '…' : texto;
  }

  /** Leva à citação: rola até o comentário original (se já está na lista) e o destaca por um instante. */
  protected irParaComentario(id: unknown): void {
    const alvo = typeof id === 'string' ? document.getElementById(`evento-${id}`) : null;
    if (!alvo) return;
    alvo.scrollIntoView({ block: 'center', behavior: 'smooth' });
    alvo.classList.add('destacado-evento');
    setTimeout(() => alvo.classList.remove('destacado-evento'), 1800);
  }

  protected removerArquivo(i: number): void {
    this.arquivos.update((l) => l.filter((_, j) => j !== i));
  }

  protected comentar(): void {
    if (!this.textoComentario.trim() && !this.arquivos().length) return;
    this.enviando.set(true);
    this.dialogos.executar(this.api.comentar(this.numero(), this.textoComentario.trim(), this.arquivos(), this.respondendoA()?.id ?? null), 'Enviando o comentário…').subscribe({
      next: () => {
        this.enviando.set(false);
        this.respondendoA.set(null);
        this.textoComentario = '';
        this.arquivos.set([]);
        this.carregarEventos(true);
      },
      error: (e) => { this.enviando.set(false); this.dialogos.mostrarErro(e); },
    });
  }

  protected baixar(anexo: AnexoEvento): void {
    // `baixarArquivo` já salva o arquivo; aqui só o erro é tratado
    this.api.baixarAnexo(this.numero(), anexo.id, anexo.nome).subscribe({
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

  /** Mudanças da edição em texto: "Prioridade: Normal → Alta", "Responsáveis: entrou Ana". */
  protected camposEditados(e: EventoTarefa): string[] {
    const campos = (e.dados['campos'] ?? {}) as Record<string, Record<string, unknown>>;
    return Object.entries(campos).map(([nome, v]) => {
      const rotulo = CAMPOS[nome] ?? nome;
      if (nome === 'descricao') return `${rotulo} alterada`;
      if (nome === 'responsaveis' || nome === 'participantes') {
        const entraram = (v['entraram'] as string[]) ?? [];
        const sairam = (v['sairam'] as string[]) ?? [];
        return `${rotulo}: ${[entraram.length ? `entrou ${entraram.join(', ')}` : '', sairam.length ? `saiu ${sairam.join(', ')}` : ''].filter(Boolean).join('; ')}`;
      }
      const texto = (x: unknown) => (Array.isArray(x) ? x.join(', ') || '—' : nome === 'prioridade' ? ROTULOS_PRIORIDADE[x as PrioridadeTarefa] ?? String(x) : String(x ?? '—'));
      // Edições migradas do 10.23.1.220 podem não ter o valor anterior
      return 'de' in v ? `${rotulo}: ${texto(v['de'])} → ${texto(v['para'])}` : `${rotulo}: ${texto(v['para'])}`;
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

  // --- Subtarefas e dependências ---

  /** Baixa o relatório memorial da tarefa (todos os acontecimentos) em PDF ou XLSX. */
  protected memorial(formato: 'pdf' | 'xlsx'): void {
    const t = this.tarefa();
    if (!t) return;
    this.dialogos.executar(this.api.memorial(t.numero, formato), 'Gerando o memorial…').subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o memorial') });
  }

  protected concluidasSub(t: TarefaDetalhe): number {
    return t.subtarefas.filter((x) => x.status === 'concluida').length;
  }

  protected criarSubtarefa(): void {
    const t = this.tarefa();
    const titulo = this.novaSubtarefa.trim();
    if (!t || !titulo) return;
    this.dialogos.executar(this.api.criarSubtarefa(t.numero, { titulo })).subscribe({
      next: () => { this.novaSubtarefa = ''; this.recarregar(); },
      error: (e) => this.falha(e),
    });
  }

  /** Tarefas da equipe que ainda podem bloquear esta (abertas, fora ela mesma, a mãe, as subtarefas e as já escolhidas). */
  protected candidatas(t: TarefaDetalhe): TarefaResumo[] {
    const fora = new Set([t.numero, t.tarefa_pai?.numero, ...t.subtarefas.map((s) => s.numero), ...t.bloqueada_por.map((b) => b.numero)]);
    return this.equipeTarefas().filter((c) => c.status !== 'concluida' && !fora.has(c.numero));
  }

  protected carregarCandidatas(t: TarefaDetalhe): void {
    if (!t.equipe || this.equipeTarefas().length) return;
    const vazio = { status: [], prioridade: '' as const, marcador_id: '', responsavel_id: null, busca: '' };
    this.api.listar({ tipo: 'equipe', equipeId: t.equipe.id }, vazio).subscribe({ next: (l) => this.equipeTarefas.set(l.itens), error: () => undefined });
  }

  /** O campo é um datalist: ao escolher uma opção ("#12 Título"), grava a dependência. */
  protected escolherDependencia(t: TarefaDetalhe, texto: string): void {
    this.buscaDependencia = texto;
    const numero = /^#(\d+)\s/.exec(texto)?.[1];
    if (!numero) return;
    this.buscaDependencia = '';
    this.gravarDependencias(t, [...t.bloqueada_por.map((b) => b.numero), Number(numero)]);
  }

  protected removerDependencia(t: TarefaDetalhe, numero: number): void {
    this.gravarDependencias(t, t.bloqueada_por.map((b) => b.numero).filter((n) => n !== numero));
  }

  private gravarDependencias(t: TarefaDetalhe, numeros: number[]): void {
    this.dialogos.executar(this.api.definirDependencias(t.numero, numeros)).subscribe({ next: (n) => this.atualizar(n), error: (e) => this.falha(e) });
  }

  // --- Atividades agendadas, seguidores e menções ---

  protected atividadesAbertas(): Atividade[] {
    return this.atividades().filter((a) => a.situacao !== 'concluida');
  }

  protected carregarAtividades(): void {
    const t = this.tarefa();
    if (!t) return;
    this.api.atividadesDaTarefa(t.numero).subscribe({ next: (l) => this.atividades.set(l), error: () => undefined });
    if (t.equipe && !this.pessoasMencao().length) this.api.pessoas(t.equipe.id).subscribe({ next: (p) => this.pessoasMencao.set(p), error: () => undefined });
  }

  protected agendarAtividade(): void {
    const t = this.tarefa();
    const n = this.novaAtividade;
    if (!t || !n.resumo.trim()) return;
    this.dialogos.executar(this.api.agendarAtividade(t.numero, { resumo: n.resumo.trim(), tipo: n.tipo, nota: '', prazo: n.prazo || null, responsavel_id: n.responsavel_id })).subscribe({
      next: () => { this.novaAtividade = { ...n, resumo: '' }; this.recarregar(); },
      error: (e) => this.falha(e),
    });
  }

  protected abrirConclusao(a: Atividade): void {
    this.feedbackAtividade = '';
    this.concluindo.set(a.id);
  }

  /** Conclui com o feedback; "e agendar a próxima" já deixa o formulário de nova atividade preenchido com o mesmo tipo. */
  protected concluirAtividade(a: Atividade, proxima: boolean): void {
    this.api.concluirAtividade(a.id, this.feedbackAtividade.trim()).subscribe({
      next: () => {
        this.concluindo.set(null);
        if (proxima) this.novaAtividade = { tipo: a.tipo, resumo: '', prazo: '', responsavel_id: a.responsavel?.id ?? null };
        this.recarregar();
      },
      error: (e) => this.falha(e),
    });
  }

  protected async excluirAtividade(a: Atividade): Promise<void> {
    const ok = await this.dialogos.confirmar({ titulo: 'Excluir esta atividade?', mensagem: `"${a.resumo}" será removida.`, rotuloConfirmar: 'Excluir', perigo: true });
    if (ok) this.api.excluirAtividade(a.id).subscribe({ next: () => this.carregarAtividades(), error: (e) => this.falha(e) });
  }

  protected alternarSeguir(t: TarefaDetalhe): void {
    this.api.seguir(t.numero, !t.seguindo).subscribe({ next: (n) => this.atualizar(n), error: (e) => this.falha(e) });
  }

  protected nomesSeguidores(t: TarefaDetalhe): string {
    return t.seguidores.map((p) => p.nome).join(', ');
  }

  /** Insere `@login` no comentário (o campo volta para "Mencionar alguém…"). */
  protected mencionar(login: string): void {
    if (!login) return;
    this.textoComentario = `${this.textoComentario}${this.textoComentario && !this.textoComentario.endsWith(' ') ? ' ' : ''}@${login} `;
  }

  // --- Marco da tarefa ---

  protected carregarMarcos(t: TarefaDetalhe): void {
    if (t.equipe && !this.marcosEquipe().length) this.api.marcos(t.equipe.id).subscribe({ next: (m) => this.marcosEquipe.set(m), error: () => undefined });
  }

  protected trocarMarco(t: TarefaDetalhe, marcoId: string | null): void {
    if (marcoId === t.marco_id) return;
    this.dialogos.executar(this.api.definirMarco(t.numero, marcoId)).subscribe({ next: (n) => this.atualizar(n), error: (e) => this.falha(e) });
  }

  protected nomeMarco(t: TarefaDetalhe): string {
    return this.marcosEquipe().find((m) => m.id === t.marco_id)?.nome ?? (t.marco_id ? 'Marco da equipe' : 'Nenhum');
  }
}
