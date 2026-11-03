// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API do módulo Chamados (/api/chamados).

import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import {
  AberturaChamado, AlteracaoChamado, AprovacaoPendente, CampoLeitura, Categoria, CategoriaCatalogo, ChamadoDetalhe, ContextoAbertura, ContextoChamados,
  CategoriaItil, CategoriaItilResumo, ConfiguracaoMigracaoGlpi, GravacaoCategoriaItil, LeituraMigracaoGlpi, GravacaoCampo, GravacaoRecorrente, LocalResumo, ParametrosGerais, PessoaResumo, Recorrente, SaudeChamados, SetorAtendimento, StatusApresentacao,
  Substatus, Expediente, FaixaExpediente, FiltroFila, FiltroMeus, GravacaoCategoria,
  ListaChamados, Ordenacao, SetorResumo, Sla, MotivoPendencia, RelatorioChamados, RespostaPronta, GravacaoRespostaPronta, ConfigPainel, EstadoPainel, ParametrosRh, ConfigServicoRh,
} from './chamados.models';

@Injectable({ providedIn: 'root' })
export class ChamadosApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/chamados`;

  contexto(): Observable<ContextoChamados> {
    return this.http.get<ContextoChamados>(`${this.base}/contexto`);
  }

  catalogo(): Observable<CategoriaCatalogo[]> {
    return this.http.get<CategoriaCatalogo[]>(`${this.base}/catalogo`);
  }

  /** Abre o chamado: `dados` (JSON) e os arquivos em multipart. */
  abrir(dados: AberturaChamado, arquivos: File[]): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(this.base, this.formulario(dados, arquivos));
  }

  meus(filtro: FiltroMeus, busca = '', pagina = 1, ordem: Ordenacao | null = null): Observable<ListaChamados> {
    return this.http.get<ListaChamados>(`${this.base}/meus`, { params: this.ordenacao(new HttpParams().set('filtro', filtro).set('busca', busca).set('pagina', pagina), ordem) });
  }

  /** `recorte`: os parâmetros de um clique nos Relatórios (ex.: `{escopo_relatorio: 'true', resolvido_por: '12', ...}`), repassados como vieram. */
  fila(filtro: FiltroFila, busca = '', pagina = 1, tamanho = 50, ordem: Ordenacao | null = null, recorte: Record<string, string> = {}): Observable<ListaChamados> {
    const params = new HttpParams({ fromObject: recorte }).set('filtro', filtro).set('busca', busca).set('pagina', pagina).set('tamanho', tamanho);
    return this.http.get<ListaChamados>(this.base, { params: this.ordenacao(params, ordem) });
  }

  /** Coluna clicada e sentido; sem ordem, vale a ordem padrão da lista. */
  private ordenacao(params: HttpParams, ordem: Ordenacao | null): HttpParams {
    return ordem ? params.set('ordem', ordem.coluna).set('direcao', ordem.direcao) : params;
  }

  detalhe(numero: number): Observable<ChamadoDetalhe> {
    return this.http.get<ChamadoDetalhe>(`${this.base}/${numero}`);
  }

  assumir(numero: number, versao: number): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/assumir`, { versao });
  }

  responder(numero: number, texto: string, privado: boolean, arquivos: File[]): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/acompanhamentos`, this.formulario({ texto, privado }, arquivos));
  }

  solucionar(numero: number, texto: string, arquivos: File[]): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/solucao`, this.formulario({ texto }, arquivos));
  }

  // --- Marco 2 ---

  contextoAbertura(): Observable<ContextoAbertura> {
    return this.http.get<ContextoAbertura>(`${this.base}/abertura/contexto`);
  }

  locais(busca: string, limite = 20): Observable<LocalResumo[]> {
    return this.http.get<LocalResumo[]>(`${this.base}/locais`, { params: { busca, limite } });
  }

  pessoas(busca: string): Observable<PessoaResumo[]> {
    return this.http.get<PessoaResumo[]>(`${this.base}/pessoas`, { params: { busca } });
  }

  setoresAtivos(): Observable<SetorResumo[]> {
    return this.http.get<SetorResumo[]>(`${this.base}/setores`);
  }

  minhasAprovacoes(): Observable<AprovacaoPendente[]> {
    return this.http.get<AprovacaoPendente[]>(`${this.base}/aprovacoes/minhas`);
  }

  responderAprovacao(id: string, aprovar: boolean, resposta: string): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/aprovacoes/${id}/responder`, { aprovar, resposta });
  }

  /** `null`: a pessoa deixou de ver o chamado (passou para outro setor). */
  alterar(numero: number, dados: AlteracaoChamado): Observable<ChamadoDetalhe | null> {
    return this.http.patch<ChamadoDetalhe | null>(`${this.base}/${numero}`, dados);
  }

  responsaveis(numero: number): Observable<PessoaResumo[]> {
    return this.http.get<PessoaResumo[]>(`${this.base}/${numero}/responsaveis`);
  }

  pendente(numero: number, motivo: string): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/pendente`, { motivo });
  }

  retomar(numero: number): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/retomar`, {});
  }

  naoResolveu(numero: number, motivo: string): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/nao-resolveu`, { motivo });
  }

  incluirEmCopia(numero: number, alvo: { usuario_id?: number; setor_id?: number }): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/em-copia`, alvo);
  }

  /** `null`: a pessoa saiu da própria cópia e deixou de ver o chamado. */
  removerEmCopia(numero: number, atorId: string): Observable<ChamadoDetalhe | null> {
    return this.http.delete<ChamadoDetalhe | null>(`${this.base}/${numero}/em-copia/${atorId}`);
  }

  criarTarefa(numero: number, texto: string, responsavelId: number | null, privada: boolean): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/tarefas`, { texto, responsavel_id: responsavelId, privada });
  }

  marcarTarefa(numero: number, tarefaId: string, feita: boolean): Observable<ChamadoDetalhe> {
    return this.http.patch<ChamadoDetalhe>(`${this.base}/${numero}/tarefas/${tarefaId}`, { feita });
  }

  pedirAprovacao(numero: number, alvo: { alvo_usuario_id?: number; alvo_setor_id?: number }, pedido: string): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/aprovacoes`, { ...alvo, pedido });
  }

  dadoPessoal(numero: number, campoId: string): Observable<{ valor: string }> {
    return this.http.get<{ valor: string }>(`${this.base}/${numero}/dados-pessoais/${campoId}`);
  }

  camposDaCategoria(categoriaId: string): Observable<CampoLeitura[]> {
    return this.http.get<CampoLeitura[]>(`${this.base}/parametros/categorias/${categoriaId}/campos`);
  }

  salvarCampo(categoriaId: string, id: string | null, dados: GravacaoCampo): Observable<CampoLeitura> {
    const base = `${this.base}/parametros/categorias/${categoriaId}/campos`;
    return id ? this.http.put<CampoLeitura>(`${base}/${id}`, dados) : this.http.post<CampoLeitura>(base, dados);
  }

  excluirCampo(categoriaId: string, id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/categorias/${categoriaId}/campos/${id}`);
  }

  baixarAnexo(numero: number, anexoId: string, nome: string): Observable<HttpResponse<Blob>> {
    return baixarArquivo(this.http, `${this.base}/${numero}/anexos/${anexoId}`, nome);
  }

  // --- Parâmetros ---

  setores(): Observable<SetorResumo[]> {
    return this.http.get<SetorResumo[]>(`${this.base}/parametros/setores`);
  }

  expedientes(): Observable<Expediente[]> {
    return this.http.get<Expediente[]>(`${this.base}/parametros/expedientes`);
  }

  salvarExpediente(id: string | null, dados: { nome: string; ativo: boolean; faixas: FaixaExpediente[] }): Observable<Expediente> {
    return id ? this.http.put<Expediente>(`${this.base}/parametros/expedientes/${id}`, dados) : this.http.post<Expediente>(`${this.base}/parametros/expedientes`, dados);
  }

  excluirExpediente(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/expedientes/${id}`);
  }

  slas(): Observable<Sla[]> {
    return this.http.get<Sla[]>(`${this.base}/parametros/slas`);
  }

  salvarSla(id: string | null, dados: Omit<Sla, 'id' | 'expediente_nome'>): Observable<Sla> {
    return id ? this.http.put<Sla>(`${this.base}/parametros/slas/${id}`, dados) : this.http.post<Sla>(`${this.base}/parametros/slas`, dados);
  }

  excluirSla(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/slas/${id}`);
  }

  categorias(): Observable<Categoria[]> {
    return this.http.get<Categoria[]>(`${this.base}/parametros/categorias`);
  }

  salvarCategoria(id: string | null, dados: GravacaoCategoria): Observable<Categoria> {
    return id ? this.http.put<Categoria>(`${this.base}/parametros/categorias/${id}`, dados) : this.http.post<Categoria>(`${this.base}/parametros/categorias`, dados);
  }

  excluirCategoria(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/categorias/${id}`);
  }

  // --- Categorias ITIL ---

  categoriasItil(): Observable<CategoriaItil[]> {
    return this.http.get<CategoriaItil[]>(`${this.base}/parametros/categorias-itil`);
  }

  salvarCategoriaItil(id: string | null, dados: GravacaoCategoriaItil): Observable<CategoriaItil> {
    return id ? this.http.put<CategoriaItil>(`${this.base}/parametros/categorias-itil/${id}`, dados)
      : this.http.post<CategoriaItil>(`${this.base}/parametros/categorias-itil`, dados);
  }

  excluirCategoriaItil(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/categorias-itil/${id}`);
  }

  // --- Migração do GLPI (Parâmetros) ---

  migracaoGlpi(): Observable<LeituraMigracaoGlpi> {
    return this.http.get<LeituraMigracaoGlpi>(`${this.base}/parametros/migracao-glpi`);
  }

  gravarMigracaoGlpi(dados: ConfiguracaoMigracaoGlpi & { senha: string | null }): Observable<LeituraMigracaoGlpi> {
    return this.http.put<LeituraMigracaoGlpi>(`${this.base}/parametros/migracao-glpi`, dados);
  }

  testarMigracaoGlpi(): Observable<{ versao: string; chamados: number }> {
    return this.http.post<{ versao: string; chamados: number }>(`${this.base}/parametros/migracao-glpi/testar`, {});
  }

  executarMigracaoGlpi(modo: 'novidades' | 'refazer'): Observable<LeituraMigracaoGlpi> {
    return this.http.post<LeituraMigracaoGlpi>(`${this.base}/parametros/migracao-glpi/executar`, { modo });
  }

  /** As ativas, para quem atende escolher no chamado. */
  categoriasItilAtivas(): Observable<CategoriaItilResumo[]> {
    return this.http.get<CategoriaItilResumo[]>(`${this.base}/categorias-itil`);
  }

  classificar(numero: number, versao: number, categoriaItilId: string | null): Observable<ChamadoDetalhe> {
    return this.http.put<ChamadoDetalhe>(`${this.base}/${numero}/categoria-itil`, { versao, categoria_itil_id: categoriaItilId });
  }

  // --- Marco 3 ---

  geral(): Observable<ParametrosGerais> {
    return this.http.get<ParametrosGerais>(`${this.base}/parametros/geral`);
  }

  salvarGeral(dados: ParametrosGerais): Observable<ParametrosGerais> {
    return this.http.put<ParametrosGerais>(`${this.base}/parametros/geral`, dados);
  }

  statusBase(): Observable<StatusApresentacao[]> {
    return this.http.get<StatusApresentacao[]>(`${this.base}/parametros/status`);
  }

  salvarStatus(status: string, nome: string, cor: string): Observable<StatusApresentacao[]> {
    return this.http.put<StatusApresentacao[]>(`${this.base}/parametros/status/${status}`, { nome, cor });
  }

  substatus(): Observable<Substatus[]> {
    return this.http.get<Substatus[]>(`${this.base}/substatus`);
  }

  salvarSubstatus(id: string | null, dados: Omit<Substatus, 'id'>): Observable<Substatus> {
    return id ? this.http.put<Substatus>(`${this.base}/parametros/substatus/${id}`, dados) : this.http.post<Substatus>(`${this.base}/parametros/substatus`, dados);
  }

  excluirSubstatus(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/substatus/${id}`);
  }

  setoresAtendimento(): Observable<SetorAtendimento[]> {
    return this.http.get<SetorAtendimento[]>(`${this.base}/parametros/setores-atendimento`);
  }

  salvarSetorAtendimento(setorId: number, veTodos: boolean): Observable<SetorAtendimento> {
    return this.http.put<SetorAtendimento>(`${this.base}/parametros/setores-atendimento/${setorId}`, { ve_todos: veTodos });
  }

  recorrentes(): Observable<Recorrente[]> {
    return this.http.get<Recorrente[]>(`${this.base}/parametros/recorrentes`);
  }

  salvarRecorrente(id: string | null, dados: GravacaoRecorrente): Observable<Recorrente> {
    return id ? this.http.put<Recorrente>(`${this.base}/parametros/recorrentes/${id}`, dados) : this.http.post<Recorrente>(`${this.base}/parametros/recorrentes`, dados);
  }

  excluirRecorrente(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/recorrentes/${id}`);
  }

  saude(): Observable<SaudeChamados> {
    return this.http.get<SaudeChamados>(`${this.base}/saude`);
  }

  /** Painel de quem atende: o setor da pessoa e os de baixo (`setorId` escolhe um deles). */
  painel(setorId: number | null): Observable<EstadoPainel> {
    const params = setorId === null ? new HttpParams() : new HttpParams().set('setor_id', setorId);
    return this.http.get<EstadoPainel>(`${this.base}/painel`, { params });
  }

  configPainel(): Observable<ConfigPainel> {
    return this.http.get<ConfigPainel>(`${this.base}/parametros/painel`);
  }

  salvarConfigPainel(dados: ConfigPainel): Observable<ConfigPainel> {
    return this.http.put<ConfigPainel>(`${this.base}/parametros/painel`, dados);
  }

  parametrosRh(): Observable<ParametrosRh> {
    return this.http.get<ParametrosRh>(`${this.base}/parametros/rh`);
  }

  salvarParametrosRh(destino: ParametrosRh['destino'], servicos: Record<string, ConfigServicoRh>, servicosExoneracao: Record<string, ConfigServicoRh>): Observable<ParametrosRh> {
    return this.http.put<ParametrosRh>(`${this.base}/parametros/rh`, { destino, servicos, servicos_exoneracao: servicosExoneracao });
  }

  avaliar(numero: number, nota: number, comentario = ''): Observable<ChamadoDetalhe> {
    return this.http.post<ChamadoDetalhe>(`${this.base}/${numero}/satisfacao`, { nota, comentario });
  }

  respostasProntas(): Observable<RespostaPronta[]> {
    return this.http.get<RespostaPronta[]>(`${this.base}/respostas-prontas`);
  }

  motivosPendencia(): Observable<MotivoPendencia[]> {
    return this.http.get<MotivoPendencia[]>(`${this.base}/motivos-pendencia`);
  }

  relatorios(inicio: string, fim: string, setorId: number | null): Observable<RelatorioChamados> {
    let params = new HttpParams();
    if (inicio) params = params.set('inicio', inicio);
    if (fim) params = params.set('fim', fim);
    if (setorId !== null) params = params.set('setor_id', setorId);
    return this.http.get<RelatorioChamados>(`${this.base}/relatorios`, { params });
  }

  /** Baixa a lista de chamados abertos no período (PDF paisagem ou XLSX); o nome do arquivo vem da API. */
  exportarRelatorio(inicio: string, fim: string, setorId: number | null, comSolucao: boolean, formato: 'pdf' | 'xlsx'): Observable<HttpResponse<Blob>> {
    let params = new HttpParams().set('inicio', inicio).set('fim', fim).set('com_solucao', comSolucao).set('formato', formato);
    if (setorId !== null) params = params.set('setor_id', setorId);
    return baixarArquivo(this.http, `${this.base}/relatorios/exportar?${params.toString()}`, `chamados.${formato}`);
  }

  parametrosRespostas(): Observable<RespostaPronta[]> {
    return this.http.get<RespostaPronta[]>(`${this.base}/parametros/respostas-prontas`);
  }

  salvarResposta(id: string | null, dados: GravacaoRespostaPronta): Observable<RespostaPronta> {
    return id ? this.http.put<RespostaPronta>(`${this.base}/parametros/respostas-prontas/${id}`, dados)
      : this.http.post<RespostaPronta>(`${this.base}/parametros/respostas-prontas`, dados);
  }

  excluirResposta(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/respostas-prontas/${id}`);
  }

  parametrosMotivos(): Observable<MotivoPendencia[]> {
    return this.http.get<MotivoPendencia[]>(`${this.base}/parametros/motivos-pendencia`);
  }

  salvarMotivo(id: string | null, dados: Omit<MotivoPendencia, 'id'>): Observable<MotivoPendencia> {
    return id ? this.http.put<MotivoPendencia>(`${this.base}/parametros/motivos-pendencia/${id}`, dados)
      : this.http.post<MotivoPendencia>(`${this.base}/parametros/motivos-pendencia`, dados);
  }

  excluirMotivo(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/parametros/motivos-pendencia/${id}`);
  }

  private formulario(dados: object, arquivos: File[]): FormData {
    const corpo = new FormData();
    corpo.append('dados', JSON.stringify(dados));
    for (const arquivo of arquivos) corpo.append('arquivos', arquivo, arquivo.name);
    return corpo;
  }
}
