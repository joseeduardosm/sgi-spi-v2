// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API do Patrimônio (/api/patrimonio).

import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { baixarArquivo } from '../../shared/utilitarios/download';
import {
  AcessoPatrimonio, Agrupamento, Baixa, Bem, Classificacao, DadosBem, Evento, FiltrosBens, Grupo, ListaBens, PrefixoChapa, Localizacao, MotivoBaixa, Movimentacao, PainelPatrimonio,
} from './patrimonio.models';

/** Converte um objeto em parâmetros de consulta, ignorando o que está vazio. */
function parametros(filtros: object): HttpParams {
  let p = new HttpParams();
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor !== undefined && valor !== null && valor !== '') p = p.set(chave, String(valor));
  }
  return p;
}

@Injectable({ providedIn: 'root' })
export class PatrimonioApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/patrimonio`;
  private readonly cabecalhoCanal = (canal: string) => new HttpHeaders({ 'X-Canal': canal });
  /** Canal gravado no histórico: celular (telas estreitas) ou web. A fila offline envia como `offline`. */
  private canal(): string {
    return typeof window !== 'undefined' && window.matchMedia?.('(max-width: 760px)').matches ? 'celular' : 'web';
  }
  private get opcoes() { return { headers: this.cabecalhoCanal(this.canal()) }; }

  acesso(): Observable<AcessoPatrimonio> { return this.http.get<AcessoPatrimonio>(`${this.base}/acesso`); }

  // Localizações, grupos e parâmetros
  opcoesSetores(): Observable<{ id: number; nome: string }[]> { return this.http.get<{ id: number; nome: string }[]>(`${this.base}/opcoes-setores`); }
  opcoesUsuarios(busca = ''): Observable<OpcaoUsuario[]> { return this.http.get<OpcaoUsuario[]>(`${this.base}/opcoes-usuarios`, { params: parametros({ busca }) }); }
  localizacoes(): Observable<Localizacao[]> { return this.http.get<Localizacao[]>(`${this.base}/localizacoes`); }
  criarSala(ladoId: string, numero: number): Observable<Localizacao> { return this.http.post<Localizacao>(`${this.base}/localizacoes/lados/${ladoId}/salas`, { numero }); }
  criarAreaComum(andarId: string, nome: string, sigla = 'H'): Observable<Localizacao> { return this.http.post<Localizacao>(`${this.base}/localizacoes/andares/${andarId}/areas-comuns`, { nome, sigla }); }
  dadosSala(id: string, setorId: number | null, responsavelId: number | null): Observable<Localizacao> {
    return this.http.put<Localizacao>(`${this.base}/localizacoes/${id}/dados`, { setor_id: setorId, responsavel_id: responsavelId });
  }
  atualizarLocalizacao(id: string, dados: { nome?: string; ativo?: boolean }): Observable<Localizacao> { return this.http.put<Localizacao>(`${this.base}/localizacoes/${id}`, dados); }
  excluirSala(id: string): Observable<void> { return this.http.delete<void>(`${this.base}/localizacoes/${id}`); }
  grupos(todos = false): Observable<Grupo[]> { return this.http.get<Grupo[]>(`${this.base}/grupos`, { params: parametros({ todos }) }); }
  criarGrupo(dados: Partial<Grupo>): Observable<Grupo> { return this.http.post<Grupo>(`${this.base}/grupos`, dados); }
  atualizarGrupo(id: string, dados: Partial<Grupo>): Observable<Grupo> { return this.http.put<Grupo>(`${this.base}/grupos/${id}`, dados); }
  prefixos(todos = false): Observable<PrefixoChapa[]> { return this.http.get<PrefixoChapa[]>(`${this.base}/prefixos`, { params: parametros({ todos }) }); }
  criarPrefixo(codigo: string): Observable<PrefixoChapa> { return this.http.post<PrefixoChapa>(`${this.base}/prefixos`, { codigo }); }
  atualizarPrefixo(id: string, dados: { padrao?: boolean; ativo?: boolean }): Observable<PrefixoChapa> { return this.http.put<PrefixoChapa>(`${this.base}/prefixos/${id}`, dados); }
  excluirPrefixo(id: string): Observable<void> { return this.http.delete<void>(`${this.base}/prefixos/${id}`); }
  excluirGrupo(id: string): Observable<void> { return this.http.delete<void>(`${this.base}/grupos/${id}`); }
  parametros(): Observable<{ ufesp: string }> { return this.http.get<{ ufesp: string }>(`${this.base}/parametros`); }
  salvarParametros(ufesp: string): Observable<{ ufesp: string }> { return this.http.put<{ ufesp: string }>(`${this.base}/parametros`, { ufesp }); }

  // Bens
  bens(filtros: FiltrosBens): Observable<ListaBens> { return this.http.get<ListaBens>(`${this.base}/bens`, { params: parametros(filtros) }); }
  bem(id: string): Observable<Bem> { return this.http.get<Bem>(`${this.base}/bens/${id}`); }
  /** Descrições já cadastradas que casam com o texto (autocompletar do cadastro). */
  sugestoesDescricao(texto: string): Observable<string[]> { return this.http.get<string[]>(`${this.base}/bens/sugestoes-descricao`, { params: parametros({ q: texto }) }); }
  /** Levantamento inicial: informa a sala de um bem que ainda está sem local (sem movimentação nem aprovação). */
  localizarBem(id: string, localizacaoId: string): Observable<Bem> { return this.http.post<Bem>(`${this.base}/bens/${id}/localizar`, { localizacao_id: localizacaoId }); }
  bemPorChapa(chapa: string): Observable<Bem> { return this.http.get<Bem>(`${this.base}/bens/chapa/${encodeURIComponent(chapa)}`); }
  cadastrarBem(dados: DadosBem, canal?: string): Observable<Bem> {
    return this.http.post<Bem>(`${this.base}/bens`, dados, canal ? { headers: this.cabecalhoCanal(canal) } : this.opcoes);
  }
  alterarBem(id: string, dados: Partial<DadosBem>): Observable<Bem> { return this.http.put<Bem>(`${this.base}/bens/${id}`, dados, this.opcoes); }
  ajustarLocal(id: string, localizacaoId: string, motivo: string): Observable<Bem> {
    return this.http.post<Bem>(`${this.base}/bens/${id}/local`, { localizacao_id: localizacaoId, motivo }, this.opcoes);
  }
  reverter(id: string, justificativa: string, localizacaoId?: string): Observable<Bem> {
    return this.http.post<Bem>(`${this.base}/bens/${id}/reverter`, { justificativa, localizacao_id: localizacaoId ?? null });
  }
  adicionarFoto(id: string, arquivo: Blob, nome: string): Observable<Bem> {
    const f = new FormData();
    f.append('arquivo', arquivo, nome);
    return this.http.post<Bem>(`${this.base}/bens/${id}/fotos`, f);
  }
  removerFoto(id: string, fotoId: string): Observable<Bem> { return this.http.delete<Bem>(`${this.base}/bens/${id}/fotos/${fotoId}`); }
  /** Endereço (autenticado pelo interceptador) da imagem de uma foto, para baixar como blob. */
  fotoBlob(id: string, fotoId: string): Observable<Blob> { return this.http.get(`${this.base}/bens/${id}/fotos/${fotoId}/arquivo`, { responseType: 'blob' }); }
  historico(id: string, campo?: string): Observable<Evento[]> { return this.http.get<Evento[]>(`${this.base}/bens/${id}/historico`, { params: parametros({ campo }) }); }
  trajeto(id: string): Observable<Evento[]> { return this.http.get<Evento[]>(`${this.base}/bens/${id}/trajeto`); }

  // Movimentações
  movimentacoes(filtros: object = {}): Observable<Movimentacao[]> { return this.http.get<Movimentacao[]>(`${this.base}/movimentacoes`, { params: parametros(filtros) }); }
  movimentacao(id: string): Observable<Movimentacao> { return this.http.get<Movimentacao>(`${this.base}/movimentacoes/${id}`); }
  solicitarMovimentacao(dados: { id_cliente?: string; bens_ids?: string[]; chapas?: string[]; destino_id: string; motivo: string }, canal?: string): Observable<Movimentacao> {
    return this.http.post<Movimentacao>(`${this.base}/movimentacoes`, dados, canal ? { headers: this.cabecalhoCanal(canal) } : this.opcoes);
  }
  acaoMovimentacao(id: string, acao: 'autorizar' | 'recusar' | 'cancelar' | 'concluir', motivo?: string): Observable<Movimentacao> {
    return this.http.post<Movimentacao>(`${this.base}/movimentacoes/${id}/${acao}`, motivo === undefined ? {} : { motivo }, this.opcoes);
  }
  receber(id: string, bemId: string): Observable<Movimentacao> { return this.http.post<Movimentacao>(`${this.base}/movimentacoes/${id}/receber`, { bem_id: bemId }, this.opcoes); }

  // Inservíveis e extraviados
  classificacoes(filtros: object = {}): Observable<Classificacao[]> { return this.http.get<Classificacao[]>(`${this.base}/classificacoes`, { params: parametros(filtros) }); }
  classificacao(id: string): Observable<Classificacao> { return this.http.get<Classificacao>(`${this.base}/classificacoes/${id}`); }
  criarClassificacao(tipo: string, idCliente?: string): Observable<Classificacao> { return this.http.post<Classificacao>(`${this.base}/classificacoes`, { tipo, id_cliente: idCliente ?? null }); }
  /** Compartilha a lista (rascunho) com as pessoas indicadas, substituindo as anteriores. */
  compartilharClassificacao(id: string, usuariosIds: number[]): Observable<Classificacao> { return this.http.put<Classificacao>(`${this.base}/classificacoes/${id}/colaboradores`, { usuarios_ids: usuariosIds }); }
  descartarClassificacao(id: string): Observable<void> { return this.http.delete<void>(`${this.base}/classificacoes/${id}`); }
  incluirNaClassificacao(id: string, entrada: { chapa?: string; bem_id?: string }): Observable<Classificacao> { return this.http.post<Classificacao>(`${this.base}/classificacoes/${id}/bens`, entrada); }
  tirarDaClassificacao(id: string, itemId: string): Observable<Classificacao> { return this.http.delete<Classificacao>(`${this.base}/classificacoes/${id}/bens/${itemId}`); }
  /** Apaga a justificativa (e a categoria) dos itens. */
  removerJustificativa(id: string, itensIds: string[]): Observable<Classificacao> {
    return this.http.post<Classificacao>(`${this.base}/classificacoes/${id}/justificativa/remover`, { itens_ids: itensIds });
  }

  justificar(id: string, itensIds: string[], justificativa: string, categoria: string | null = null): Observable<Classificacao> {
    return this.http.post<Classificacao>(`${this.base}/classificacoes/${id}/justificativa`, { itens_ids: itensIds, justificativa, categoria });
  }
  anexarNaClassificacao(id: string, itemId: string, arquivo: File): Observable<Classificacao> {
    const f = new FormData();
    f.append('arquivo', arquivo, arquivo.name);
    return this.http.post<Classificacao>(`${this.base}/classificacoes/${id}/itens/${itemId}/anexo`, f);
  }
  baixarAnexoClassificacao(id: string, itemId: string): Observable<unknown> { return baixarArquivo(this.http, `${this.base}/classificacoes/${id}/itens/${itemId}/anexo`, 'anexo'); }
  enviarClassificacao(id: string): Observable<Classificacao> { return this.http.post<Classificacao>(`${this.base}/classificacoes/${id}/enviar`, {}); }
  decidirClassificacao(id: string, aprovadosIds: string[], motivoRecusa?: string): Observable<Classificacao> {
    return this.http.post<Classificacao>(`${this.base}/classificacoes/${id}/decisao`, { aprovados_ids: aprovadosIds, motivo_recusa: motivoRecusa ?? null });
  }

  // Baixas
  baixas(filtros: object = {}): Observable<Baixa[]> { return this.http.get<Baixa[]>(`${this.base}/baixas`, { params: parametros(filtros) }); }
  baixa(id: string): Observable<Baixa> { return this.http.get<Baixa>(`${this.base}/baixas/${id}`); }
  /** A baixa herda os bens aprovados de uma lista de inservíveis/extraviados já aprovada. */
  criarBaixa(classificacaoId: string, idCliente?: string): Observable<Baixa> { return this.http.post<Baixa>(`${this.base}/baixas`, { classificacao_id: classificacaoId, id_cliente: idCliente ?? null }); }
  /** Compartilha a baixa (rascunho) com as pessoas indicadas, substituindo as anteriores. */
  compartilharBaixa(id: string, usuariosIds: number[]): Observable<Baixa> { return this.http.put<Baixa>(`${this.base}/baixas/${id}/colaboradores`, { usuarios_ids: usuariosIds }); }
  descartarBaixa(id: string): Observable<void> { return this.http.delete<void>(`${this.base}/baixas/${id}`); }
  incluirNaBaixa(id: string, entrada: { chapa?: string; bem_id?: string }): Observable<Baixa> { return this.http.post<Baixa>(`${this.base}/baixas/${id}/bens`, entrada); }
  tirarDaBaixa(id: string, itemId: string): Observable<Baixa> { return this.http.delete<Baixa>(`${this.base}/baixas/${id}/bens/${itemId}`); }
  motivoBaixa(id: string, itensIds: string[], motivo: MotivoBaixa, processo: string): Observable<Baixa> {
    return this.http.post<Baixa>(`${this.base}/baixas/${id}/motivo`, { itens_ids: itensIds, motivo, processo });
  }
  enviarBaixa(id: string): Observable<Baixa> { return this.http.post<Baixa>(`${this.base}/baixas/${id}/enviar`, {}); }
  /** Conclui a baixa com o PDF do de acordo da autoridade (na maioria das vezes, a publicação no D.O.E.). */
  concluirBaixa(id: string, arquivo: File): Observable<Baixa> {
    const dados = new FormData();
    dados.append('arquivo', arquivo);
    return this.http.post<Baixa>(`${this.base}/baixas/${id}/conclusao`, dados);
  }
  recusarBaixa(id: string, motivo: string): Observable<Baixa> { return this.http.post<Baixa>(`${this.base}/baixas/${id}/recusa`, { motivo }); }
  baixarConclusaoBaixa(id: string): Observable<unknown> { return baixarArquivo(this.http, `${this.base}/baixas/${id}/conclusao`, 'de-acordo-baixa.pdf'); }
  /** Relatório consolidado (PDF) ou Excel de uma lista de inservíveis/extraviados. */
  relatorioClassificacao(id: string, formato: 'pdf' | 'xlsx', tipo: string): Observable<unknown> { return baixarArquivo(this.http, `${this.base}/classificacoes/${id}/relatorio?formato=${formato}`, `relatorio-${tipo}.${formato}`); }
  /** Relatório consolidado (PDF) ou Excel de uma baixa. */
  relatorioBaixa(id: string, formato: 'pdf' | 'xlsx'): Observable<unknown> { return baixarArquivo(this.http, `${this.base}/baixas/${id}/relatorio?formato=${formato}`, `relatorio-baixa.${formato}`); }
  baixarTermo(id: string): Observable<unknown> { return baixarArquivo(this.http, `${this.base}/baixas/${id}/termo`, 'termo-baixa.pdf'); }

  // Painel e exportação
  painel(filtros: { agrupar_por: Agrupamento; situacao?: string; conservacao?: number | ''; garantia?: string }): Observable<PainelPatrimonio> {
    return this.http.get<PainelPatrimonio>(`${this.base}/painel`, { params: parametros(filtros) });
  }
  bensDoGrupo(filtros: { agrupar_por: Agrupamento; chave: string; situacao?: string; conservacao?: number | ''; garantia?: string }): Observable<Bem[]> {
    return this.http.get<Bem[]>(`${this.base}/painel/grupo`, { params: parametros(filtros) });
  }
  exportar(relatorio: 'bens' | 'fora-garantia' | 'painel' | 'movimentacoes', formato: 'xlsx' | 'pdf', filtros: object = {}): Observable<unknown> {
    return baixarArquivo(this.http, `${this.base}/exportar/${relatorio}?${parametros({ formato, ...filtros }).toString()}`, `patrimonio.${formato}`);
  }
}
