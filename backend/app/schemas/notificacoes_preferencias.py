# Criado por José Eduardo Santana Martins
# Este arquivo serve para definir o formato dos dados das preferências de notificação (canais, navegador, silenciados e obrigatórias).
"""Schemas das preferências das Notificações (`/api/notificacoes/preferencias` e rotas vizinhas)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Canal = Literal["email", "navegador", "desktop"]
Frequencia = Literal["imediato", "diario", "semanal"]


class CanalDoEvento(BaseModel):
    disponivel: bool = Field(..., description="O evento pode sair por este canal (ex.: novidades do sistema só por e-mail).")
    ligado: bool = Field(..., description="Ligado pela pessoa ou obrigatório.")
    obrigatorio: bool = Field(..., description="Definido pela administração: aparece marcado e travado (\"definida pela administração\").")


class EventoPreferencia(BaseModel):
    chave: str = Field(..., description="Chave estável do evento (ex.: `contratos.medicao_concluida`).")
    rotulo: str
    descricao: str = Field(..., description="Quem recebe e quando.")
    canais: dict[Canal, CanalDoEvento]


class ModuloPreferencia(BaseModel):
    chave: str
    rotulo: str
    eventos: list[EventoPreferencia]


class ConfiguracaoNotificacoes(BaseModel):
    frequencia_email: Frequencia = "imediato"
    silencio_inicio: str | None = Field(None, description="Início do \"não perturbe\" (HH:MM, horário de São Paulo). Vale para navegador e desktop; o e-mail não é afetado.")
    silencio_fim: str | None = Field(None, description="Fim do \"não perturbe\" (HH:MM). Faixa que atravessa a meia-noite é aceita (19:00 a 07:00).")
    silencio_fins_de_semana: bool = Field(False, description="Sem pop-ups nos sábados e domingos.")


class AparelhoNavegador(BaseModel):
    id: uuid.UUID
    rotulo: str
    criada_em: datetime
    ultimo_envio_em: datetime | None


class SituacaoNavegador(BaseModel):
    disponivel: bool = Field(..., description="O servidor tem as chaves VAPID configuradas.")
    chave_publica_vapid: str | None = Field(None, description="Chave pública usada em `pushManager.subscribe` (nula se indisponível).")
    inscricoes: int = Field(..., description="Navegadores desta pessoa inscritos.")
    aparelhos: list[AparelhoNavegador]
    explicacao: str | None = Field(None, description="Por que o canal está indisponível.")


class Silenciado(BaseModel):
    id: int
    tipo: Literal["contrato", "tarefa"]
    alvo_id: uuid.UUID
    rotulo: str


class PreferenciasLeitura(BaseModel):
    modulos: list[ModuloPreferencia]
    configuracao: ConfiguracaoNotificacoes
    navegador: SituacaoNavegador
    silenciados: list[Silenciado]


class GravacaoPreferencias(BaseModel):
    """Corpo do `PUT`: substitui tudo de uma vez."""

    canais: dict[str, list[Canal]] = Field(default_factory=dict, description="`{evento: [canais ligados]}`. Evento ausente = tudo desligado. Canal fora de `canais_disponiveis` do evento: `422`.")
    configuracao: ConfiguracaoNotificacoes = Field(default_factory=ConfiguracaoNotificacoes)


class InscricaoNavegadorEntrada(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=2000)
    p256dh: str = Field(..., min_length=10, max_length=200, description="Chave `p256dh` da `PushSubscription` (base64 URL).")
    auth: str = Field(..., min_length=4, max_length=100, description="Segredo `auth` da `PushSubscription` (base64 URL).")
    rotulo: str = Field("", max_length=200, description="Navegador e sistema (ex.: \"Chrome no Windows\"), para a pessoa reconhecer o aparelho.")


class RemocaoInscricao(BaseModel):
    endpoint: str = Field(..., min_length=10, max_length=2000)


class TesteCanal(BaseModel):
    canal: Canal


class RespostaTeste(BaseModel):
    enviado: bool
    detalhe: str = Field(..., description="O que aconteceu (ex.: \"Enviado a 1 navegador\" ou por que não deu).")


class PedidoSilenciar(BaseModel):
    entrega_id: uuid.UUID = Field(..., description="Entrega (da própria caixa) de um aviso ligado a contrato ou tarefa.")
    tipo: Literal["contrato", "tarefa"] | None = Field(None, description="Só é preciso quando o aviso tem contrato e tarefa; senão é deduzido.")


class CienciaPorToken(BaseModel):
    token: str = Field(..., description="Token do botão \"Ciente\" do pop-up do navegador.")


class ObrigatoriaEntrada(BaseModel):
    evento: str
    canal: Canal
    setor_id: int | None = None
    usuario_id: int | None = None


class ObrigatoriaLeitura(BaseModel):
    id: int
    evento: str
    evento_rotulo: str
    canal: Canal
    setor_id: int | None
    setor_nome: str | None
    usuario_id: int | None
    usuario_nome: str | None
    criada_em: datetime


class LinhaEntrega(BaseModel):
    canal: Canal
    enviadas: int
    falhas: int


class PainelEntregas(BaseModel):
    dias: int
    por_canal: list[LinhaEntrega]
    ultimas_falhas: list[str] = Field(..., description="Até 20 mensagens de erro recentes (e-mail e navegador).")
    inscricoes_total: int
    inscricoes_com_falhas: int = Field(..., description="Inscrições do navegador com 3 ou mais falhas seguidas.")
