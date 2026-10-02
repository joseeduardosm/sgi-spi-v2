// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a sessão do usuário: login, logout, token e dados do usuário logado.

import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, map, Observable, of, tap } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { Papel, Usuario } from '../modelos/usuario.model';
import { MotivoSaida, RequisicaoLogin, RespostaToken, SessaoAutenticada } from './autenticacao.models';

// Chave onde a sessão fica guardada no localStorage (sobrevive ao recarregar a página)
const CHAVE_ARMAZENAMENTO = 'sgi-spi.sessao';
// Chave usada antes da troca de nome (Contratos SPI → SGI SPI): lida uma vez e migrada, para ninguém ser deslogado
const CHAVE_ANTIGA = 'contratos-spi.sessao';
// setTimeout aceita no máximo ~24,8 dias
const ESPERA_MAXIMA_MS = 2_147_483_647;
// Quanto tempo antes do vencimento (sem renovação, ex.: aba ociosa) o sistema avisa que a sessão vai expirar
const AVISO_ANTES_DE_EXPIRAR_MS = 2 * 60_000;

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
  private readonly dialogos = inject(DialogosService);

  // Sessão atual (null = ninguém logado) e o temporizador que encerra a sessão quando o token vence
  private readonly sessao = signal<SessaoAutenticada | null>(null);
  private temporizadorExpiracao?: ReturnType<typeof setTimeout>;
  private temporizadorAviso?: ReturnType<typeof setTimeout>;

  // Valores derivados (computed): recalculados automaticamente a partir de `sessao`
  readonly usuario = computed<Usuario | null>(() => this.sessao()?.usuario ?? null);
  readonly autenticado = computed(() => this.sessao() !== null);

  /** Ao criar o serviço (abertura do sistema), tenta recuperar a sessão salva no navegador. */
  constructor() {
    this.restaurar();
    // Outra aba renovou a sessão ou saiu: esta aba acompanha (senão ela venceria com o token antigo e derrubaria as demais)
    if (typeof window !== 'undefined') window.addEventListener('storage', (evento) => this.aoMudarArmazenamento(evento));
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
    // Sessão expirada: guarda a tela de onde a pessoa saiu para o login devolvê-la a ela
    const atual = this.roteador.url;
    this.limpar();
    const parametros = motivo === 'expirada' ? { sessao: 'expirada', ...(atual && !atual.startsWith('/login') && atual !== '/' ? { retorno: atual } : {}) } : {};
    void this.roteador.navigate(['/login'], { queryParams: parametros });
  }

  /**
   * Token renovado pela API (cabeçalho `X-Token-Renovado`): guarda e adia o vencimento. A pessoa que continua usando o
   * sistema não cai; só quem fica parado até o vencimento é deslogado.
   */
  renovar(tokenAcesso: string, expiraEm: string): void {
    const sessao = this.sessao();
    const instante = new Date(expiraEm).getTime();
    if (!sessao || Number.isNaN(instante) || instante <= sessao.expiraEm) return;
    const nova = { ...sessao, tokenAcesso, expiraEm: instante };
    this.sessao.set(nova);
    this.persistir(nova);
    this.agendarExpiracao(instante);
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
      const antiga = localStorage.getItem(CHAVE_ANTIGA);
      if (antiga !== null && localStorage.getItem(CHAVE_ARMAZENAMENTO) === null) localStorage.setItem(CHAVE_ARMAZENAMENTO, antiga);
      localStorage.removeItem(CHAVE_ANTIGA);
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

  /** Reage a mudanças do `localStorage` feitas em outra aba: token renovado ou saída. */
  private aoMudarArmazenamento(evento: StorageEvent): void {
    if (evento.key !== CHAVE_ARMAZENAMENTO) return;
    if (evento.newValue === null) {
      // Outra aba saiu (ou a sessão expirou lá): esta também volta ao login
      if (this.sessao()) {
        clearTimeout(this.temporizadorExpiracao);
        clearTimeout(this.temporizadorAviso);
        this.sessao.set(null);
        void this.roteador.navigate(['/login']);
      }
      return;
    }
    try {
      const nova = JSON.parse(evento.newValue) as SessaoAutenticada;
      if (nova.expiraEm > Date.now()) {
        this.sessao.set(nova);
        this.agendarExpiracao(nova.expiraEm);
      }
    } catch {
      // valor inválido: ignora
    }
  }

  /** Aviso "sua sessão vai expirar" (só se nada foi renovado até lá); "Continuar conectado" faz uma chamada que renova. */
  private async avisarExpiracao(): Promise<void> {
    const atual = this.sessao();
    // Não atropela outra confirmação aberta (ex.: excluir) nem avisa se a sessão já foi renovada
    if (!atual || atual.expiraEm - Date.now() > AVISO_ANTES_DE_EXPIRAR_MS + 1000 || this.dialogos.confirmacao()) return;
    const continuar = await this.dialogos.confirmar({
      titulo: 'Sua sessão vai expirar',
      mensagem: 'Por segurança, a sessão termina depois de um tempo sem uso. Deseja continuar conectado?',
      rotuloConfirmar: 'Continuar conectado',
    });
    if (continuar) this.validarSessao().subscribe();
  }

  /** Programa o logout automático para o momento em que o token vence (e o aviso pouco antes). */
  private agendarExpiracao(expiraEm: number): void {
    clearTimeout(this.temporizadorExpiracao);
    clearTimeout(this.temporizadorAviso);
    const ateAviso = expiraEm - Date.now() - AVISO_ANTES_DE_EXPIRAR_MS;
    if (ateAviso > 0 && ateAviso < ESPERA_MAXIMA_MS) this.temporizadorAviso = setTimeout(() => void this.avisarExpiracao(), ateAviso);
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
    clearTimeout(this.temporizadorAviso);
    this.sessao.set(null);
    try {
      localStorage.removeItem(CHAVE_ARMAZENAMENTO);
    } catch {
      // ignorado
    }
  }
}
