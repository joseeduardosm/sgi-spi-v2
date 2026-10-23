// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API da admissão, dos modelos, dos checklists, das boas-vindas e da bio do RH (/api/rh).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { baixarArquivo } from '../../shared/utilitarios/download';
import { Bio, BoasVindas, Checklist, GravacaoChecklist, LeituraAdmissao, ModeloRh, ResumoAdmissao, TextoParaCopiar, TipoProtocoloResolucao } from './rh-admissao.models';
import { GravacaoFicha, LeituraFicha } from './rh-pre-cadastro.models';

@Injectable({ providedIn: 'root' })
export class RhAdmissaoApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/rh`;
  private readonly adm = `${this.base}/admissoes`;

  // --- Admissões ---
  listar(status = '', busca = ''): Observable<ResumoAdmissao[]> {
    let params = new HttpParams();
    if (status) params = params.set('status', status);
    if (busca) params = params.set('busca', busca);
    return this.http.get<ResumoAdmissao[]>(this.adm, { params });
  }
  obter(id: number): Observable<LeituraAdmissao> { return this.http.get<LeituraAdmissao>(`${this.adm}/${id}`); }
  iniciar(fichaId: number): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(this.adm, { ficha_id: fichaId }); }
  cancelar(id: number): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/cancelar`, {}); }
  solicitacoes(): Observable<Record<string, string>> { return this.http.get<Record<string, string>>(`${this.adm}/solicitacoes`); }
  tiposProtocolo(todos = false): Observable<TipoProtocoloResolucao[]> { return this.http.get<TipoProtocoloResolucao[]>(`${this.adm}/tipos-protocolo`, { params: todos ? { todos: true } : {} }); }

  /** Foto da pessoa (PNG ou JPG): vai no formulário do GLPI e, com a conta criada, para o Diretório (intranet). */
  enviarFoto(id: number, arquivo: File): Observable<LeituraAdmissao> {
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    return this.http.put<LeituraAdmissao>(`${this.adm}/${id}/foto`, corpo);
  }
  removerFoto(id: number): Observable<LeituraAdmissao> { return this.http.delete<LeituraAdmissao>(`${this.adm}/${id}/foto`); }
  urlFoto(id: number): string { return `${this.adm}/${id}/foto`; }

  abrirChamado(id: number, solicitacoes: Record<string, boolean>, observacoes: string, usuarioEspelho: string): Observable<LeituraAdmissao> {
    return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/chamado`, { solicitacoes, observacoes, usuario_espelho: usuarioEspelho });
  }
  registrarDocumento(id: number, docId: number, enviadoEm: string, observacao: string, comprovante: File | null): Observable<LeituraAdmissao> {
    const corpo = new FormData();
    corpo.append('enviado_em', enviadoEm);
    corpo.append('observacao', observacao);
    if (comprovante) corpo.append('comprovante', comprovante);
    return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/documentos/${docId}`, corpo);
  }
  desfazerDocumento(id: number, docId: number): Observable<LeituraAdmissao> { return this.http.delete<LeituraAdmissao>(`${this.adm}/${id}/documentos/${docId}`); }
  concluirDocumentos(id: number): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/documentos/concluir`, {}); }
  baixarComprovante(id: number, docId: number) { return baixarArquivo(this.http, `${this.adm}/${id}/documentos/${docId}/comprovante`, 'comprovante'); }

  gerarResolucao(id: number): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/resolucao`, {}); }
  salvarResolucao(id: number, html: string): Observable<LeituraAdmissao> { return this.http.put<LeituraAdmissao>(`${this.adm}/${id}/resolucao`, { html }); }
  baixarResolucao(id: number) { return baixarArquivo(this.http, `${this.adm}/${id}/resolucao.pdf`, 'resolucao.pdf'); }
  resolucaoParaCopiar(id: number): Observable<TextoParaCopiar> { return this.http.get<TextoParaCopiar>(`${this.adm}/${id}/resolucao/copia`); }
  liberarNumero(id: number, motivo: string): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/protocolo/liberar`, { motivo }); }
  reservarNumero(id: number, tipoId: string): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/protocolo`, { tipo_protocolo_id: tipoId }); }
  registrarPublicacao(id: number, arquivo: File, publicadoEm: string): Observable<LeituraAdmissao> {
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    corpo.append('publicado_em', publicadoEm);
    return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/publicacao`, corpo);
  }
  ajustarPublicacao(id: number, publicadoEm: string): Observable<LeituraAdmissao> { return this.http.put<LeituraAdmissao>(`${this.adm}/${id}/publicacao`, { publicado_em: publicadoEm }); }
  baixarPublicacao(id: number) { return baixarArquivo(this.http, `${this.adm}/${id}/publicacao.pdf`, 'publicacao.pdf'); }
  /** O e-mail de nomeação sai sozinho ao registrar a publicação; isto só reenvia quando o envio automático falhou. */
  reenviarEmail(id: number): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/email`, {}); }
  registrarPosse(id: number, posseEm: string): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/posse`, { posse_em: posseEm }); }
  salvarTermo(id: number, html: string): Observable<LeituraAdmissao> { return this.http.put<LeituraAdmissao>(`${this.adm}/${id}/termo`, { html }); }
  baixarTermo(id: number) { return baixarArquivo(this.http, `${this.adm}/${id}/termo.pdf`, 'termo-de-posse.pdf'); }
  concluir(id: number): Observable<LeituraAdmissao> { return this.http.post<LeituraAdmissao>(`${this.adm}/${id}/concluir`, {}); }

  // --- Modelos e checklists ---
  modelos(): Observable<ModeloRh[]> { return this.http.get<ModeloRh[]>(`${this.base}/modelos`); }
  placeholders(): Observable<Record<string, string>> { return this.http.get<Record<string, string>>(`${this.base}/modelos/placeholders`); }
  salvarModelo(tipo: string, assunto: string, html: string): Observable<ModeloRh> { return this.http.put<ModeloRh>(`${this.base}/modelos/${tipo}`, { assunto, html }); }
  restaurarModelo(tipo: string): Observable<ModeloRh> { return this.http.post<ModeloRh>(`${this.base}/modelos/${tipo}/restaurar`, {}); }
  checklists(): Observable<Checklist[]> { return this.http.get<Checklist[]>(`${this.base}/checklists`); }
  criarChecklist(dados: GravacaoChecklist): Observable<Checklist> { return this.http.post<Checklist>(`${this.base}/checklists`, dados); }
  alterarChecklist(id: number, dados: GravacaoChecklist): Observable<Checklist> { return this.http.put<Checklist>(`${this.base}/checklists/${id}`, dados); }
  excluirChecklist(id: number): Observable<void> { return this.http.delete<void>(`${this.base}/checklists/${id}`); }

  // --- Da própria pessoa ---
  boasVindas(): Observable<BoasVindas> { return this.http.get<BoasVindas>(`${this.base}/boas-vindas`); }
  confirmarBoasVindas(): Observable<void> { return this.http.post<void>(`${this.base}/boas-vindas/confirmar`, {}); }
  minhaBio(): Observable<Bio> { return this.http.get<Bio>(`${this.base}/minha-bio`); }
  salvarBio(dados: Bio): Observable<Bio> { return this.http.put<Bio>(`${this.base}/minha-bio`, dados); }
  minhaFicha(): Observable<LeituraFicha | null> { return this.http.get<LeituraFicha | null>(`${this.base}/minha-ficha`); }
  enviarMinhaFicha(dados: Omit<GravacaoFicha, 'login_proposto' | 'status'>): Observable<LeituraFicha> { return this.http.put<LeituraFicha>(`${this.base}/minha-ficha`, dados); }
  validarFicha(id: number): Observable<LeituraFicha> { return this.http.post<LeituraFicha>(`${this.base}/pre-cadastros/${id}/validar`, {}); }
}
