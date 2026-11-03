// Criado por José Eduardo Santana Martins
// Este arquivo serve para chamar a API do plano de face da rede (/api/rede).

import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import {
  BemResumo, CaminhoRede, EquipamentoDetalhe, EquipamentoResumo, GravacaoEquipamento, GravacaoModelo, GravacaoPonto, GravacaoPorta, GravacaoRack, ModeloFace, PontoRede, PortaDetalhe,
  ParametrosRede, PortaDoBem, Rack, SalaResumo, TopologiaRede, Vlan,
} from './rede.models';

@Injectable({ providedIn: 'root' })
export class RedeApiService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/rede`;

  equipamentos(busca = '', tipo = ''): Observable<EquipamentoResumo[]> {
    let params = new HttpParams().set('busca', busca);
    if (tipo) params = params.set('tipo', tipo);
    return this.http.get<EquipamentoResumo[]>(`${this.base}/equipamentos`, { params });
  }

  /** Árvore da rede montada pelas conexões; `raizId` troca o núcleo do grupo dele. */
  topologia(raizId: string | null = null): Observable<TopologiaRede> {
    return this.http.get<TopologiaRede>(`${this.base}/topologia`, { params: raizId ? { raiz_id: raizId } : {} });
  }

  /** Parâmetros do módulo (intervalo do ping); só Controle total. */
  parametros(): Observable<ParametrosRede> {
    return this.http.get<ParametrosRede>(`${this.base}/parametros`);
  }

  salvarParametros(dados: ParametrosRede): Observable<ParametrosRede> {
    return this.http.put<ParametrosRede>(`${this.base}/parametros`, dados);
  }

  equipamento(id: string): Observable<EquipamentoDetalhe> {
    return this.http.get<EquipamentoDetalhe>(`${this.base}/equipamentos/${id}`);
  }

  salvarEquipamento(id: string | null, dados: GravacaoEquipamento): Observable<EquipamentoDetalhe> {
    return id ? this.http.put<EquipamentoDetalhe>(`${this.base}/equipamentos/${id}`, dados) : this.http.post<EquipamentoDetalhe>(`${this.base}/equipamentos`, dados);
  }

  excluirEquipamento(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/equipamentos/${id}`);
  }

  porta(id: string): Observable<PortaDetalhe> {
    return this.http.get<PortaDetalhe>(`${this.base}/portas/${id}`);
  }

  configurarPorta(id: string, dados: GravacaoPorta): Observable<PortaDetalhe> {
    return this.http.put<PortaDetalhe>(`${this.base}/portas/${id}`, dados);
  }

  ligar(id: string, dados: { porta_id?: string | null; bem_id?: string | null; descricao?: string; forcar?: boolean }): Observable<PortaDetalhe> {
    return this.http.post<PortaDetalhe>(`${this.base}/portas/${id}/conexao`, dados);
  }

  desligar(id: string): Observable<PortaDetalhe> {
    return this.http.delete<PortaDetalhe>(`${this.base}/portas/${id}/conexao`);
  }

  /** Põe um dispositivo atrás do último da porta (ex.: o PC ligado no telefone IP). */
  adicionarAtras(id: string, dados: { bem_id?: string | null; descricao?: string }): Observable<PortaDetalhe> {
    return this.http.post<PortaDetalhe>(`${this.base}/portas/${id}/conexao/atras`, dados);
  }

  removerAtras(id: string, dispositivoId: string): Observable<PortaDetalhe> {
    return this.http.delete<PortaDetalhe>(`${this.base}/portas/${id}/conexao/atras/${dispositivoId}`);
  }

  modelos(): Observable<ModeloFace[]> {
    return this.http.get<ModeloFace[]>(`${this.base}/modelos`);
  }

  salvarModelo(id: string | null, dados: GravacaoModelo): Observable<ModeloFace> {
    return id ? this.http.put<ModeloFace>(`${this.base}/modelos/${id}`, dados) : this.http.post<ModeloFace>(`${this.base}/modelos`, dados);
  }

  excluirModelo(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/modelos/${id}`);
  }

  vlans(): Observable<Vlan[]> {
    return this.http.get<Vlan[]>(`${this.base}/vlans`);
  }

  salvarVlan(id: string | null, dados: { numero: number; nome: string; descricao: string }): Observable<Vlan> {
    return id ? this.http.put<Vlan>(`${this.base}/vlans/${id}`, dados) : this.http.post<Vlan>(`${this.base}/vlans`, dados);
  }

  excluirVlan(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/vlans/${id}`);
  }

  pontos(busca = ''): Observable<PontoRede[]> {
    return this.http.get<PontoRede[]>(`${this.base}/pontos`, { params: { busca } });
  }

  salvarPonto(id: string | null, dados: GravacaoPonto): Observable<PontoRede> {
    return id ? this.http.put<PontoRede>(`${this.base}/pontos/${id}`, dados) : this.http.post<PontoRede>(`${this.base}/pontos`, dados);
  }

  excluirPonto(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/pontos/${id}`);
  }

  racks(): Observable<Rack[]> {
    return this.http.get<Rack[]>(`${this.base}/racks`);
  }

  salvarRack(id: string | null, dados: GravacaoRack): Observable<Rack> {
    return id ? this.http.put<Rack>(`${this.base}/racks/${id}`, dados) : this.http.post<Rack>(`${this.base}/racks`, dados);
  }

  excluirRack(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/racks/${id}`);
  }

  salas(busca: string, todas = false): Observable<SalaResumo[]> {
    return this.http.get<SalaResumo[]>(`${this.base}/salas`, { params: { busca, todas } });
  }

  bens(busca: string): Observable<BemResumo[]> {
    return this.http.get<BemResumo[]>(`${this.base}/bens`, { params: { busca } });
  }

  /** Do core até a porta e o que está nela (equipamentos, cabos, patch panel, ponto e dispositivos em cascata). */
  caminho(portaId: string): Observable<CaminhoRede> {
    return this.http.get<CaminhoRede>(`${this.base}/portas/${portaId}/caminho`);
  }

  portasDoBem(bemId: string): Observable<PortaDoBem[]> {
    return this.http.get<PortaDoBem[]>(`${this.base}/bens/${bemId}/portas`);
  }
}
