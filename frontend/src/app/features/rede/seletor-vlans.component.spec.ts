// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o seletor de VLANs da porta: selos só com o número e a cor da VLAN, busca, "Todas"/"Limpar",
// resumo em faixas, escolha pelo teclado, a regra de não repetir entre tag e sem tag e a janelinha de cor (só para quem administra).

import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it } from 'vitest';

import { Vlan } from './rede.models';
import { faixasDeVlans, SeletorVlansComponent } from './seletor-vlans.component';

const VLANS: Vlan[] = [
  { id: 'a', numero: 10, nome: 'Dados', descricao: '', cor_indice: 4, portas: 0 },
  { id: 'b', numero: 11, nome: 'Voz', descricao: '', cor_indice: 2, portas: 0 },
  { id: 'c', numero: 30, nome: 'Câmeras', descricao: '', cor_indice: 7, portas: 0 },
];

/** Monta o seletor com as entradas pedidas e devolve o elemento e os valores emitidos. */
function montar(entradas: Record<string, unknown>) {
  const fixture = TestBed.createComponent(SeletorVlansComponent);
  fixture.componentRef.setInput('vlans', VLANS);
  for (const [nome, valor] of Object.entries(entradas)) fixture.componentRef.setInput(nome, valor);
  const emitidos: string[][] = [];
  fixture.componentInstance.valorChange.subscribe((v) => emitidos.push(v));
  fixture.detectChanges();
  const raiz = fixture.nativeElement as HTMLElement;
  const campo = () => raiz.querySelector('input.busca-vlan') as HTMLInputElement;
  const opcoes = () => Array.from(raiz.querySelectorAll('li[role="option"]')).map((li) => li.textContent?.replace(/\s+/g, ' ').trim());
  const botao = (texto: string) => Array.from(raiz.querySelectorAll('button')).find((b) => b.textContent?.trim() === texto) as HTMLButtonElement;
  const digitar = (texto: string) => {
    campo().dispatchEvent(new Event('focus'));
    campo().value = texto;
    campo().dispatchEvent(new Event('input'));
    fixture.detectChanges();
  };
  return { fixture, raiz, campo, opcoes, botao, digitar, emitidos };
}

describe('faixasDeVlans', () => {
  it('agrupa números seguidos em faixas, como no switch', () => {
    expect(faixasDeVlans([2471, 2469, 2470, 2480, 2482, 2483])).toBe('2469–2471, 2480, 2482–2483');
    expect(faixasDeVlans([])).toBe('');
  });
});

describe('SeletorVlansComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideHttpClient()] }));

  it('mostra só o número no selo, com a cor da VLAN e o nome no title, em ordem; o resumo vem em faixas', () => {
    const { raiz, emitidos } = montar({ valor: ['c', 'b', 'a'], prefixoResumo: 'Com tag' });
    const selos = Array.from(raiz.querySelectorAll('.pilula-marcador > button:first-child')) as HTMLButtonElement[];
    expect(selos.map((s) => s.textContent?.trim())).toEqual(['10', '11', '30']);
    expect(selos[0].className).toContain('marcador-cor-4');
    expect(selos[2].title).toContain('Câmeras');
    expect(raiz.querySelector('.resumo-vlans')?.textContent?.replace(/\s+/g, ' ').trim()).toBe('Com tag: 10–11, 30 (3 VLANs)');
    (raiz.querySelector('.tirar') as HTMLButtonElement).click();
    expect(emitidos).toEqual([['c', 'b']]);
  });

  it('busca pelo número ou pelo nome (sem acento) e não oferece as já usadas aqui ou no outro campo', () => {
    const { opcoes, digitar } = montar({ valor: ['a'], excluir: ['b'] });
    digitar('');
    expect(opcoes()).toEqual(['30 Câmeras']);
    digitar('cam');
    expect(opcoes()).toEqual(['30 Câmeras']);
    digitar('9');
    expect(opcoes()).toEqual([]);
  });

  it('"Todas" põe as que não estão em nenhum campo e "Limpar" tira todas', () => {
    const { botao, emitidos } = montar({ valor: ['a'], excluir: ['b'] });
    botao('Todas').click();
    expect(emitidos.at(-1)).toEqual(['a', 'c']);
    botao('Limpar').click();
    expect(emitidos.at(-1)).toEqual([]);
  });

  it('Enter escolhe a destacada sem enviar o formulário; Backspace com o campo vazio tira a última', () => {
    const { campo, digitar, emitidos } = montar({ valor: ['a'] });
    digitar('11');
    const enter = new KeyboardEvent('keydown', { key: 'Enter', cancelable: true });
    campo().dispatchEvent(enter);
    expect(enter.defaultPrevented).toBe(true);
    expect(emitidos.at(-1)).toEqual(['a', 'b']);
    campo().dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace' }));
    expect(emitidos.at(-1)).toEqual([]);
  });

  it('o selo abre a janelinha de cor só para quem administra', () => {
    const sem = montar({ valor: ['a'] });
    (sem.raiz.querySelector('.pilula-marcador > button') as HTMLButtonElement).click();
    sem.fixture.detectChanges();
    expect(sem.raiz.querySelector('.janela-cor-marcador')).toBeNull();
    const com = montar({ valor: ['a'], podeGerir: true });
    (com.raiz.querySelector('.pilula-marcador > button') as HTMLButtonElement).click();
    com.fixture.detectChanges();
    expect(com.raiz.querySelector('.janela-cor-marcador')?.textContent).toContain('VLAN 10 em todas as portas');
  });

  it('desabilitado não mostra o campo, o × nem os botões', () => {
    const { raiz } = montar({ valor: ['a'], desabilitado: true });
    expect(raiz.querySelector('input.busca-vlan')).toBeNull();
    expect(raiz.querySelector('.tirar')).toBeNull();
    expect(Array.from(raiz.querySelectorAll('button')).some((b) => b.textContent?.trim() === 'Todas')).toBe(false);
  });
});
