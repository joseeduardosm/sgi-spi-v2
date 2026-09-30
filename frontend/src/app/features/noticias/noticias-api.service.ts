// Criado por José Eduardo Santana Martins
// Este arquivo serve para centralizar as chamadas à API do Módulo Notícias e do portal.

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { ambiente } from '../../../environments/ambiente';
import {
  Atalho, Categoria, Ciencias, ConfiguracaoGestao, ConfiguracaoPortal, GravacaoNoticia, ModoCapa, NoticiaGestao, NoticiaGestaoResumo,
  NoticiaPublica, PaginaNoticias, PapelNoticias, Pessoa, Portal, Revisao, SetorResumo,
} from './noticias.models';

export interface FiltrosArquivo { busca: string; categoria: number | null; ano: number | null; mes: number | null }

@Injectable({ providedIn: 'root' })
export class NoticiasApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/noticias`;
  private readonly portalBase = `${ambiente.urlApi}/portal`;

  // --- Público ---
  portal(): Observable<Portal> {
    return this.http.get<Portal>(this.portalBase);
  }

  publicas(f: FiltrosArquivo, pagina: number, tamanho = 12): Observable<PaginaNoticias> {
    let p = new HttpParams().set('pagina', pagina).set('tamanho', tamanho);
    if (f.busca.trim()) p = p.set('busca', f.busca.trim());
    if (f.categoria) p = p.set('categoria_id', f.categoria);
    if (f.ano) p = p.set('ano', f.ano);
    if (f.mes) p = p.set('mes', f.mes);
    return this.http.get<PaginaNoticias>(`${this.base}/publicas`, { params: p });
  }

  publica(slug: string): Observable<NoticiaPublica> {
    return this.http.get<NoticiaPublica>(`${this.base}/publicas/${encodeURIComponent(slug)}`);
  }

  // --- Gestão ---
  papel(): Observable<PapelNoticias> {
    return this.http.get<PapelNoticias>(`${this.base}/papel`);
  }

  listar(situacao: string, busca: string): Observable<NoticiaGestaoResumo[]> {
    let p = new HttpParams();
    if (situacao) p = p.set('situacao', situacao);
    if (busca.trim()) p = p.set('busca', busca.trim());
    return this.http.get<NoticiaGestaoResumo[]>(this.base, { params: p });
  }

  detalhe(id: string): Observable<NoticiaGestao> {
    return this.http.get<NoticiaGestao>(`${this.base}/${id}`);
  }

  criar(dados: GravacaoNoticia): Observable<NoticiaGestao> {
    return this.http.post<NoticiaGestao>(this.base, dados);
  }

  salvar(id: string, dados: GravacaoNoticia): Observable<NoticiaGestao> {
    return this.http.put<NoticiaGestao>(`${this.base}/${id}`, dados);
  }

  excluir(id: string) {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  acao(id: string, acao: 'enviar-revisao' | 'arquivar' | 'desarquivar'): Observable<NoticiaGestao> {
    return this.http.post<NoticiaGestao>(`${this.base}/${id}/${acao}`, {});
  }

  aprovar(id: string, publicarEm: string | null): Observable<NoticiaGestao> {
    return this.http.post<NoticiaGestao>(`${this.base}/${id}/aprovar`, { publicar_em: publicarEm });
  }

  devolver(id: string, motivo: string): Observable<NoticiaGestao> {
    return this.http.post<NoticiaGestao>(`${this.base}/${id}/devolver`, { motivo });
  }

  capa(id: string, modo: ModoCapa, recorte: object | null, arquivo: File | null): Observable<NoticiaGestao> {
    const corpo = new FormData();
    corpo.append('modo', modo);
    corpo.append('recorte', recorte ? JSON.stringify(recorte) : '');
    if (arquivo) corpo.append('arquivo', arquivo);
    return this.http.post<NoticiaGestao>(`${this.base}/${id}/capa`, corpo);
  }

  anexar(id: string, arquivo: File): Observable<NoticiaGestao> {
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    return this.http.post<NoticiaGestao>(`${this.base}/${id}/anexos`, corpo);
  }

  removerAnexo(id: string, anexoId: string): Observable<NoticiaGestao> {
    return this.http.delete<NoticiaGestao>(`${this.base}/${id}/anexos/${anexoId}`);
  }

  revisoes(id: string): Observable<Revisao[]> {
    return this.http.get<Revisao[]>(`${this.base}/${id}/revisoes`);
  }

  ciencias(id: string): Observable<Ciencias> {
    return this.http.get<Ciencias>(`${this.base}/${id}/ciencias`);
  }

  /** Arquivo da gestão (exige token): devolve um endereço local (blob) para <img> e <iframe>. */
  blob(url: string): Observable<string> {
    return this.http.get(url, { responseType: 'blob' }).pipe(map((b) => URL.createObjectURL(b)));
  }

  categorias(): Observable<Categoria[]> {
    return this.http.get<Categoria[]>(`${this.base}/categorias`);
  }

  salvarCategoria(dados: Omit<Categoria, 'id'>, id?: number): Observable<Categoria> {
    return id ? this.http.put<Categoria>(`${this.base}/categorias/${id}`, dados) : this.http.post<Categoria>(`${this.base}/categorias`, dados);
  }

  setores(): Observable<SetorResumo[]> {
    return this.http.get<SetorResumo[]>(`${this.base}/opcoes-setores`);
  }

  /** Fonte do seletor de usuários (formato `OpcaoUsuario`). */
  opcoesUsuarios = (busca: string): Observable<OpcaoUsuario[]> =>
    this.http.get<Pessoa[]>(`${this.base}/opcoes-usuarios`, { params: { busca } })
      .pipe(map((l) => l.map((p) => ({ id: p.id, login: p.login, nome_completo: p.nome, cargo: '', ativo: true }))));

  configuracao(): Observable<ConfiguracaoGestao> {
    return this.http.get<ConfiguracaoGestao>(`${this.portalBase}/configuracao`);
  }

  salvarConfiguracao(dados: ConfiguracaoPortal & { curadoria: string[] | null }): Observable<ConfiguracaoGestao> {
    return this.http.put<ConfiguracaoGestao>(`${this.portalBase}/configuracao`, dados);
  }

  atalhos(): Observable<Atalho[]> {
    return this.http.get<Atalho[]>(`${this.portalBase}/atalhos`);
  }

  salvarAtalho(dados: { titulo: string; url: string; ativo: boolean; nova_aba: boolean }, imagem: File | null, id?: number): Observable<Atalho> {
    const corpo = new FormData();
    corpo.append('titulo', dados.titulo);
    corpo.append('url', dados.url);
    corpo.append('ativo', String(dados.ativo));
    corpo.append('nova_aba', String(dados.nova_aba));
    if (imagem) corpo.append('imagem', imagem);
    return id ? this.http.put<Atalho>(`${this.portalBase}/atalhos/${id}`, corpo) : this.http.post<Atalho>(`${this.portalBase}/atalhos`, corpo);
  }

  excluirAtalho(id: number) {
    return this.http.delete<void>(`${this.portalBase}/atalhos/${id}`);
  }

  ordenarAtalhos(ids: number[]) {
    return this.http.post<void>(`${this.portalBase}/atalhos/ordem`, { ids });
  }
}
