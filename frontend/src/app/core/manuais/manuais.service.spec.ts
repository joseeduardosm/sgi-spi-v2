// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar as chamadas do serviço dos Manuais.

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ManuaisService } from './manuais.service';

describe('ManuaisService', () => {
  let servico: ManuaisService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    servico = TestBed.inject(ManuaisService);
    http = TestBed.inject(HttpTestingController);
  });

  it('busca com o termo na query e baixa a imagem como blob', () => {
    servico.buscar('férias').subscribe();
    const busca = http.expectOne((r) => r.url.endsWith('/manuais/busca'));
    expect(busca.request.params.get('q')).toBe('férias');
    busca.flush({ itens: [] });

    servico.imagem('/uploads/images/a.png').subscribe((blob) => expect(blob.size).toBe(3));
    const imagem = http.expectOne((r) => r.url.endsWith('/manuais/imagem'));
    expect(imagem.request.responseType).toBe('blob');
    expect(imagem.request.params.get('caminho')).toBe('/uploads/images/a.png');
    imagem.flush(new Blob(['abc']));
  });
});
