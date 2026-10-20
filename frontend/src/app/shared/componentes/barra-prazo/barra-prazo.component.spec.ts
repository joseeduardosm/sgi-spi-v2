// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a barra de prazo em dias úteis (aberto, vencido e encerrado pela entrega).

import { ComponentFixture, TestBed } from '@angular/core/testing';

import { BarraPrazoComponent } from './barra-prazo.component';

describe('BarraPrazoComponent', () => {
  let fixture: ComponentFixture<BarraPrazoComponent>;

  function montar(entradas: Record<string, unknown>): HTMLElement {
    fixture = TestBed.createComponent(BarraPrazoComponent);
    for (const [nome, valor] of Object.entries(entradas)) fixture.componentRef.setInput(nome, valor);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  const base = { prazoDias: 5, decorridos: 2, restantes: 3, percentual: 40, limite: '2026-10-30T23:59:59-03:00' };

  it('mostra os dias úteis restantes e a data limite enquanto o prazo está aberto', () => {
    const el = montar({ ...base, situacao: 'aberto' });
    expect(el.textContent).toContain('3 dias úteis restantes');
    expect(el.textContent).toContain('2 de 5 dias úteis');
    expect(el.querySelector('.barra-prazo')?.classList.contains('perigo')).toBe(false);
    expect(el.querySelector('[role=progressbar]')?.getAttribute('aria-valuenow')).toBe('2');
  });

  it('fica em perigo e diz que venceu quando passou do limite sem a entrega', () => {
    const el = montar({ ...base, situacao: 'vencido', decorridos: 5, restantes: 0, percentual: 100, entrega: 'nota fiscal' });
    expect(el.textContent).toContain('Prazo vencido');
    expect(el.textContent).toContain('sem a nota fiscal');
    expect(el.querySelector('.barra-prazo')?.classList.contains('perigo')).toBe(true);
  });

  it('mostra o prazo encerrado, em verde, quando a entrega foi feita', () => {
    const el = montar({ ...base, situacao: 'encerrado', encerradaEm: '2026-10-27T10:00:00-03:00', percentual: 60, entrega: 'nota fiscal anexada' });
    expect(el.textContent).toContain('Prazo encerrado: nota fiscal anexada em 27/10/2026');
    expect(el.querySelector('.barra-prazo')?.classList.contains('perigo')).toBe(false);
    expect(el.querySelector('.barra-prazo')?.classList.contains('alerta')).toBe(false);
  });

  it('muda para alerta a partir de 50% do prazo e para perigo a partir de 80%', () => {
    expect(montar({ ...base, situacao: 'aberto', percentual: 60 }).querySelector('.barra-prazo')?.classList.contains('alerta')).toBe(true);
    expect(montar({ ...base, situacao: 'aberto', percentual: 80 }).querySelector('.barra-prazo')?.classList.contains('perigo')).toBe(true);
  });
});
