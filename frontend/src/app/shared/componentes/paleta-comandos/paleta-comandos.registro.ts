// Criado por José Eduardo Santana Martins
// Este arquivo serve para registrar os comandos da paleta (Ctrl+K) e filtrá-los por texto e por permissão.

import { NivelAcl } from '../../../core/acesso/acesso.service';
import { normalizarTexto } from '../../../core/navegacao/telas-menu';

/** Um comando da paleta: abre uma rota ou executa uma ação. */
export interface ComandoPaleta {
  id: string;
  rotulo: string;
  /** Texto de apoio mostrado ao lado do rótulo. */
  descricao?: string;
  /** Palavras que também encontram o comando (sem acento). */
  palavras: string[];
  /** Permissão exigida (recurso da ACL e nível mínimo; padrão LEITURA). Sem `acl`, todo usuário logado vê. */
  acl?: string;
  nivelAcl?: NivelAcl;
  rota?: string;
  /** Ação própria (abrir modal, trocar tema…); `rota` e `executar` são excludentes. */
  acao?: 'abrir-chamado' | 'sugerir-melhoria' | 'alternar-tema';
}

/** Comandos de "criar" e de apoio. Os de tela inteira (Ir para…) vêm do menu e não ficam aqui. */
export const COMANDOS: readonly ComandoPaleta[] = [
  { id: 'nova-tarefa', rotulo: 'Nova tarefa', descricao: 'Criar uma tarefa', palavras: ['criar', 'tarefa', 'novo'], rota: '/tarefas/nova' },
  { id: 'minhas-tarefas', rotulo: 'Minhas tarefas', descricao: 'Ver o quadro', palavras: ['tarefas', 'quadro', 'fila'], rota: '/tarefas' },
  { id: 'minhas-atividades', rotulo: 'Minhas atividades', descricao: 'Atividades agendadas para mim', palavras: ['atividades', 'agenda'], rota: '/tarefas/atividades' },
  { id: 'calendario-vencimentos', rotulo: 'Calendário de vencimentos', descricao: 'Vigência, reajuste, NF, certidões e prazos dos contratos', palavras: ['vencimento', 'vigencia', 'prazo', 'contratos', 'agenda'], acl: 'contratos', rota: '/contratos/calendario' },
  { id: 'reservar-espaco', rotulo: 'Reservar espaço', descricao: 'Nova reserva de sala ou espaço', palavras: ['reserva', 'sala', 'auditorio', 'novo'], rota: '/reserva-espacos/nova' },
  { id: 'novo-contrato', rotulo: 'Novo contrato', descricao: 'Cadastrar um contrato', palavras: ['criar', 'contrato', 'cadastrar'], acl: 'contratos', nivelAcl: 'MODIFICACAO', rota: '/contratos/novo' },
  { id: 'nova-empresa', rotulo: 'Nova empresa contratada', descricao: 'Cadastrar uma empresa', palavras: ['criar', 'empresa', 'fornecedor', 'cadastrar'], acl: 'contratos', nivelAcl: 'MODIFICACAO', rota: '/contratos/empresas/nova' },
  { id: 'abrir-chamado', rotulo: 'Abrir chamado', descricao: 'Chamado no GLPI', palavras: ['chamado', 'glpi', 'ti', 'suporte', 'ajuda'], acl: 'abrir-chamado', acao: 'abrir-chamado' },
  { id: 'sugerir-melhoria', rotulo: 'Sugerir melhoria', descricao: 'Enviar uma sugestão sobre o sistema', palavras: ['melhoria', 'sugestao', 'ideia', 'problema'], acao: 'sugerir-melhoria' },
  { id: 'nova-mensagem', rotulo: 'Nova mensagem', descricao: 'Enviar um aviso aos colegas', palavras: ['mensagem', 'aviso', 'comunicado', 'enviar'], rota: '/mensagens?nova=1' },
  { id: 'alternar-tema', rotulo: 'Alternar tema claro/escuro', descricao: 'Muda a aparência do portal', palavras: ['tema', 'escuro', 'claro', 'aparencia', 'dark'], acao: 'alternar-tema' },
];

/**
 * Comandos que combinam com o texto (rótulo, descrição ou palavras, sem acento nem maiúsculas) e que o usuário pode usar.
 * Sem texto, devolve todos os permitidos. O rótulo que começa com o texto vem antes.
 */
export function filtrarComandos(
  comandos: readonly ComandoPaleta[], texto: string, pode: (acl: string, nivel: NivelAcl) => boolean,
): ComandoPaleta[] {
  const alvo = normalizarTexto(texto);
  const permitidos = comandos.filter((c) => !c.acl || pode(c.acl, c.nivelAcl ?? 'LEITURA'));
  if (!alvo) return [...permitidos];
  const combina = (c: ComandoPaleta) => [c.rotulo, c.descricao ?? '', ...c.palavras].some((t) => normalizarTexto(t).includes(alvo));
  return permitidos.filter(combina).sort((a, b) => Number(normalizarTexto(b.rotulo).startsWith(alvo)) - Number(normalizarTexto(a.rotulo).startsWith(alvo)));
}
