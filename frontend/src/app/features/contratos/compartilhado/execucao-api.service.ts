// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API de checklists, formulários de avaliação e competências.

import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { ambiente } from '../../../../environments/ambiente';
import { baixarArquivo } from '../../../shared/utilitarios/download';
import {
  Checklist,
  DefinicaoFormulario,
  DetalheCompetencia,
  CorrecaoItens,
  Etapa,
  Formulario,
  HistoricoItemContrato,
  ListaCorrecoes,
  PreviaCorrecao,
  PainelExecucao,
  RespostaAvaliacao,
} from './contratos.models';
import { GrupoDestinatarios } from './opcao-email.component';

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

  // --- Download em XLSX (planilha preenchida, no formato da importação) ---
  /** Baixa o contrato em planilha. */
  baixarContratoXlsx(id: string) {
    return baixarArquivo(this.http, this.url(id, '/exportacao-xlsx'), 'contrato.xlsx');
  }

  /** Baixa uma versão do checklist ou do formulário de avaliação em planilha. */
  baixarModeloXlsx(id: string, tipo: 'checklists' | 'formularios', versaoId: string) {
    return baixarArquivo(this.http, this.url(id, `/${tipo}/${versaoId}/xlsx`), `${tipo}.xlsx`);
  }

  // --- Checklists ---
  /** Versões do checklist do contrato. */
  checklists(id: string): Observable<Checklist[]> {
    return this.http.get<Checklist[]>(this.url(id, '/checklists'));
  }

  /** Cria (sem checklistId) ou edita (com checklistId) uma versão do checklist. */
  salvarChecklist(id: string, dados: { nome: string; itens: { nome: string; observacao: string; obrigatorio: boolean; com_validade?: boolean; vale_outros_contratos?: boolean }[] }, checklistId?: string): Observable<Checklist[]> {
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

  // --- Destinatários dos e-mails da execução ---
  /** Prepostos ativos com e-mail, em um grupo só. */
  gruposPrepostos(id: string): Observable<GrupoDestinatarios[]> {
    return this.http.get<{ id: string; nome: string; email: string; cargo: string }[]>(this.url(id, '/prepostos')).pipe(
      map((l) => [{ titulo: 'Prepostos da empresa contratada', itens: l }]),
    );
  }

  /** Usuários do Financeiro agrupados por setor (DOF e subsetores). */
  gruposFinanceiro(id: string): Observable<GrupoDestinatarios[]> {
    return this.http.get<{ setor: string; usuarios: { id: number; nome: string; email: string; cargo: string }[] }[]>(this.url(id, '/financeiro')).pipe(
      map((l) => l.map((g) => ({ titulo: g.setor, itens: g.usuarios }))),
    );
  }

  // --- Correção de itens ---
  correcoes(id: string): Observable<ListaCorrecoes> {
    return this.http.get<ListaCorrecoes>(this.url(id, '/itens/correcoes'));
  }

  historicoItens(id: string): Observable<HistoricoItemContrato[]> {
    return this.http.get<HistoricoItemContrato[]>(this.url(id, '/itens/historico'));
  }

  previaCorrecao(id: string, dados: { justificativa: string; itens: Record<string, string>[] }): Observable<PreviaCorrecao> {
    return this.http.post<PreviaCorrecao>(this.url(id, '/itens/correcoes/previa'), dados);
  }

  proporCorrecao(id: string, dados: { justificativa: string; itens: Record<string, string>[] }): Observable<CorrecaoItens> {
    return this.http.post<CorrecaoItens>(this.url(id, '/itens/correcoes'), dados);
  }

  decidirCorrecao(id: string, correcaoId: string, acao: 'confirmar' | 'recusar' | 'cancelar', motivo = ''): Observable<CorrecaoItens> {
    return this.http.post<CorrecaoItens>(this.url(id, `/itens/correcoes/${correcaoId}/${acao}`), acao === 'recusar' ? { motivo } : {});
  }

  // --- Formulários ---
  /** Exclui (logicamente) uma versão inativa do formulário de avaliação. */
  excluirFormulario(id: string, formularioId: string): Observable<Formulario[]> {
    return this.http.delete<Formulario[]>(this.url(id, `/formularios/${formularioId}`));
  }

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
  concluirMedicao(id: string, c: string, notas: string[], enviarEmail = false, prepostosIds: string[] | null = null): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/medicao/concluir'), { notas_empenho_ids: notas, enviar_email: enviarEmail, prepostos_ids: enviarEmail ? prepostosIds : null });
  }

  /** Etapa 2: notas da avaliação inicial. */
  avaliacaoInicial(id: string, c: string, respostas: RespostaAvaliacao[]): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/inicial'), { respostas });
  }

  /** Etapa 2: notas e complemento do gestor. */
  avaliacaoGestor(id: string, c: string, respostas: RespostaAvaliacao[], complemento: string): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/gestor'), { respostas, complemento });
  }

  /** Etapa 2: ciência no ateste ou geração do PDF. */
  acaoAvaliacao(id: string, c: string, acao: 'ciencia' | 'pdf', enviarEmail = false, prepostosIds: string[] | null = null): Observable<DetalheCompetencia> {
    const params: Record<string, string | string[]> = acao === 'pdf' && enviarEmail ? { enviar_email: 'true', ...(prepostosIds ? { prepostos_ids: prepostosIds } : {}) } : {};
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/avaliacao/${acao}`), {}, { params });
  }

  /** Etapa 2: envia a via assinada ou o pedido de reconsideração. */
  enviarAvaliacao(id: string, c: string, tipo: 'assinada' | 'reconsideracao', arquivo: File): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/avaliacao/${tipo}`), this.formulario({ arquivo }));
  }

  /**
   * Etapa 3: registra as notas fiscais (uma ou mais). `notas` é a lista final, na ordem desejada: `id` mantém uma nota já
   * registrada, e `arquivo`/`xml` são posições nas listas `arquivos` e `xmls` (os PDFs e XMLs novos).
   */
  notaFiscal(id: string, c: string, dados: {
    recebida_em: string; prazo_pagamento_dias: number; notas: { id: string | null; arquivo: number | null; xml: number | null; valor_bruto?: string | null; numero?: string | null }[];
    arquivos: File[]; xmls: File[]; enviar_email?: boolean; financeiro_ids?: (string | number)[] | null;
  }): Observable<DetalheCompetencia> {
    const corpo = this.formulario({ recebida_em: dados.recebida_em, prazo_pagamento_dias: dados.prazo_pagamento_dias, notas: JSON.stringify(dados.notas), enviar_email: !!dados.enviar_email });
    // Ids separados por vírgula; vazio = ninguém do Financeiro (ausente = todos)
    if (dados.enviar_email && dados.financeiro_ids) corpo.append('financeiro_ids', dados.financeiro_ids.join(','));
    dados.arquivos.forEach((a) => corpo.append('arquivos', a));
    dados.xmls.forEach((x) => corpo.append('xmls', x));
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/nota-fiscal'), corpo);
  }

  /** Etapa 4: salva a retenção de tributos conferida (Financeiro, equipe ou SuperRoot). */
  salvarRetencao(id: string, c: string, dados: {
    notas: ({ nota_id: string } & Record<string, string>)[]; discriminacao_conferida: boolean; enviar_email?: boolean;
  }): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/retencao'), dados);
  }

  /** Etapa 4: recusa a nota fiscal com justificativa (reabre a etapa da nota; e-mail obrigatório à equipe e aos prepostos). */
  recusarNota(id: string, c: string, justificativa: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/retencao/recusar'), { justificativa });
  }

  /** Reenvia o e-mail de uma recusa (com o PDF anexado). */
  reenviarEmailRecusa(id: string, c: string, recusaId: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/recusas/${recusaId}/reenviar-email`), null);
  }

  /** Reenvia o e-mail da NF (ao Financeiro) ou da retenção (à equipe). */
  reenviarEmail(id: string, c: string, tipo: 'nf' | 'retencao'): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/reenviar-email-${tipo}`), null);
  }

  /** Etapa 5: registra a consulta ao CADIN. */
  cadin(id: string, c: string, campos: Record<string, string | boolean | File | null>): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/cadin'), this.formulario(campos));
  }

  /** Conclui a etapa do checklist com os documentos obrigatórios anexados (opcionais podem faltar). */
  concluirChecklist(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/checklist/concluir'), {});
  }

  /** Etapa 5: traz o documento igual, ainda válido, de outro contrato da mesma empresa (`origem_id` da sugestão). */
  reaproveitarDocumento(id: string, c: string, documentoId: string, origemId: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/checklist/${documentoId}/reaproveitar`), { origem_id: origemId });
  }

  /** Etapa 5: traz de uma vez todos os documentos válidos de outros contratos da mesma empresa. */
  reaproveitarTodos(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/checklist/reaproveitar-todos'), {});
  }

  /** Etapa 5: anexa um documento do checklist mensal. */
  documentoMensal(id: string, c: string, documentoId: string, arquivo: File, validade?: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/checklist/${documentoId}`), this.formulario({ arquivo, validade }));
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
  zerar(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/zerar'), {});
  }

  /** Reabre a competência numa etapa anterior; as posteriores são descartadas. */
  reabrir(id: string, c: string, etapa: Etapa, justificativa: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/reabrir'), { etapa, justificativa });
  }

  /** Reenvia o e-mail da medição concluída à equipe e ao preposto. */
  reenviarEmailMedicao(id: string, competenciaId: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, competenciaId, '/reenviar-email-medicao'), null);
  }

  /** Reenvia o relatório de avaliação aos prepostos (cópia para a equipe), pedindo a devolução assinada. */
  reenviarEmailAvaliacao(id: string, competenciaId: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, competenciaId, '/reenviar-email-avaliacao'), null);
  }
}
