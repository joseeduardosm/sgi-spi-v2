/**
 * =============================================================================
 * ARQUIVO: portarias-api.service.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Centralizar as chamadas à API da portaria de designação da equipe do
 * contrato e do cadastro das autoridades signatárias.
 *
 * RESUMO TÉCNICO:
 * Serviço Angular (providedIn root) com HttpClient. Cada método devolve um
 * Observable com o painel de portarias atualizado (ou a lista de autoridades
 * e ciências); a publicação envia o PDF por FormData e a evidência é baixada
 * com baixarArquivo().
 *
 * FINALIDADE DE NEGÓCIO:
 * Apoia o fluxo de designação de gestor e fiscais: nomeações, ciência de cada
 * nomeado, escolha da autoridade que assina, aceite ou devolução, número
 * reservado no Protocolo e publicação no Diário Oficial (D.O.E.), com PDF de
 * evidência para juntar ao processo no SEI.
 *
 * CONTEXTO NO SISTEMA:
 * Usado por portarias-equipe.component.ts, janela-ciencia-nomeacao e pela
 * tela de autoridades. Contrato da API em docs/endpoints/contratos-portarias.md.
 *
 * =============================================================================
 */

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { baixarArquivo } from '../../../shared/utilitarios/download';
import { AutoridadePortaria, CienciaPendente, GravacaoAutoridade, NomeacaoEntrada, PainelPortarias, UsuarioAutoridade } from './contratos.models';

/** Portarias do contrato e autoridades (docs/endpoints/contratos-portarias.md). */
@Injectable({ providedIn: 'root' })
export class PortariasApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/contratos`;
  private readonly baseAutoridades = `${ambiente.urlApi}/portarias/autoridades`;

  /** Painel de portarias do contrato: a em andamento, o histórico e a equipe atual. */
  painel(contratoId: string): Observable<PainelPortarias> {
    return this.http.get<PainelPortarias>(`${this.base}/${contratoId}/portarias`);
  }

  /** Abre a portaria com as nomeações (função + usuário). */
  criar(contratoId: string, nomeacoes: NomeacaoEntrada[]): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias`, { nomeacoes });
  }

  /** Troca as nomeações de uma portaria ainda em andamento. */
  alterarNomeacoes(contratoId: string, portariaId: string, nomeacoes: NomeacaoEntrada[]): Observable<PainelPortarias> {
    return this.http.put<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/nomeacoes`, { nomeacoes });
  }

  /** Com todos cientes: escolhe a autoridade, gera o texto e reserva o número no Protocolo. */
  escolherAutoridade(contratoId: string, portariaId: string, autoridadeId: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/autoridade`, { autoridade_id: autoridadeId });
  }

  /** Aceite da portaria pela autoridade escolhida. */
  aceitar(contratoId: string, portariaId: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/aceite`, {});
  }

  /** Devolve a portaria para ajuste, com motivo obrigatório. */
  devolver(contratoId: string, portariaId: string, motivo: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/devolucao`, { motivo });
  }

  /** Cancela a portaria em andamento, com motivo. */
  cancelar(contratoId: string, portariaId: string, motivo: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/cancelamento`, { motivo });
  }

  /** Publica a portaria anexando o PDF do D.O.E. ao número reservado (sem precisar do módulo Protocolo): aplica a nova equipe. */
  publicar(contratoId: string, portariaId: string, arquivo: File): Observable<PainelPortarias> {
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/publicacao`, corpo);
  }

  /** Baixa o PDF de evidência (ciências e aceite), para juntar ao SEI. */
  baixarEvidencia(contratoId: string, portariaId: string) {
    return baixarArquivo(this.http, `${this.base}/${contratoId}/portarias/${portariaId}/evidencia`, 'evidencia-portaria.pdf');
  }

  /** Nomeações do usuário logado aguardando a ciência dele. */
  ciencias(): Observable<CienciaPendente[]> {
    return this.http.get<CienciaPendente[]>(`${ambiente.urlApi}/portarias/ciencias`);
  }

  /** Registra a ciência do usuário logado; devolve as pendências que sobraram. */
  darCiencia(portariaId: string): Observable<CienciaPendente[]> {
    return this.http.post<CienciaPendente[]>(`${ambiente.urlApi}/portarias/${portariaId}/ciencia`, {});
  }

  /** Autoridades cadastradas que podem assinar portarias. */
  autoridades(): Observable<AutoridadePortaria[]> {
    return this.http.get<AutoridadePortaria[]>(this.baseAutoridades);
  }

  /** Usuários ativos para escolher a autoridade (busca por nome ou login). */
  usuariosParaAutoridade(busca: string): Observable<UsuarioAutoridade[]> {
    return this.http.get<UsuarioAutoridade[]>(`${this.baseAutoridades}/usuarios`, { params: { busca } });
  }

  /** Cadastra uma autoridade; devolve a lista atualizada. */
  criarAutoridade(dados: GravacaoAutoridade): Observable<AutoridadePortaria[]> {
    return this.http.post<AutoridadePortaria[]>(this.baseAutoridades, dados);
  }

  /** Altera os dados de uma autoridade; devolve a lista atualizada. */
  alterarAutoridade(id: string, dados: GravacaoAutoridade): Observable<AutoridadePortaria[]> {
    return this.http.put<AutoridadePortaria[]>(`${this.baseAutoridades}/${id}`, dados);
  }

  /** Exclui uma autoridade; devolve a lista atualizada. */
  excluirAutoridade(id: string): Observable<AutoridadePortaria[]> {
    return this.http.delete<AutoridadePortaria[]>(`${this.baseAutoridades}/${id}`);
  }
}
