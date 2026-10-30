// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de prorrogação, reajuste e aditamento/supressão.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { baixarArquivo } from '../../../shared/utilitarios/download';
import { CalculoMesQuebrado, GravacaoPosAssinatura, PainelAlteracao, PainelReajuste, ProcessoProrrogacao, Prorrogacao, Reajuste, RegraSobDemanda, VigenciaRetroativa } from './contratos.models';

/** Corpo do rascunho da prorrogação (prazo, plano dos itens sob demanda e o cálculo dos meses quebrados; nulo mantém a escolha). */
export interface GravacaoProrrogacao {
  meses: number | null;
  regra_sob_demanda: RegraSobDemanda;
  plano_sob_demanda: { item_id: string; limite: string; apontamentos: Record<string, string> }[];
  calculo_mes_quebrado?: CalculoMesQuebrado | null;
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

  /** Gera o PDF e o XLSX da memória de cálculo da prorrogação (nova versão só se os dados mudaram). */
  gerarMemoriaProrrogacao(id: string): Observable<ProcessoProrrogacao> {
    return this.http.post<ProcessoProrrogacao>(`${this.base}/${id}/prorrogacao/memoria/arquivos`, {});
  }

  /** Anexa (ou substitui) o PDF de um documento do checklist da prorrogação. */
  anexarDocumentoProrrogacao(id: string, documentoId: string, arquivo: File): Observable<ProcessoProrrogacao> {
    return this.http.post<ProcessoProrrogacao>(`${this.base}/${id}/prorrogacao/checklist/${documentoId}`, this.arquivo({ arquivo }));
  }

  /** Inclui um documento fora do checklist padrão (nome, descrição e PDF); nunca obrigatório. */
  incluirDocumentoProrrogacao(id: string, nome: string, descricao: string, arquivo: File): Observable<ProcessoProrrogacao> {
    return this.http.post<ProcessoProrrogacao>(`${this.base}/${id}/prorrogacao/checklist/incluir`, this.arquivo({ nome, descricao, arquivo }));
  }

  /** Exclui um documento incluído no checklist da prorrogação. */
  excluirDocumentoProrrogacao(id: string, documentoId: string): Observable<ProcessoProrrogacao> {
    return this.http.delete<ProcessoProrrogacao>(`${this.base}/${id}/prorrogacao/checklist/${documentoId}`);
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

  /** Grava o pós-assinatura (PNCP, DOE, garantia, Contratos.gov) de uma prorrogação registrada. */
  salvarPosAssinatura(id: string, prorrogacaoId: string, dados: GravacaoPosAssinatura): Observable<Prorrogacao[]> {
    return this.http.put<Prorrogacao[]>(`${this.base}/${id}/prorrogacoes/${prorrogacaoId}/pos-assinatura`, dados);
  }

  /** Baixa a planilha de dados de garantia para a DOF (XLSX). */
  baixarPlanilhaGarantia(id: string, prorrogacaoId: string) {
    return baixarArquivo(this.http, `${this.base}/${id}/prorrogacoes/${prorrogacaoId}/garantia/planilha`, 'dados-garantia.xlsx');
  }

  /** Baixa o termo ou o parecer de uma prorrogação. */
  baixarProrrogacao(id: string, anexoId: string) {
    return baixarArquivo(this.http, `${this.base}/${id}/prorrogacoes/arquivos/${anexoId}`);
  }

  // --- Vigência retroativa ---
  /** Vigências anteriores ao início do contrato. */
  vigenciasRetroativas(id: string): Observable<VigenciaRetroativa[]> {
    return this.http.get<VigenciaRetroativa[]>(`${this.base}/${id}/vigencias-retroativas`);
  }

  /** Cadastra uma vigência retroativa com o Termo Aditivo assinado. */
  cadastrarVigenciaRetroativa(id: string, meses: number, assinadaEm: string, numeroTermo: string, termo: File): Observable<VigenciaRetroativa[]> {
    return this.http.post<VigenciaRetroativa[]>(`${this.base}/${id}/vigencias-retroativas`,
      this.arquivo({ meses: String(meses), assinada_em: assinadaEm, numero_termo: numeroTermo, termo }));
  }

  /** Desfaz a vigência retroativa mais antiga. */
  desfazerVigenciaRetroativa(id: string, vigenciaId: string): Observable<VigenciaRetroativa[]> {
    return this.http.delete<VigenciaRetroativa[]>(`${this.base}/${id}/vigencias-retroativas/${vigenciaId}`);
  }

  // --- Reajuste ---
  /** Reajuste em elaboração, vigências disponíveis e histórico. */
  reajustes(id: string): Observable<PainelReajuste> {
    return this.http.get<PainelReajuste>(`${this.base}/${id}/reajustes`);
  }

  /** Abre um reajuste para a vigência e a data de efeito; o retroativo dispensa a data (vale o início da vigência seguinte). */
  abrirReajuste(id: string, sequencia: number, dataEfeito: string): Observable<PainelReajuste> {
    return this.http.post<PainelReajuste>(`${this.base}/${id}/reajustes`, { sequencia_vigencia: sequencia, data_efeito: dataEfeito });
  }

  /** Abre o reajuste retroativo da vigência retroativa escolhida. */
  abrirReajusteRetroativo(id: string, sequencia: number): Observable<PainelReajuste> {
    return this.http.post<PainelReajuste>(`${this.base}/${id}/reajustes`, { sequencia_vigencia: sequencia, retroativo: true });
  }

  /** Anexa a evidência do índice ou o apostilamento (que conclui o reajuste). */
  enviarReajuste(id: string, reajusteId: string, acao: 'evidencia' | 'concluir', arquivo: File): Observable<PainelReajuste> {
    return this.http.post<PainelReajuste>(`${this.base}/${id}/reajustes/${reajusteId}/${acao}`, this.arquivo({ arquivo }));
  }

  /** Calculadora ao vivo: o reajuste como ficaria com estes índices e tetos, sem gravar nada. */
  previaMemoriaReajuste(id: string, reajusteId: string, itens: { item_id: string; indice_percentual: string; valor_referencial: string | null }[]): Observable<Reajuste> {
    return this.http.post<Reajuste>(`${this.base}/${id}/reajustes/${reajusteId}/memoria/previa`, { itens });
  }

  /** Grava índice e teto de cada item e, se informado, como calcular os meses quebrados (nulo mantém a escolha). */
  salvarMemoriaReajuste(id: string, reajusteId: string, itens: { item_id: string; indice_percentual: string; valor_referencial: string | null }[],
                        calculo: CalculoMesQuebrado | null = null): Observable<PainelReajuste> {
    return this.http.put<PainelReajuste>(`${this.base}/${id}/reajustes/${reajusteId}/memoria`, { itens, calculo_mes_quebrado: calculo });
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
