// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o carregamento dos atalhos fixos da barra lateral.

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AtalhosFixosService } from './atalhos-fixos.service';

describe('AtalhosFixosService', () => {
  let servico: AtalhosFixosService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    servico = TestBed.inject(AtalhosFixosService);
    http = TestBed.inject(HttpTestingController);
  });

  it('carrega as categorias e esvazia a lista quando a API falha', () => {
    servico.carregar();
    http.expectOne((r) => r.url.endsWith('/atalhos')).flush({ categorias: [{ id: 1, nome: 'Sistemas', ordem: 0, ativo: true, atalhos: [] }] });
    expect(servico.categorias().length).toBe(1);

    servico.carregar();
    http.expectOne((r) => r.url.endsWith('/atalhos')).flush('erro', { status: 500, statusText: 'Erro' });
    expect(servico.categorias()).toEqual([]);
  });

  it('recarrega a barra depois de gravar um atalho', () => {
    servico.excluirAtalho(3).subscribe();
    http.expectOne((r) => r.url.endsWith('/atalhos/itens/3')).flush(null);
    http.expectOne((r) => r.url.endsWith('/atalhos')).flush({ categorias: [] });
  });
});
