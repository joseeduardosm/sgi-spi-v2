// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API do Módulo Tarefas.

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import {
  AcaoPipeline, AgendaPessoa, Equipe, EventoTarefa, FiltrosTarefas, LinhaDoTempo, ListaTarefas, Marcador, PessoaCarga, PrioridadeTarefa, TarefaDetalhe,
} from './tarefas.models';

export interface Escopo { tipo: 'minhas' | 'equipe' | 'pessoa'; equipeId?: string | null; login?: string | null }

@Injectable({ providedIn: 'root' })
export class TarefasApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/tarefas`;

  listar(escopo: Escopo, filtros: FiltrosTarefas): Observable<ListaTarefas> {
    let p = new HttpParams().set('escopo', escopo.tipo);
    if (escopo.equipeId) p = p.set('equipe_id', escopo.equipeId);
    if (escopo.login) p = p.set('login', escopo.login);
    for (const s of filtros.status) p = p.append('status', s);
    if (filtros.prioridade) p = p.set('prioridade', filtros.prioridade);
    if (filtros.marcador_id) p = p.set('marcador_id', filtros.marcador_id);
    if (filtros.responsavel_id) p = p.set('responsavel_id', filtros.responsavel_id);
    if (filtros.busca.trim()) p = p.set('busca', filtros.busca.trim());
    return this.http.get<ListaTarefas>(this.base, { params: p });
  }

  detalhe(numero: number): Observable<TarefaDetalhe> {
    return this.http.get<TarefaDetalhe>(`${this.base}/${numero}`);
  }

  criar(dados: {
    titulo: string; descricao: string; prazo: string; prioridade: PrioridadeTarefa; equipe_id: string | null;
    responsavel_id: number | null; participantes_ids: number[]; marcadores_ids: string[];
  }): Observable<TarefaDetalhe> {
    return this.http.post<TarefaDetalhe>(this.base, dados);
  }

  editar(numero: number, dados: { titulo: string; descricao: string; prioridade: PrioridadeTarefa; participantes_ids: number[]; marcadores_ids: string[]; versao: number }) {
    return this.http.put<TarefaDetalhe>(`${this.base}/${numero}`, dados);
  }

  prazo(numero: number, prazo: string, justificativa: string, versao: number) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/prazo`, { prazo, justificativa, versao });
  }

  mover(numero: number, acao: AcaoPipeline, texto = '', versao?: number) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/mover`, { acao, texto, versao });
  }

  transferir(numero: number, para_id: number, justificativa: string, novo_prazo: string | null, versao: number) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/transferir`, { para_id, justificativa, novo_prazo, versao });
  }

  comentar(numero: number, texto: string, arquivos: File[]): Observable<EventoTarefa> {
    const corpo = new FormData();
    corpo.append('texto', texto);
    for (const a of arquivos) corpo.append('arquivos', a);
    return this.http.post<EventoTarefa>(`${this.base}/${numero}/comentarios`, corpo);
  }

  linhaDoTempo(numero: number, filtro: string, antesDe: string | null): Observable<LinhaDoTempo> {
    let p = new HttpParams().set('limite', 30);
    if (filtro) p = p.set('filtro', filtro);
    if (antesDe) p = p.set('antes_de', antesDe);
    return this.http.get<LinhaDoTempo>(`${this.base}/${numero}/linha-do-tempo`, { params: p });
  }

  baixarAnexo(numero: number, anexoId: string, nome: string) {
    return baixarArquivo(this.http, `${this.base}/${numero}/anexos/${anexoId}`, nome);
  }

  removerEvento(numero: number, eventoId: string, motivo: string) {
    return this.http.post<EventoTarefa>(`${this.base}/${numero}/eventos/${eventoId}/remover`, { motivo });
  }

  checklist(numero: number, acao: 'incluir' | 'marcar' | 'remover', texto = '', item_id: string | null = null) {
    return this.http.post<TarefaDetalhe>(`${this.base}/${numero}/checklist`, { acao, texto, item_id });
  }

  excluir(numero: number) {
    return this.http.delete<void>(`${this.base}/${numero}`);
  }

  ordenar(numeros: number[]) {
    return this.http.post<void>(`${this.base}/ordem`, { numeros });
  }

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

  equipes(): Observable<Equipe[]> {
    return this.http.get<Equipe[]>(`${this.base}/equipes`);
  }

  salvarEquipe(dados: { nome: string; equipe_pai_id: string | null; lideres_ids: number[]; membros_ids: number[] }, id?: string) {
    return id ? this.http.put<Equipe>(`${this.base}/equipes/${id}`, dados) : this.http.post<Equipe>(`${this.base}/equipes`, dados);
  }

  excluirEquipe(id: string) {
    return this.http.delete<void>(`${this.base}/equipes/${id}`);
  }

  marcadores(equipeId: string): Observable<Marcador[]> {
    return this.http.get<Marcador[]>(`${this.base}/equipes/${equipeId}/marcadores`);
  }

  criarMarcador(equipeId: string, nome: string, cor: string) {
    return this.http.post<Marcador>(`${this.base}/equipes/${equipeId}/marcadores`, { nome, cor });
  }

  excluirMarcador(id: string) {
    return this.http.delete<void>(`${this.base}/marcadores/${id}`);
  }
}
