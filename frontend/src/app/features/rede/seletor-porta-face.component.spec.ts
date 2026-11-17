/**
 * =============================================================================
 * ARQUIVO: seletor-porta-face.component.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar a escolha da porta clicando na face do equipamento.
 *
 * RESUMO TÉCNICO:
 * Testes de unidade (TestBed) do SeletorPortaFaceComponent e de
 * posicoesDoModelo: posições por coluna e por linha (iguais às do backend),
 * porta ocupada desativada, extras fora da grade e o clique emitindo o id.
 *
 * FINALIDADE DE NEGÓCIO:
 * Garante que só dá para escolher uma porta livre (que serve) e que a face
 * fica igual à do equipamento.
 *
 * CONTEXTO NO SISTEMA:
 * Cobre seletor-porta-face.component.ts, usado no cadastro do equipamento.
 *
 * =============================================================================
 */

import { TestBed } from '@angular/core/testing';

import { ModeloFace } from './rede.models';
import { posicoesDoModelo, SeletorPortaFaceComponent } from './seletor-porta-face.component';

/** Modelo 2 linhas × 2 colunas + 1 SFP (porta 5). */
const MODELO: ModeloFace = { id: 'm', nome: 'Teste', fabricante: '', linhas: 2, colunas: 2, numeracao: 'coluna', altura_u: 1, equipamentos: 0,
  portas_extras: [{ numero: 5, rotulo: 'SFP 1', tipo: 'fibra' }] } as ModeloFace;

describe('SeletorPortaFaceComponent', () => {
  it('posições por coluna (1 em cima, 2 embaixo) e por linha', () => {
    expect(posicoesDoModelo(MODELO)).toEqual({ 1: [1, 1], 2: [2, 1], 3: [1, 2], 4: [2, 2] });
    expect(posicoesDoModelo({ ...MODELO, numeracao: 'linha' })).toEqual({ 1: [1, 1], 2: [1, 2], 3: [2, 1], 4: [2, 2] });
  });

  it('ocupada fica desativada e o clique na livre emite o id', () => {
    const fixture = TestBed.createComponent(SeletorPortaFaceComponent);
    fixture.componentRef.setInput('modelo', MODELO);
    fixture.componentRef.setInput('posicoes', posicoesDoModelo(MODELO));
    fixture.componentRef.setInput('nome', 'teste');
    fixture.componentRef.setInput('opcoes', [1, 2, 3, 4, 5].map((n) => ({ id: `p${n}`, numero: n, nome: n === 5 ? 'SFP 1' : String(n), livre: n !== 2, dica: '' })));
    fixture.componentRef.setInput('valor', 'p3');
    fixture.detectChanges();
    let escolhida = '';
    fixture.componentInstance.valorChange.subscribe((id) => (escolhida = id));
    const elemento: HTMLElement = fixture.nativeElement;
    const radios = [...elemento.querySelectorAll('input[type=radio]')] as HTMLInputElement[];
    expect(radios.length).toBe(5);
    expect(radios.find((r) => r.value === 'p2')!.disabled).toBe(true);
    expect(elemento.querySelector('.face-extras')!.textContent).toContain('SFP 1');
    expect(elemento.querySelector('[data-estado="escolhida"]')!.textContent).toContain('3');
    radios.find((r) => r.value === 'p4')!.click();
    expect(escolhida).toBe('p4');
  });
});
