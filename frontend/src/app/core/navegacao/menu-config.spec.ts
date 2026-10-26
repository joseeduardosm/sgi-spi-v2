// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar como a configuração do menu (ordem, grupos, links e ocultos) é aplicada ao menu do código.

import { aplicarConfiguracao, NoMenu } from './menu-config';
import { ItemNavegacao } from './navegacao.model';
import { telasDoMenu } from './telas-menu';

describe('aplicarConfiguracao', () => {
  // Menu do código: Início, grupo Módulos (Contratos, RH, Ramais) e Usuários
  const codigo = (): ItemNavegacao[] => [
    { id: 'inicio', rotulo: 'Início', rota: '/' },
    { id: 'modulos', rotulo: 'Módulos', filhos: [
      { id: 'contratos', rotulo: 'Contratos', rota: '/contratos', destino: '/contratos/painel' },
      { id: 'rh', rotulo: 'RH', rota: '/rh' },
      { id: 'ramais', rotulo: 'Ramais', rota: '/ramais' },
    ] },
    { id: 'usuarios', rotulo: 'Usuários', rota: '/usuarios' },
  ];
  const ids = (itens: ItemNavegacao[]): string[] => itens.flatMap((i) => [i.id, ...(i.filhos ?? []).map((f) => `${i.id}>${f.id}`)]);

  it('sem configuração devolve o menu do código', () => {
    expect(ids(aplicarConfiguracao(codigo(), []))).toEqual(['inicio', 'modulos', 'modulos>contratos', 'modulos>rh', 'modulos>ramais', 'usuarios']);
  });

  it('reordena, renomeia e oculta; o que a configuração não cita entra no fim, no lugar padrão', () => {
    const nos: NoMenu[] = [{ id: 'usuarios', tipo: 'modulo' }, { id: 'inicio', tipo: 'modulo', rotulo: 'Página inicial' }, { id: 'rh', tipo: 'modulo', oculto: true }];
    const menu = aplicarConfiguracao(codigo(), nos);
    expect(ids(menu)).toEqual(['usuarios', 'inicio', 'modulos', 'modulos>contratos', 'modulos>ramais']);
    expect(menu[1].rotulo).toBe('Página inicial');
  });

  it('cria grupo e link, leva módulo para o grupo e esconde grupo vazio', () => {
    const nos: NoMenu[] = [
      { id: 'g-1', tipo: 'grupo', rotulo: 'Gestão de pessoas' },
      { id: 'rh', tipo: 'modulo', pai_id: 'g-1' },
      { id: 'l-1', tipo: 'link', rotulo: 'Portal', url: 'https://portal.exemplo.gov.br', pai_id: 'g-1' },
      { id: 'g-vazio', tipo: 'grupo', rotulo: 'Vazio' },
    ];
    const menu = aplicarConfiguracao(codigo(), nos);
    expect(ids(menu)).toEqual(['g-1', 'g-1>rh', 'g-1>l-1', 'inicio', 'modulos', 'modulos>contratos', 'modulos>ramais', 'usuarios']);
    const link = menu[0].filhos![1];
    expect(link.href).toBe('https://portal.exemplo.gov.br');
    expect(link.novaAba).toBe(true);
  });

  it('link interno guarda a consulta em destino e usa a rota sem ela', () => {
    const [grupo] = aplicarConfiguracao(codigo(), [{ id: 'l-2', tipo: 'link', rotulo: 'Ramais da SPI', url: '/ramais?q=spi' }]);
    expect(grupo.rota).toBe('/ramais');
    expect(grupo.destino).toBe('/ramais?q=spi');
  });

  it('ignora ids que não existem e grupo inexistente manda o item para o primeiro nível', () => {
    const menu = aplicarConfiguracao(codigo(), [{ id: 'fantasma', tipo: 'modulo' }, { id: 'rh', tipo: 'modulo', pai_id: 'nao-existe' }]);
    expect(ids(menu)).toEqual(['rh', 'inicio', 'modulos', 'modulos>contratos', 'modulos>ramais', 'usuarios']);
  });

  it('ocultar um grupo oculta o que está dentro, e o oculto some da busca global', () => {
    const menu = aplicarConfiguracao(codigo(), [{ id: 'modulos', tipo: 'modulo', oculto: true }]);
    expect(ids(menu)).toEqual(['inicio', 'usuarios']);
    expect(telasDoMenu([{ legenda: 'Navegação', itens: menu }]).map((t) => t.id)).toEqual(['inicio', 'usuarios']);
  });

  it('no editor (mostrarOcultos) os ocultos ficam marcados e o item do grupo oculto também', () => {
    const menu = aplicarConfiguracao(codigo(), [{ id: 'modulos', tipo: 'modulo', oculto: true }], true);
    expect(menu[0].oculto).toBe(true);
    expect(menu[0].filhos!.every((f) => f.oculto)).toBe(true);
  });

  it('grupo dentro de grupo não passa de dois níveis', () => {
    const menu = aplicarConfiguracao(codigo(), [{ id: 'g-1', tipo: 'grupo', rotulo: 'A' }, { id: 'g-2', tipo: 'grupo', rotulo: 'B', pai_id: 'g-1' }, { id: 'rh', tipo: 'modulo', pai_id: 'g-2' }]);
    expect(ids(menu).filter((i) => i.startsWith('g-2'))).toEqual([]);
    expect(ids(menu)).toContain('rh');
  });
});
