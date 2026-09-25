// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de contratos, empresas, orçamento, painel, relatórios e modelos.

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
  /** Carteira paginada, com busca livre. */
  listar(busca: string, pagina: number, tamanhoPagina: number): Observable<Pagina<ResumoContrato>> {
    const params = new HttpParams().set('busca', busca).set('pagina', pagina).set('tamanho_pagina', tamanhoPagina);
    return this.http.get<Pagina<ResumoContrato>>(this.base, { params });
  }

  /** Detalhe completo do contrato. */
  consultar(id: string): Observable<DetalheContrato> {
    return this.http.get<DetalheContrato>(`${this.base}/${id}`);
  }

  /** Cadastra um contrato. */
  criar(dados: GravacaoContrato): Observable<DetalheContrato> {
    return this.http.post<DetalheContrato>(this.base, dados);
  }

  /** Altera um contrato (a `versao` enviada precisa ser a atual; senão, 409). */
  alterar(id: string, dados: GravacaoContrato): Observable<DetalheContrato> {
    return this.http.put<DetalheContrato>(`${this.base}/${id}`, dados);
  }

  /** Exclui um contrato (exige controle total). */
  excluir(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  /** Próximo número livre do ano, sugerido no cadastro. */
  proximoNumero(ano: number): Observable<{ numero: string }> {
    return this.http.get<{ numero: string }>(`${this.base}/proximo-numero`, { params: { ano } });
  }

  /** Fonte do seletor de usuários da equipe (não exige acesso ao módulo Usuários). */
  readonly opcoesUsuarios = (busca: string): Observable<OpcaoUsuario[]> =>
    this.http.get<OpcaoUsuario[]>(`${this.base}/opcoes-usuarios`, { params: { busca, limite: 20 } });

  /** Histórico de alterações campo a campo. */
  historico(id: string): Observable<AlteracaoCampo[]> {
    return this.http.get<AlteracaoCampo[]>(`${this.base}/${id}/historico`);
  }

  // --- Documentos importantes ---
  /** Catálogo de documentos importantes, anexados ou não. */
  documentos(id: string): Observable<DocumentoContrato[]> {
    return this.http.get<DocumentoContrato[]>(`${this.base}/${id}/documentos`);
  }

  /** Anexa um PDF a um documento do catálogo (envio como formulário multipart). */
  enviarDocumento(id: string, codigo: number, arquivo: File): Observable<DocumentoContrato[]> {
    const dados = new FormData();
    dados.append('arquivo', arquivo);
    return this.http.post<DocumentoContrato[]>(`${this.base}/${id}/documentos/${codigo}`, dados);
  }

  /** Baixa o PDF de um documento importante. */
  baixarDocumento(id: string, codigo: number) {
    return baixarArquivo(this.http, `${this.base}/${id}/documentos/${codigo}/arquivo`);
  }

  // --- Previsão e NEs ---
  /** Previsão orçamentária de todas as vigências. */
  previsao(id: string): Observable<Previsao> {
    return this.http.get<Previsao>(`${this.base}/${id}/previsao`);
  }

  /** Grava a grade de apontamentos de uma vigência (e sela a previsão). */
  salvarPrevisao(id: string, vigencia: number, apontamentos: { item_id: string; competencia: string; quantidade: string }[]): Observable<Previsao> {
    return this.http.put<Previsao>(`${this.base}/${id}/previsao/${vigencia}`, { apontamentos });
  }

  /** Baixa a planilha da previsão de uma vigência. */
  exportarPrevisao(id: string, vigencia: number) {
    return baixarArquivo(this.http, `${this.base}/${id}/previsao/${vigencia}/xlsx`, 'previsao.xlsx');
  }

  /** Notas de Empenho do contrato. */
  notas(id: string): Observable<NotaEmpenho[]> {
    return this.http.get<NotaEmpenho[]>(`${this.base}/${id}/notas-empenho`);
  }

  /** Cadastra (sem notaId) ou altera (com notaId) uma NE. */
  salvarNota(id: string, dados: { numero: string; valor_original: string }, notaId?: string): Observable<NotaEmpenho[]> {
    return notaId
      ? this.http.put<NotaEmpenho[]>(`${this.base}/${id}/notas-empenho/${notaId}`, dados)
      : this.http.post<NotaEmpenho[]>(`${this.base}/${id}/notas-empenho`, dados);
  }

  /** Exclui uma NE nunca usada. */
  excluirNota(id: string, notaId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/notas-empenho/${notaId}`);
  }

  // --- Empresas ---
  /** Lista paginada de empresas, com busca e ordenação no servidor. */
  empresas(busca: string, ordenar: string, direcao: string, pagina: number, tamanhoPagina: number): Observable<Pagina<ResumoEmpresa>> {
    const params = new HttpParams()
      .set('busca', busca).set('ordenar', ordenar).set('direcao', direcao).set('pagina', pagina).set('tamanho_pagina', tamanhoPagina);
    return this.http.get<Pagina<ResumoEmpresa>>(`${this.base}/empresas`, { params });
  }

  /** Empresas para o seletor do cadastro de contrato. */
  opcoesEmpresas(incluirInativas = false): Observable<OpcaoEmpresa[]> {
    return this.http.get<OpcaoEmpresa[]>(`${this.base}/empresas/opcoes`, { params: { incluir_inativas: incluirInativas } });
  }

  /** Detalhe de uma empresa. */
  empresa(id: string): Observable<DetalheEmpresa> {
    return this.http.get<DetalheEmpresa>(`${this.base}/empresas/${id}`);
  }

  /** Cadastra (sem id) ou altera (com id) uma empresa. */
  salvarEmpresa(dados: GravacaoEmpresa, id?: string): Observable<DetalheEmpresa> {
    return id ? this.http.put<DetalheEmpresa>(`${this.base}/empresas/${id}`, dados) : this.http.post<DetalheEmpresa>(`${this.base}/empresas`, dados);
  }

  /** Exclui uma empresa sem contratos. */
  excluirEmpresa(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/empresas/${id}`);
  }

  /** Cadastra (sem prepostoId) ou altera (com prepostoId) um preposto. */
  salvarPreposto(empresaId: string, dados: GravacaoPreposto, prepostoId?: string): Observable<DetalheEmpresa> {
    const url = `${this.base}/empresas/${empresaId}/prepostos`;
    return prepostoId ? this.http.put<DetalheEmpresa>(`${url}/${prepostoId}`, dados) : this.http.post<DetalheEmpresa>(url, dados);
  }

  /** Exclui um preposto. */
  excluirPreposto(empresaId: string, prepostoId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/empresas/${empresaId}/prepostos/${prepostoId}`);
  }

  // --- Painel, relatórios e modelos ---
  /** Dados do painel; só os filtros preenchidos vão na URL. */
  painel(filtros: { exercicio?: number; empresa_id?: string; contrato_id?: string }): Observable<PainelContratos> {
    let params = new HttpParams();
    for (const [chave, valor] of Object.entries(filtros)) if (valor) params = params.set(chave, valor);
    return this.http.get<PainelContratos>(`${this.base}/painel`, { params });
  }

  /** Baixa o relatório executivo de NEs (SuperRoot). */
  relatorioNotas(formato: 'xlsx' | 'pdf') {
    return baixarArquivo(this.http, `${this.base}/relatorios/notas-empenho?formato=${formato}`);
  }

  /** Baixa a previsão orçamentária consolidada com os cenários escolhidos (SuperRoot). */
  relatorioPrevisao(parametros: Record<string, string | number | boolean>) {
    const params = new HttpParams({ fromObject: Object.fromEntries(Object.entries(parametros).map(([k, v]) => [k, String(v)])) });
    return baixarArquivo(this.http, `${this.base}/relatorios/previsao-orcamentaria?${params.toString()}`);
  }

  /** Modelos globais, opcionalmente de um tipo. */
  modelos(tipo?: 'checklist' | 'formulario', somenteAtivos = true): Observable<Modelo[]> {
    let params = new HttpParams().set('somente_ativos', somenteAtivos);
    if (tipo) params = params.set('tipo', tipo);
    return this.http.get<Modelo[]>(`${this.base}/modelos`, { params });
  }

  /** Cria (sem id) ou altera (com id) um modelo global. */
  salvarModelo(dados: unknown, id?: string): Observable<Modelo> {
    return id ? this.http.put<Modelo>(`${this.base}/modelos/${id}`, dados) : this.http.post<Modelo>(`${this.base}/modelos`, dados);
  }

  /** Exclui um modelo global. */
  excluirModelo(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/modelos/${id}`);
  }

  // --- Importação do SGI (SuperRoot) ---
  /** Andamento da importação do SGI. */
  estadoMigracaoSgi(): Observable<EstadoMigracaoSgi> {
    return this.http.get<EstadoMigracaoSgi>(`${this.base}/migracao-sgi`);
  }

  /** Inicia a importação do SGI com as senhas informadas (não são guardadas). */
  iniciarMigracaoSgi(senhaOrigem: string, senhaDestino: string): Observable<EstadoMigracaoSgi> {
    return this.http.post<EstadoMigracaoSgi>(`${this.base}/migracao-sgi`, { senha_origem: senhaOrigem, senha_destino: senhaDestino });
  }
}
