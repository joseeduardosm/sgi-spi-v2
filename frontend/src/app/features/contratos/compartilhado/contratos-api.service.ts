import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { OpcaoUsuario } from '../../../core/modelos/usuario.model';
import { baixarArquivo } from '../../../shared/utilitarios/download';
import {
  AlteracaoCampo,
  DetalheContrato,
  DetalheEmpresa,
  DocumentoContrato,
  EstadoMigracaoSgi,
  GravacaoContrato,
  GravacaoEmpresa,
  GravacaoPreposto,
  Modelo,
  NotaEmpenho,
  OpcaoEmpresa,
  Pagina,
  PainelContratos,
  Previsao,
  ResumoContrato,
  ResumoEmpresa,
} from './contratos.models';

/** Contratos, empresas, orçamento, painel, relatórios e modelos (docs/endpoints/contratos-*.md). */
@Injectable({ providedIn: 'root' })
export class ContratosApiService {
  private readonly http = inject(HttpClient);
  readonly base = `${ambiente.urlApi}/contratos`;

  // --- Carteira e contrato ---
  listar(busca: string, pagina: number, tamanhoPagina: number): Observable<Pagina<ResumoContrato>> {
    const params = new HttpParams().set('busca', busca).set('pagina', pagina).set('tamanho_pagina', tamanhoPagina);
    return this.http.get<Pagina<ResumoContrato>>(this.base, { params });
  }

  consultar(id: string): Observable<DetalheContrato> {
    return this.http.get<DetalheContrato>(`${this.base}/${id}`);
  }

  criar(dados: GravacaoContrato): Observable<DetalheContrato> {
    return this.http.post<DetalheContrato>(this.base, dados);
  }

  alterar(id: string, dados: GravacaoContrato): Observable<DetalheContrato> {
    return this.http.put<DetalheContrato>(`${this.base}/${id}`, dados);
  }

  excluir(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  proximoNumero(ano: number): Observable<{ numero: string }> {
    return this.http.get<{ numero: string }>(`${this.base}/proximo-numero`, { params: { ano } });
  }

  /** Fonte do seletor de usuários da equipe (não exige acesso ao módulo Usuários). */
  readonly opcoesUsuarios = (busca: string): Observable<OpcaoUsuario[]> =>
    this.http.get<OpcaoUsuario[]>(`${this.base}/opcoes-usuarios`, { params: { busca, limite: 20 } });

  historico(id: string): Observable<AlteracaoCampo[]> {
    return this.http.get<AlteracaoCampo[]>(`${this.base}/${id}/historico`);
  }

  // --- Documentos importantes ---
  documentos(id: string): Observable<DocumentoContrato[]> {
    return this.http.get<DocumentoContrato[]>(`${this.base}/${id}/documentos`);
  }

  enviarDocumento(id: string, codigo: number, arquivo: File): Observable<DocumentoContrato[]> {
    const dados = new FormData();
    dados.append('arquivo', arquivo);
    return this.http.post<DocumentoContrato[]>(`${this.base}/${id}/documentos/${codigo}`, dados);
  }

  baixarDocumento(id: string, codigo: number) {
    return baixarArquivo(this.http, `${this.base}/${id}/documentos/${codigo}/arquivo`);
  }

  // --- Previsão e NEs ---
  previsao(id: string): Observable<Previsao> {
    return this.http.get<Previsao>(`${this.base}/${id}/previsao`);
  }

  salvarPrevisao(id: string, vigencia: number, apontamentos: { item_id: string; competencia: string; quantidade: string }[]): Observable<Previsao> {
    return this.http.put<Previsao>(`${this.base}/${id}/previsao/${vigencia}`, { apontamentos });
  }

  exportarPrevisao(id: string, vigencia: number) {
    return baixarArquivo(this.http, `${this.base}/${id}/previsao/${vigencia}/xlsx`, 'previsao.xlsx');
  }

  notas(id: string): Observable<NotaEmpenho[]> {
    return this.http.get<NotaEmpenho[]>(`${this.base}/${id}/notas-empenho`);
  }

  salvarNota(id: string, dados: { numero: string; valor_original: string }, notaId?: string): Observable<NotaEmpenho[]> {
    return notaId
      ? this.http.put<NotaEmpenho[]>(`${this.base}/${id}/notas-empenho/${notaId}`, dados)
      : this.http.post<NotaEmpenho[]>(`${this.base}/${id}/notas-empenho`, dados);
  }

  excluirNota(id: string, notaId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/notas-empenho/${notaId}`);
  }

  // --- Empresas ---
  empresas(busca: string, ordenar: string, direcao: string, pagina: number, tamanhoPagina: number): Observable<Pagina<ResumoEmpresa>> {
    const params = new HttpParams()
      .set('busca', busca).set('ordenar', ordenar).set('direcao', direcao).set('pagina', pagina).set('tamanho_pagina', tamanhoPagina);
    return this.http.get<Pagina<ResumoEmpresa>>(`${this.base}/empresas`, { params });
  }

  opcoesEmpresas(incluirInativas = false): Observable<OpcaoEmpresa[]> {
    return this.http.get<OpcaoEmpresa[]>(`${this.base}/empresas/opcoes`, { params: { incluir_inativas: incluirInativas } });
  }

  empresa(id: string): Observable<DetalheEmpresa> {
    return this.http.get<DetalheEmpresa>(`${this.base}/empresas/${id}`);
  }

  salvarEmpresa(dados: GravacaoEmpresa, id?: string): Observable<DetalheEmpresa> {
    return id ? this.http.put<DetalheEmpresa>(`${this.base}/empresas/${id}`, dados) : this.http.post<DetalheEmpresa>(`${this.base}/empresas`, dados);
  }

  excluirEmpresa(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/empresas/${id}`);
  }

  salvarPreposto(empresaId: string, dados: GravacaoPreposto, prepostoId?: string): Observable<DetalheEmpresa> {
    const url = `${this.base}/empresas/${empresaId}/prepostos`;
    return prepostoId ? this.http.put<DetalheEmpresa>(`${url}/${prepostoId}`, dados) : this.http.post<DetalheEmpresa>(url, dados);
  }

  excluirPreposto(empresaId: string, prepostoId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/empresas/${empresaId}/prepostos/${prepostoId}`);
  }

  // --- Painel, relatórios e modelos ---
  painel(filtros: { exercicio?: number; empresa_id?: string; contrato_id?: string }): Observable<PainelContratos> {
    let params = new HttpParams();
    for (const [chave, valor] of Object.entries(filtros)) if (valor) params = params.set(chave, valor);
    return this.http.get<PainelContratos>(`${this.base}/painel`, { params });
  }

  relatorioNotas(formato: 'xlsx' | 'pdf') {
    return baixarArquivo(this.http, `${this.base}/relatorios/notas-empenho?formato=${formato}`);
  }

  relatorioPrevisao(parametros: Record<string, string | number | boolean>) {
    const params = new HttpParams({ fromObject: Object.fromEntries(Object.entries(parametros).map(([k, v]) => [k, String(v)])) });
    return baixarArquivo(this.http, `${this.base}/relatorios/previsao-orcamentaria?${params.toString()}`);
  }

  modelos(tipo?: 'checklist' | 'formulario', somenteAtivos = true): Observable<Modelo[]> {
    let params = new HttpParams().set('somente_ativos', somenteAtivos);
    if (tipo) params = params.set('tipo', tipo);
    return this.http.get<Modelo[]>(`${this.base}/modelos`, { params });
  }

  salvarModelo(dados: unknown, id?: string): Observable<Modelo> {
    return id ? this.http.put<Modelo>(`${this.base}/modelos/${id}`, dados) : this.http.post<Modelo>(`${this.base}/modelos`, dados);
  }

  excluirModelo(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/modelos/${id}`);
  }

  // --- Importação do SGI (SuperRoot) ---
  estadoMigracaoSgi(): Observable<EstadoMigracaoSgi> {
    return this.http.get<EstadoMigracaoSgi>(`${this.base}/migracao-sgi`);
  }

  iniciarMigracaoSgi(senhaOrigem: string, senhaDestino: string): Observable<EstadoMigracaoSgi> {
    return this.http.post<EstadoMigracaoSgi>(`${this.base}/migracao-sgi`, { senha_origem: senhaOrigem, senha_destino: senhaDestino });
  }
}
