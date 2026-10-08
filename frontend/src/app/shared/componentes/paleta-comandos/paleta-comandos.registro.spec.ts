// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a filtragem dos comandos da paleta (Ctrl+K) por texto e por permissão.

import { COMANDOS, filtrarComandos } from './paleta-comandos.registro';

const todos = () => true;
const nada = () => false;

describe('paleta-comandos.registro', () => {
  it('sem texto mostra todos os comandos permitidos; sem ACL esconde os que exigem permissão', () => {
    expect(filtrarComandos(COMANDOS, '', todos).length).toBe(COMANDOS.length);
    const publicos = filtrarComandos(COMANDOS, '', nada).map((c) => c.id);
    expect(publicos).toContain('nova-tarefa');
    expect(publicos).not.toContain('novo-contrato');
    expect(publicos).not.toContain('abrir-chamado');
  });

  it('procura por rótulo, descrição e palavras, sem acento nem maiúsculas', () => {
    expect(filtrarComandos(COMANDOS, 'AUDITÓRIO', todos).map((c) => c.id)).toEqual(['reservar-espaco']);
    expect(filtrarComandos(COMANDOS, 'glpi', todos).map((c) => c.id)).toEqual(['abrir-chamado']);
    expect(filtrarComandos(COMANDOS, 'nada disso existe', todos)).toEqual([]);
  });

  it('o rótulo que começa com o texto vem primeiro', () => {
    const ids = filtrarComandos(COMANDOS, 'nova', todos).map((c) => c.id);
    expect(ids.slice(0, 3).every((id) => ['nova-tarefa', 'nova-empresa', 'nova-mensagem'].includes(id))).toBe(true);
  });

  it('pede o nível certo de ACL ao verificar a permissão', () => {
    const pedidos: string[] = [];
    filtrarComandos(COMANDOS, '', (acl, nivel) => { pedidos.push(`${acl}:${nivel}`); return true; });
    expect(pedidos).toContain('contratos:MODIFICACAO');
    expect(pedidos).toContain('abrir-chamado:LEITURA');
  });
});
