// Criado por José Eduardo Santana Martins
// Este arquivo serve para definir os tipos do plano de face da rede (equipamentos, portas, VLANs, conexões e pontos).

export type TipoEquipamento = 'switch' | 'patch_panel' | 'roteador' | 'access_point' | 'outro';
/** Função na topologia (camadas): o núcleo em alta disponibilidade (primário e secundário), a distribuição e o acesso. */
export type FuncaoEquipamento = 'core_primario' | 'core_secundario' | 'distribuicao' | 'acesso';
export type SituacaoPing = 'no_ar' | 'fora';
export type StatusPorta = 'up' | 'down' | 'desativada';

export const ROTULOS_TIPO_EQUIPAMENTO: Record<TipoEquipamento, string> = {
  switch: 'Switch', patch_panel: 'Patch panel', roteador: 'Roteador', access_point: 'Access point', outro: 'Outro',
};
export const ROTULOS_FUNCAO_EQUIPAMENTO: Record<FuncaoEquipamento, string> = {
  core_primario: 'Core primário', core_secundario: 'Core secundário', distribuicao: 'Distribuição', acesso: 'Acesso',
};
export const ROTULOS_PING: Record<SituacaoPing, string> = { no_ar: 'No ar', fora: 'Fora do ar' };
/** Patch panel é passivo: o único tipo sem IP de gerência e sem função (as duas coisas são obrigatórias nos outros). */
export function ehPassivo(tipo: TipoEquipamento): boolean {
  return tipo === 'patch_panel';
}
export const ROTULOS_STATUS_PORTA: Record<StatusPorta, string> = { up: 'Ligada', down: 'Desligada', desativada: 'Desativada' };
/** Cor do selo do status da porta (tokens de status do DESIGN.md). */
export const COR_STATUS_PORTA: Record<StatusPorta, string> = { up: 'sucesso', down: 'perigo', desativada: 'neutro' };

export interface PortaExtra { numero: number; rotulo: string; tipo: 'cobre' | 'fibra' }
export interface GravacaoModelo { nome: string; fabricante: string; linhas: number; colunas: number; numeracao: 'coluna' | 'linha'; portas_extras: PortaExtra[]; altura_u: number }
export interface ModeloFace extends GravacaoModelo { id: string; equipamentos: number }

export interface GravacaoEquipamento {
  nome: string; tipo: TipoEquipamento; modelo_face_id: string | null; bem_id: string | null; localizacao_id: string | null; rack_id: string | null;
  posicao_u: number | null; ip_gerencia: string; numero_serie: string; observacao: string; ativo: boolean; funcao: FuncaoEquipamento | null;
}
export interface EquipamentoResumo extends GravacaoEquipamento {
  id: string; modelo_nome: string; altura_u: number; rack_nome: string; sala: string; portas_total: number; portas_up: number; portas_down: number; portas_desativadas: number;
  /** Ping do IP de gerência: `fora` só depois de 3 falhas seguidas; null = sem teste. */
  ping_situacao: SituacaoPing | null; ping_verificado_em: string | null; ping_mudou_em: string | null;
  /** Sem IP ou sem função (cadastro de antes da regra): a próxima edição exige os dois. */
  cadastro_incompleto: boolean;
}
export interface ParametrosRede { ping_intervalo_min: number }
/** Dispositivo atrás do primeiro na mesma porta (ex.: o PC ligado no telefone IP). */
export interface DispositivoAtras { id: string; ordem: number; texto: string; bem_id: string | null }
export interface Conexao {
  tipo: 'porta' | 'bem' | 'descricao'; texto: string; porta_id: string | null; equipamento_id: string | null; bem_id: string | null;
  /** Em cascata, na ordem: switch → primeiro (telefone IP) → estes (PC...). */
  atras?: DispositivoAtras[];
}
/** Modos de porta das marcas em uso (Cisco, Huawei, 3Com/H3C); as regras de cada um estão em `MODOS_PORTA`. */
export type ModoPorta = 'access' | 'trunk' | 'hybrid' | 'dot1q_tunnel' | 'dinamico_auto' | 'dinamico_desejavel' | 'roteada';
/**
 * Rótulo, onde existe e o que o modo aceita: `nativa` = rótulo do campo da VLAN principal (vazio = não tem), `tag` = VLANs com tag,
 * `semTag` = VLANs sem tag além da PVID, `voz` = VLAN de voz, `ip` = IP da interface.
 */
export const MODOS_PORTA: { valor: ModoPorta; rotulo: string; curto: string; nativa: string; tag: boolean; semTag: boolean; voz: boolean; ip: boolean; dica: string }[] = [
  { valor: 'access', rotulo: 'Access (uma VLAN)', curto: 'Access', nativa: 'VLAN', tag: false, semTag: false, voz: true, ip: false,
    dica: 'Uma VLAN sem tag (computador, impressora). Cisco, Huawei e 3Com/H3C.' },
  { valor: 'trunk', rotulo: 'Trunk (várias VLANs com tag)', curto: 'Trunk', nativa: 'VLAN nativa (sem tag)', tag: true, semTag: false, voz: false, ip: false,
    dica: 'Ligação entre switches: a nativa sem tag e as demais com tag. Cisco, Huawei e 3Com/H3C.' },
  { valor: 'hybrid', rotulo: 'Hybrid (VLANs com e sem tag)', curto: 'Hybrid', nativa: 'PVID (VLAN padrão)', tag: true, semTag: true, voz: true, ip: false,
    dica: 'Várias VLANs sem tag e com tag na mesma porta. Huawei e 3Com/H3C.' },
  { valor: 'dot1q_tunnel', rotulo: 'QinQ (dot1q-tunnel)', curto: 'QinQ', nativa: 'VLAN externa', tag: false, semTag: false, voz: false, ip: false,
    dica: 'Põe uma VLAN externa por fora das VLANs do cliente. Cisco e Huawei.' },
  { valor: 'dinamico_auto', rotulo: 'Dinâmico auto (DTP)', curto: 'Dinâmico auto', nativa: 'VLAN (quando access)', tag: true, semTag: false, voz: true, ip: false,
    dica: 'Vira trunk só se o outro lado pedir. Cisco.' },
  { valor: 'dinamico_desejavel', rotulo: 'Dinâmico desirable (DTP)', curto: 'Dinâmico desirable', nativa: 'VLAN (quando access)', tag: true, semTag: false, voz: true,
    ip: false, dica: 'Pede trunk ao outro lado. Cisco.' },
  { valor: 'roteada', rotulo: 'Roteada (L3, sem VLAN)', curto: 'Roteada', nativa: '', tag: false, semTag: false, voz: false, ip: true,
    dica: 'Porta de camada 3 com IP próprio: "no switchport" na Cisco, "undo portswitch" na Huawei.' },
];

export function modoPorta(valor: ModoPorta): (typeof MODOS_PORTA)[number] {
  return MODOS_PORTA.find((m) => m.valor === valor) ?? MODOS_PORTA[0];
}

/** Resumo das VLANs da porta (lista de portas e dica da face). Ex.: "Hybrid: PVID 10 · sem tag 30 · com tag 20 · voz 20". */
export function textoVlanPorta(p: Porta): string {
  const m = modoPorta(p.modo);
  if (p.modo === 'roteada') return `Roteada${p.ip_interface ? ': ' + p.ip_interface : ''}`;
  const partes: string[] = [];
  if (p.vlan_nativa) partes.push(p.modo === 'access' ? String(p.vlan_nativa) : `${m.nativa.split(' (')[0]} ${p.vlan_nativa}`);
  if (p.vlans_sem_tag?.length) partes.push(`sem tag ${p.vlans_sem_tag.join(', ')}`);
  if (p.vlans_tag.length) partes.push(`com tag ${p.vlans_tag.join(', ')}`);
  if (p.vlan_voz) partes.push(`voz ${p.vlan_voz}`);
  if (p.modo === 'access') return partes.join(' · ') || '—';
  return m.curto + (partes.length ? ': ' + partes.join(' · ') : '');
}

export interface Porta {
  id: string; numero_logico: number; nome: string; descricao: string; mac: string; velocidade_mbps: number | null; duplex: 'full' | 'half' | null;
  status: StatusPorta | null; modo: ModoPorta; vlan_nativa_id: string | null; vlan_nativa: number | null; vlans_tag: number[]; vlans_tag_ids: string[];
  vlans_sem_tag: number[]; vlans_sem_tag_ids: string[]; vlan_voz_id: string | null; vlan_voz: number | null; ip_interface: string;
  ultima_mudanca: string | null; erros_entrada: number; erros_saida: number; conexao: Conexao | null; ponto: string; chamados_abertos: number;
}
export interface EquipamentoDetalhe extends EquipamentoResumo { modelo: ModeloFace | null; posicoes: Record<string, [number, number]>; portas: Porta[] }
export interface PortaDetalhe extends Porta {
  equipamento_id: string; equipamento_nome: string; chamados: { numero: number; titulo: string; status_base: string; aberto_em: string }[];
}
export interface GravacaoPorta {
  descricao: string; modo: ModoPorta; vlan_nativa_id: string | null; vlans_tag: string[]; vlans_sem_tag: string[]; vlan_voz_id: string | null;
  ip_interface: string; velocidade_mbps: number | null;
  duplex: 'full' | 'half' | null; status: StatusPorta | null;
}
export interface Vlan { id: string; numero: number; nome: string; descricao: string; portas: number }
export interface PontoRede { id: string; codigo: string; localizacao_id: string | null; porta_id: string | null; observacao: string; sala: string; caminho: string[] }
export type GravacaoPonto = Omit<PontoRede, 'id' | 'sala' | 'caminho'>;

/** Velocidade legível: 100 Mb/s, 1 Gb/s, 10 Gb/s. */
export function velocidade(mbps: number | null): string {
  if (!mbps) return '—';
  return mbps >= 1000 ? `${(mbps / 1000).toLocaleString('pt-BR')} Gb/s` : `${mbps} Mb/s`;
}

export type CorRack = 'preto' | 'cinza' | 'azul' | 'verde' | 'amarelo' | 'laranja' | 'vermelho';
export const CORES_RACK: [CorRack, string][] = [['preto', 'Preto'], ['cinza', 'Cinza'], ['azul', 'Azul'], ['verde', 'Verde'], ['amarelo', 'Amarelo'], ['laranja', 'Laranja'], ['vermelho', 'Vermelho']];
export interface GravacaoRack { nome: string; cor: CorRack; localizacao_id: string | null; altura_u: number; observacao: string }
export interface Rack extends GravacaoRack { id: string; sala: string; equipamentos: number }
export interface SalaResumo { id: string; codigo: string; nome: string; rotulo: string; andar: number | null }
export interface BemResumo { id: string; chapa: string; descricao: string; sala: string }
export interface PortaDoBem { porta_id: string; porta_nome: string; equipamento_id: string; equipamento_nome: string; /** Vazio = direto na porta. */ atras_de?: string; /** Atrás de outro: tirar só este. */ dispositivo_id?: string | null }

/** Um equipamento na árvore da topologia (filhos = os que se ligam a ele por cabo). */
export interface NoTopologia {
  id: string; nome: string; tipo: TipoEquipamento; rack_nome: string; rack_cor: CorRack | null; sala: string; ip_gerencia: string;
  funcao: FuncaoEquipamento | null; ping_situacao: SituacaoPing | null;
  /** Core secundário na frente porque o primário está fora do ar. */
  assumiu: boolean;
  portas_total: number; portas_up: number; portas_down: number; pontos: number; bens: number;
  porta_acima: string; porta_no_pai: string; cabos_com_pai: number; tambem_ligado: string[]; filhos: NoTopologia[];
}
export interface TopologiaRede { raizes: NoTopologia[]; sem_ligacao: NoTopologia[] }
/** Caminho da porta até o core (`GET /rede/portas/{id}/caminho`): do topo para baixo. */
export interface EtapaCaminho {
  tipo: 'equipamento' | 'ponto'; nome: string; cabo: string; equipamento_id: string | null; tipo_equipamento: TipoEquipamento | null;
  funcao: FuncaoEquipamento | null; ping_situacao: SituacaoPing | null;
  /** Portas dos quadradinhos: a que sobe (canto de cima) e a que desce (canto de baixo), com a configuração completa para a dica. */
  porta_entrada: Porta | null; porta_saida: Porta | null;
}
export interface CaminhoRede { etapas: EtapaCaminho[]; dispositivos: { texto: string; bem_id: string | null }[]; cabo_dispositivos: string; aviso: string }
