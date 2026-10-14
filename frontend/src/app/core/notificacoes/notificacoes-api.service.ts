// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API das notificações (/api/notificacoes).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import {
  CanalNotificacao, ConfiguracaoNotificacoes, Destinatarios, EntregaDetalhe, EntregaResumo, EnviadaDetalhe, EnviadaResumo, EnvioNotificacao, Obrigatoria,
  PainelEntregas, Pagina, Preferencias, ResumoCaixa, RespostaTeste, Silenciado, SituacaoNavegador,
} from './notificacoes.models';

@Injectable({ providedIn: 'root' })
export class NotificacoesApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/notificacoes`;

  /** Instalador do SGI SPI Alertas (Windows). */
  baixarClienteWindows(): Observable<unknown> {
    return baixarArquivo(this.http, `${this.base}/cliente-windows`, 'SgiSpiAlertas.msi');
  }

  resumo(): Observable<ResumoCaixa> {
    return this.http.get<ResumoCaixa>(`${this.base}/resumo`);
  }

  listar(estado: string, busca: string, pagina: number, tamanho = 20): Observable<Pagina<EntregaResumo>> {
    const params = new HttpParams().set('estado', estado).set('busca', busca).set('pagina', pagina).set('tamanho_pagina', tamanho);
    return this.http.get<Pagina<EntregaResumo>>(this.base, { params });
  }

  abrir(id: string): Observable<EntregaDetalhe> {
    return this.http.get<EntregaDetalhe>(`${this.base}/${id}`);
  }

  ciencia(id: string): Observable<EntregaDetalhe> {
    return this.http.post<EntregaDetalhe>(`${this.base}/${id}/ciencia`, {});
  }

  /** Prévia do e-mail da notificação (HTML no layout oficial, igual ao do changelog): `## título`, `- lista` e `**negrito**`. */
  previa(assunto: string, corpo: string, link: string | null, autorNome: string | null = null): Observable<string> {
    return this.http.post<{ html: string }>(`${this.base}/previa`, { assunto, corpo, link: link || null, autor_nome: autorNome }).pipe(map((r) => r.html));
  }

  /** Marca várias notificações de uma vez: lidas, não lidas ou cientes. */
  marcarLote(ids: string[], acao: 'lida' | 'nao_lida' | 'ciente'): Observable<{ atualizadas: number }> {
    return this.http.post<{ atualizadas: number }>(`${this.base}/lote`, { ids, acao });
  }

  destinatarios(): Observable<Destinatarios> {
    return this.http.get<Destinatarios>(`${this.base}/destinatarios`);
  }

  enviar(dados: EnvioNotificacao): Observable<{ notificacao_id: string; destinatarios: number }> {
    return this.http.post<{ notificacao_id: string; destinatarios: number }>(this.base, dados);
  }

  enviadas(pagina: number): Observable<Pagina<EnviadaResumo>> {
    return this.http.get<Pagina<EnviadaResumo>>(`${this.base}/enviadas`, { params: new HttpParams().set('pagina', pagina) });
  }

  enviada(id: string): Observable<EnviadaDetalhe> {
    return this.http.get<EnviadaDetalhe>(`${this.base}/enviadas/${id}`);
  }

  lembrar(id: string): Observable<{ lembrados: number }> {
    return this.http.post<{ lembrados: number }>(`${this.base}/enviadas/${id}/lembrar`, {});
  }

  // --- Preferências, navegador, silenciados e administração ---------------------------------------------------------

  preferencias(): Observable<Preferencias> {
    return this.http.get<Preferencias>(`${this.base}/preferencias`);
  }

  salvarPreferencias(canais: Record<string, CanalNotificacao[]>, configuracao: ConfiguracaoNotificacoes): Observable<Preferencias> {
    return this.http.put<Preferencias>(`${this.base}/preferencias`, { canais, configuracao });
  }

  inscreverNavegador(dados: { endpoint: string; p256dh: string; auth: string; rotulo: string }): Observable<SituacaoNavegador> {
    return this.http.post<SituacaoNavegador>(`${this.base}/navegador/inscricoes`, dados);
  }

  removerNavegador(endpoint: string): Observable<SituacaoNavegador> {
    return this.http.post<SituacaoNavegador>(`${this.base}/navegador/inscricoes/remover`, { endpoint });
  }

  testar(canal: CanalNotificacao): Observable<RespostaTeste> {
    return this.http.post<RespostaTeste>(`${this.base}/testar`, { canal });
  }

  silenciar(entregaId: string, tipo?: 'contrato' | 'tarefa'): Observable<Silenciado> {
    return this.http.post<Silenciado>(`${this.base}/silenciar`, { entrega_id: entregaId, tipo: tipo ?? null });
  }

  voltarAAvisar(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/silenciados/${id}`);
  }

  obrigatorias(): Observable<Obrigatoria[]> {
    return this.http.get<Obrigatoria[]>(`${this.base}/obrigatorias`);
  }

  criarObrigatoria(dados: { evento: string; canal: CanalNotificacao; setor_id?: number | null; usuario_id?: number | null }): Observable<Obrigatoria> {
    return this.http.post<Obrigatoria>(`${this.base}/obrigatorias`, dados);
  }

  removerObrigatoria(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/obrigatorias/${id}`);
  }

  painelEntregas(dias: number): Observable<PainelEntregas> {
    return this.http.get<PainelEntregas>(`${this.base}/painel-entregas`, { params: new HttpParams().set('dias', dias) });
  }
}
