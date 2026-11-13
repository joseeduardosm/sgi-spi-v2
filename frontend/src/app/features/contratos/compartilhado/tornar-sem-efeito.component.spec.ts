/**
 * =============================================================================
 * ARQUIVO: tornar-sem-efeito.component.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar o botão "Tornar sem efeito" e a janela que pede o motivo.
 *
 * RESUMO TÉCNICO:
 * Testes de unidade (TestBed) do TornarSemEfeitoComponent com um
 * AlteracoesApiService falso: botão desativado mostra o motivo do bloqueio;
 * a janela só libera o envio com 10+ caracteres; o envio chama a API com o
 * tipo, o registro e o motivo e emite `concluido`.
 *
 * FINALIDADE DE NEGÓCIO:
 * Garante que nenhum evento é tornado sem efeito sem motivo e que a pessoa vê
 * por que o botão está bloqueado.
 *
 * CONTEXTO NO SISTEMA:
 * Cobre tornar-sem-efeito.component.ts, usado no histórico das telas de
 * reajuste, repactuação, aditamento/supressão, prorrogação e na aba Eventos.
 *
 * =============================================================================
 */

import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { AlteracoesApiService } from './alteracoes-api.service';
import { TornarSemEfeitoComponent } from './tornar-sem-efeito.component';

describe('TornarSemEfeitoComponent', () => {
  /** Chamadas feitas à API falsa: [contrato, tipo, registro, motivo]. */
  let chamadas: string[][];

  beforeEach(() => {
    chamadas = [];
    TestBed.configureTestingModule({
      providers: [{ provide: AlteracoesApiService, useValue: {
        tornarSemEfeito: (...args: string[]) => { chamadas.push(args); return of(undefined); },
      } }],
    });
  });

  /** Cria o componente com os inputs do caso e devolve atalhos para o teste. */
  function abrir(pode: boolean, motivoBloqueio = '') {
    const fixture = TestBed.createComponent(TornarSemEfeitoComponent);
    fixture.componentRef.setInput('contratoId', 'c1');
    fixture.componentRef.setInput('tipo', 'reajustes');
    fixture.componentRef.setInput('registroId', 'r1');
    fixture.componentRef.setInput('pode', pode);
    fixture.componentRef.setInput('motivoBloqueio', motivoBloqueio);
    fixture.detectChanges();
    const elemento: HTMLElement = fixture.nativeElement;
    const botoes = () => [...elemento.querySelectorAll('button')].filter((b) => b.textContent?.includes('Tornar sem efeito')) as HTMLButtonElement[];
    return { fixture, elemento, botoes };
  }

  it('bloqueado: botão desativado e o motivo à vista', () => {
    const { elemento, botoes } = abrir(false, 'A competência 02/2026 já foi medida com o preço novo.');
    expect(botoes()[0].disabled).toBe(true);
    expect(elemento.textContent).toContain('02/2026 já foi medida');
  });

  it('pede motivo de 10+ caracteres, chama a API e avisa o pai', async () => {
    const { fixture, elemento, botoes } = abrir(true);
    let concluiu = false;
    fixture.componentInstance.concluido.subscribe(() => (concluiu = true));
    botoes()[0].click();
    fixture.detectChanges();
    const enviar = botoes().at(-1)!;
    expect(enviar.disabled).toBe(true);

    const motivo = elemento.querySelector('textarea')!;
    motivo.value = 'Curto';
    motivo.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(botoes().at(-1)!.disabled).toBe(true);

    motivo.value = 'Índice aplicado por engano';
    motivo.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    botoes().at(-1)!.click();
    expect(chamadas).toEqual([['c1', 'reajustes', 'r1', 'Índice aplicado por engano']]);
    expect(concluiu).toBe(true);
  });
});
