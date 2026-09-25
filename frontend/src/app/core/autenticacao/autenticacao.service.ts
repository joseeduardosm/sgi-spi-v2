// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a sessão do usuário: login, logout, token e dados do usuário logado.

import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, map, Observable, of, tap } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { Papel, Usuario } from '../modelos/usuario.model';
import { MotivoSaida, RequisicaoLogin, RespostaToken, SessaoAutenticada } from './autenticacao.models';

// Chave onde a sessão fica guardada no localStorage (sobrevive ao recarregar a página)
const CHAVE_ARMAZENAMENTO = 'contratos-spi.sessao';
// setTimeout aceita no máximo ~24,8 dias
const ESPERA_MAXIMA_MS = 2_147_483_647;

/**
 * Serviço único (`providedIn: 'root'`) que guarda a sessão.
 *
 * Usa signals: `usuario` e `autenticado` são valores reativos; componentes e guardas que os leem
 * são atualizados sozinhos quando a sessão muda.
 */
@Injectable({ providedIn: 'root' })
export class AutenticacaoService {
  private readonly http = inject(HttpClient);
  private readonly roteador = inject(Router);

  // Sessão atual (null = ninguém logado) e o temporizador que encerra a sessão quando o token vence
  private readonly sessao = signal<SessaoAutenticada | null>(null);
  private temporizadorExpiracao?: ReturnType<typeof setTimeout>;

  // Valores derivados (computed): recalculados automaticamente a partir de `sessao`
  readonly usuario = computed<Usuario | null>(() => this.sessao()?.usuario ?? null);
  readonly autenticado = computed(() => this.sessao() !== null);

  /** Ao criar o serviço (abertura do sistema), tenta recuperar a sessão salva no navegador. */
  constructor() {
    this.restaurar();
  }

  /** Token JWT atual, usado pelo interceptador. */
  get token(): string | null {
    return this.sessao()?.tokenAcesso ?? null;
  }

  /** Faz login na API e inicia a sessão com o token recebido; devolve o usuário. */
  entrar(credenciais: RequisicaoLogin): Observable<Usuario> {
    return this.http.post<RespostaToken>(`${ambiente.urlApi}/autenticacao/login`, credenciais).pipe(
      // Converte a resposta da API para o formato guardado no navegador
      map((resposta) => ({
        tokenAcesso: resposta.token_acesso,
        expiraEm: new Date(resposta.expira_em).getTime(),
        usuario: resposta.usuario,
      })),
      tap((sessao) => this.iniciar(sessao)),
      map((sessao) => sessao.usuario),
    );
  }

  /** Encerra a sessão local. O JWT é stateless: basta descartá-lo no cliente. */
  sair(motivo: MotivoSaida = 'usuario'): void {
    this.limpar();
    const parametros = motivo === 'expirada' ? { sessao: 'expirada' } : {};
    void this.roteador.navigate(['/login'], { queryParams: parametros });
  }

  /** Confirma no backend que o token armazenado ainda é válido e atualiza os dados do usuário. */
  validarSessao(): Observable<boolean> {
    if (!this.sessao()) return of(false);
    return this.http.get<Usuario>(`${ambiente.urlApi}/autenticacao/sessao`).pipe(
      tap((usuario) => this.definirUsuario(usuario)),
      map(() => true),
      // 401 já é tratado pelo interceptador; outros erros (API fora do ar) não derrubam a sessão
      catchError(() => of(this.autenticado())),
    );
  }

  /** Substitui os dados do usuário da sessão (ex.: após revalidar o perfil). */
  definirUsuario(usuario: Usuario): void {
    const sessao = this.sessao();
    if (!sessao) return;
    const nova = { ...sessao, usuario };
    this.sessao.set(nova);
    this.persistir(nova);
  }

  /** Verdadeiro se o usuário tem pelo menos um dos papéis informados. */
  possuiPapel(...papeis: Papel[]): boolean {
    const usuario = this.usuario();
    return !!usuario && papeis.some((p) => usuario.papeis.includes(p));
  }

  /** Começa uma sessão nova: guarda em memória, no navegador e agenda o fim. */
  private iniciar(sessao: SessaoAutenticada): void {
    this.sessao.set(sessao);
    this.persistir(sessao);
    this.agendarExpiracao(sessao.expiraEm);
  }

  /** Recupera a sessão do localStorage, se ainda estiver dentro da validade. */
  private restaurar(): void {
    let sessao: SessaoAutenticada | null = null;
    try {
      const bruto = localStorage.getItem(CHAVE_ARMAZENAMENTO);
      sessao = bruto ? (JSON.parse(bruto) as SessaoAutenticada) : null;
    // Conteúdo corrompido no navegador: trata como sem sessão
    } catch {
      sessao = null;
    }
    if (sessao && sessao.expiraEm > Date.now()) {
      this.sessao.set(sessao);
      this.agendarExpiracao(sessao.expiraEm);
    } else {
      this.limpar();
    }
  }

  /** Programa o logout automático para o momento em que o token vence. */
  private agendarExpiracao(expiraEm: number): void {
    clearTimeout(this.temporizadorExpiracao);
    // Tempo até o vencimento (nunca negativo e dentro do limite do setTimeout)
    const espera = Math.min(Math.max(expiraEm - Date.now(), 0), ESPERA_MAXIMA_MS);
    this.temporizadorExpiracao = setTimeout(() => {
      const atual = this.sessao();
      // Se ainda não venceu (espera limitada pelo teto do setTimeout), agenda de novo
      if (atual && atual.expiraEm <= Date.now()) this.sair('expirada');
      else if (atual) this.agendarExpiracao(atual.expiraEm);
    }, espera);
  }

  /** Salva a sessão no localStorage. */
  private persistir(sessao: SessaoAutenticada): void {
    try {
      localStorage.setItem(CHAVE_ARMAZENAMENTO, JSON.stringify(sessao));
    } catch {
      // armazenamento indisponível: a sessão vale apenas para esta aba
    }
  }

  /** Apaga a sessão da memória e do navegador e cancela o temporizador. */
  private limpar(): void {
    clearTimeout(this.temporizadorExpiracao);
    this.sessao.set(null);
    try {
      localStorage.removeItem(CHAVE_ARMAZENAMENTO);
    } catch {
      // ignorado
    }
  }
}
