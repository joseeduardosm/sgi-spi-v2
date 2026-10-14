// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o Gantt das tarefas: barras, agrupamento, dependências, marcos e recolher grupos.

import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, expect, it } from 'vitest';

import { GanttTarefasComponent } from './gantt-tarefas.component';
import { Marco, TarefaResumo } from './tarefas.models';

function tarefa(numero: number, extra: Partial<TarefaResumo> = {}): TarefaResumo {
  return {
    numero, titulo: `Tarefa ${numero}`, status: 'a_fazer', prazo: '2026-10-20T21:00:00Z', prazo_original: '2026-10-20T21:00:00Z', criado_em: '2026-10-10T12:00:00Z', iniciada_em: null, concluida_em: null,
    atrasada: false, responsaveis: [], checklist_feitos: 0, checklist_total: 0, bloqueada: false, bloqueada_por_numeros: [], marco_id: null, ...extra,
  } as unknown as TarefaResumo;
}

function montar(tarefas: TarefaResumo[], marcos: Marco[] = []) {
  TestBed.configureTestingModule({ providers: [provideRouter([])] });
  const fixture = TestBed.createComponent(GanttTarefasComponent);
  fixture.componentRef.setInput('tarefas', tarefas);
  fixture.componentRef.setInput('marcos', marcos);
  fixture.detectChanges();
  return fixture;
}

describe('GanttTarefasComponent', () => {
  it('desenha uma barra por tarefa visível, agrupadas por situação (concluídas recolhidas)', () => {
    const f = montar([tarefa(1), tarefa(2, { status: 'em_andamento' }), tarefa(3, { status: 'concluida', concluida_em: '2026-10-12T15:00:00Z' })]);
    const raiz = f.nativeElement as HTMLElement;
    expect(raiz.querySelectorAll('.barra').length).toBe(2);
    expect(raiz.querySelectorAll('.gantt-grupo').length).toBe(3);
    // Abre o grupo das concluídas
    const grupo = [...raiz.querySelectorAll<HTMLButtonElement>('.gantt-grupo button')].find((b) => b.textContent?.includes('Concluída'));
    grupo?.click();
    f.detectChanges();
    expect(raiz.querySelectorAll('.barra').length).toBe(3);
  });

  it('liga com seta a tarefa que bloqueia à bloqueada, só quando as duas estão na tela', () => {
    const f = montar([tarefa(1), tarefa(2, { bloqueada: true, bloqueada_por_numeros: [1, 99] })]);
    expect((f.nativeElement as HTMLElement).querySelectorAll('.gantt-sobreposicao path[marker-end]').length).toBe(1);
  });

  it('a tarefa bloqueada começa onde a bloqueadora termina (e não na criação)', () => {
    const f = montar([tarefa(1, { prazo: '2026-10-15T21:00:00Z' }), tarefa(2, { bloqueada: true, bloqueada_por_numeros: [1] })]);
    const barras = [...(f.nativeElement as HTMLElement).querySelectorAll<HTMLElement>('.barra')];
    const esquerda = (el: HTMLElement) => parseFloat(el.style.left);
    expect(esquerda(barras[1])).toBeGreaterThan(esquerda(barras[0]));
  });

  it('zoom in e out mudam a escala em passos e respeitam os limites', () => {
    const f = montar([tarefa(1)]);
    const raiz = f.nativeElement as HTMLElement;
    const [menos, mais] = [...raiz.querySelectorAll<HTMLButtonElement>('.zoom-gantt button')];
    const pct = () => raiz.querySelector('.zoom-gantt output')?.textContent?.trim();
    expect(pct()).toBe('100%');
    mais.click(); f.detectChanges();
    expect(pct()).toBe('125%');
    menos.click(); menos.click(); f.detectChanges();
    expect(pct()).toBe('80%');
    for (let i = 0; i < 20; i++) menos.click();
    f.detectChanges();
    expect(menos.disabled).toBe(true);
  });

  it('mostra o progresso do checklist e marca a atrasada', () => {
    const f = montar([tarefa(1, { status: 'em_andamento', checklist_total: 4, checklist_feitos: 1, atrasada: true })]);
    const barra = (f.nativeElement as HTMLElement).querySelector('.barra') as HTMLElement;
    expect(barra.classList.contains('atrasada')).toBe(true);
    expect((barra.querySelector('.preenchimento') as HTMLElement).style.width).toBe('25%');
  });

  it('coloca os marcos numa faixa própria e avisa quando não há tarefas', () => {
    const marco = { id: 'm', nome: 'Fase 1', descricao: '', data_alvo: '2026-10-30', atingido_em: null, situacao: 'no_prazo', total: 1, concluidas: 0, atrasadas: 0 } as Marco;
    const comMarco = montar([tarefa(1)], [marco]);
    expect((comMarco.nativeElement as HTMLElement).querySelectorAll('.marco').length).toBe(1);
    TestBed.resetTestingModule();
    const vazio = montar([]);
    expect((vazio.nativeElement as HTMLElement).textContent).toContain('Nenhuma tarefa');
  });
});
