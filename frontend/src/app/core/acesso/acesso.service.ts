// Criado por José Eduardo Santana Martins
// Este arquivo serve para carregar e consultar os níveis de acesso (ACL) do usuário logado.

import { HttpClient } from '@angular/common/http';
import { effect, inject, Injectable, signal } from '@angular/core';
import { catchError, map, Observable, of, shareReplay, switchMap, tap } from 'rxjs';

import { ambiente } from '../../../environments/ambiente';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';

/** Níveis de acesso da ACL, do menor para o maior. */
export type NivelAcl = 'LEITURA' | 'MODIFICACAO' | 'CONTROLE_TOTAL';

// Lista em ordem (para seletores) e os textos exibidos na tela
export const NIVEIS_ACL: NivelAcl[] = ['LEITURA', 'MODIFICACAO', 'CONTROLE_TOTAL'];
export const ROTULOS_NIVEL: Record<NivelAcl, string> = {
  LEITURA: 'Leitura',
  MODIFICACAO: 'Modificação',
  CONTROLE_TOTAL: 'Controle total',
};

/** Nome curto e frase do que um nível libera em um módulo (vem da API, de `services/acl_niveis.py`). */
export interface TextoNivel { rotulo: string; descricao: string; }
export type NiveisTextos = Record<NivelAcl, TextoNivel>;

/** Nome do nível no módulo (o genérico se a API não mandou os textos). */
export function rotuloNivel(niveis: NiveisTextos | undefined, nivel: NivelAcl): string {
  return niveis?.[nivel]?.rotulo || ROTULOS_NIVEL[nivel];
}

/**
 * Níveis que valem a pena oferecer num seletor: esconde os que o módulo declara iguais ao anterior ("Igual a Leitura…"),
 * para não repetir o mesmo rótulo. Mantém o nível `atual`, mesmo repetido, para o valor gravado continuar visível.
 */
export function niveisDistintos(niveis: NiveisTextos | undefined, atual?: NivelAcl | ''): NivelAcl[] {
  return NIVEIS_ACL.filter((n) => n === atual || !(niveis?.[n]?.descricao ?? '').startsWith('Igual a '));
}

/** Frase do que o nível libera no módulo; vazia sem os textos. */
export function descricaoNivel(niveis: NiveisTextos | undefined, nivel: NivelAcl): string {
  return niveis?.[nivel]?.descricao ?? '';
}

// Posição numérica de cada nível, para comparar "tem pelo menos"
const POSICAO: Record<NivelAcl, number> = { LEITURA: 1, MODIFICACAO: 2, CONTROLE_TOTAL: 3 };

/** `AcessoEfetivo` da API. */
export interface AcessoEfetivo {
  recurso_id: number;
  nome: string;
  slug: string;
  url_base: string;
  nivel: NivelAcl | null;
  niveis?: NiveisTextos;
  /** De onde vem o nível: perfil ativo, setor ou regra direta (cada um com o seu nível). */
  origens?: Partial<Record<'perfil' | 'setor' | 'direta', NivelAcl>>;
}

/**
 * Acessos efetivos do usuário (GET /api/acl/meus-acessos), usados para ocultar módulos.
 * A proteção efetiva continua no backend.
 */
/** O que a pessoa pode fazer no módulo Chamados (`papeis` de `GET /chamados/contexto`). */
export interface PapeisChamadosAcesso {
  abrir: boolean;
  atender: boolean;
  administrar: boolean;
}

/** O que a pessoa pode fazer no plano de face da rede (`GET /rede/contexto`). */
export interface PapeisRedeAcesso {
  ver: boolean;
  editar: boolean;
  administrar: boolean;
}

@Injectable({ providedIn: 'root' })
export class AcessoService {
  private readonly http = inject(HttpClient);
  private readonly autenticacao = inject(AutenticacaoService);

  // Mapa slug → nível do usuário; `carregado` indica se a resposta da API já chegou
  private readonly niveis = signal<ReadonlyMap<string, NivelAcl>>(new Map());
  readonly carregado = signal(false);
  /**
   * Acesso ao Painel Executivo. Fica fora do mapa de níveis porque, sem regras, esse recurso NÃO é aberto a todos
   * (diferente dos demais): quem diz é `GET /painel-executivo/acesso`.
   */
  readonly painelExecutivo = signal(false);
  /**
   * Papéis no módulo Chamados. Também fica fora do mapa de níveis: sem regras na ACL, o módulo é fechado (só o SuperRoot)
   * até a virada do GLPI; quem diz é `GET /chamados/contexto` (403 = nenhum papel).
   */
  readonly chamados = signal<PapeisChamadosAcesso | null>(null);
  /** O "Abrir chamado" do sistema vai para o módulo do SGI (e não para o GLPI)? Depende do papel e da data "a partir de". */
  readonly abreNoSgi = signal(false);
  /** Papéis no plano de face da rede: fechado (só o SuperRoot) até haver regras; quem diz é `GET /rede/contexto`. */
  readonly rede = signal<PapeisRedeAcesso | null>(null);
  // Requisição em andamento, compartilhada entre chamadas simultâneas (evita pedir duas vezes)
  private carregamentoPendente?: Observable<void>;

  constructor() {
    // Recarrega ao entrar, trocar de usuário ou concluir a revalidação do perfil
    // `effect` roda de novo sempre que um signal lido dentro dele muda (aqui, o usuário da sessão)
    effect(() => {
      const usuario = this.autenticacao.usuario();
      if (usuario && !usuario.perfil_restrito) this.carregar().subscribe();
      else this.reiniciar();
    });
  }

  /** Verdadeiro se o usuário tem ao menos `nivelMinimo` no recurso. SuperRoot sempre pode. */
  pode(slug: string, nivelMinimo: NivelAcl = 'LEITURA'): boolean {
    if (this.autenticacao.possuiPapel('SuperRoot')) return true;
    const nivel = this.niveis().get(slug);
    return !!nivel && POSICAO[nivel] >= POSICAO[nivelMinimo];
  }

  /** Busca os acessos na API; chamadas repetidas durante o carregamento reaproveitam a mesma requisição. */
  carregar(): Observable<void> {
    // `??=` só cria a requisição se ainda não houver uma em andamento
    this.carregamentoPendente ??= this.http.get<AcessoEfetivo[]>(`${ambiente.urlApi}/acl/meus-acessos`).pipe(
      tap((itens) => {
        // Guarda só os recursos com algum nível (nulo = sem acesso)
        this.niveis.set(new Map(itens.filter((i) => i.nivel).map((i) => [i.slug, i.nivel!])));
      }),
      switchMap(() => this.http.get<{ pode: boolean }>(`${ambiente.urlApi}/painel-executivo/acesso`).pipe(
        tap((r) => this.painelExecutivo.set(r.pode)),
        catchError(() => of({ pode: false })),
      )),
      switchMap(() => this.http.get<{ papeis: PapeisChamadosAcesso; inicio_atendimento: string | null; atendimento_aberto: boolean }>(
        `${ambiente.urlApi}/chamados/contexto`).pipe(
        tap((r) => {
          this.chamados.set(r.papeis);
          // "A partir de": sem data marcada vale o papel; com data, antes dela só quem administra abre no SGI (os demais, no GLPI)
          this.abreNoSgi.set(r.papeis.abrir && (!r.inicio_atendimento || r.atendimento_aberto || r.papeis.administrar));
        }),
        // 403 (sem papel) ou erro: o módulo fica escondido
        catchError(() => {
          this.chamados.set(null);
    this.abreNoSgi.set(false);
          return of(null);
        }),
      )),
      switchMap(() => this.http.get<PapeisRedeAcesso>(`${ambiente.urlApi}/rede/contexto`).pipe(
        tap((r) => this.rede.set(r.ver ? r : null)),
        catchError(() => {
          this.rede.set(null);
          return of(null);
        }),
      )),
      tap(() => this.carregado.set(true)),
      map(() => undefined),
      // Erro na API não trava a tela: considera carregado (sem acessos)
      catchError(() => {
        this.carregado.set(true);
        return of(undefined);
      }),
      // Ao terminar, libera para uma próxima carga; `shareReplay` entrega o mesmo resultado a todos os inscritos
      tap(() => (this.carregamentoPendente = undefined)),
      shareReplay(1),
    );
    return this.carregamentoPendente;
  }

  /** Esquece os acessos (logout ou perfil pendente). */
  private reiniciar(): void {
    this.niveis.set(new Map());
    this.painelExecutivo.set(false);
    this.chamados.set(null);
    this.abreNoSgi.set(false);
    this.rede.set(null);
    this.carregado.set(false);
  }
}
