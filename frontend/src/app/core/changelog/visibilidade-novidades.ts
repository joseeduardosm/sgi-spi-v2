/**
 * =============================================================================
 * ARQUIVO: visibilidade-novidades.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Dizer se uma novidade do Changelog aparece para o usuário logado, pelo
 * módulo dela (selo da novidade).
 *
 * RESUMO TÉCNICO:
 * Função pura `moduloVisivel(modulo, acesso, autenticacao)`. Os módulos
 * abertos a todos (Geral, RH, Tarefas, Reserva de Espaços, Melhorias,
 * Ramais, Notificações) sempre aparecem; os de recurso da ACL usam
 * `acesso.pode(slug)`; Chamados e Rede usam os papéis que a API devolve;
 * Administração só para o SuperRoot. O SuperRoot vê tudo.
 *
 * FINALIDADE DE NEGÓCIO:
 * Decisão do usuário (13/11/2026): cada pessoa vê no Changelog só as
 * atualizações dos módulos que ela usa, sem notícias de telas que nem
 * aparecem para ela.
 *
 * CONTEXTO NO SISTEMA:
 * Usada pela tela do Changelog (features/changelog) e pela bolinha do menu
 * (core/changelog/novidades-vistas.service.ts). Os slugs são os mesmos do
 * menu (core/navegacao/navegacao.ts).
 *
 * =============================================================================
 */

import { AcessoService } from '../acesso/acesso.service';
import { AutenticacaoService } from '../autenticacao/autenticacao.service';

/** Módulos que todo usuário logado usa (estão no menu de todos). */
const ABERTOS = new Set(['Geral', 'RH', 'Tarefas', 'Reserva de Espaços', 'Melhorias', 'Ramais', 'Notificações']);

/** Módulo da novidade → recurso da ACL que libera o módulo (o mesmo do item no menu). */
const POR_ACL: Record<string, string> = {
  Contratos: 'contratos', 'Notícias': 'noticias', Protocolo: 'protocolo', 'Patrimônio': 'patrimonio', 'Contratações': 'contratacoes', Manuais: 'manuais',
};

/** A novidade daquele módulo aparece para o usuário logado? */
export function moduloVisivel(modulo: string, acesso: AcessoService, autenticacao: AutenticacaoService): boolean {
  // O SuperRoot administra o sistema inteiro: vê todas as novidades
  if (autenticacao.possuiPapel('SuperRoot')) return true;
  if (ABERTOS.has(modulo)) return true;
  if (modulo in POR_ACL) return acesso.pode(POR_ACL[modulo]);
  if (modulo === 'Chamados') {
    const c = acesso.chamados();
    return !!c && (c.abrir || c.atender || c.administrar);
  }
  if (modulo === 'Rede') return !!acesso.rede()?.ver;
  // Administração (e qualquer módulo novo ainda sem regra aqui): só o SuperRoot
  return false;
}
