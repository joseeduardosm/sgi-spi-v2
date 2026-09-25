// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de prorrogação, reajuste e aditamento/supressão.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { baixarArquivo } from '../../../shared/utilitarios/download';
import { CamposParecer, PainelAlteracao, PainelReajuste, ProcessoProrrogacao, Prorrogacao, RegraSobDemanda } from './contratos.models';

/** Corpo do rascunho da prorrogação (prazo, plano dos itens sob demanda e campos do parecer). */
export interface GravacaoProrrogacao extends CamposParecer {
  meses: number | null;
  regra_sob_demanda: RegraSobDemanda;
  plano_sob_demanda: { item_id: string; limite: string; apontamentos: Record<string, string> }[];
}

/** Prorrogação, reajuste e aditamento/supressão (docs/endpoints/contratos-alteracoes.md). */
@Injectable({ providedIn: 'root' })
export class AlteracoesApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/contratos`;

  /** Monta um FormData (multipart) para os envios com PDF. */
  private arquivo(campos: Record<string, string | File>): FormData {
    const dados = new FormData();
    for (const [chave, valor] of Object.entries(campos)) dados.append(chave, valor);
    return dados;
  }

  // --- Prorrogação ---
  /** Rascunho da prorrogação (ou os dados para começar um). */
  prorrogacao(id: string): Observable<ProcessoProrrogacao> {
    return this.http.get<ProcessoProrrogacao>(`${this.base}/${id}/prorrogacao`);
  }

  /** Salva o rascunho da prorrogação. */
  salvarProrrogacao(id: string, dados: GravacaoProrrogacao): Observable<ProcessoProrrogacao> {
    return this.http.put<ProcessoProrrogacao>(`${this.base}/${id}/prorrogacao`, dados);
  }

  /** Descarta o rascunho da prorrogação. */
  descartarProrrogacao(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}/prorrogacao`);
  }

  /** Registra ciência no parecer ou gera o PDF do parecer. */
  acaoProrrogacao(id: string, acao: 'ciencia' | 'parecer'): Observable<ProcessoProrrogacao> {
    return this.http.post<ProcessoProrrogacao>(`${this.base}/${id}/prorrogacao/${acao}`, {});
  }

  /** Registra a prorrogação com o Termo Aditivo assinado. */
  registrarProrrogacao(id: string, assinadaEm: string, numeroTermo: string, termo: File): Observable<Prorrogacao[]> {
    return this.http.post<Prorrogacao[]>(`${this.base}/${id}/prorrogacao/registrar`,
      this.arquivo({ assinada_em: assinadaEm, numero_termo: numeroTermo, termo }));
  }

  /** Prorrogações já registradas. */
  prorrogacoes(id: string): Observable<Prorrogacao[]> {
    return this.http.get<Prorrogacao[]>(`${this.base}/${id}/prorrogacoes`);
  }

  /** Desfaz a última prorrogação. */
  desfazerProrrogacao(id: string, prorrogacaoId: string): Observable<Prorrogacao[]> {
    return this.http.delete<Prorrogacao[]>(`${this.base}/${id}/prorrogacoes/${prorrogacaoId}`);
  }

  /** Baixa o termo ou o parecer de uma prorrogação. */
  baixarProrrogacao(id: string, anexoId: string) {
    return baixarArquivo(this.http, `${this.base}/${id}/prorrogacoes/arquivos/${anexoId}`);
  }

  // --- Reajuste ---
  /** Reajuste em elaboração, vigências disponíveis e histórico. */
  reajustes(id: string): Observable<PainelReajuste> {
    return this.http.get<PainelReajuste>(`${this.base}/${id}/reajustes`);
  }

  /** Abre um reajuste para a vigência e o mês de referência. */
  abrirReajuste(id: string, sequencia: number, mesReferencia: string): Observable<PainelReajuste> {
    return this.http.post<PainelReajuste>(`${this.base}/${id}/reajustes`, { sequencia_vigencia: sequencia, mes_referencia: mesReferencia });
  }

  /** Anexa a evidência do índice ou o apostilamento (que conclui o reajuste). */
  enviarReajuste(id: string, reajusteId: string, acao: 'evidencia' | 'concluir', arquivo: File): Observable<PainelReajuste> {
    return this.http.post<PainelReajuste>(`${this.base}/${id}/reajustes/${reajusteId}/${acao}`, this.arquivo({ arquivo }));
  }

  /** Grava índice e teto de cada item. */
  salvarMemoriaReajuste(id: string, reajusteId: string, itens: { item_id: string; indice_percentual: string; valor_referencial: string | null }[]): Observable<PainelReajuste> {
    return this.http.put<PainelReajuste>(`${this.base}/${id}/reajustes/${reajusteId}/memoria`, { itens });
  }

  /** Gera os arquivos da memória ou cancela o reajuste. */
  acaoReajuste(id: string, reajusteId: string, acao: 'memoria/arquivos' | 'cancelar'): Observable<PainelReajuste> {
    return this.http.post<PainelReajuste>(`${this.base}/${id}/reajustes/${reajusteId}/${acao}`, {});
  }

  /** Baixa um arquivo do reajuste. */
  baixarReajuste(id: string, reajusteId: string, anexoId: string) {
    return baixarArquivo(this.http, `${this.base}/${id}/reajustes/${reajusteId}/arquivos/${anexoId}`);
  }

  // --- Aditamento / supressão ---
  /** Alteração em andamento, vigências e histórico. */
  alteracoes(id: string): Observable<PainelAlteracao> {
    return this.http.get<PainelAlteracao>(`${this.base}/${id}/alteracoes`);
  }

  /** Inicia um aditamento ou uma supressão. */
  abrirAlteracao(id: string, tipo: 'aditamento' | 'supressao', sequencia: number, mesEfeito: string): Observable<PainelAlteracao> {
    return this.http.post<PainelAlteracao>(`${this.base}/${id}/alteracoes`, { tipo, sequencia_vigencia: sequencia, mes_efeito: mesEfeito });
  }

  /** Anexa um documento da alteração (justificativa, autorização, De Acordo ou termo). */
  enviarDocumentoAlteracao(id: string, alteracaoId: string, tipo: 'justificativa' | 'autorizacao' | 'de_acordo' | 'termo', arquivo: File): Observable<PainelAlteracao> {
    return this.http.post<PainelAlteracao>(`${this.base}/${id}/alteracoes/${alteracaoId}/documentos/${tipo}`, this.arquivo({ arquivo }));
  }

  /** Grava as novas quantidades por item. */
  salvarQuantitativos(id: string, alteracaoId: string, itens: { item_id: string; quantidade_nova: string }[]): Observable<PainelAlteracao> {
    return this.http.put<PainelAlteracao>(`${this.base}/${id}/alteracoes/${alteracaoId}/quantitativos`, { itens });
  }

  /** Ações da alteração: ciência, memória, consolidado, conclusão ou cancelamento. */
  acaoAlteracao(id: string, alteracaoId: string, acao: 'ciencia' | 'memoria' | 'consolidado' | 'concluir' | 'cancelar'): Observable<PainelAlteracao> {
    return this.http.post<PainelAlteracao>(`${this.base}/${id}/alteracoes/${alteracaoId}/${acao}`, {});
  }

  /** Baixa um arquivo da alteração. */
  baixarAlteracao(id: string, alteracaoId: string, anexoId: string) {
    return baixarArquivo(this.http, `${this.base}/${id}/alteracoes/${alteracaoId}/arquivos/${anexoId}`);
  }
}
