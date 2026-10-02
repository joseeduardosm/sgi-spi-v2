# Criado por José Eduardo Santana Martins
# Este arquivo serve para importar todos os modelos para que o banco e o Alembic os conheçam.
"""Pacote dos modelos (tabelas) do banco, escritos com SQLAlchemy 2.

Cada classe aqui representa uma tabela. Importar todas neste arquivo garante que
`Base.metadata` conheça o banco inteiro: o Alembic compara esse retrato com o banco real para
gerar as migrações, e os testes o usam para criar as tabelas no SQLite.
"""
from app.models.acl import NivelAcl, RecursoAcl, RegraAcl, acl_regras_setores, acl_regras_usuarios
from app.models.anexo import Anexo
from app.models.auditoria import RegistroAuditoria
from app.models.contratacoes import (
    ComentarioImportado, DocumentoContratacao, HistoricoItem, ItemContratacao, LinhaTabelaTr, MembroDocumento, RevisaoItem, SecaoContratacao,
    VersaoDocumento,
)
from app.models.contratos import (
    Contrato,
    DesignacaoEquipe,
    DocumentoContrato,
    EmpresaContratada,
    ItemContrato,
    PrepostoEmpresa,
)
from app.models.diretorio_ldap import DiretorioLdap
from app.models.envio_changelog import EnvioChangelog
from app.models.melhorias import AnexoSugestao, EventoSugestao, SugestaoMelhoria
from app.models.mensagem import EntregaMensagem, Mensagem
from app.models.noticias import AnexoNoticia, AtalhoPortal, CategoriaNoticia, ConfiguracaoPortal, Noticia, RevisaoNoticia
from app.models.protocolo import EventoProtocolo, NumeroProtocolo, SequenciaProtocolo, TipoProtocolo
from app.models.rh import AlteracaoCadastral, Afastamento, DadosFuncionais, EventoAfastamento, Feriado, ParametrosRh, PeriodoAquisitivo
from app.models.servidor_smtp import ServidorSmtp
from app.models.setor import MembroSetor, Setor
from app.models.tarefas import (
    AnexoEventoTarefa, EquipeTarefas, EventoTarefa, ItemChecklistTarefa, LiderEquipeTarefas, MarcadorTarefa, MembroEquipeTarefas,
    ParticipanteTarefa, Tarefa, VinculoMarcadorTarefa,
)
from app.models.usuario import OrigemUsuario, Papel, Usuario

# Nomes exportados por `from app.models import *`
__all__ = [
    "ComentarioImportado",
    "DocumentoContratacao",
    "HistoricoItem",
    "ItemContratacao",
    "LinhaTabelaTr",
    "MembroDocumento",
    "RevisaoItem",
    "SecaoContratacao",
    "VersaoDocumento",
    "EventoProtocolo",
    "NumeroProtocolo",
    "SequenciaProtocolo",
    "TipoProtocolo",
    "AnexoSugestao",
    "EventoSugestao",
    "SugestaoMelhoria",
    "AnexoNoticia",
    "AtalhoPortal",
    "CategoriaNoticia",
    "ConfiguracaoPortal",
    "Noticia",
    "RevisaoNoticia",
    "Anexo",
    "Contrato",
    "DesignacaoEquipe",
    "DocumentoContrato",
    "EmpresaContratada",
    "ItemContrato",
    "PrepostoEmpresa",
    "DiretorioLdap",
    "EnvioChangelog",
    "EntregaMensagem",
    "Mensagem",
    "AlteracaoCadastral",
    "Afastamento",
    "DadosFuncionais",
    "EventoAfastamento",
    "Feriado",
    "AnexoEventoTarefa",
    "EquipeTarefas",
    "EventoTarefa",
    "ItemChecklistTarefa",
    "LiderEquipeTarefas",
    "MarcadorTarefa",
    "MembroEquipeTarefas",
    "ParticipanteTarefa",
    "Tarefa",
    "VinculoMarcadorTarefa",
    "ParametrosRh",
    "PeriodoAquisitivo",
    "ServidorSmtp",
    "MembroSetor",
    "NivelAcl",
    "OrigemUsuario",
    "Papel",
    "RecursoAcl",
    "RegistroAuditoria",
    "RegraAcl",
    "Setor",
    "Usuario",
    "acl_regras_setores",
    "acl_regras_usuarios",
]
