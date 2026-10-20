// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a trilha de etapas (estados, linhas entre passos, progresso, passo clicável e bloqueado).

import { TestBed } from '@angular/core/testing';

import { EtapaTrilha, TrilhaEtapasComponent } from './trilha-etapas.component';

const etapas: EtapaTrilha[] = [
  { id: 'a', rotulo: 'Nomeações', estado: 'concluida' },
  { id: 'b', rotulo: 'Ciência', estado: 'atual' },
  { id: 'c', rotulo: 'Autoridade', estado: 'bloqueada' },
  { id: 'd', rotulo: 'Parecer', estado: 'aguardando', opcional: true },
];

function montar(extras: Record<string, unknown> = {}) {
  const fixture = TestBed.createComponent(TrilhaEtapasComponent);
  fixture.componentRef.setInput('etapas', etapas);
  for (const [k, v] of Object.entries(extras)) fixture.componentRef.setInput(k, v);
  fixture.detectChanges();
  return fixture;
}

describe('TrilhaEtapasComponent', () => {
  it('numera os passos, marca o concluído com ✓ e mostra o progresso', () => {
    const el = montar().nativeElement as HTMLElement;
    const bolinhas = Array.from(el.querySelectorAll('.bolinha-etapa')).map((b) => b.textContent?.trim());
    expect(bolinhas).toEqual(['✓', '2', '3', '4']);
    expect(el.textContent).toContain('1 de 4 etapas concluídas');
    expect(el.textContent).toContain('25,0%');
    expect(el.querySelector('li.atual')?.getAttribute('aria-current') ?? el.querySelector('li.atual .passo')?.getAttribute('aria-current')).toBe('step');
  });

  it('liga os passos: verde do concluído ao atual, cinza nos demais; opcional aparece como tal', () => {
    const el = montar().nativeElement as HTMLElement;
    const ligas = Array.from(el.querySelectorAll('li')).map((li) => li.getAttribute('data-liga'));
    expect(ligas).toEqual(['verde', 'cinza', 'cinza', null]);
    expect(el.textContent).toContain('opcional');
  });

  it('na versão compacta não mostra a barra de progresso', () => {
    const el = montar({ compacta: true }).nativeElement as HTMLElement;
    expect(el.querySelector('.progresso-etapas')).toBeNull();
  });

  it('navegável: clicar escolhe o passo; o bloqueado não recebe clique', () => {
    const fixture = montar({ navegavel: true });
    const el = fixture.nativeElement as HTMLElement;
    const escolhidos: string[] = [];
    fixture.componentInstance.escolheu.subscribe((id) => escolhidos.push(id));
    const botoes = el.querySelectorAll('button');
    expect((botoes[2] as HTMLButtonElement).disabled).toBe(true);
    (botoes[0] as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(escolhidos).toEqual(['a']);
    expect(el.querySelector('li.selecionada')).not.toBeNull();
  });
});
