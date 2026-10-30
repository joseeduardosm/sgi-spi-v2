// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos de dados da admissão, dos modelos, dos checklists, das boas-vindas e da bio do RH.

export type ChaveEtapa = 'chamado' | 'documentos' | 'resolucao' | 'protocolo' | 'publicacao' | 'posse' | 'concluida';

export interface EtapaAdmissao { chave: ChaveEtapa; rotulo: string; estado: 'feita' | 'atual' | 'pendente'; em: string | null }

export interface DocumentoAdmissao {
  id: number; descricao: string; obrigatorio: boolean; enviado_em: string | null; enviado_por_nome: string; registrado_em: string | null; tem_comprovante: boolean; observacao: string;
  /** Incluído durante a admissão (fora do checklist do cargo): nunca obrigatório, com descrição e arquivo próprios. */
  incluido_no_processo?: boolean; detalhe?: string; tem_arquivo?: boolean; incluido_por_nome?: string; incluido_em?: string | null;
}

export interface ResumoAdmissao {
  id: number; ficha_id: number; nome: string; login_proposto: string | null; cargo_rotulo: string; setor_nome: string; status: 'andamento' | 'concluida' | 'cancelada';
  etapa: string; etapa_rotulo: string; atualizado_em: string;
}

export interface LeituraAdmissao extends ResumoAdmissao {
  etapas: EtapaAdmissao[]; solicitacoes: Record<string, boolean>; chamado_glpi_id: number | null; chamado_url: string | null; chamado_links: { url: string; texto: string }[]; tem_foto: boolean; documentos: DocumentoAdmissao[];
  resolucao_html: string | null; sem_numero: boolean; numero_protocolo_id: string | null; numero_protocolo: string | null; publicado_em: string | null; tem_publicacao: boolean;
  email_enviado_em: string | null; email_erro: string | null; email_destino: string | null; posse_em: string | null; termo_html: string | null; concluida_em: string | null;
  conta_vinculada: boolean; usuario_id: number | null;
}

export interface TipoProtocoloResolucao { id: string; nome: string; tem_faixa_no_ano: boolean }

export type TipoModelo = 'resolucao_nomeacao' | 'email_nomeacao_publicada' | 'termo_posse' | 'boas_vindas';
export interface ModeloRh { tipo: TipoModelo; nome: string; assunto: string; html: string; atualizado_em: string }

export interface ItemChecklist { descricao: string; obrigatorio: boolean }
/** Classificação do cargo: grupo 1 ou 2 e nível (ex.: grupo 1, nível 15 = "1.15"). */
export interface ClassificacaoChecklist { grupo: 1 | 2; nivel: number }
export interface Checklist { id: number; nome: string; ativo: boolean; classificacoes: ClassificacaoChecklist[]; aplica_a_outros: boolean; itens: ItemChecklist[] }
export type GravacaoChecklist = Omit<Checklist, 'id'>;

/** "1.15": grupo e nível com dois dígitos, como no quadro da SPI. */
export function rotuloClassificacao(c: ClassificacaoChecklist): string {
  return `${c.grupo}.${String(c.nivel).padStart(2, '0')}`;
}

export interface BoasVindas { pendente: boolean; titulo: string; html: string; nome: string }
export interface Bio { bio_texto: string; bio_visivel: boolean }

/** Texto da resolução já preenchido, para colar no SEI: formatado e simples. */
export interface TextoParaCopiar { html: string; texto: string }
