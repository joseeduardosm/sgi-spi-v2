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

  private url(contratoId: string, caminho: string): string {
    return `${this.base}/${contratoId}${caminho}`;
  }

  private formulario(campos: Record<string, string | boolean | number | File | null | undefined>): FormData {
    const dados = new FormData();
    for (const [chave, valor] of Object.entries(campos)) {
      if (valor === null || valor === undefined) continue;
      dados.append(chave, valor instanceof File ? valor : String(valor));
    }
    return dados;
  }

  // --- Checklists ---
  checklists(id: string): Observable<Checklist[]> {
    return this.http.get<Checklist[]>(this.url(id, '/checklists'));
  }

  salvarChecklist(id: string, dados: { nome: string; itens: { nome: string; observacao: string; obrigatorio: boolean }[] }, checklistId?: string): Observable<Checklist[]> {
    return checklistId
      ? this.http.put<Checklist[]>(this.url(id, `/checklists/${checklistId}`), dados)
      : this.http.post<Checklist[]>(this.url(id, '/checklists'), dados);
  }

  acaoChecklist(id: string, checklistId: string, acao: 'duplicar' | 'ativar'): Observable<Checklist[]> {
    return this.http.post<Checklist[]>(this.url(id, `/checklists/${checklistId}/${acao}`), {});
  }

  excluirChecklist(id: string, checklistId: string): Observable<Checklist[]> {
    return this.http.delete<Checklist[]>(this.url(id, `/checklists/${checklistId}`));
  }

  // --- Formulários ---
  formularios(id: string): Observable<Formulario[]> {
    return this.http.get<Formulario[]>(this.url(id, '/formularios'));
  }

  salvarFormulario(id: string, dados: { nome: string; definicao: DefinicaoFormulario }, formularioId?: string): Observable<Formulario[]> {
    return formularioId
      ? this.http.put<Formulario[]>(this.url(id, `/formularios/${formularioId}`), dados)
      : this.http.post<Formulario[]>(this.url(id, '/formularios'), dados);
  }

  acaoFormulario(id: string, formularioId: string, acao: 'duplicar' | 'ativar'): Observable<Formulario[]> {
    return this.http.post<Formulario[]>(this.url(id, `/formularios/${formularioId}/${acao}`), {});
  }

  // --- Competências ---
  painel(id: string): Observable<PainelExecucao> {
    return this.http.get<PainelExecucao>(this.url(id, '/execucao'));
  }

  gerar(id: string): Observable<PainelExecucao> {
    return this.http.post<PainelExecucao>(this.url(id, '/execucao/gerar'), {});
  }

  porIdentificador(id: string, identificador: string): Observable<DetalheCompetencia> {
    return this.http.get<DetalheCompetencia>(this.url(id, `/competencias/identificador/${identificador}`));
  }

  private competencia(id: string, competenciaId: string, caminho: string): string {
    return this.url(id, `/competencias/${competenciaId}${caminho}`);
  }

  baixar(id: string, competenciaId: string, anexoId: string) {
    return baixarArquivo(this.http, this.competencia(id, competenciaId, `/arquivos/${anexoId}`));
  }

  salvarMedicao(id: string, c: string, itens: { id: string; quantidade_medida: string }[], notas: string[]): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/medicao'), { itens, notas_empenho_ids: notas });
  }

  cienciaMedicao(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/medicao/ciencia'), {});
  }

  concluirMedicao(id: string, c: string, notas: string[]): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/medicao/concluir'), { notas_empenho_ids: notas });
  }

  avaliacaoInicial(id: string, c: string, respostas: RespostaAvaliacao[]): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/inicial'), { respostas });
  }

  avaliacaoGestor(id: string, c: string, respostas: RespostaAvaliacao[], complemento: string): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/gestor'), { respostas, complemento });
  }

  assinaturas(id: string, c: string, assinaturas: Pick<AssinaturaAteste, 'papel' | 'usuario_id'>[]): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/assinaturas'), { assinaturas });
  }

  acaoAvaliacao(id: string, c: string, acao: 'ciencia' | 'pdf'): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/avaliacao/${acao}`), {});
  }

  enviarAvaliacao(id: string, c: string, tipo: 'assinada' | 'reconsideracao', arquivo: File): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/avaliacao/${tipo}`), this.formulario({ arquivo }));
  }

  notaFiscal(id: string, c: string, campos: Record<string, string | boolean | File | null>): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/nota-fiscal'), this.formulario(campos));
  }

  cadin(id: string, c: string, campos: Record<string, string | boolean | File | null>): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/cadin'), this.formulario(campos));
  }

  /** Conclui a etapa do checklist com os documentos obrigatórios anexados (opcionais podem faltar). */
  concluirChecklist(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/checklist/concluir'), {});
  }

  documentoMensal(id: string, c: string, documentoId: string, arquivo: File): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/checklist/${documentoId}`), this.formulario({ arquivo }));
  }

  consolidado(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/consolidado'), {});
  }

  ordemBancaria(id: string, c: string, arquivo: File): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/ordem-bancaria'), this.formulario({ arquivo }));
  }

  reabrir(id: string, c: string, etapa: Etapa, justificativa: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/reabrir'), { etapa, justificativa });
  }
}
