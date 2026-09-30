// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a identificação do módulo pela rota em que a sugestão foi enviada.

import { moduloDaTela } from './melhorias.models';

describe('moduloDaTela', () => {
  it('usa o primeiro trecho da rota, como a API', () => {
    expect(moduloDaTela('/contratos/abc/execucao/2026-02?etapa=avaliacao')).toBe('contratos');
    expect(moduloDaTela('/admin/acl')).toBe('administracao');
    expect(moduloDaTela('/usuarios/12')).toBe('administracao');
    expect(moduloDaTela('/')).toBe('portal');
    expect(moduloDaTela('/qualquer-coisa')).toBe('geral');
  });
});
