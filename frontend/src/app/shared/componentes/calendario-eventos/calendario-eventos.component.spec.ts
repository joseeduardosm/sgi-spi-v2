// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar as semanas exibidas e o agrupamento de eventos do calendário genérico.

import { TestBed } from '@angular/core/testing';

import { CalendarioEventosComponent, semanasExibidas } from './calendario-eventos.component';

describe('calendario-eventos', () => {
  it('o mês exibe semanas completas (domingo a sábado) e a semana exibe só sete dias', () => {
    const referencia = new Date(2026, 9, 8); // 08/10/2026 (quinta)
    const mes = semanasExibidas(referencia, 'mes');
    expect(mes.every((s) => s.length === 7 && s[0].getDay() === 0)).toBe(true);
    expect(mes[0][0].getTime()).toBeLessThanOrEqual(new Date(2026, 9, 1).getTime());
    const semana = semanasExibidas(referencia, 'semana');
    expect(semana.length).toBe(1);
    expect(semana[0][0].getDate()).toBe(4);
    expect(semana[0][6].getDate()).toBe(10);
  });

  it('coloca cada evento no seu dia, em ordem de hora, e avisa o período visível', () => {
    const fixture = TestBed.createComponent(CalendarioEventosComponent);
    const periodos: { de: string; ate: string }[] = [];
    fixture.componentInstance.periodoMudou.subscribe((p) => periodos.push(p));
    const hoje = new Date();
    const dia = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, '0')}-15`;
    fixture.componentRef.setInput('eventos', [
      { data: dia, hora: '15:00:00', rotulo: 'Tarde', severidade: 'info' },
      { data: dia, hora: '08:30:00', rotulo: 'Manhã', severidade: 'alta' },
    ]);
    fixture.detectChanges();
    const pilulas = Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('.pilula-evento')).map((e) => e.textContent?.trim());
    expect(pilulas).toEqual(['08:30Manhã', '15:00Tarde']);
    expect(periodos.length).toBeGreaterThan(0);
    expect(periodos[0].de <= dia && dia <= periodos[0].ate).toBe(true);
  });
});
