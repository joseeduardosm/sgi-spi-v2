// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de checklists, formulários de avaliação e competências.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { baixarArquivo } from '../../../shared/utilitarios/download';
import {
  AssinaturaAteste,
  Checklist,
  DefinicaoFormulario,
  DetalheCompetencia,
  Etapa,
  Formulario,
  PainelExecucao,
  RespostaAvaliacao,
} from './contratos.models';

/** Checklists, formulários de avaliação e competências (docs/endpoints/contratos-execucao.md). */
@Injectable({ providedIn: 'root' })
export class ExecucaoApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/contratos`;

  /** Monta a URL de um recurso do contrato. */
  private url(contratoId: string, caminho: string): string {
    return `${this.base}/${contratoId}${caminho}`;
  }

  /**
   * Monta um FormData (multipart) a partir de um objeto, pulando campos vazios. Usado nas etapas
   * que enviam PDF junto com outros campos.
   */
  private formulario(campos: Record<string, string | boolean | number | File | null | undefined>): FormData {
    const dados = new FormData();
    for (const [chave, valor] of Object.entries(campos)) {
      if (valor === null || valor === undefined) continue;
      dados.append(chave, valor instanceof File ? valor : String(valor));
    }
    return dados;
  }

  // --- Checklists ---
  /** Versões do checklist do contrato. */
  checklists(id: string): Observable<Checklist[]> {
    return this.http.get<Checklist[]>(this.url(id, '/checklists'));
  }

  /** Cria (sem checklistId) ou edita (com checklistId) uma versão do checklist. */
  salvarChecklist(id: string, dados: { nome: string; itens: { nome: string; observacao: string; obrigatorio: boolean }[] }, checklistId?: string): Observable<Checklist[]> {
    return checklistId
      ? this.http.put<Checklist[]>(this.url(id, `/checklists/${checklistId}`), dados)
      : this.http.post<Checklist[]>(this.url(id, '/checklists'), dados);
  }

  /** Duplica ou ativa uma versão do checklist. */
  acaoChecklist(id: string, checklistId: string, acao: 'duplicar' | 'ativar'): Observable<Checklist[]> {
    return this.http.post<Checklist[]>(this.url(id, `/checklists/${checklistId}/${acao}`), {});
  }

  /** Exclui (logicamente) uma versão inativa do checklist. */
  excluirChecklist(id: string, checklistId: string): Observable<Checklist[]> {
    return this.http.delete<Checklist[]>(this.url(id, `/checklists/${checklistId}`));
  }

  // --- Formulários ---
  /** Versões do formulário de avaliação. */
  formularios(id: string): Observable<Formulario[]> {
    return this.http.get<Formulario[]>(this.url(id, '/formularios'));
  }

  /** Cria ou edita uma versão do formulário. */
  salvarFormulario(id: string, dados: { nome: string; definicao: DefinicaoFormulario }, formularioId?: string): Observable<Formulario[]> {
    return formularioId
      ? this.http.put<Formulario[]>(this.url(id, `/formularios/${formularioId}`), dados)
      : this.http.post<Formulario[]>(this.url(id, '/formularios'), dados);
  }

  /** Duplica ou ativa uma versão do formulário. */
  acaoFormulario(id: string, formularioId: string, acao: 'duplicar' | 'ativar'): Observable<Formulario[]> {
    return this.http.post<Formulario[]>(this.url(id, `/formularios/${formularioId}/${acao}`), {});
  }

  // --- Competências ---
  /** Aba Execução: pré-requisitos e competências. */
  painel(id: string): Observable<PainelExecucao> {
    return this.http.get<PainelExecucao>(this.url(id, '/execucao'));
  }

  /** Gera as competências que faltam. */
  gerar(id: string): Observable<PainelExecucao> {
    return this.http.post<PainelExecucao>(this.url(id, '/execucao/gerar'), {});
  }

  /** Competência pelo identificador da URL (ex.: 2026-03). */
  porIdentificador(id: string, identificador: string): Observable<DetalheCompetencia> {
    return this.http.get<DetalheCompetencia>(this.url(id, `/competencias/identificador/${identificador}`));
  }

  /** Monta a URL de um recurso da competência. */
  private competencia(id: string, competenciaId: string, caminho: string): string {
    return this.url(id, `/competencias/${competenciaId}${caminho}`);
  }

  /** Baixa um PDF da competência. */
  baixar(id: string, competenciaId: string, anexoId: string) {
    return baixarArquivo(this.http, this.competencia(id, competenciaId, `/arquivos/${anexoId}`));
  }

  /** Etapa 1: grava as quantidades medidas e as NEs escolhidas, em ordem. */
  salvarMedicao(id: string, c: string, itens: { id: string; quantidade_medida: string }[], notas: string[]): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/medicao'), { itens, notas_empenho_ids: notas });
  }

  /** Etapa 1: registra a ciência do usuário logado. */
  cienciaMedicao(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/medicao/ciencia'), {});
  }

  /** Etapa 1: conclui a medição (as NEs precisam ser as mesmas da última gravação). */
  concluirMedicao(id: string, c: string, notas: string[]): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/medicao/concluir'), { notas_empenho_ids: notas });
  }

  /** Etapa 2: notas da avaliação inicial. */
  avaliacaoInicial(id: string, c: string, respostas: RespostaAvaliacao[]): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/inicial'), { respostas });
  }

  /** Etapa 2: notas e complemento do gestor. */
  avaliacaoGestor(id: string, c: string, respostas: RespostaAvaliacao[], complemento: string): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/gestor'), { respostas, complemento });
  }

  /** Etapa 2: quem assina o ateste. */
  assinaturas(id: string, c: string, assinaturas: Pick<AssinaturaAteste, 'papel' | 'usuario_id'>[]): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/assinaturas'), { assinaturas });
  }

  /** Etapa 2: ciência no ateste ou geração do PDF. */
  acaoAvaliacao(id: string, c: string, acao: 'ciencia' | 'pdf'): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/avaliacao/${acao}`), {});
  }

  /** Etapa 2: envia a via assinada ou o pedido de reconsideração. */
  enviarAvaliacao(id: string, c: string, tipo: 'assinada' | 'reconsideracao', arquivo: File): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/avaliacao/${tipo}`), this.formulario({ arquivo }));
  }

  /** Etapa 3: registra a nota fiscal (campos + PDFs). */
  notaFiscal(id: string, c: string, campos: Record<string, string | boolean | File | null>): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/nota-fiscal'), this.formulario(campos));
  }

  /** Etapa 4: registra a consulta ao CADIN. */
  cadin(id: string, c: string, campos: Record<string, string | boolean | File | null>): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/cadin'), this.formulario(campos));
  }

  /** Conclui a etapa do checklist com os documentos obrigatórios anexados (opcionais podem faltar). */
  concluirChecklist(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/checklist/concluir'), {});
  }

  /** Etapa 5: anexa um documento do checklist mensal. */
  documentoMensal(id: string, c: string, documentoId: string, arquivo: File): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/checklist/${documentoId}`), this.formulario({ arquivo }));
  }

  /** Etapa 6: gera o documento consolidado. */
  consolidado(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/consolidado'), {});
  }

  /** Etapa 7: anexa a ordem bancária e conclui a competência. */
  ordemBancaria(id: string, c: string, arquivo: File): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/ordem-bancaria'), this.formulario({ arquivo }));
  }

  /** Reabre a competência em uma etapa anterior (SuperRoot ou gestor). */
  reabrir(id: string, c: string, etapa: Etapa, justificativa: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/reabrir'), { etapa, justificativa });
  }
}
