// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir as configurações do ambiente de desenvolvimento (`ng serve`).

/** Configurações de desenvolvimento; substitui `ambiente.ts` quando o projeto roda com `ng serve`. */
export const ambiente = {
  producao: false,
  // No `ng serve`, o proxy.conf.json repassa /api para o backend em 127.0.0.1:8000
  urlApi: '/api',
};
