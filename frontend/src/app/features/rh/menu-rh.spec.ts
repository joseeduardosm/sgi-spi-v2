/**
 * =============================================================================
 * ARQUIVO: menu-rh.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testes unitários do menu do Módulo RH: quem vê cada tela, quais grupos
 * são numerados e a que grupo pertence cada URL.
 *
 * RESUMO TÉCNICO:
 * Usa Jasmine (describe/it/expect) sobre as funções puras gruposVisiveis e
 * grupoDaRota de menu-rh.ts, variando os papéis do usuário (cgp, autorizador
 * e nivel_rh da ACL). Não precisa de TestBed porque não há componente.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege a regra de visibilidade do RH: o servidor comum vê só o que é de
 * todos; quem tem acesso ao recurso "rh" da ACL (controle de acesso) vê
 * Setores e Cargos; só a CGP vê a entrada de pessoas; autorizadores veem o
 * painel de aprovação; e a numeração só aparece em sequências reais.
 *
 * CONTEXTO NO SISTEMA:
 * Cobre menu-rh.ts, usado pelo inicio-rh.component.ts e pela sub-navegação
 * do app-cabecalho-rh. Roda com "npx ng test".
 *
 * =============================================================================
 */

import { grupoDaRota, gruposVisiveis } from './menu-rh';
import { PapeisRh } from './rh.models';

/** Papéis de um servidor comum, sem acesso ao módulo nem papel de autorizador ou CGP. */
const comum: PapeisRh = { cgp: false, autorizador: false, nivel_rh: null };
/** Lista plana das rotas visíveis para os papéis, na ordem do menu. */
const rotas = (p: PapeisRh): string[] => gruposVisiveis(p).flatMap((g) => g.telas.map((t) => t.rota));

// describe agrupa os casos; cada it é um caso de teste com as suas expectativas (expect)
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
