// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados do Módulo Protocolo (numeração institucional).

export interface SequenciaProtocolo { id: string; exercicio: number; inicio: number; fim: number; /** Do início até este número (exclusive): "Reservado CGI". */ liberar_a_partir_de: number | null }
export interface TipoProtocolo {
  id: string; nome: string;
  /** Setor que pode consumir os números (null = todos); só ele, a administração e o Serviço de Apoio Administrativo veem o tipo. */
  setor_id: number | null; setor_nome: string | null;
  /** O usuário pode reservar números do tipo. */
  pode_consumir: boolean;
  sequencias: SequenciaProtocolo[];
}
export interface ListaTipos { pode_administrar: boolean; itens: TipoProtocolo[] }

export type EstadoNumero = 'livre' | 'reservado_cgi' | 'reservado' | 'utilizado' | 'anulado';
export type TipoEventoProtocolo = 'reservou' | 'lancou' | 'anexou' | 'concluiu' | 'liberou' | 'anulou' | 'sigilo' | 'vinculou' | 'ampliou';

export interface EventoProtocolo { tipo: TipoEventoProtocolo; autor_nome: string; texto: string; ocorrido_em: string }
export interface ArquivoProtocolo { id: string; nome: string; tamanho: number; pode_baixar: boolean }

export interface NumeroProtocolo {
  id: string;
  sequencia_id: string;
  tipo_id: string;
  tipo_nome: string;
  exercicio: number;
  numero: number;
  /** Ex.: `005/2026`. */
  numero_formatado: string;
  estado: EstadoNumero;
  finalidade: string;
  reservado_por_id: number | null;
  reservado_por_nome: string;
  reservado_em: string | null;
  usado_em: string | null;
  contrato_id: string | null;
  contrato_numero: string | null;
  sigiloso: boolean;
  anulado_em: string | null;
  motivo_anulacao: string | null;
  arquivo: ArquivoProtocolo | null;
  pode_anexar: boolean;
  pode_liberar: boolean;
  /** Reservado e sem documento: quem reservou ou a administração conclui sem subir o arquivo (documento sigiloso, por exemplo). */
  pode_concluir_sem_documento: boolean;
  pode_alterar_sigilo: boolean;
  /** Livre e o usuário pode escolher este número (administração; a CGI, nos "Reservado CGI"). */
  pode_reservar: boolean;
  /** Linha do tempo (só no detalhe). */
  eventos: EventoProtocolo[];
}

export interface ListaNumeros {
  sequencia: SequenciaProtocolo;
  tipo_id: string;
  tipo_nome: string;
  /** O usuário pode reservar números deste tipo (sem restrição de setor, é do setor ou administra). */
  pode_consumir: boolean;
  pode_administrar: boolean;
  usuario_id: number;
  livres: number;
  /** Números ainda "Reservado CGI". */
  reservados_cgi: number;
  /** O usuário é da Coordenadoria de Gestão e Infraestrutura (ou administra) e dá andamento na faixa reservada. */
  pode_usar_reserva_cgi: boolean;
  itens: NumeroProtocolo[];
}

export interface MesPainel { mes: number; reservados: number; utilizados: number }
export interface PessoaPainel { usuario_id: number | null; nome: string; quantidade: number }
export interface PendentePainel { id: string; numero_formatado: string; finalidade: string; reservado_por_nome: string; reservado_em: string }
export interface PainelProtocolo {
  tipo_id: string;
  tipo_nome: string;
  ano: number;
  meses: MesPainel[];
  mais_reservaram: PessoaPainel[];
  mais_utilizaram: PessoaPainel[];
  sem_documento: PendentePainel[];
}

export const ROTULOS_ESTADO: Record<EstadoNumero, string> = { livre: 'Livre', reservado_cgi: 'Reservado CGI', reservado: 'Reservado', utilizado: 'Utilizado', anulado: 'Anulado' };
export const ROTULOS_EVENTO: Record<TipoEventoProtocolo, string> = {
  reservou: 'Reservou', lancou: 'Lançou', anexou: 'Anexou o documento', concluiu: 'Concluiu sem documento', liberou: 'Liberou a reserva', anulou: 'Anulou',
  sigilo: 'Sigilo', vinculou: 'Vínculo com contrato', ampliou: 'Ampliou a faixa',
};
