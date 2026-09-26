// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a janela de importação de contrato por XLSX (validação e bloqueio da confirmação).

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { PreviaImportacao } from '../compartilhado/contratos.models';
import { ImportacaoXlsxComponent, validarPlanilha } from './importacao-xlsx.component';

/** Prévia mínima; os testes sobrescrevem erros e `pode_importar`. */
const previa = (extras: Partial<PreviaImportacao> = {}): PreviaImportacao => ({
  contrato: {
    numero: '007/2026', apelido: '', objeto: 'Limpeza', data_inicio: '2026-03-01', data_fim: '2027-02-28', vigencia_inicial_meses: 12,
    vigencia_maxima_meses: 60, periodicidade_meses: 1, mes_reajuste: 3, sei_gestao_numero: '1', sei_gestao_link: '', sei_execucao_numero: '2', sei_execucao_link: '',
  },
  empresa: null, preposto: null, itens: [], valor_global_estimado: null, erros: [], avisos: [], pode_importar: true, ...extras,
});

describe('ImportacaoXlsxComponent', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()] });
  });

  it('recusa no navegador o que não é .xlsx, vazio ou grande demais', () => {
    expect(validarPlanilha(new File(['x'], 'contrato.xlsx'))).toBeNull();
    expect(validarPlanilha(new File(['x'], 'contrato.csv'))).toContain('.xlsx');
    expect(validarPlanilha(new File([], 'contrato.xlsx'))).toContain('vazio');
  });

  it('envia para a prévia e bloqueia a confirmação quando há erros', () => {
    const fixture = TestBed.createComponent(ImportacaoXlsxComponent);
    const http = TestBed.inject(HttpTestingController);
    const elemento: HTMLElement = fixture.nativeElement;
    fixture.detectChanges();
    (elemento.querySelector('button') as HTMLButtonElement).click();
    fixture.detectChanges();

    const campo = elemento.querySelector('input[type=file]') as HTMLInputElement;
    const arquivo = new File(['PK'], 'contrato.xlsx');
    Object.defineProperty(campo, 'files', { value: [arquivo] });
    campo.dispatchEvent(new Event('change'));
    http.expectOne('/api/contratos/importacao-xlsx/previa').flush(
      previa({ erros: [{ linha: 3, campo: 'CNPJ', mensagem: 'CNPJ inválido' }], pode_importar: false }),
    );
    fixture.detectChanges();

    expect(elemento.textContent).toContain('Linha 3 · CNPJ: CNPJ inválido');
    const confirmar = [...elemento.querySelectorAll('button')].find((b) => b.textContent?.includes('Confirmar importação'))!;
    expect(confirmar.disabled).toBe(true);
    http.verify();
  });
});
