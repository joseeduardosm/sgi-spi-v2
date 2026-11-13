/**
 * =============================================================================
 * ARQUIVO: campo-emails-adicionais.component.spec.ts
 *
 * FINALIDADE:
 * Testar o campo "Outros e-mails desta ocorrência" do diário de bordo.
 *
 * RESUMO TÉCNICO:
 * Cria o componente com o TestBed, preenche `salvos` e confere a lista
 * `escolhidos`: adicionar pelo campo, recusar e-mail inválido, não repetir,
 * transformar texto colado com vírgula em fichas e incluir um e-mail salvo.
 *
 * FINALIDADE DE NEGÓCIO:
 * Garante que só e-mails válidos vão para a ocorrência e que os e-mails
 * guardados no contrato chegam desmarcados (só entram se a pessoa clicar).
 *
 * CONTEXTO NO SISTEMA:
 * Testa `campo-emails-adicionais.component.ts`, usado pela aba Diário
 * (`detalhe/aba-diario.component.ts`).
 *
 * =============================================================================
 */

import { TestBed } from '@angular/core/testing';

import { CampoEmailsAdicionaisComponent } from './campo-emails-adicionais.component';

describe('CampoEmailsAdicionaisComponent', () => {
  /** Monta o componente com dois e-mails salvos no contrato e devolve o elemento e a instância. */
  function montar() {
    const fixture = TestBed.createComponent(CampoEmailsAdicionaisComponent);
    fixture.componentRef.setInput('salvos', [{ id: 1, email: 'obra@acme.com' }, { id: 2, email: 'fiscal@orgao.sp.gov.br' }]);
    fixture.detectChanges();
    return { fixture, el: fixture.nativeElement as HTMLElement, comp: fixture.componentInstance };
  }

  /** Digita no campo e aperta Enter, como o usuário faria. */
  function digitarEnter(el: HTMLElement, texto: string) {
    const campo = el.querySelector('input') as HTMLInputElement;
    campo.value = texto;
    campo.dispatchEvent(new Event('input'));
    campo.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
  }

  it('os salvos começam desmarcados e clicar inclui na ocorrência', () => {
    const { fixture, el, comp } = montar();
    expect(comp.escolhidos()).toEqual([]);
    const botoes = el.querySelectorAll('.salvos li > button');
    expect(botoes.length).toBe(2);
    (botoes[0] as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(comp.escolhidos()).toEqual(['obra@acme.com']);
    // Quem já foi escolhido sai de "Usados antes"
    expect(el.querySelectorAll('.salvos li > button').length).toBe(1);
  });

  it('Enter adiciona em minúsculas, sem repetir', () => {
    const { el, comp } = montar();
    digitarEnter(el, ' Novo@Acme.com ');
    digitarEnter(el, 'novo@acme.com');
    expect(comp.escolhidos()).toEqual(['novo@acme.com']);
  });

  it('recusa e-mail inválido e mostra o erro', () => {
    const { fixture, el, comp } = montar();
    digitarEnter(el, 'sem-arroba');
    fixture.detectChanges();
    expect(comp.escolhidos()).toEqual([]);
    expect(el.querySelector('.erro-campo')?.textContent).toContain('E-mail inválido');
  });

  it('texto colado com vírgula vira uma ficha para cada e-mail', () => {
    const { el, comp } = montar();
    const campo = el.querySelector('input') as HTMLInputElement;
    campo.value = 'a@x.com, b@y.com,';
    campo.dispatchEvent(new Event('input'));
    expect(comp.escolhidos()).toEqual(['a@x.com', 'b@y.com']);
  });

  it('o × de um salvo pede a remoção ao componente pai', () => {
    const { el, comp } = montar();
    const pedidos: number[] = [];
    comp.removerSalvo.subscribe((s) => pedidos.push(s.id));
    (el.querySelector('.botao-remover-salvo button') as HTMLButtonElement).click();
    expect(pedidos).toEqual([1]);
  });
});
