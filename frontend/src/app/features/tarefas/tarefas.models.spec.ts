// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os utilitários do Módulo Tarefas (textos, avatares, prazo, raias, calendário e Gantt).

import {
  acaoEntre, agruparRaias, barraGantt, corAvatar, duracao, iniciais, porDiaDoPrazo, prazoPadrao, prazoRelativo, semanasDoMes, situacaoPrazo,
  tamanhoLegivel, TarefaResumo,
} from './tarefas.models';

describe('utilitários de tarefas', () => {
  it('descreve o prazo relativo', () => {
    const dia = 86_400_000;
    expect(prazoRelativo(new Date(Date.now() - 3 * dia - 1000).toISOString())).toBe('Atrasada há 3 dias');
    expect(prazoRelativo(new Date(Date.now() + 5 * dia - 1000).toISOString())).toBe('Vence em 5 dias');
    expect(prazoRelativo(new Date(Date.now() - dia).toISOString(), true)).toBe('');
  });

  it('formata duração e tamanho', () => {
    expect(duracao(3 * 3600 + 20 * 60)).toBe('3 h 20 min');
    expect(duracao(2 * 86400 + 4 * 3600)).toBe('2 d 4 h');
    expect(tamanhoLegivel(25)).toBe('25 B');
    expect(tamanhoLegivel(1.2 * 1024 * 1024)).toBe('1,2 MB');
  });
});

describe('funções das visões do quadro', () => {
  const pessoa = (id: number, nome: string) => ({ id, nome, login: nome.toLowerCase() });
  const tarefa = (numero: number, responsavel: ReturnType<typeof pessoa> | null, prazo = '2026-10-05T15:00:00') =>
    ({ numero, responsavel, prazo, status: 'a_fazer' }) as unknown as TarefaResumo;

  it('gera iniciais e cor fixa do avatar', () => {
    expect(iniciais('Ana Maria Souza')).toBe('AS');
    expect(iniciais('  lia ')).toBe('L');
    expect(iniciais('')).toBe('?');
    expect(corAvatar(7)).toBe(corAvatar(7));
    expect(corAvatar(1)).not.toBe(corAvatar(2));
  });

  it('classifica o chip de prazo', () => {
    const agora = new Date(2026, 8, 30, 10, 0);
    expect(situacaoPrazo({ status: 'a_fazer', prazo: new Date(2026, 8, 29, 18).toISOString() }, agora)).toBe('atrasada');
    expect(situacaoPrazo({ status: 'a_fazer', prazo: new Date(2026, 9, 1, 23).toISOString() }, agora)).toBe('proxima');
    expect(situacaoPrazo({ status: 'a_fazer', prazo: new Date(2026, 9, 3).toISOString() }, agora)).toBe('normal');
    expect(situacaoPrazo({ status: 'concluida', prazo: new Date(2026, 8, 1).toISOString() }, agora)).toBe('concluida');
  });

  it('calcula o prazo padrão da criação rápida (7 dias, 18:00)', () => {
    const d = prazoPadrao(new Date(2026, 8, 30, 9, 15));
    expect([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes()]).toEqual([2026, 9, 7, 18, 0]);
  });

  it('agrupa as raias por responsável, com "sem responsável" no fim', () => {
    const raias = agruparRaias([tarefa(1, pessoa(2, 'Beto')), tarefa(2, null), tarefa(3, pessoa(1, 'Ana')), tarefa(4, pessoa(2, 'Beto'))]);
    expect(raias.map((r) => [r.pessoa?.nome ?? '—', r.itens.map((t) => t.numero)])).toEqual([['Ana', [3]], ['Beto', [1, 4]], ['—', [2]]]);
  });

  it('monta as semanas do mês e distribui as tarefas pelo dia do prazo', () => {
    const semanas = semanasDoMes(2026, 8); // setembro de 2026 começa numa terça
    expect(semanas[0][0].getDate()).toBe(30);
    expect(semanas[0][2].getDate()).toBe(1);
    expect(semanas.every((s) => s.length === 7)).toBe(true);
    expect(semanas.at(-1)!.some((d) => d.getMonth() === 8 && d.getDate() === 30)).toBe(true);
    const mapa = porDiaDoPrazo([tarefa(1, null, '2026-10-05T15:00:00'), tarefa(2, null, '2026-10-05T09:00:00'), tarefa(3, null, '2026-10-06T09:00:00')]);
    expect(mapa.get('2026-10-05')!.map((t) => t.numero)).toEqual([2, 1]);
    expect(mapa.get('2026-10-06')!.length).toBe(1);
  });

  it('posiciona as barras do Gantt na janela', () => {
    const inicio = new Date(2026, 8, 1);
    const dia = (d: number) => new Date(2026, 8, d).toISOString();
    const dentro = barraGantt({ inicio: dia(3), prazo: dia(8), concluida_em: null }, inicio, 10)!;
    expect(dentro.esquerda).toBeCloseTo(20);
    expect(dentro.largura).toBeCloseTo(50);
    // Começou antes da janela (dia -5 = 26/08) e termina depois dela: ocupa a janela inteira
    const cortada = barraGantt({ inicio: dia(-5), prazo: dia(20), concluida_em: null }, inicio, 10)!;
    expect(cortada.cortadaInicio && cortada.cortadaFim).toBe(true);
    expect(cortada.esquerda).toBe(0);
    expect(cortada.esquerda + cortada.largura).toBeCloseTo(100);
    expect(barraGantt({ inicio: dia(15), prazo: dia(20), concluida_em: null }, inicio, 10)).toBeNull();
    // Concluída: a barra termina na conclusão
    expect(barraGantt({ inicio: dia(2), prazo: dia(9), concluida_em: dia(4) }, inicio, 10)!.largura).toBeCloseTo(20);
  });

  it('converte o movimento entre colunas na ação do pipeline', () => {
    expect(acaoEntre('a_fazer', 'em_andamento', false)).toBe('iniciar');
    expect(acaoEntre('em_andamento', 'concluida', true)).toBe('entregar');
    expect(acaoEntre('a_fazer', 'em_validacao', false)).toBeNull();
  });
});
