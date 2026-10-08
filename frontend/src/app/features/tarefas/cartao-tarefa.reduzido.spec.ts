// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a versão reduzida do cartão da tarefa (número, prazo, criticidade e marcadores).

import { TestBed } from '@angular/core/testing';

import { CartaoTarefaComponent } from './cartao-tarefa.component';
import { TarefaResumo } from './tarefas.models';

describe('CartaoTarefaComponent (versão reduzida)', () => {
  it('traz número, prazo, sigla da criticidade e um marcador por etiqueta', () => {
    const fixture = TestBed.createComponent(CartaoTarefaComponent);
    const tarefa = {
      numero: 1234, titulo: 'Teste', status: 'a_fazer', prioridade: 'critica', prazo: '2026-10-20T21:00:00Z', responsaveis: [], prorrogacoes: 0,
      marcadores: [{ id: 'a', nome: 'Contrato 1', cor_indice: 2 }, { id: 'b', nome: 'Medição', cor_indice: 5 }],
    } as unknown as TarefaResumo;
    fixture.componentRef.setInput('tarefa', tarefa);
    fixture.detectChanges();
    const mini = (fixture.nativeElement as HTMLElement).querySelector('.mini-cartao') as HTMLElement;
    expect(mini.querySelector('.mini-numero')?.textContent).toBe('#1234');
    expect(mini.querySelector('.mini-prioridade')?.textContent).toBe('C');
    expect(mini.querySelectorAll('.mini-marcadores i').length).toBe(2);
    expect(mini.querySelector('.mini-prazo')?.textContent).toMatch(/\d{2}\/\d{2}/);
  });
});
