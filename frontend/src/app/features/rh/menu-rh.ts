/**
 * =============================================================================
 * ARQUIVO: menu-rh.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Define, num só lugar, os grupos e as telas do Módulo RH, usados pelo
 * painel de entrada e pela sub-navegação do cabeçalho do RH.
 *
 * RESUMO TÉCNICO:
 * Exporta as interfaces TelaRh e GrupoRh, a constante GRUPOS_RH e duas
 * funções puras: gruposVisiveis (filtra telas pelos papéis e ajusta a
 * numeração) e grupoDaRota (descobre o grupo de uma URL, inclusive subpáginas
 * e com query string).
 *
 * FINALIDADE DE NEGÓCIO:
 * Organiza o RH pela forma como o trabalho é feito (estrutura, entrada de
 * pessoas, vida funcional, configuração) e esconde de cada pessoa as telas que
 * o papel dela não usa. A visibilidade aqui é só de menu: a API continua
 * validando cada acesso.
 *
 * CONTEXTO NO SISTEMA:
 * Consumido por inicio-rh.component.ts e pelo app-cabecalho-rh; testado em
 * menu-rh.spec.ts. Os papéis (PapeisRh) vêm de RhApiService.papeis e as rotas
 * correspondem a rh.routes.ts.
 *
 * =============================================================================
 */

import { PapeisRh } from './rh.models';

/** Uma tela do RH e quem a vê. */
export interface TelaRh {
  rota: string;
  rotulo: string;
  descricao: string;
  /** Quem vê a tela no menu (a API continua validando o acesso). */
  visivel: (p: PapeisRh) => boolean;
}

/** Grupo de telas. Numerado = sequência real de trabalho (1, 2, 3…); sem número = telas independentes. */
export interface GrupoRh {
  id: string;
  titulo: string;
  descricao: string;
  numerado: boolean;
  telas: TelaRh[];
}

// Regras de visibilidade reaproveitadas nas telas:
// todos = qualquer usuário; temAcessoAoModulo = tem algum nível no recurso "rh" da ACL
// (controle de acesso por módulo); ehRh = é da CGP (Coordenação de Gestão de Pessoas).
const todos = (): boolean => true;
const temAcessoAoModulo = (p: PapeisRh): boolean => !!p.nivel_rh;
const ehRh = (p: PapeisRh): boolean => p.cgp;

/** Catálogo dos grupos e telas do RH, na ordem em que aparecem no painel de entrada. */
export const GRUPOS_RH: GrupoRh[] = [
  {
    id: 'estrutura', titulo: 'Estrutura', numerado: true,
    descricao: 'Monte a organização da SPI: primeiro os setores, depois os cargos (vagas) de cada um e, por fim, veja o resultado no organograma.',
    telas: [
      { rota: '/rh/setores', rotulo: 'Setores', descricao: 'Unidades, siglas, hierarquia e quem as integra.', visivel: temAcessoAoModulo },
      { rota: '/rh/cargos', rotulo: 'Cargos', descricao: 'Vagas de cada setor, ocupantes e exonerações.', visivel: temAcessoAoModulo },
      { rota: '/rh/organograma', rotulo: 'Organograma', descricao: 'A estrutura com quem ocupa cada cargo.', visivel: todos },
    ],
  },
  {
    id: 'entrada', titulo: 'Entrada de pessoas', numerado: true,
    descricao: 'Da ficha da pessoa até a posse: cadastre a ficha e acompanhe a admissão passo a passo.',
    telas: [
      { rota: '/rh/pre-cadastros', rotulo: 'Pré-cadastro', descricao: 'Ficha de quem vai entrar, por formulário ou planilha.', visivel: ehRh },
      { rota: '/rh/admissoes', rotulo: 'Admissões', descricao: 'GLPI, documentos, resolução, publicação e posse.', visivel: ehRh },
    ],
  },
  {
    id: 'vida', titulo: 'Vida funcional', numerado: false,
    descricao: 'O dia a dia de quem já trabalha na SPI.',
    telas: [
      { rota: '/rh/ferias', rotulo: 'Férias e LP', descricao: 'Agende e acompanhe férias e licença-prêmio.', visivel: todos },
      { rota: '/rh/painel-afastamentos', rotulo: 'Painel', descricao: 'Pedidos de afastamento para decidir.', visivel: (p) => temAcessoAoModulo(p) || p.cgp || p.autorizador },
      { rota: '/rh/validacoes', rotulo: 'Validações', descricao: 'Alterações de cadastro que o RH confere.', visivel: ehRh },
      { rota: '/rh/meu-cadastro', rotulo: 'Meu cadastro', descricao: 'Seus dados funcionais e a sua bio.', visivel: todos },
    ],
  },
  {
    id: 'configuracao', titulo: 'Configuração', numerado: false,
    descricao: 'Regras e textos que o RH mantém.',
    telas: [
      { rota: '/rh/feriados', rotulo: 'Feriados', descricao: 'Feriados e pontos facultativos (valem para os prazos).', visivel: todos },
      { rota: '/rh/modelos', rotulo: 'Modelos', descricao: 'Textos e documentos das admissões e checklists.', visivel: ehRh },
      { rota: '/rh/parametros', rotulo: 'Parâmetros', descricao: 'Regras de férias, licença-prêmio e setores de apoio.', visivel: ehRh },
    ],
  },
];

/** Telas do grupo que a pessoa vê (grupo sem nenhuma tela visível some). Quem vê só uma tela de uma sequência não a vê numerada: "1" sozinho enganaria. */
export function gruposVisiveis(papeis: PapeisRh): GrupoRh[] {
  return GRUPOS_RH.map((g) => {
    const telas = g.telas.filter((t) => t.visivel(papeis));
    return { ...g, telas, numerado: g.numerado && telas.length > 1 };
  }).filter((g) => g.telas.length);
}

/** Grupo ao qual a URL pertence (a tela ou uma subpágina dela, ex.: `/rh/admissoes/12`); undefined fora dos grupos. */
export function grupoDaRota(url: string): GrupoRh | undefined {
  // Descarta a consulta (?...) e a âncora (#...) para comparar só o caminho
  const caminho = url.split('?')[0].split('#')[0];
  return GRUPOS_RH.find((g) => g.telas.some((t) => caminho === t.rota || caminho.startsWith(t.rota + '/')));
}
