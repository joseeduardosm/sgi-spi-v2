// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API do Diretório (ramais, aniversariantes, mural, favoritos, foto e preferências).

import { HttpClient, HttpParams, HttpResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { baixarArquivo } from '../../shared/utilitarios/download';
import { Aniversariante, ContatoDetalhe, FiltrosRamais, OpcoesFiltro, PaginaContatos, Parabens, PeriodoAniversario, Preferencias } from './diretorio.models';

@Injectable({ providedIn: 'root' })
export class DiretorioApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api/diretorio';

  ramais(f: FiltrosRamais, pagina: number, tamanho: number): Observable<PaginaContatos> {
    let params = new HttpParams().set('pagina', pagina).set('tamanho', tamanho);
    if (f.q.trim()) params = params.set('q', f.q.trim());
    if (f.setor) params = params.set('setor', f.setor);
    if (f.andar) params = params.set('andar', f.andar);
    if (f.predio) params = params.set('predio', f.predio);
    if (f.favoritos) params = params.set('favoritos', true);
    if (f.em_ferias) params = params.set('em_ferias', true);
    return this.http.get<PaginaContatos>(`${this.base}/ramais`, { params });
  }

  filtros(): Observable<OpcoesFiltro> {
    return this.http.get<OpcoesFiltro>(`${this.base}/filtros`);
  }

  detalhe(id: number): Observable<ContatoDetalhe> {
    return this.http.get<ContatoDetalhe>(`${this.base}/ramais/${id}`);
  }

  baixarVcard(id: number, nome: string): Observable<HttpResponse<Blob>> {
    return baixarArquivo(this.http, `${this.base}/ramais/${id}/vcard`, `${nome}.vcf`);
  }

  /** Endereço local (blob) do QR Code do contato, para usar em <img>. */
  qrcode(id: number): Observable<string> {
    return this.http.get(`${this.base}/ramais/${id}/qrcode`, { responseType: 'blob' }).pipe(map((b) => URL.createObjectURL(b)));
  }

  favoritar(id: number, favorito: boolean): Observable<void> {
    const url = `${this.base}/favoritos/${id}`;
    return favorito ? this.http.put<void>(url, null) : this.http.delete<void>(url);
  }

  aniversariantes(periodo: PeriodoAniversario): Observable<Aniversariante[]> {
    return this.http.get<Aniversariante[]>(`${this.base}/aniversariantes`, { params: { periodo } });
  }

  mural(id: number): Observable<Parabens[]> {
    return this.http.get<Parabens[]>(`${this.base}/aniversariantes/${id}/parabens`);
  }

  parabenizar(id: number, texto: string): Observable<Parabens> {
    return this.http.post<Parabens>(`${this.base}/aniversariantes/${id}/parabens`, { texto });
  }

  apagarRecado(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/aniversariantes/${id}/parabens`);
  }

  preferencias(): Observable<Preferencias> {
    return this.http.get<Preferencias>(`${this.base}/preferencias`);
  }

  ocultarAniversario(ocultar: boolean): Observable<Preferencias> {
    return this.http.patch<Preferencias>(`${this.base}/preferencias`, { ocultar_aniversario: ocultar });
  }

  enviarFoto(arquivo: File): Observable<Preferencias> {
    const corpo = new FormData();
    corpo.append('arquivo', arquivo, arquivo.name);
    return this.http.put<Preferencias>(`${this.base}/foto`, corpo);
  }

  removerFoto(): Observable<Preferencias> {
    return this.http.delete<Preferencias>(`${this.base}/foto`);
  }
}
