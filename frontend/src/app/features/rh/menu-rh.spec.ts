// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar os grupos do Módulo RH: quem vê cada tela, a numeração das sequências e o grupo de cada URL.

import { grupoDaRota, gruposVisiveis } from './menu-rh';
import { PapeisRh } from './rh.models';

const comum: PapeisRh = { cgp: false, autorizador: false, nivel_rh: null };
const rotas = (p: PapeisRh): string[] => gruposVisiveis(p).flatMap((g) => g.telas.map((t) => t.rota));

describe('menu do RH', () => {
  it('quem não tem acesso ao módulo vê só o que é de todos', () => {
    expect(rotas(comum)).toEqual(['/rh/organograma', '/rh/ferias', '/rh/meu-cadastro', '/rh/feriados']);
    expect(gruposVisiveis(comum).map((g) => g.id)).toEqual(['estrutura', 'vida', 'configuracao']);
  });

  it('quem gere setores e cargos vê Setores e Cargos, mas não a entrada de pessoas', () => {
    const r = rotas({ ...comum, nivel_rh: 'MODIFICACAO' });
    expect(r).toContain('/rh/setores');
    expect(r).toContain('/rh/cargos');
    expect(r).not.toContain('/rh/admissoes');
  });

  it('o RH vê tudo; o painel aparece a quem está no recurso ACL rh e aos autorizadores (aprovam por ele)', () => {
    expect(rotas({ cgp: true, autorizador: false, nivel_rh: 'CONTROLE_TOTAL' })).toHaveLength(12);
    expect(rotas(comum)).not.toContain('/rh/painel-afastamentos');
    expect(rotas({ ...comum, autorizador: true })).toContain('/rh/painel-afastamentos');
    expect(rotas({ ...comum, nivel_rh: 'LEITURA' })).toContain('/rh/painel-afastamentos');
  });

  it('só as sequências reais são numeradas', () => {
    const numerados = gruposVisiveis({ cgp: true, autorizador: true, nivel_rh: 'CONTROLE_TOTAL' }).filter((g) => g.numerado).map((g) => g.id);
    expect(numerados).toEqual(['estrutura', 'entrada']);
  });

  it('quem vê só uma tela da sequência não a vê numerada', () => {
    expect(gruposVisiveis(comum).find((g) => g.id === 'estrutura')?.numerado).toBe(false);
    expect(gruposVisiveis({ ...comum, nivel_rh: 'LEITURA' }).find((g) => g.id === 'estrutura')?.numerado).toBe(true);
  });

  it('reconhece o grupo pela URL, inclusive subpáginas e consulta', () => {
    expect(grupoDaRota('/rh/cargos')?.id).toBe('estrutura');
    expect(grupoDaRota('/rh/admissoes/12?etapa=2')?.id).toBe('entrada');
    expect(grupoDaRota('/rh/pre-cadastros/nova')?.id).toBe('entrada');
    expect(grupoDaRota('/rh/historico/5')).toBeUndefined();
    expect(grupoDaRota('/rh')).toBeUndefined();
  });
});
