// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API de Contratações (/api/contratacoes).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { baixarArquivo } from '../../shared/utilitarios/download';
import {
  Alteracoes, Conferencia, DocumentoContratacao, DocumentoResumo, EntradaHistorico, ListaDocumentos, Membro, PainelContratacoes, PreviaImportacao, PreviaLote, Situacao,
  TipoDocumento, TipoItem, Versao, VersaoDetalhe,
} from './contratacoes.models';

@Injectable({ providedIn: 'root' })
export class ContratacoesApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/contratacoes`;
  private readonly doc = (id: string) => `${this.base}/documentos/${id}`;

  painel(): Observable<PainelContratacoes> {
    return this.http.get<PainelContratacoes>(`${this.base}/painel`);
  }

  listar(filtros: { tipo?: string; situacao?: string; busca?: string }): Observable<ListaDocumentos> {
    let params = new HttpParams();
    for (const [chave, valor] of Object.entries(filtros)) if (valor) params = params.set(chave, valor);
    return this.http.get<ListaDocumentos>(`${this.base}/documentos`, { params });
  }

  doContrato(contratoId: string): Observable<DocumentoResumo[]> {
    return this.http.get<DocumentoResumo[]>(`${this.base}/por-contrato/${contratoId}`);
  }

  criar(dados: { tipo: TipoDocumento; nome: string; processo: string; link_sei: string | null }): Observable<DocumentoContratacao> {
    return this.http.post<DocumentoContratacao>(`${this.base}/documentos`, dados);
  }

  abrir(id: string): Observable<DocumentoContratacao> {
    return this.http.get<DocumentoContratacao>(this.doc(id));
  }

  alterar(id: string, dados: { nome: string; processo: string; link_sei: string | null }): Observable<DocumentoContratacao> {
    return this.http.put<DocumentoContratacao>(this.doc(id), dados);
  }

  excluir(id: string): Observable<void> {
    return this.http.delete<void>(this.doc(id));
  }

  duplicar(id: string): Observable<DocumentoContratacao> {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/duplicar`, {});
  }

  situacao(id: string, situacao: Situacao, confirmar: boolean): Observable<DocumentoContratacao> {
    return this.http.put<DocumentoContratacao>(`${this.doc(id)}/situacao`, { situacao, confirmar });
  }

  conferencia(id: string): Observable<Conferencia> {
    return this.http.get<Conferencia>(`${this.doc(id)}/conferencia`);
  }

  vincular(id: string, contratoId: string | null): Observable<DocumentoContratacao> {
    return this.http.put<DocumentoContratacao>(`${this.doc(id)}/contrato`, { contrato_id: contratoId });
  }

  compartilhar(id: string, usuarioId: number, papel: 'editor' | 'revisor'): Observable<Membro[]> {
    return this.http.put<Membro[]>(`${this.doc(id)}/membros/${usuarioId}`, { papel });
  }

  descompartilhar(id: string, usuarioId: number): Observable<Membro[]> {
    return this.http.delete<Membro[]>(`${this.doc(id)}/membros/${usuarioId}`);
  }

  readonly opcoesUsuarios = (busca: string): Observable<OpcaoUsuario[]> =>
    this.http.get<OpcaoUsuario[]>(`${this.base}/opcoes-usuarios`, { params: new HttpParams().set('busca', busca) });

  // Seções
  criarSecao(id: string, titulo: string) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/secoes`, { titulo });
  }
  renomearSecao(id: string, secaoId: string, titulo: string) {
    return this.http.put<DocumentoContratacao>(`${this.doc(id)}/secoes/${secaoId}`, { titulo });
  }
  excluirSecao(id: string, secaoId: string) {
    return this.http.delete<DocumentoContratacao>(`${this.doc(id)}/secoes/${secaoId}`);
  }
  moverSecao(id: string, secaoId: string, ordem: number) {
    return this.http.put<DocumentoContratacao>(`${this.doc(id)}/secoes/${secaoId}/ordem`, { ordem });
  }

  // Itens
  criarItem(id: string, dados: { secao_id: string; pai_id: string | null; tipo: TipoItem; conteudo?: string; conteudo_html?: string; posicao?: number }) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/itens`, dados);
  }
  editarItem(id: string, itemId: string, dados: { tipo?: TipoItem; conteudo?: string; conteudo_html?: string; precisa_revisao?: boolean }) {
    return this.http.put<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}`, dados);
  }
  excluirItem(id: string, itemId: string) {
    return this.http.delete<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}`);
  }
  moverItem(id: string, itemId: string, dados: { secao_id: string; pai_id: string | null; ordem: number }) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}/mover`, dados);
  }
  duplicarItem(id: string, itemId: string) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}/duplicar`, {});
  }
  limparFilhos(id: string, itemId: string) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}/limpar-filhos`, {});
  }
  previaLote(id: string, dados: { secao_id: string; pai_id: string | null; texto: string }) {
    return this.http.post<PreviaLote>(`${this.doc(id)}/lote/previa`, dados);
  }
  criarLote(id: string, dados: { secao_id: string; pai_id: string | null; texto: string }) {
    return this.http.post<{ criados: number }>(`${this.doc(id)}/lote`, dados);
  }
  incluirLinhaTr(id: string, itemId: string, dados: Record<string, string>) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}/linhas-tr`, dados);
  }
  excluirLinhaTr(id: string, linhaId: string) {
    return this.http.delete<DocumentoContratacao>(`${this.doc(id)}/linhas-tr/${linhaId}`);
  }

  // Revisões
  criarRevisao(id: string, itemId: string, dados: { comentario: string; conteudo_proposto_html?: string | null }) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}/revisoes`, dados);
  }
  aplicarRevisao(id: string, itemId: string, revisaoId: string) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}/revisoes/${revisaoId}/aplicar`, {});
  }
  resolverRevisao(id: string, itemId: string, revisaoId: string, resolvida: boolean) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/itens/${itemId}/revisoes/${revisaoId}/resolver`, { resolvida });
  }

  // Versões e histórico
  versoes(id: string): Observable<Versao[]> {
    return this.http.get<Versao[]>(`${this.doc(id)}/versoes`);
  }
  salvarVersao(id: string, resumo: string): Observable<Versao> {
    return this.http.post<Versao>(`${this.doc(id)}/versoes`, { resumo });
  }
  versao(id: string, numero: number): Observable<VersaoDetalhe> {
    return this.http.get<VersaoDetalhe>(`${this.doc(id)}/versoes/${numero}`);
  }
  alteracoes(id: string, numero: number, contra?: number): Observable<Alteracoes> {
    let params = new HttpParams();
    if (contra) params = params.set('contra', contra);
    return this.http.get<Alteracoes>(`${this.doc(id)}/versoes/${numero}/alteracoes`, { params });
  }
  restaurarVersao(id: string, numero: number) {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/versoes/${numero}/restaurar`, {});
  }
  historicoItem(id: string, itemId: string): Observable<EntradaHistorico[]> {
    return this.http.get<EntradaHistorico[]>(`${this.doc(id)}/itens/${itemId}/historico`);
  }
  restaurarItem(id: string, historicoId: string, estado: 'antes' | 'depois') {
    return this.http.post<DocumentoContratacao>(`${this.doc(id)}/historico/${historicoId}/restaurar`, { estado });
  }

  // Exportar e importar
  exportar(id: string, formato: 'word' | 'pdf', nome: string) {
    return baixarArquivo(this.http, `${this.doc(id)}/exportar/${formato}`, `${nome}.${formato === 'word' ? 'docx' : 'pdf'}`);
  }
  importarWord(arquivo: File, dados: { tipo: TipoDocumento; nome: string; processo: string; confirmar: boolean }): Observable<PreviaImportacao> {
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    corpo.append('tipo', dados.tipo);
    corpo.append('nome', dados.nome);
    corpo.append('processo', dados.processo);
    corpo.append('confirmar', String(dados.confirmar));
    return this.http.post<PreviaImportacao>(`${this.base}/importar-word`, corpo);
  }
}
