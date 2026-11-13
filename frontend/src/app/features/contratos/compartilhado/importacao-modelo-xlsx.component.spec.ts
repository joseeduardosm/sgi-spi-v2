/**
 * =============================================================================
 * ARQUIVO: importacao-modelo-xlsx.component.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar a janela de importação de checklist e formulário de avaliação por
 * planilha XLSX: a prévia e o bloqueio da confirmação quando há erros.
 *
 * RESUMO TÉCNICO:
 * Testes Jasmine com TestBed. O HttpClient é trocado pelo de teste
 * (HttpTestingController), que intercepta as chamadas e devolve respostas
 * simuladas com flush(). O AcessoService é substituído por um falso que
 * libera tudo.
 *
 * FINALIDADE DE NEGÓCIO:
 * Garante que uma planilha com erro nunca seja gravada (o botão Confirmar
 * fica bloqueado e os erros aparecem com a linha) e que, com a prévia válida,
 * a confirmação reenvia a planilha e a tela recarrega a lista.
 *
 * CONTEXTO NO SISTEMA:
 * Cobre importacao-modelo-xlsx.component.ts e, indiretamente, as rotas
 * /contratos/{id}/checklists/importacao-xlsx (prévia e gravação).
 *
 * =============================================================================
 */

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AcessoService } from '../../../core/acesso/acesso.service';
import { PreviaImportacaoModelo } from './contratos.models';
import { ImportacaoModeloXlsxComponent } from './importacao-modelo-xlsx.component';

/** Prévia mínima de checklist; os testes sobrescrevem erros e `pode_importar`. */
const previa = (extras: Partial<PreviaImportacaoModelo> = {}): PreviaImportacaoModelo => ({
  tipo: 'checklist', nome: 'Mensal', documentos: [{ linha: 7, nome: 'FGTS', observacao: '', obrigatorio: true, com_validade: false }],
  escala: [], faixas: [], grupos: [], erros: [], avisos: [], pode_importar: true, ...extras,
});

describe('ImportacaoModeloXlsxComponent', () => {
  // Antes de cada teste: HttpClient de teste (nenhuma chamada real sai) e permissão sempre liberada
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: AcessoService, useValue: { pode: () => true } }],
    });
  });

  /** Cria o componente de um contrato, clica em "Importar XLSX" e devolve o controlador HTTP de teste. */
  function abrir() {
    const fixture = TestBed.createComponent(ImportacaoModeloXlsxComponent);
    fixture.componentRef.setInput('tipo', 'checklist');
    fixture.componentRef.setInput('contratoId', 'c1');
    const elemento: HTMLElement = fixture.nativeElement;
    fixture.detectChanges();
    (elemento.querySelector('button') as HTMLButtonElement).click();
    fixture.detectChanges();
    return { fixture, elemento, http: TestBed.inject(HttpTestingController) };
  }

  /**
   * Simula a escolha de uma planilha no campo de arquivo. Como `files` é só leitura no navegador,
   * o teste o redefine com Object.defineProperty e dispara o evento change.
   */
  function escolher(elemento: HTMLElement) {
    const campo = elemento.querySelector('input[type=file]') as HTMLInputElement;
    Object.defineProperty(campo, 'files', { value: [new File(['PK'], 'checklist.xlsx')] });
    campo.dispatchEvent(new Event('change'));
  }

  it('bloqueia a confirmação quando a prévia traz erros', () => {
    const { fixture, elemento, http } = abrir();
    escolher(elemento);
    http.expectOne('/api/contratos/c1/checklists/importacao-xlsx/previa').flush(
      previa({ erros: [{ linha: 7, campo: 'Documento', mensagem: 'Informe o nome do documento.' }], pode_importar: false }),
    );
    fixture.detectChanges();
    expect(elemento.textContent).toContain('Linha 7 · Documento: Informe o nome do documento.');
    const confirmar = [...elemento.querySelectorAll('button')].find((b) => b.textContent?.includes('Confirmar importação'))!;
    expect(confirmar.disabled).toBe(true);
    http.verify();
  });

  it('confirma reenviando a planilha e avisa a tela para recarregar', () => {
    const { fixture, elemento, http } = abrir();
    let recarregou = false;
    fixture.componentInstance.importado.subscribe(() => (recarregou = true));
    escolher(elemento);
    http.expectOne('/api/contratos/c1/checklists/importacao-xlsx/previa').flush(previa());
    fixture.detectChanges();
    const confirmar = [...elemento.querySelectorAll('button')].find((b) => b.textContent?.includes('Confirmar importação'))!;
    expect(confirmar.disabled).toBe(false);
    confirmar.click();
    http.expectOne('/api/contratos/c1/checklists/importacao-xlsx').flush([]);
    expect(recarregou).toBe(true);
  });
});
