/**
 * =============================================================================
 * ARQUIVO: diferenca-manual.component.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar a pergunta e o formulário da diferença retroativa informada
 * manualmente, usada no reajuste e na repactuação de contratos.
 *
 * RESUMO TÉCNICO:
 * Testes de unidade (Jasmine + TestBed do Angular) do DiferencaManualComponent.
 * Criam o componente com inputs simulados, clicam nos botões, preenchem
 * caixas, valor, justificativa e PDF e conferem o texto exibido e o evento
 * "salvar" emitido.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege a regra de que meses pagos fora do sistema só viram diferença manual
 * com meses marcados, valor, justificativa e PDF da memória; que a pergunta
 * usa Sim verde e Não vermelho; e que, depois de gravada, a diferença mostra a
 * observação que sai nos documentos em vez de perguntar de novo.
 *
 * CONTEXTO NO SISTEMA:
 * Cobre diferenca-manual.component.ts, usado pelas telas de reajuste e de
 * repactuação; os tipos vêm de contratos.models.ts.
 *
 * =============================================================================
 */

import { TestBed } from '@angular/core/testing';

import { DiferencaManual, GravacaoDiferencaManual, MesSemMedicao } from './contratos.models';
import { DiferencaManualComponent } from './diferenca-manual.component';

/** Monta um mês sem medição concluída (formato devolvido pela API) para os cenários de teste. */
const mes = (id: string, rotulo: string, inicio: string, fim: string): MesSemMedicao => ({
  competencia_id: id, identificador: id, rotulo, periodo_inicio: inicio, periodo_fim: fim, coberta_por_outra: false,
});
/** Dois meses candidatos (jan e fev/2026) usados na maioria dos testes. */
const MESES = [mes('c1', '01/2026', '2026-01-01', '2026-01-31'), mes('c2', '02/2026', '2026-02-01', '2026-02-28')];

describe('DiferencaManualComponent', () => {
  /**
   * Cria o componente com os inputs informados e devolve atalhos para o teste.
   * `fixture.componentRef.setInput` define um input() do Angular como faria o
   * componente pai; `detectChanges` atualiza o HTML após a mudança.
   * @returns fixture, elemento raiz e uma função que acha um botão pelo texto.
   */
  function abrir(meses: MesSemMedicao[] = MESES, diferenca: DiferencaManual | null = null) {
    const fixture = TestBed.createComponent(DiferencaManualComponent);
    fixture.componentRef.setInput('meses', meses);
    fixture.componentRef.setInput('diferenca', diferenca);
    fixture.componentRef.setInput('podeEditar', true);
    fixture.detectChanges();
    const elemento: HTMLElement = fixture.nativeElement;
    const botao = (texto: string) => [...elemento.querySelectorAll('button')].find((b) => b.textContent?.includes(texto)) as HTMLButtonElement;
    return { fixture, elemento, botao };
  }

  it('pergunta com a quantidade de meses e o período', () => {
    const { elemento, botao } = abrir();
    expect(elemento.textContent).toContain('Identifiquei que 2 meses do período de');
    expect(elemento.textContent).toContain('01/01/2026');
    expect(elemento.textContent).toContain('28/02/2026');
    expect(elemento.textContent).toContain('não possuem medições finalizadas. Deseja inserir o valor da diferença manualmente?');
    // Sim (verde) e Não (vermelho), separados
    expect(botao('Sim').classList).toContain('acao-positiva');
    expect(botao('Não').classList).toContain('acao-recusar');
  });

  it('não mostra nada sem meses e sem diferença (e aceita a API antiga, sem os campos)', () => {
    const fixture = TestBed.createComponent(DiferencaManualComponent);
    fixture.componentRef.setInput('meses', undefined);
    fixture.componentRef.setInput('diferenca', undefined);
    fixture.componentRef.setInput('podeEditar', true);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent?.trim()).toBe('');
  });

  it('no Sim, exige meses, valor, justificativa e PDF antes de salvar e emite o que foi preenchido', () => {
    const { fixture, elemento, botao } = abrir();
    botao('Sim').click();
    fixture.detectChanges();
    const salvar = botao('Salvar diferença manual');
    expect(salvar.disabled).toBe(true);

    // Captura o que o componente emite em `salvar` (output do Angular é assinado com subscribe)
    const emitidos: GravacaoDiferencaManual[] = [];
    fixture.componentInstance.salvar.subscribe((d) => emitidos.push(d));
    // Marca só fevereiro, informa −150,50, a justificativa e o PDF
    const caixas = elemento.querySelectorAll<HTMLInputElement>('input[type=checkbox]');
    caixas[1].checked = true;
    caixas[1].dispatchEvent(new Event('change'));
    const valor = elemento.querySelector<HTMLInputElement>('#diferenca-manual-valor')!;
    valor.value = '-150,50';
    valor.dispatchEvent(new Event('input'));
    const justificativa = elemento.querySelector<HTMLTextAreaElement>('#diferenca-manual-justificativa')!;
    justificativa.value = 'Pago antes do SGI';
    justificativa.dispatchEvent(new Event('input'));
    const arquivo = elemento.querySelector<HTMLInputElement>('input[type=file]')!;
    Object.defineProperty(arquivo, 'files', { value: [new File(['%PDF'], 'memoria.pdf', { type: 'application/pdf' })] });
    arquivo.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    // Com tudo preenchido o botão libera; o valor vai à API com ponto decimal e só o mês marcado
    expect(salvar.disabled).toBe(false);
    salvar.click();
    expect(emitidos.length).toBe(1);
    expect(emitidos[0].valor).toBe('-150.50');
    expect(emitidos[0].competencias_ids).toEqual(['c2']);
    expect(emitidos[0].justificativa).toBe('Pago antes do SGI');
    expect(emitidos[0].arquivo.name).toBe('memoria.pdf');
  });

  it('com a diferença gravada, mostra a observação e não pergunta de novo', () => {
    const { elemento } = abrir(MESES, {
      valor: '400.00', justificativa: 'x', meses: MESES, arquivo: { anexo_id: 'a1', nome: 'm.pdf', tamanho: 10, enviado_em: '2026-03-15T10:00:00Z' },
      informado_por: 'Gestora', informado_em: '2026-03-15T10:00:00Z', observacao: 'O valor de R$ 400,00 foi inserido manualmente por Gestora', competencia_diferenca: null,
    });
    expect(elemento.textContent).toContain('O valor de R$ 400,00 foi inserido manualmente por Gestora');
    expect(elemento.textContent).toContain('01/2026, 02/2026');
    expect(elemento.textContent).not.toContain('Deseja inserir o valor da diferença manualmente?');
  });
});
