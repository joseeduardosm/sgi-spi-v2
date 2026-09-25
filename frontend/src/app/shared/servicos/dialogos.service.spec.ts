// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o serviço de diálogos (confirmação, erro e janela de processamento).

import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Subject } from 'rxjs';

import { DialogosService } from './dialogos.service';

describe('DialogosService', () => {
  let dialogos: DialogosService;

  beforeEach(() => {
    // Relógio falso: permite avançar o tempo da contagem regressiva sem esperar de verdade
    vi.useFakeTimers();
    dialogos = TestBed.inject(DialogosService);
  });

  afterEach(() => vi.useRealTimers());

  it('só permite confirmar depois da contagem regressiva', async () => {
    const resposta = dialogos.confirmar({ titulo: 'Excluir', mensagem: 'Sem volta.', segundos: 3 });
    expect(dialogos.segundosRestantes()).toBe(3);

    dialogos.responderConfirmacao(true);
    expect(dialogos.confirmacao()).not.toBeNull();

    vi.advanceTimersByTime(3000);
    expect(dialogos.segundosRestantes()).toBe(0);
    dialogos.responderConfirmacao(true);

    await expect(resposta).resolves.toBe(true);
    expect(dialogos.confirmacao()).toBeNull();
  });

  it('cancelar responde falso imediatamente', async () => {
    const resposta = dialogos.confirmar({ titulo: 'Gerar', mensagem: 'Confirma?', segundos: 5 });
    dialogos.responderConfirmacao(false);
    await expect(resposta).resolves.toBe(false);
  });

  it('abrir outra confirmação cancela a anterior', async () => {
    const primeira = dialogos.confirmar({ titulo: 'A', mensagem: 'a' });
    void dialogos.confirmar({ titulo: 'B', mensagem: 'b' });
    await expect(primeira).resolves.toBe(false);
    expect(dialogos.confirmacao()?.titulo).toBe('B');
  });

  it('mostra o erro da API com o código de correlação do cabeçalho', () => {
    dialogos.mostrarErro(
      new HttpErrorResponse({
        status: 409,
        error: { detalhe: 'Número já cadastrado.', codigo: 'conflito' },
        headers: new HttpHeaders({ 'X-Correlacao': 'abc123def456' }),
      }),
    );
    expect(dialogos.erro()).toMatchObject({ mensagem: 'Número já cadastrado.', codigo: 'conflito', correlacao: 'abc123def456' });
  });

  it('mantém a janela de processamento enquanto a operação não termina', () => {
    // Subject: fluxo controlado pelo teste, que decide quando a "operação" emite e termina
    const operacao = new Subject<number>();
    const recebidos: number[] = [];
    dialogos.executar(operacao, 'Gerando PDF…').subscribe((v) => recebidos.push(v));
    expect(dialogos.processando()).toEqual(['Gerando PDF…']);

    operacao.next(1);
    operacao.complete();
    expect(recebidos).toEqual([1]);
    expect(dialogos.processando()).toEqual([]);
  });

  it('remove a janela de processamento também em caso de erro', () => {
    const operacao = new Subject<number>();
    dialogos.executar(operacao).subscribe({ error: () => undefined });
    operacao.error(new Error('falhou'));
    expect(dialogos.processando()).toEqual([]);
  });
});
