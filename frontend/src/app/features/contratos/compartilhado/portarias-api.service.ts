// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API da portaria de designação do contrato e das autoridades signatárias.

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

  painel(contratoId: string): Observable<PainelPortarias> {
    return this.http.get<PainelPortarias>(`${this.base}/${contratoId}/portarias`);
  }

  /** Abre a portaria com as nomeações (função + usuário). */
  criar(contratoId: string, nomeacoes: NomeacaoEntrada[]): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias`, { nomeacoes });
  }

  alterarNomeacoes(contratoId: string, portariaId: string, nomeacoes: NomeacaoEntrada[]): Observable<PainelPortarias> {
    return this.http.put<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/nomeacoes`, { nomeacoes });
  }

  /** Com todos cientes: escolhe a autoridade, gera o texto e reserva o número no Protocolo. */
  escolherAutoridade(contratoId: string, portariaId: string, autoridadeId: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/autoridade`, { autoridade_id: autoridadeId });
  }

  aceitar(contratoId: string, portariaId: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/aceite`, {});
  }

  devolver(contratoId: string, portariaId: string, motivo: string): Observable<PainelPortarias> {
    return this.http.post<PainelPortarias>(`${this.base}/${contratoId}/portarias/${portariaId}/devolucao`, { motivo });
  }

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

  darCiencia(portariaId: string): Observable<CienciaPendente[]> {
    return this.http.post<CienciaPendente[]>(`${ambiente.urlApi}/portarias/${portariaId}/ciencia`, {});
  }

  autoridades(): Observable<AutoridadePortaria[]> {
    return this.http.get<AutoridadePortaria[]>(this.baseAutoridades);
  }

  /** Usuários ativos para escolher a autoridade (busca por nome ou login). */
  usuariosParaAutoridade(busca: string): Observable<UsuarioAutoridade[]> {
    return this.http.get<UsuarioAutoridade[]>(`${this.baseAutoridades}/usuarios`, { params: { busca } });
  }

  criarAutoridade(dados: GravacaoAutoridade): Observable<AutoridadePortaria[]> {
    return this.http.post<AutoridadePortaria[]>(this.baseAutoridades, dados);
  }

  alterarAutoridade(id: string, dados: GravacaoAutoridade): Observable<AutoridadePortaria[]> {
    return this.http.put<AutoridadePortaria[]>(`${this.baseAutoridades}/${id}`, dados);
  }

  excluirAutoridade(id: string): Observable<AutoridadePortaria[]> {
    return this.http.delete<AutoridadePortaria[]>(`${this.baseAutoridades}/${id}`);
  }
}
