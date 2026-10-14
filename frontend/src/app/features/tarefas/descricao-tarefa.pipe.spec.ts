// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a exibição e a conversão da descrição das tarefas (HTML do editor rico e texto simples antigo).

import { describe, expect, it } from 'vitest';

import { descricaoEhHtml, descricaoParaEditor } from './descricao-tarefa.pipe';

describe('descrição da tarefa', () => {
  it('reconhece HTML do editor e texto simples', () => {
    expect(descricaoEhHtml('<p>Oi</p>')).toBe(true);
    expect(descricaoEhHtml('Linha 1\nLinha 2 a < b')).toBe(false);
    expect(descricaoEhHtml('')).toBe(false);
  });

  it('converte o texto simples antigo em parágrafos para o editor, escapando marcação', () => {
    expect(descricaoParaEditor('A\nB <i>')).toBe('<p>A</p><p>B &lt;i&gt;</p>');
    expect(descricaoParaEditor('<p>Já é HTML</p>')).toBe('<p>Já é HTML</p>');
    expect(descricaoParaEditor('')).toBe('');
  });
});
