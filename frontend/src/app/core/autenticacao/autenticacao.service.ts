import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, map, Observable, of, tap } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { Papel, Usuario } from '../modelos/usuario.model';
import { MotivoSaida, RequisicaoLogin, RespostaToken, SessaoAutenticada } from './autenticacao.models';

const CHAVE_ARMAZENAMENTO = 'contratos-spi.sessao';
// setTimeout aceita no máximo ~24,8 dias
const ESPERA_MAXIMA_MS = 2_147_483_647;

@Injectable({ providedIn: 'root' })
export class AutenticacaoService {
  private readonly http = inject(HttpClient);
  private readonly roteador = inject(Router);

  private readonly sessao = signal<SessaoAutenticada | null>(null);
  private temporizadorExpiracao?: ReturnType<typeof setTimeout>;

  readonly usuario = computed<Usuario | null>(() => this.sessao()?.usuario ?? null);
  readonly autenticado = computed(() => this.sessao() !== null);

  constructor() {
    this.restaurar();
  }

  get token(): string | null {
    return this.sessao()?.tokenAcesso ?? null;
  }

  entrar(credenciais: RequisicaoLogin): Observable<Usuario> {
    return this.http.post<RespostaToken>(`${ambiente.urlApi}/autenticacao/login`, credenciais).pipe(
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

  possuiPapel(...papeis: Papel[]): boolean {
    const usuario = this.usuario();
    return !!usuario && papeis.some((p) => usuario.papeis.includes(p));
  }

  private iniciar(sessao: SessaoAutenticada): void {
    this.sessao.set(sessao);
    this.persistir(sessao);
    this.agendarExpiracao(sessao.expiraEm);
  }

  private restaurar(): void {
    let sessao: SessaoAutenticada | null = null;
    try {
      const bruto = localStorage.getItem(CHAVE_ARMAZENAMENTO);
      sessao = bruto ? (JSON.parse(bruto) as SessaoAutenticada) : null;
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

  private agendarExpiracao(expiraEm: number): void {
    clearTimeout(this.temporizadorExpiracao);
    const espera = Math.min(Math.max(expiraEm - Date.now(), 0), ESPERA_MAXIMA_MS);
    this.temporizadorExpiracao = setTimeout(() => {
      const atual = this.sessao();
      if (atual && atual.expiraEm <= Date.now()) this.sair('expirada');
      else if (atual) this.agendarExpiracao(atual.expiraEm);
    }, espera);
  }

  private persistir(sessao: SessaoAutenticada): void {
    try {
      localStorage.setItem(CHAVE_ARMAZENAMENTO, JSON.stringify(sessao));
    } catch {
      // armazenamento indisponível: a sessão vale apenas para esta aba
    }
  }

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
