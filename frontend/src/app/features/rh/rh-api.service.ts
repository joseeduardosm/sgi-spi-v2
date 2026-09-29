// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API do Módulo RH (/api/rh).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import {
  Afastamento, CadastroRh, CompetenciaFolha, DadosFuncionais, Feriado, MeusAfastamentos, PainelAfastamentos, PapeisRh, ParametrosRh, TipoAfastamento, UsuarioPendente,
} from './rh.models';

/** Filtros do painel de afastamentos. */
export interface FiltrosPainel {
  visao: 'mensal' | 'anual';
  ano: number;
  mes?: number;
  pessoa_id?: number | null;
  setor_id?: number | null;
  tipo?: TipoAfastamento | '';
}

@Injectable({ providedIn: 'root' })
export class RhApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/rh`;

  papeis(): Observable<PapeisRh> {
    return this.http.get<PapeisRh>(`${this.base}/papeis`);
  }

  // --- Cadastro (CGP) ---
  pendencias(): Observable<UsuarioPendente[]> {
    return this.http.get<UsuarioPendente[]>(`${this.base}/cadastro/pendencias`);
  }

  cadastro(usuarioId: number): Observable<CadastroRh> {
    return this.http.get<CadastroRh>(`${this.base}/cadastro/usuarios/${usuarioId}`);
  }

  validar(alteracaoId: string): Observable<CadastroRh> {
    return this.http.post<CadastroRh>(`${this.base}/cadastro/alteracoes/${alteracaoId}/validar`, {});
  }

  recusar(alteracaoId: string, justificativa: string, valorCorrigido: string | null): Observable<CadastroRh> {
    return this.http.post<CadastroRh>(`${this.base}/cadastro/alteracoes/${alteracaoId}/recusar`, { justificativa, valor_corrigido: valorCorrigido });
  }

  salvarFuncionais(usuarioId: number, dados: Omit<DadosFuncionais, 'autorizador_nome' | 'autorizador_sugerido_id' | 'substituto_nome' | 'atualizado_por_nome' | 'atualizado_em' | 'periodos'>): Observable<CadastroRh> {
    return this.http.put<CadastroRh>(`${this.base}/cadastro/usuarios/${usuarioId}/funcionais`, dados);
  }

  /** Ajuste da CGP nos dias creditados do período aquisitivo vigente. */
  ajustarPeriodo(usuarioId: number, diasCreditados: number): Observable<CadastroRh> {
    return this.http.put<CadastroRh>(`${this.base}/cadastro/usuarios/${usuarioId}/periodo-vigente`, { dias_creditados: diasCreditados });
  }

  // --- Parâmetros ---
  /** Feriados e pontos facultativos do ano (todos leem). */
  feriados(ano: number): Observable<Feriado[]> {
    return this.http.get<Feriado[]>(`${this.base}/feriados`, { params: { ano } });
  }

  /** Cadastra (sem id) ou altera (com id) um feriado ou ponto facultativo (só CGP). */
  salvarFeriado(dados: Omit<Feriado, 'id'>, id?: string): Observable<Feriado> {
    const corpo = { data: dados.data, descricao: dados.descricao, tipo: dados.tipo, abrangencia: dados.abrangencia };
    return id ? this.http.put<Feriado>(`${this.base}/feriados/${id}`, corpo) : this.http.post<Feriado>(`${this.base}/feriados`, corpo);
  }

  excluirFeriado(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/feriados/${id}`);
  }

  /** Meses disponíveis para a folha de ponto (o atual vem marcado). */
  competenciasFolha(): Observable<CompetenciaFolha[]> {
    return this.http.get<CompetenciaFolha[]>(`${this.base}/folha-ponto/competencias`);
  }

  /** Baixa a folha de ponto do próprio usuário (PDF) na competência AAAA-MM. */
  folhaPonto(competencia: string) {
    return baixarArquivo(this.http, `${this.base}/folha-ponto?competencia=${competencia}`, `folha-ponto-${competencia}.pdf`);
  }

  parametros(): Observable<ParametrosRh> {
    return this.http.get<ParametrosRh>(`${this.base}/parametros`);
  }

  salvarParametros(dados: ParametrosRh): Observable<ParametrosRh> {
    return this.http.put<ParametrosRh>(`${this.base}/parametros`, dados);
  }

  // --- Afastamentos ---
  meus(exercicio: number): Observable<MeusAfastamentos> {
    return this.http.get<MeusAfastamentos>(`${this.base}/afastamentos/meus`, { params: new HttpParams().set('exercicio', exercicio) });
  }

  agendar(tipo: TipoAfastamento, inicio: string, fim: string): Observable<Afastamento> {
    return this.http.post<Afastamento>(`${this.base}/afastamentos`, { tipo, inicio, fim });
  }

  alterar(id: string, tipo: TipoAfastamento, inicio: string, fim: string): Observable<Afastamento> {
    return this.http.put<Afastamento>(`${this.base}/afastamentos/${id}`, { tipo, inicio, fim });
  }

  cancelar(id: string, justificativa: string | null): Observable<Afastamento> {
    return this.http.post<Afastamento>(`${this.base}/afastamentos/${id}/cancelar`, { justificativa });
  }

  aprovar(id: string): Observable<Afastamento> {
    return this.http.post<Afastamento>(`${this.base}/afastamentos/${id}/aprovar`, {});
  }

  recusarAfastamento(id: string, justificativa: string): Observable<Afastamento> {
    return this.http.post<Afastamento>(`${this.base}/afastamentos/${id}/recusar`, { justificativa });
  }

  aprovacoes(): Observable<Afastamento[]> {
    return this.http.get<Afastamento[]>(`${this.base}/afastamentos/aprovacoes`);
  }

  painel(filtros: FiltrosPainel): Observable<PainelAfastamentos> {
    return this.http.get<PainelAfastamentos>(`${this.base}/afastamentos/painel`, { params: this.parametrosPainel(filtros) });
  }

  exportar(filtros: FiltrosPainel, formato: 'pdf' | 'xlsx') {
    const params = this.parametrosPainel(filtros).set('formato', formato);
    return baixarArquivo(this.http, `${this.base}/afastamentos/painel/exportar?${params.toString()}`, `ferias-licencas.${formato}`);
  }

  private parametrosPainel(f: FiltrosPainel): HttpParams {
    let p = new HttpParams().set('visao', f.visao).set('ano', f.ano);
    if (f.visao === 'mensal' && f.mes) p = p.set('mes', f.mes);
    if (f.pessoa_id) p = p.set('pessoa_id', f.pessoa_id);
    if (f.setor_id) p = p.set('setor_id', f.setor_id);
    if (f.tipo) p = p.set('tipo', f.tipo);
    return p;
  }
}
