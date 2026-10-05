// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar o modal "Abrir Chamado" e falar com a API de chamados (GLPI).

import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { Observable } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';

/** Dados do cadastro do usuário que vão no chamado (`DadosSolicitante` da API). */
export interface DadosSolicitante {
  nome: string;
  setor: string;
  superior_imediato: string;
  email: string;
  telefone: string;
  celular: string;
  andar_lado: string;
  /** Campos cujo valor ainda é uma alteração aguardando validação da CGP (valem como temporários no chamado). */
  aguardando_validacao: string[];
}

/** Uma localização do GLPI (pergunta "Local do Problema"). */
export interface LocalChamado {
  id: number;
  nome: string;
}

/** Chamado criado no GLPI (`ChamadoAberto` da API). */
export interface ChamadoAberto {
  glpi_id: number;
  assunto: string;
  url: string;
  aberto_em: string;
  anexos_enviados: number;
  anexos_com_falha: string[];
}

/** Abertura de chamado pelo SGI: o chamado é criado no GLPI em nome do usuário. */
@Injectable({ providedIn: 'root' })
export class ChamadoService {
  private readonly http = inject(HttpClient);
  private readonly base = `${ambiente.urlApi}/chamados`;

  /** O modal está aberto? (a barra lateral abre; o modal fecha) */
  readonly modalAberto = signal(false);

  abrirModal(): void {
    this.modalAberto.set(true);
  }

  fecharModal(): void {
    this.modalAberto.set(false);
  }

  /** Dados do cadastro que acompanham o chamado (somente leitura na tela). */
  solicitante(): Observable<DadosSolicitante> {
    return this.http.get<DadosSolicitante>(`${this.base}/solicitante`);
  }

  /** Locais do GLPI para a lista "Local do problema" (obrigatória, como no formulário do GLPI). */
  locais(): Observable<{ itens: LocalChamado[] }> {
    return this.http.get<{ itens: LocalChamado[] }>(`${this.base}/locais`);
  }

  /** Cria o chamado no GLPI (multipart: `dados` com assunto, descrição e local, e os anexos em `arquivos`). */
  abrir(assunto: string, descricao: string, localId: number, anexos: File[] = []): Observable<ChamadoAberto> {
    const corpo = new FormData();
    corpo.append('dados', JSON.stringify({ assunto, descricao, local_id: localId }));
    for (const a of anexos) corpo.append('arquivos', a, a.name);
    return this.http.post<ChamadoAberto>(this.base, corpo);
  }
}
