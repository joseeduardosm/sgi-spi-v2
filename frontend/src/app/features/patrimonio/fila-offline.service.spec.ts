/**
 * =============================================================================
 * ARQUIVO: fila-offline.service.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testes unitários da fila offline do Patrimônio (FilaOfflineService).
 *
 * RESUMO TÉCNICO:
 * Usa fake-indexeddb para simular o IndexedDB (o jsdom não tem) e um dublê do
 * PatrimonioApiService com vi.fn(). Alterna navigator.onLine para simular a
 * queda e a volta do sinal e confere ordem de envio, retenção na fila,
 * marcação de erro e o mapa id_cliente -> id do servidor.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege o inventário feito em campo sem internet: nada do que foi lido ou
 * cadastrado no aparelho pode se perder, duplicar ou ser enviado fora de
 * ordem, e o item recusado pela regra precisa mostrar o motivo.
 *
 * CONTEXTO NO SISTEMA:
 * Cobre fila-offline.service.ts, usado pelas telas de cadastro de bem,
 * movimentação e listas de classificação/baixa do Patrimônio.
 *
 * =============================================================================
 */
import { IDBFactory } from 'fake-indexeddb';

import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { FilaOfflineService } from './fila-offline.service';
import { PatrimonioApiService } from './patrimonio-api.service';

/** Monta uma ação de cadastro de bem com a chapa informada (id_cliente derivado da chapa). */
const BEM = (chapa: string) => ({ tipo: 'cadastro_bem' as const, corpo: { id_cliente: `id-${chapa}`, chapa, descricao: 'Cadeira', localizacao_id: 's', conservacao: 4, situacao: 'ativo' as const, origem: 'proprio' as const } });

describe('FilaOfflineService', () => {
  let api: { cadastrarBem: ReturnType<typeof vi.fn>; criarClassificacao: ReturnType<typeof vi.fn>; incluirNaClassificacao: ReturnType<typeof vi.fn> };

  /**
   * Cria o serviço com um dublê da API (vi.fn registra as chamadas e devolve
   * respostas de sucesso por padrão). O TestBed é o injetor de testes do Angular.
   */
  function criar() {
    api = { cadastrarBem: vi.fn(() => of({})), criarClassificacao: vi.fn(() => of({ id: 'servidor-1' })), incluirNaClassificacao: vi.fn(() => of({})) };
    TestBed.configureTestingModule({ providers: [{ provide: PatrimonioApiService, useValue: api }] });
    return TestBed.inject(FilaOfflineService);
  }

  // Antes de cada teste: começa sem sinal, para que nada seja enviado sozinho
  beforeEach(() => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
    // Banco novo e vazio a cada teste (o jsdom não traz IndexedDB)
    Object.defineProperty(globalThis, 'indexedDB', { value: new IDBFactory(), configurable: true, writable: true });
  });

  it('guarda a ação sem sinal e não envia enquanto estiver offline', async () => {
    const fila = criar();
    await fila.enfileirar(BEM('A-1'), 'Cadastro do bem A-1');
    expect(fila.itens().length).toBe(1);
    expect(api.cadastrarBem).not.toHaveBeenCalled();
  });

  it('envia em ordem quando o sinal volta e esvazia a fila', async () => {
    const fila = criar();
    await fila.enfileirar(BEM('A-1'), 'a');
    await fila.enfileirar(BEM('A-2'), 'b');
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
    await fila.sincronizar();
    expect(api.cadastrarBem.mock.calls.map((c) => c[0].chapa)).toEqual(['A-1', 'A-2']);
    expect(api.cadastrarBem.mock.calls[0][1]).toBe('offline');
    expect(fila.itens().length).toBe(0);
  });

  it('para no primeiro problema de conexão e mantém o item para a próxima tentativa', async () => {
    const fila = criar();
    await fila.enfileirar(BEM('A-1'), 'a');
    await fila.enfileirar(BEM('A-2'), 'b');
    api.cadastrarBem.mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 0 })));
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
    await fila.sincronizar();
    expect(api.cadastrarBem).toHaveBeenCalledTimes(1);
    expect(fila.itens().length).toBe(2);
    expect(fila.itens().every((i) => i.erro === null)).toBe(true);
  });

  it('marca com o motivo o item recusado pela regra e segue com os demais', async () => {
    const fila = criar();
    await fila.enfileirar(BEM('A-1'), 'a');
    await fila.enfileirar(BEM('A-2'), 'b');
    api.cadastrarBem.mockReturnValueOnce(throwError(() => new HttpErrorResponse({ status: 409, error: { detalhe: 'Já existe um bem com a chapa A-1.' } })));
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
    await fila.sincronizar();
    expect(fila.itens().length).toBe(1);
    expect(fila.itens()[0].erro).toBe('Já existe um bem com a chapa A-1.');
  });

  it('inclui chapas em uma lista criada no próprio aparelho usando o id guardado do servidor', async () => {
    const fila = criar();
    await fila.enfileirar({ tipo: 'criar_classificacao', corpo: { id_cliente: 'lista-local', tipo: 'inservivel' } }, 'Lista');
    await fila.enfileirar({ tipo: 'incluir_classificacao', corpo: { lista: { id_cliente: 'lista-local' }, chapa: 'X-9' } }, 'Chapa X-9');
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true });
    await fila.sincronizar();
    expect(api.criarClassificacao).toHaveBeenCalledWith('inservivel', 'lista-local');
    expect(api.incluirNaClassificacao).toHaveBeenCalledWith('servidor-1', { chapa: 'X-9' });
  });
});
