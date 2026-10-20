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
  salvarChecklist(id: string, dados: { nome: string; itens: { nome: string; observacao: string; obrigatorio: boolean; com_validade?: boolean; vale_outros_contratos?: boolean; pedir_envio?: boolean }[] }, checklistId?: string): Observable<Checklist[]> {
    return checklistId
      ? this.http.put<Checklist[]>(this.url(id, `/checklists/${checklistId}`), dados)
      : this.http.post<Checklist[]>(this.url(id, '/checklists'), dados);
  }

  /** Liga ou desliga "Pedir para enviar" de um documento (vale também com o checklist ativo). */
  definirPedirEnvio(id: string, checklistId: string, itemId: string, pedirEnvio: boolean): Observable<Checklist[]> {
    return this.http.put<Checklist[]>(this.url(id, `/checklists/${checklistId}/itens/${itemId}/pedir-envio`), { pedir_envio: pedirEnvio });
  }

  /** Duplica ou ativa uma versão do checklist. */
  acaoChecklist(id: string, checklistId: string, acao: 'duplicar' | 'ativar'): Observable<Checklist[]> {
    return this.http.post<Checklist[]>(this.url(id, `/checklists/${checklistId}/${acao}`), {});
  }

  /** Exclui (logicamente) uma versão inativa do checklist. */
  excluirChecklist(id: string, checklistId: string): Observable<Checklist[]> {
    return this.http.delete<Checklist[]>(this.url(id, `/checklists/${checklistId}`));
  }

  // --- Rascunhos salvos no servidor (visíveis à equipe) ---
  /** Rascunho salvo da tela (`null` se não há). Nas telas por competência, `chave` é o id da competência. */
  lerRascunho(contratoId: string, tipo: TipoRascunho, chave = ''): Observable<RascunhoServidor | null> {
    return this.http.get<RascunhoServidor | null>(this.url(contratoId, `/rascunhos/${tipo}`), { params: { chave } });
  }

  /** Salva (ou grava por cima) o rascunho; `versao` é a que a pessoa viu (`null` se não havia). */
  salvarRascunho(contratoId: string, tipo: TipoRascunho, chave: string, dados: Record<string, unknown>, versao: number | null): Observable<RascunhoServidor> {
    return this.http.put<RascunhoServidor>(this.url(contratoId, `/rascunhos/${tipo}`), { dados, versao }, { params: { chave } });
  }

  apagarRascunho(contratoId: string, tipo: TipoRascunho, chave = ''): Observable<void> {
    return this.http.delete<void>(this.url(contratoId, `/rascunhos/${tipo}`), { params: { chave } });
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

  /**
   * Abre um arquivo da competência (PDF) em uma nova aba. A aba é aberta no clique (evita o bloqueio de pop-up) e, quando o arquivo
   * autenticado chega, passa a mostrá-lo; em erro, a aba é fechada e `aoErro` recebe o erro.
   */
  abrirEmNovaAba(id: string, competenciaId: string, anexoId: string, aoErro: (erro: unknown) => void): void {
    const aba = window.open('', '_blank');
    this.http.get(this.competencia(id, competenciaId, `/arquivos/${anexoId}`), { responseType: 'blob' }).subscribe({
      next: (corpo) => {
        const endereco = URL.createObjectURL(new Blob([corpo], { type: corpo.type || 'application/pdf' }));
        if (aba) aba.location.href = endereco;
        else window.open(endereco, '_blank');
        setTimeout(() => URL.revokeObjectURL(endereco), 120000);
      },
      error: (erro) => {
        aba?.close();
        aoErro(erro);
      },
    });
  }

  /** Etapa 1: grava as quantidades medidas e as NEs escolhidas, em ordem. */
  salvarMedicao(id: string, c: string, itens: { id: string; quantidade_medida: string; acerto?: string; despesa_variavel?: boolean }[], notas: string[]): Observable<DetalheCompetencia> {
    return this.http.put<DetalheCompetencia>(this.competencia(id, c, '/medicao'), { itens, notas_empenho_ids: notas });
  }

  /** Etapa 1: registra a ciência do usuário logado. */
  cienciaMedicao(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/medicao/ciencia'), {});
  }

  /** Etapa 1: conclui a medição (as NEs precisam ser as mesmas da última gravação). */
  concluirMedicao(id: string, c: string, notas: string[], prepostosIds: string[] | null, prazoContestacaoDias: number | null): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/medicao/concluir'), {
      notas_empenho_ids: notas, prepostos_ids: prepostosIds, prazo_contestacao_dias: prazoContestacaoDias,
    });
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

  /** Etapa 2: gera o relatório de avaliação e envia o e-mail único (medição + avaliação) aos prepostos escolhidos, com o prazo de contestação. */
  enviarMedicaoEAvaliacao(id: string, c: string, prepostosIds: string[], prazoContestacaoDias: number): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/avaliacao/enviar'), { prepostos_ids: prepostosIds, prazo_contestacao_dias: prazoContestacaoDias });
  }

  /**
   * Etapa 3: registra as notas fiscais (uma ou mais). `notas` é a lista final, na ordem desejada: `id` mantém uma nota já
   * registrada, e `arquivo`/`xml` são posições nas listas `arquivos` e `xmls` (os PDFs e XMLs novos).
   */
  notaFiscal(id: string, c: string, dados: {
    recebida_em: string; prazo_pagamento_dias: number; notas: { id: string | null; arquivo: number | null; xml: number | null; valor_bruto?: string | null; numero?: string | null }[];
    arquivos: File[]; xmls: File[];
    /** Documentos de despesas variáveis (obrigatórios com item marcado na medição) e seus PDFs. */
    despesas?: { id: string | null; tipo: string; numero: string | null; valor: string; arquivo: number | null }[]; arquivosDespesas?: File[];
  }): Observable<DetalheCompetencia> {
    const corpo = this.formulario({ recebida_em: dados.recebida_em, prazo_pagamento_dias: dados.prazo_pagamento_dias, notas: JSON.stringify(dados.notas) });
    if (dados.despesas?.length) corpo.append('despesas', JSON.stringify(dados.despesas));
    dados.arquivosDespesas?.forEach((a) => corpo.append('arquivos_despesas', a));
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

  /** Reenvia o e-mail da pendência no CADIN (aos prepostos, equipe em cópia). */
  reenviarEmailCadin(id: string, c: string, consultaId: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, `/cadin/${consultaId}/reenviar-email`), {});
  }

  /** Reenvia aos prepostos o e-mail de pagamento da competência com a OB lançada (equipe em cópia). */
  reenviarEmailOb(id: string, c: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, c, '/ordem-bancaria/reenviar-email'), {});
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

  /** Texto do despacho de pagamento (máscara ativa), para mostrar na tela e copiar; `html` nulo = sem máscara ativa. */
  despacho(id: string, c: string): Observable<{ html: string | null; titulo: string }> {
    return this.http.get<{ html: string | null; titulo: string }>(this.competencia(id, c, '/despacho'));
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

  /** Medição adicional: outra medição e outro pagamento no período da competência (justificativa obrigatória; anexo PDF opcional). */
  incluirMedicaoAdicional(id: string, competenciaId: string, justificativa: string, arquivo: File | null): Observable<DetalheCompetencia> {
    const corpo = new FormData();
    corpo.append('justificativa', justificativa);
    if (arquivo) corpo.append('arquivo', arquivo, arquivo.name);
    return this.http.post<DetalheCompetencia>(this.competencia(id, competenciaId, '/adicional'), corpo);
  }

  /** Exclui a medição adicional (equipe do contrato); a competência regular não pode ser excluída. */
  excluirMedicaoAdicional(id: string, competenciaId: string): Observable<void> {
    return this.http.delete<void>(this.competencia(id, competenciaId, ''));
  }

  /** Reemite o documento executivo e o e-mail único da medição (contestação aceita ou envio que falhou), reiniciando o prazo. */
  reemitirMedicao(id: string, competenciaId: string, prazoContestacaoDias: number | null = null): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, competenciaId, '/medicao/reemitir'), { prazo_contestacao_dias: prazoContestacaoDias });
  }

  /** Reenvia o relatório de avaliação aos prepostos (cópia para a equipe), pedindo a devolução assinada. */
  reenviarEmailAvaliacao(id: string, competenciaId: string): Observable<DetalheCompetencia> {
    return this.http.post<DetalheCompetencia>(this.competencia(id, competenciaId, '/reenviar-email-avaliacao'), null);
  }
}

/** Tela que pode ter rascunho salvo no servidor. */
export type TipoRascunho = 'diario' | 'avaliacao' | 'medicao';

/** Rascunho salvo no servidor (`LeituraRascunho` da API). */
export interface RascunhoServidor {
  tipo: TipoRascunho;
  chave: string;
  dados: Record<string, unknown>;
  versao: number;
  atualizado_em: string;
  atualizado_por_id: number | null;
  atualizado_por_nome: string;
}
