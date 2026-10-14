// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o esqueleto de carregamento (formas e acessibilidade).

import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { EsqueletoComponent } from './esqueleto.component';

function montar(entradas: Record<string, unknown>): HTMLElement {
  const fixture = TestBed.createComponent(EsqueletoComponent);
  for (const [nome, valor] of Object.entries(entradas)) fixture.componentRef.setInput(nome, valor);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('EsqueletoComponent', () => {
  it('anuncia o carregamento para leitor de tela', () => {
    const raiz = montar({ tipo: 'lista', linhas: 3 });
    const bloco = raiz.querySelector('.esqueleto');
    expect(bloco?.getAttribute('role')).toBe('status');
    expect(bloco?.getAttribute('aria-busy')).toBe('true');
    expect(raiz.querySelector('.somente-leitor')?.textContent).toContain('Carregando');
  });

  it('desenha a quantidade pedida de itens na lista e de linhas e colunas na tabela', () => {
    expect(montar({ tipo: 'lista', linhas: 4 }).querySelectorAll('.item-lista').length).toBe(4);
    const tabela = montar({ tipo: 'tabela', linhas: 3, colunas: 5 });
    expect(tabela.querySelectorAll('.lin-tabela').length).toBe(3);
    expect(tabela.querySelector('.cab-tabela')?.children.length).toBe(5);
  });

  it('desenha o quadro com colunas de cartões', () => {
    const quadro = montar({ tipo: 'quadro', linhas: 3, colunas: 4 });
    expect(quadro.querySelectorAll('.coluna-esq').length).toBe(4);
    expect(quadro.querySelectorAll('.coluna-esq .cartao').length).toBe(12);
  });

  it('tem forma própria para painel e formulário', () => {
    expect(montar({ tipo: 'painel' }).querySelectorAll('.cartao').length).toBe(4);
    expect(montar({ tipo: 'formulario', linhas: 3 }).querySelectorAll('.campo-esq').length).toBe(3);
  });
});
