// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a fila offline do Patrimônio: guarda no aparelho, envia em ordem quando volta o sinal e para no problema de conexão.
import { IDBFactory } from 'fake-indexeddb';

import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { FilaOfflineService } from './fila-offline.service';
import { PatrimonioApiService } from './patrimonio-api.service';

const BEM = (chapa: string) => ({ tipo: 'cadastro_bem' as const, corpo: { id_cliente: `id-${chapa}`, chapa, descricao: 'Cadeira', localizacao_id: 's', conservacao: 4, situacao: 'ativo' as const, origem: 'proprio' as const } });

describe('FilaOfflineService', () => {
  let api: { cadastrarBem: ReturnType<typeof vi.fn>; criarClassificacao: ReturnType<typeof vi.fn>; incluirNaClassificacao: ReturnType<typeof vi.fn> };

  function criar() {
    api = { cadastrarBem: vi.fn(() => of({})), criarClassificacao: vi.fn(() => of({ id: 'servidor-1' })), incluirNaClassificacao: vi.fn(() => of({})) };
    TestBed.configureTestingModule({ providers: [{ provide: PatrimonioApiService, useValue: api }] });
    return TestBed.inject(FilaOfflineService);
  }

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
