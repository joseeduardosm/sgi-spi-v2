/**
 * =============================================================================
 * ARQUIVO: diferenca-manual.component.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar o formulário da diferença retroativa do cálculo manual (mês a mês),
 * usado no reajuste e na repactuação de contratos.
 *
 * RESUMO TÉCNICO:
 * Testes de unidade (Jasmine + TestBed do Angular) do DiferencaManualComponent.
 * Criam o componente com inputs simulados, preenchem o valor de cada mês,
 * justificativa e PDF e conferem o total, os selos de situação e o evento
 * "salvar" emitido.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege a regra do cálculo manual: a diferença é informada mês a mês (mês
 * medido e mês em andamento inclusive), o total é a soma, justificativa e PDF
 * são obrigatórios, e a diferença gravada mostra os meses e a observação.
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

/** Monta um mês candidato (formato devolvido pela API) para os cenários de teste. */
const mes = (id: string, rotulo: string, extra: Partial<MesSemMedicao> = {}): MesSemMedicao => ({
  competencia_id: id, identificador: id, rotulo, periodo_inicio: '2026-01-01', periodo_fim: '2026-01-31', coberta_por_outra: false, ...extra,
});
/** Janeiro medido no SGI, fevereiro sem medição e março em andamento. */
const MESES = [mes('c1', '01/2026', { medida: true }), mes('c2', '02/2026'), mes('c3', '03/2026', { em_andamento: true })];

describe('DiferencaManualComponent', () => {
  /**
   * Cria o componente com os inputs informados e devolve atalhos para o teste.
   * `fixture.componentRef.setInput` define um input() do Angular como faria o
   * componente pai; `detectChanges` atualiza o HTML após a mudança.
   */
  function abrir(meses: MesSemMedicao[] = MESES, diferenca: DiferencaManual | null = null) {
    const fixture = TestBed.createComponent(DiferencaManualComponent);
    fixture.componentRef.setInput('meses', meses);
    fixture.componentRef.setInput('diferenca', diferenca);
    fixture.componentRef.setInput('podeEditar', true);
    fixture.detectChanges();
    const elemento: HTMLElement = fixture.nativeElement;
    const botao = (texto: string) => [...elemento.querySelectorAll('button')].find((b) => b.textContent?.includes(texto)) as HTMLButtonElement;
    /** Digita um texto num campo e avisa o Angular (o evento "input" atualiza o ngModel). */
    const digitar = (campo: HTMLInputElement | HTMLTextAreaElement, texto: string) => { campo.value = texto; campo.dispatchEvent(new Event('input')); };
    return { fixture, elemento, botao, digitar };
  }

  it('lista os meses com a situação no SGI (medido, sem medição, em andamento)', () => {
    const { elemento } = abrir();
    expect(elemento.textContent).toContain('Medido no SGI');
    expect(elemento.textContent).toContain('Sem medição no SGI');
    expect(elemento.textContent).toContain('Em andamento');
    expect(elemento.querySelectorAll('input[inputmode=decimal]').length).toBe(3);
  });

  it('aceita a API antiga, sem os campos, sem quebrar', () => {
    const fixture = TestBed.createComponent(DiferencaManualComponent);
    fixture.componentRef.setInput('meses', undefined);
    fixture.componentRef.setInput('diferenca', undefined);
    fixture.componentRef.setInput('podeEditar', true);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Não há meses');
  });

  it('soma os meses, exige justificativa e PDF e emite só os meses preenchidos', async () => {
    const { fixture, elemento, botao, digitar } = abrir();
    const salvar = botao('Salvar diferença mês a mês');
    expect(salvar.disabled).toBe(true);
    const emitidos: GravacaoDiferencaManual[] = [];
    fixture.componentInstance.salvar.subscribe((d) => emitidos.push(d));

    // Janeiro (medido) 1.200,50 e março (em andamento) −200,00; fevereiro em branco
    const campos = elemento.querySelectorAll<HTMLInputElement>('input[inputmode=decimal]');
    digitar(campos[0], '1.200,50');
    digitar(campos[2], '-200');
    digitar(elemento.querySelector<HTMLTextAreaElement>('#diferenca-manual-justificativa')!, 'Pago antes do SGI');
    const arquivo = elemento.querySelector<HTMLInputElement>('input[type=file]')!;
    Object.defineProperty(arquivo, 'files', { value: [new File(['%PDF'], 'memoria.pdf', { type: 'application/pdf' })] });
    arquivo.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(elemento.textContent).toContain('Total (2 meses)');
    expect(salvar.disabled).toBe(false);
    salvar.click();
    expect(emitidos.length).toBe(1);
    expect(emitidos[0].competencias_ids).toEqual(['c1', 'c3']);
    expect(emitidos[0].valores).toEqual(['1200.50', '-200']);
    expect(emitidos[0].justificativa).toBe('Pago antes do SGI');
    expect(emitidos[0].arquivo.name).toBe('memoria.pdf');
  });

  it('valor zero num mês não libera o salvar', async () => {
    const { fixture, elemento, botao, digitar } = abrir();
    digitar(elemento.querySelectorAll<HTMLInputElement>('input[inputmode=decimal]')[1], '0');
    digitar(elemento.querySelector<HTMLTextAreaElement>('#diferenca-manual-justificativa')!, 'x');
    fixture.detectChanges();
    await fixture.whenStable();
    expect(botao('Salvar diferença mês a mês').disabled).toBe(true);
  });

  it('com a diferença gravada, mostra os meses, o total e a observação', () => {
    const gravados = [mes('c1', '01/2026', { medida: true, valor: '300.00' }), mes('c2', '02/2026', { valor: '100.00' })];
    const { elemento } = abrir(MESES, {
      valor: '400.00', justificativa: 'x', meses: gravados, arquivo: { anexo_id: 'a1', nome: 'm.pdf', tamanho: 10, enviado_em: '2026-03-15T10:00:00Z' },
      informado_por: 'Gestora', informado_em: '2026-03-15T10:00:00Z', observacao: 'O valor de R$ 400,00 foi inserido manualmente por Gestora', competencia_diferenca: null,
    });
    expect(elemento.textContent).toContain('O valor de R$ 400,00 foi inserido manualmente por Gestora');
    expect(elemento.textContent).toContain('Diferença informada mês a mês');
    expect(elemento.textContent).toContain('01/2026');
    expect(elemento.querySelectorAll('input[inputmode=decimal]').length).toBe(0);
  });
});
