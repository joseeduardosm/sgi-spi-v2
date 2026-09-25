// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as configurações do ambiente de produção (build final servido pelo Nginx).

/**
 * Configurações por ambiente. No build de desenvolvimento, o Angular troca este arquivo por
 * `ambiente.desenvolvimento.ts` (ver `fileReplacements` no angular.json).
 */
export const ambiente = {
  producao: true,
  // Caminho da API: relativo, pois o Nginx entrega o frontend e repassa /api para o backend no mesmo endereço
  urlApi: '/api',
};
