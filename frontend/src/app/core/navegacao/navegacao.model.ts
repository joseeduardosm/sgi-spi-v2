import { Papel } from '../modelos/usuario.model';
import { NomeIcone } from '../../shared/componentes/icone/icone.component';

/**
 * Item da barra lateral. Um item tem `rota` (rota interna), `href` (link externo)
 * ou `filhos` (grupo com submenu). Itens sem os papéis exigidos não são exibidos;
 * a API continua responsável por validar as permissões.
 */
export interface ItemNavegacao {
  id: string;
  rotulo: string;
  icone?: NomeIcone;
  rota?: string;
  /** Ativo somente quando a URL é exatamente `rota` (use para a rota '/'). */
  exata?: boolean;
  href?: string;
  novaAba?: boolean;
  papeis?: Papel[];
  /** Slug do recurso de ACL: o item só aparece se o usuário tiver ao menos LEITURA. */
  acl?: string;
  filhos?: ItemNavegacao[];
  /** Texto exibido quando o grupo não possui filhos visíveis. */
  textoVazio?: string;
}

export interface SecaoNavegacao {
  legenda: string;
  papeis?: Papel[];
  itens: ItemNavegacao[];
}
