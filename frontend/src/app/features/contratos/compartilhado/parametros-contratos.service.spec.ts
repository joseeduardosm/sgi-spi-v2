// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o serviço dos parâmetros de Contratos (valores de fábrica, leitura única e atualização) e o uso nas vigências.

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { montarLinha } from '../painel/vigencias.component';
import { ParametrosContratos } from './contratos.models';
import { PARAMETROS_DE_FABRICA, ParametrosContratosService } from './parametros-contratos.service';

describe('ParametrosContratosService', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] }));

  it('começa com os valores de fábrica, lê da API uma única vez e passa a usar o valor novo', () => {
    const servico = TestBed.inject(ParametrosContratosService);
    const http = TestBed.inject(HttpTestingController);
    expect(servico.valores().dias_atraso).toBe(30);

    servico.carregar();
    servico.carregar(); // a segunda chamada não faz outra requisição
    const pedido = http.expectOne((r) => r.url.endsWith('/contratos/parametros'));
    const lido: ParametrosContratos = { ...PARAMETROS_DE_FABRICA, dias_atraso: 45, atualizado_por_nome: 'root', atualizado_em: null, padroes: PARAMETROS_DE_FABRICA };
    pedido.flush(lido);
    expect(servico.valores().dias_atraso).toBe(45);
    http.verify();
  });

  it('a linha do tempo de vigências usa os limites informados', () => {
    const contrato = { contrato_id: 'c', numero: '1/2026', data_inicio: '2026-01-01', data_fim: '2026-12-31', dias_restantes: 100, vigencias: [], reajustes: [] } as never;
    expect(montarLinha(contrato, '2026-09-22').urgencia).toBe('atencao'); // padrão: crítico até 90, atenção até 180
    expect(montarLinha(contrato, '2026-09-22', { critico: 120, atencao: 200 }).urgencia).toBe('critico');
  });
});
