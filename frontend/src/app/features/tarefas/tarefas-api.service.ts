/**
 * =============================================================================
 * ARQUIVO: tarefas-api.service.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Centralizar todas as chamadas HTTP do Módulo Tarefas: tarefas, linha do
 * tempo, checklist, equipes, colunas, marcos, atividades, recorrências,
 * marcadores, desempenho, relatórios e RDM.
 *
 * RESUMO TÉCNICO:
 * Serviço Angular (providedIn: 'root') que usa HttpClient sobre a base
 * `${ambiente.urlApi}/tarefas`. Cada método monta URL, query (HttpParams) ou
 * corpo (JSON ou FormData para anexos) e devolve um Observable tipado com as
 * interfaces de tarefas.models.ts e rdm.models.ts. Downloads usam baixarArquivo.
 *
 * FINALIDADE DE NEGÓCIO:
 * O Módulo Tarefas organiza o trabalho das equipes da SPI (quadro, prazos,
 * validação pela liderança, rotinas recorrentes e mudanças com RDM). Ter um
 * único ponto de acesso à API mantém as telas simples e o contrato com o
 * backend fácil de conferir.
 *
 * CONTEXTO NO SISTEMA:
 * Consumido por todas as telas de frontend/src/app/features/tarefas. Fala com
 * as rotas de backend/app/api/routes/tarefas.py (documentadas em
 * docs/endpoints/tarefas.md).
 *
 * =============================================================================
 */

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import { FormularioRdm, RdmLeitura, RdmListada } from './rdm.models';
import {
  AcaoPipeline, AtividadeDiaria, AgendaPessoa, Atividade, AtualizacaoStatus, Marco, DesempenhoEquipe, Equipe, Estagio, Recorrencia, RegraRecorrencia, EventoTarefa, FiltrosTarefas, LinhaDoTempo, ListaTarefas, Marcador, PessoaCarga, PrioridadeTarefa, TarefaDetalhe,
} from './tarefas.models';

/**
 * De quem são as tarefas pedidas: as minhas, as de uma equipe, as de uma
 * pessoa (pelo login) ou as subtarefas de uma tarefa (pelo número).
 */
export interface Escopo { tipo: 'minhas' | 'equipe' | 'pessoa' | 'subtarefas'; equipeId?: string | null; login?: string | null; tarefa?: number | null }

/**
 * Serviço com todas as chamadas HTTP do Módulo Tarefas (/api/tarefas).
 *
 * `@Injectable({ providedIn: 'root' })` cria uma única instância para todo o
 * sistema. Cada método devolve um `Observable`: a requisição só sai quando a
 * tela chama `subscribe`. As regras (permissões, prazos, geração de
 * recorrências) ficam no backend; aqui só se monta a URL e o corpo.
 */
@Injectable({ providedIn: 'root' })
export class TarefasApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/tarefas`;

  /**
   * Lista as tarefas do escopo com os filtros da tela. `HttpParams` monta a
   * query string; `append` repete o parâmetro "status" para cada situação
   * marcada (a API recebe uma lista).
   */
  listar(escopo: Escopo, filtros: FiltrosTarefas): Observable<ListaTarefas> {
    let p = new HttpParams().set('escopo', escopo.tipo);
    if (escopo.equipeId) p = p.set('equipe_id', escopo.equipeId);
    if (escopo.login) p = p.set('login', escopo.login);
    if (escopo.tarefa) p = p.set('tarefa', escopo.tarefa);
    for (const s of filtros.status) p = p.append('status', s);
    if (filtros.prioridade) p = p.set('prioridade', filtros.prioridade);
    if (filtros.marcador_id) p = p.set('marcador_id', filtros.marcador_id);
    if (filtros.responsavel_id) p = p.set('responsavel_id', filtros.responsavel_id);
    if (filtros.busca.trim()) p = p.set('busca', filtros.busca.trim());
    return this.http.get<ListaTarefas>(this.base, { params: p });
  }

  /** Detalhe completo de uma tarefa pelo número. */
  detalhe(numero: number): Observable<TarefaDetalhe> {
    return this.http.get<TarefaDetalhe>(`${this.base}/${numero}`);
  }

  /** Cria uma tarefa (com regra de recorrência opcional) sem anexos, em JSON. */
  criar(dados: {
    titulo: string; descricao: string; prazo: string; prioridade: PrioridadeTarefa; equipe_id: string | null;
    responsaveis_ids: number[]; marcadores_ids: string[]; recorrencia?: RegraRecorrencia | null;
  }): Observable<TarefaDetalhe> {
    return this.http.post<TarefaDetalhe>(this.base, dados);
  }

  /** Cria a tarefa já com anexos (até 5), em `multipart`: os arquivos ficam no evento "Tarefa criada". */
  criarComAnexos(dados: {
    titulo: string; descricao: string; prazo: string; prioridade: PrioridadeTarefa; equipe_id: string | null;
    responsaveis_ids: number[]; marcadores_ids: string[]; recorrencia?: RegraRecorrencia | null;
  }, arquivos: File[]): Observable<TarefaDetalhe> {
    const corpo = new FormData();
    corpo.append('dados', JSON.stringify(dados));
    for (const a of arquivos) corpo.append('arquivos', a);
    return this.http.post<TarefaDetalhe>(`${this.base}/com-anexos`, corpo);
  }

  /**
   * Altera os dados principais da tarefa. `versao` é a versão que a tela
   * leu: se outra pessoa salvou antes, a API recusa (controle de concorrência).
   */
  editar(numero: number, dados: { titulo: string; descricao: string; prioridade: PrioridadeTarefa; responsaveis_ids: number[]; marcadores_ids: string[]; versao: number }) {
    return this.http.put<TarefaDetalhe>(`${this.base}/${numero}`, dados);
  }

  /** Muda o prazo da tarefa; a justificativa fica registrada na linha do tempo. */
  prazo(numero: number, prazo: string, justificativa: string, versao: number) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/prazo`, { prazo, justificativa, versao });
  }

  /** Move a tarefa no fluxo (iniciar, enviar para validação, concluir etc.), com texto opcional. */
  mover(numero: number, acao: AcaoPipeline, texto = '', versao?: number, estagioId?: string) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/mover`, { acao, texto, versao, estagio_id: estagioId ?? null });
  }

  /** Troca a coluna da tarefa dentro da mesma situação. */
  mudarEstagio(numero: number, estagioId: string) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/estagio`, { estagio_id: estagioId });
  }

  /** Colunas (estágios) do quadro da equipe. */
  estagios(equipeId: string): Observable<Estagio[]> {
    return this.http.get<Estagio[]>(`${this.base}/equipes/${equipeId}/estagios`);
  }

  /** Grava a lista completa de colunas da equipe (id nulo = coluna nova). */
  gravarEstagios(equipeId: string, estagios: { id: string | null; nome: string; categoria: string; cor_indice: number }[]): Observable<Estagio[]> {
    return this.http.put<Estagio[]>(`${this.base}/equipes/${equipeId}/estagios`, { estagios });
  }

  /** Transfere a tarefa para outra pessoa, com justificativa e, se quiser, novo prazo. */
  transferir(numero: number, para_id: number, justificativa: string, novo_prazo: string | null, versao: number) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/transferir`, { para_id, justificativa, novo_prazo, versao });
  }

  /**
   * Comenta na tarefa com anexos opcionais. Usa `FormData` (multipart) porque
   * arquivos não cabem em JSON; `emRespostaA` liga a resposta a outro evento.
   */
  comentar(numero: number, texto: string, arquivos: File[], emRespostaA: string | null = null): Observable<EventoTarefa> {
    const corpo = new FormData();
    corpo.append('texto', texto);
    if (emRespostaA) corpo.append('em_resposta_a', emRespostaA);
    for (const a of arquivos) corpo.append('arquivos', a);
    return this.http.post<EventoTarefa>(`${this.base}/${numero}/comentarios`, corpo);
  }

  /** Página da linha do tempo (30 eventos por vez); `antesDe` busca os mais antigos. */
  linhaDoTempo(numero: number, filtro: string, antesDe: string | null): Observable<LinhaDoTempo> {
    let p = new HttpParams().set('limite', 30);
    if (filtro) p = p.set('filtro', filtro);
    if (antesDe) p = p.set('antes_de', antesDe);
    return this.http.get<LinhaDoTempo>(`${this.base}/${numero}/linha-do-tempo`, { params: p });
  }

  /** Baixa um anexo da tarefa e salva no computador com o nome original. */
  baixarAnexo(numero: number, anexoId: string, nome: string) {
    return baixarArquivo(this.http, `${this.base}/${numero}/anexos/${anexoId}`, nome);
  }

  /** Remove um evento (ex.: comentário) da linha do tempo, registrando o motivo. */
  removerEvento(numero: number, eventoId: string, motivo: string) {
    return this.http.post<EventoTarefa>(`${this.base}/${numero}/eventos/${eventoId}/remover`, { motivo });
  }

  /** Inclui, marca/desmarca ou remove um item do checklist da tarefa. */
  checklist(numero: number, acao: 'incluir' | 'marcar' | 'remover', texto = '', item_id: string | null = null) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/checklist`, { acao, texto, item_id });
  }

  /** Exclui a tarefa. */
  excluir(numero: number) {
    return this.http.delete<void>(`${this.base}/${numero}`);
  }

  /** Grava a ordem manual das tarefas (lista de números na ordem desejada). */
  ordenar(numeros: number[]) {
    return this.http.post<void>(`${this.base}/ordem`, { numeros });
  }

  /** Pessoas que podem receber tarefas, com a carga de trabalho de cada uma. */
  pessoas(equipeId: string | null, busca = ''): Observable<PessoaCarga[]> {
    let p = new HttpParams();
    if (equipeId) p = p.set('equipe_id', equipeId);
    if (busca) p = p.set('busca', busca);
    return this.http.get<PessoaCarga[]>(`${this.base}/pessoas`, { params: p });
  }

  /** Agenda de uma pessoa (painel ao atribuir): carga e todas as tarefas abertas, com as concluídas do período. */
  agenda(usuarioId: number, de?: string, ate?: string): Observable<AgendaPessoa> {
    let p = new HttpParams();
    if (de) p = p.set('de', de);
    if (ate) p = p.set('ate', ate);
    return this.http.get<AgendaPessoa>(`${this.base}/pessoas/${usuarioId}/agenda`, { params: p });
  }

  /** Fonte do seletor de usuários: a carga aparece no lugar do cargo ("Alta ocupação · 8 a fazer"). */
  opcoesPessoas = (busca: string): Observable<OpcaoUsuario[]> =>
    this.pessoas(null, busca).pipe(map((lista) => lista.map((p) => ({
      id: p.id, login: p.login, nome_completo: p.nome, ativo: true,
      cargo: `${p.faixa} · ${p.a_fazer + p.em_andamento} em aberto${p.atrasadas ? ` · ${p.atrasadas} atrasada(s)` : ''}`,
    }))));

  /** Relatório memorial da tarefa (todos os acontecimentos), em PDF ou XLSX. */
  memorial(numero: number, formato: 'pdf' | 'xlsx') {
    return baixarArquivo(this.http, `${this.base}/${numero}/memorial?formato=${formato}`, `memorial-tarefa-${numero}.${formato}`);
  }

  /** Relatório XLSX ou PDF do escopo, no período (datas aaaa-mm-dd) e, opcionalmente, de um marcador. */
  relatorio(escopo: Escopo, formato: 'xlsx' | 'pdf', de: string, ate: string, marcadorId: string) {
    let p = new HttpParams().set('escopo', escopo.tipo).set('formato', formato);
    if (escopo.equipeId) p = p.set('equipe_id', escopo.equipeId);
    if (escopo.login) p = p.set('login', escopo.login);
    if (de) p = p.set('de', de);
    if (ate) p = p.set('ate', ate);
    if (marcadorId) p = p.set('marcador_id', marcadorId);
    return baixarArquivo(this.http, `${this.base}/relatorio?${p.toString()}`, `tarefas.${formato}`);
  }

  /** Equipes que o usuário enxerga. */
  equipes(): Observable<Equipe[]> {
    return this.http.get<Equipe[]>(`${this.base}/equipes`);
  }

  /** Cria (sem id) ou altera (com id) uma equipe, com líderes e membros. */
  salvarEquipe(dados: { nome: string; equipe_pai_id: string | null; lideres_ids: number[]; membros_ids: number[] }, id?: string) {
    return id ? this.http.put<Equipe>(`${this.base}/equipes/${id}`, dados) : this.http.post<Equipe>(`${this.base}/equipes`, dados);
  }

  /** Exclui uma equipe. */
  excluirEquipe(id: string) {
    return this.http.delete<void>(`${this.base}/equipes/${id}`);
  }

  // --- Marcos e status da equipe ---

  /** Marcos (entregas com data-alvo) da equipe. */
  marcos(equipeId: string): Observable<Marco[]> {
    return this.http.get<Marco[]>(`${this.base}/equipes/${equipeId}/marcos`);
  }

  /** Cria (sem id) ou altera (com id) um marco. */
  salvarMarco(equipeId: string, dados: { nome: string; descricao: string; data_alvo: string }, id?: string) {
    return id ? this.http.put<Marco>(`${this.base}/marcos/${id}`, dados) : this.http.post<Marco>(`${this.base}/equipes/${equipeId}/marcos`, dados);
  }

  /** Exclui um marco. */
  excluirMarco(id: string) {
    return this.http.delete<void>(`${this.base}/marcos/${id}`);
  }

  /** Marca o marco como atingido ou reabre (a rota muda conforme `atingido`). */
  atingirMarco(id: string, atingido: boolean) {
    return this.http.post<Marco>(`${this.base}/marcos/${id}/${atingido ? 'atingir' : 'reabrir'}`, null);
  }

  /** Liga a tarefa a um marco (ou desliga, com `null`). */
  definirMarco(numero: number, marcoId: string | null) {
    return this.http.put<TarefaDetalhe>(`${this.base}/${numero}/marco`, { marco_id: marcoId });
  }

  /** Histórico das atualizações de status publicadas pela equipe. */
  historicoStatus(equipeId: string): Observable<AtualizacaoStatus[]> {
    return this.http.get<AtualizacaoStatus[]>(`${this.base}/equipes/${equipeId}/status`);
  }

  /** Publica uma nova atualização de status da equipe (situação + texto). */
  publicarStatus(equipeId: string, situacao: string, texto: string) {
    return this.http.post<AtualizacaoStatus>(`${this.base}/equipes/${equipeId}/status`, { situacao, texto });
  }

  // --- Atividades agendadas e seguidores ---

  /** Atividades agendadas de uma tarefa (ligações, reuniões, lembretes). */
  atividadesDaTarefa(numero: number): Observable<Atividade[]> {
    return this.http.get<Atividade[]>(`${this.base}/${numero}/atividades`);
  }

  /** Atividades agendadas do usuário; `concluidas` traz as já feitas. */
  minhasAtividades(concluidas = false): Observable<Atividade[]> {
    return this.http.get<Atividade[]>(`${this.base}/atividades`, { params: { concluidas } });
  }

  /** Agenda uma atividade na tarefa para um responsável e prazo. */
  agendarAtividade(numero: number, dados: { resumo: string; tipo: string; nota: string; prazo: string | null; responsavel_id: number | null }) {
    return this.http.post<Atividade>(`${this.base}/${numero}/atividades`, dados);
  }

  /** Conclui a atividade com um retorno (feedback) em texto. */
  concluirAtividade(id: string, feedback: string) {
    return this.http.post<Atividade>(`${this.base}/atividades/${id}/concluir`, { feedback });
  }

  /** Exclui uma atividade agendada. */
  excluirAtividade(id: string) {
    return this.http.delete<void>(`${this.base}/atividades/${id}`);
  }

  /** Passa a seguir (POST) ou deixa de seguir (DELETE) a tarefa, para receber avisos. */
  seguir(numero: number, seguir: boolean) {
    return seguir ? this.http.post<TarefaDetalhe>(`${this.base}/${numero}/seguir`, null) : this.http.delete<TarefaDetalhe>(`${this.base}/${numero}/seguir`);
  }

  /** Cria uma subtarefa (herda equipe, marcadores, responsáveis e prazo da mãe quando não informados). */
  criarSubtarefa(numero: number, dados: { titulo: string; descricao?: string; prazo?: string; prioridade?: PrioridadeTarefa; responsaveis_ids?: number[]; bloqueada_por_numeros?: number[]; depende_da_anterior?: boolean }) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/subtarefas`, dados);
  }

  /** Substitui a lista de tarefas que bloqueiam esta (por número). */
  definirDependencias(numero: number, numeros: number[]) {
    return this.http.put<TarefaDetalhe>(`${this.base}/${numero}/dependencias`, { numeros });
  }

  /** "O que aconteceu": atividade diária da equipe (só a liderança). */
  atividadeDaEquipe(equipeId: string, filtros: { de: string; ate: string; pessoaId?: number | null; tipos?: string[]; busca?: string; automaticos?: boolean }): Observable<AtividadeDiaria> {
    let p = new HttpParams().set('de', filtros.de).set('ate', filtros.ate);
    if (filtros.pessoaId) p = p.set('pessoa_id', filtros.pessoaId);
    if (filtros.tipos?.length) p = p.set('tipos', filtros.tipos.join(','));
    if (filtros.busca?.trim()) p = p.set('busca', filtros.busca.trim());
    if (filtros.automaticos) p = p.set('automaticos', true);
    return this.http.get<AtividadeDiaria>(`${this.base}/equipes/${equipeId}/atividade`, { params: p });
  }

  /** Burndown, vazão, ciclo, fluxo acumulado e produtividade da equipe (só liderança). */
  desempenho(equipeId: string, de: string, ate: string, marcadorId = ''): Observable<DesempenhoEquipe> {
    let params = new HttpParams().set('de', de).set('ate', ate);
    if (marcadorId) params = params.set('marcador_id', marcadorId);
    return this.http.get<DesempenhoEquipe>(`${this.base}/equipes/${equipeId}/desempenho`, { params });
  }

  /** Os mesmos gráficos para uma pessoa (tarefas em que é responsável, inclusive as pessoais); vale para a própria pessoa, a liderança e o SuperRoot. */
  desempenhoPessoa(usuarioId: number, de: string, ate: string, marcadorId = ''): Observable<DesempenhoEquipe> {
    let params = new HttpParams().set('de', de).set('ate', ate);
    if (marcadorId) params = params.set('marcador_id', marcadorId);
    return this.http.get<DesempenhoEquipe>(`${this.base}/pessoas/${usuarioId}/desempenho`, { params });
  }

  // --- Tarefas recorrentes ---

  /** Texto da regra e as próximas datas de prazo (mesmo cálculo da geração). */
  previaRecorrencia(prazo: string, regra: RegraRecorrencia) {
    return this.http.post<{ resumo: string; proximas: string[] }>(`${this.base}/recorrencias/previa`, { prazo, regra });
  }

  /** Séries recorrentes da equipe ou, sem equipe, as pessoais. */
  recorrencias(equipeId: string | null): Observable<Recorrencia[]> {
    return this.http.get<Recorrencia[]>(`${this.base}/recorrencias`, { params: equipeId ? { equipe_id: equipeId } : {} });
  }

  /** Grava a série inteira; muda só as próximas ocorrências. */
  alterarRecorrencia(id: string, dados: {
    titulo: string; descricao: string; prioridade: PrioridadeTarefa; checklist: string[]; responsaveis_ids: number[]; marcadores_ids: string[];
    regra: RegraRecorrencia; hora_prazo?: string | null;
  }) {
    return this.http.put<Recorrencia>(`${this.base}/recorrencias/${id}`, dados);
  }

  /** Pausa a série (deixa de gerar tarefas). */
  pausarRecorrencia(id: string) {
    return this.http.post<Recorrencia>(`${this.base}/recorrencias/${id}/pausar`, null);
  }

  /** Retoma a série pausada. */
  retomarRecorrencia(id: string) {
    return this.http.post<Recorrencia>(`${this.base}/recorrencias/${id}/retomar`, null);
  }

  /** Exclui a série; as tarefas já criadas continuam. */
  excluirRecorrencia(id: string) {
    return this.http.delete<void>(`${this.base}/recorrencias/${id}`);
  }

  /** Marcadores da equipe (e globais), os mais usados primeiro; `busca` filtra por trecho do nome. */
  marcadores(equipeId: string, busca = '', limite = 100): Observable<Marcador[]> {
    return this.http.get<Marcador[]>(`${this.base}/equipes/${equipeId}/marcadores`, { params: { busca, limite } });
  }

  /** Cria o marcador na hora (nome repetido devolve o existente); sem cor, a API sorteia. */
  criarMarcador(equipeId: string, nome: string, corIndice?: number) {
    return this.http.post<Marcador>(`${this.base}/equipes/${equipeId}/marcadores`, { nome, cor_indice: corIndice ?? null });
  }

  /** Renomeia e/ou troca a cor (liderança). */
  alterarMarcador(equipeId: string, id: string, nome: string, corIndice: number) {
    return this.http.put<Marcador>(`${this.base}/equipes/${equipeId}/marcadores/${id}`, { nome, cor_indice: corIndice });
  }

  /** Exclui o marcador (liderança); ele sai de todas as tarefas. */
  excluirMarcador(id: string) {
    return this.http.delete<void>(`${this.base}/marcadores/${id}`);
  }

  // --- RDM (Requisição de Mudança) -----------------------------------------------------------------

  // RDM: Requisição de Mudança, formulário de aprovação de mudanças em
  // infraestrutura/sistemas no modelo da Prodesp.
  /** RDM da tarefa (ou um formulário pré-preenchido, se ainda não existir). */
  rdm(numero: number): Observable<RdmLeitura> {
    return this.http.get<RdmLeitura>(`${this.base}/${numero}/rdm`);
  }

  /** Salva o rascunho da RDM. */
  salvarRdm(numero: number, formulario: FormularioRdm): Observable<RdmLeitura> {
    return this.http.put<RdmLeitura>(`${this.base}/${numero}/rdm`, formulario);
  }

  /** Envia a RDM para aprovação da liderança (grava o formulário junto). */
  enviarRdm(numero: number, formulario: FormularioRdm): Observable<RdmLeitura> {
    return this.http.post<RdmLeitura>(`${this.base}/${numero}/rdm/enviar`, formulario);
  }

  /** Aprova a RDM (o backend gera o PDF e envia o e-mail). */
  aprovarRdm(numero: number): Observable<RdmLeitura> {
    return this.http.post<RdmLeitura>(`${this.base}/${numero}/rdm/aprovar`, {});
  }

  /** Reprova a RDM com o motivo informado. */
  reprovarRdm(numero: number, motivo: string): Observable<RdmLeitura> {
    return this.http.post<RdmLeitura>(`${this.base}/${numero}/rdm/reprovar`, { motivo });
  }

  /** Baixa o PDF da RDM aprovada com o nome informado. */
  pdfRdm(numero: number, nome: string) {
    return baixarArquivo(this.http, `${this.base}/${numero}/rdm/pdf`, nome);
  }

  /** RDMs enviadas das tarefas que a pessoa enxerga (`situacao` filtra). */
  rdms(situacao: string | null): Observable<RdmListada[]> {
    return this.http.get<RdmListada[]>(`${this.base}/rdms`, { params: situacao ? { situacao } : {} });
  }
}
