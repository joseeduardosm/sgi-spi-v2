// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o seletor de sala do Patrimônio (agrupamento por andar, filtro de texto e sala de depósito).
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';

import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { SeletorSalaComponent } from './seletor-sala.component';

const SALAS = [
  { id: 'a', codigo: '05A01', rotulo: '5º andar › 05A01', andar: 5, ativo: true, deposito: false, semResponsavel: false },
  { id: 'b', codigo: '05A15', rotulo: '5º andar › 05A15 — Depósito inservível', andar: 5, ativo: true, deposito: true, semResponsavel: false },
  { id: 'c', codigo: '00A01', rotulo: 'Térreo › 00A01', andar: 0, ativo: true, deposito: false, semResponsavel: false },
  { id: 'd', codigo: '-1A01', rotulo: 'Subsolo › -1A01', andar: -1, ativo: false, deposito: false, semResponsavel: false },
];

describe('SeletorSalaComponent', () => {
  function montar(entradas: Record<string, unknown> = {}) {
    TestBed.configureTestingModule({ providers: [{ provide: PatrimonioEstadoService, useValue: { salas: signal(SALAS) } }] });
    const fixture = TestBed.createComponent(SeletorSalaComponent);
    for (const [chave, valor] of Object.entries(entradas)) fixture.componentRef.setInput(chave, valor);
    fixture.detectChanges();
    return fixture;
  }

  it('agrupa por andar, do subsolo para cima, e esconde as salas inativas', () => {
    const grupos = (montar().componentInstance as unknown as { grupos: () => { titulo: string; salas: { id: string }[] }[] }).grupos();
    expect(grupos.map((g) => g.titulo)).toEqual(['Térreo', '5º andar']);
    expect(grupos.flatMap((g) => g.salas.map((s) => s.id))).toEqual(['c', 'a', 'b']);
  });

  it('mostra as inativas quando pedido', () => {
    const grupos = (montar({ soAtivas: false }).componentInstance as unknown as { grupos: () => { titulo: string }[] }).grupos();
    expect(grupos.map((g) => g.titulo)).toEqual(['Subsolo', 'Térreo', '5º andar']);
  });

  it('só oferece o depósito de inservíveis quando é o destino dos inservíveis', () => {
    const grupos = (montar({ soDeposito: true }).componentInstance as unknown as { grupos: () => { salas: { id: string }[] }[] }).grupos();
    expect(grupos.flatMap((g) => g.salas.map((s) => s.id))).toEqual(['b']);
  });

  it('filtra as salas conforme o texto digitado e desfaz a escolha ao digitar de novo', () => {
    const fixture = montar();
    const c = fixture.componentInstance as unknown as { digitou: (t: string) => void; grupos: () => { salas: { id: string }[] }[]; valor: () => string };
    c.digitou('00a');
    expect(c.grupos().flatMap((g) => g.salas.map((s) => s.id))).toEqual(['c']);
    c.digitou('depósito');
    expect(c.grupos().flatMap((g) => g.salas.map((s) => s.id))).toEqual(['b']);
    expect(c.valor()).toBe('');
  });

  it('não oferece a sala que deve ser excluída (a origem da movimentação)', () => {
    const grupos = (montar({ excluir: ['a'] }).componentInstance as unknown as { grupos: () => { salas: { id: string }[] }[] }).grupos();
    expect(grupos.flatMap((g) => g.salas.map((s) => s.id))).not.toContain('a');
  });

  describe('leitura do código da porta', () => {
    type Interno = { lerPorta: (c: string) => void; valor: () => string; avisoLeitura: () => string; lendo: { set: (v: boolean) => void; (): boolean } };

    it('escolhe a sala pelo código lido, mesmo escrito de outro jeito, e fecha o leitor', () => {
      const c = montar({ leitor: true }).componentInstance as unknown as Interno;
      c.lendo.set(true);
      c.lerPorta(' 0a1 ');
      expect(c.valor()).toBe('c');
      expect(c.lendo()).toBe(false);
      c.lerPorta('05-A-01');
      expect(c.valor()).toBe('a');
    });

    it('avisa quando o código não existe ou a sala não pode ser escolhida neste campo', () => {
      const c = montar({ leitor: true, soDeposito: true }).componentInstance as unknown as Interno;
      c.lerPorta('99A99');
      expect(c.avisoLeitura()).toContain('Nenhuma sala');
      c.lerPorta('05A01');
      expect(c.avisoLeitura()).toContain('não pode ser escolhida');
      expect(c.valor()).toBe('');
      c.lerPorta('05A15');
      expect(c.valor()).toBe('b');
    });

    it('não oferece sala inativa quando o campo só aceita ativas', () => {
      const c = montar({ leitor: true }).componentInstance as unknown as Interno;
      c.lerPorta('-1A01');
      expect(c.valor()).toBe('');
      expect(c.avisoLeitura()).toContain('não pode ser escolhida');
    });
  });
});
