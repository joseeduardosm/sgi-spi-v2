"""
===============================================================================
ARQUIVO: setor.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Definir as tabelas de setores e de membros de setor.

RESUMO TÉCNICO:
- Setor: unidade institucional ou grupo sistêmico, com hierarquia opcional
  (setor_pai_id), líder, sigla e tipo da unidade (rótulo do organograma).
- Índice único em lower(nome): "TI" e "ti" são o mesmo setor.
- MembroSetor: tabela de ligação muitos-para-muitos usuário x setor, com
  chave primária composta (o mesmo usuário não entra duas vezes).

FINALIDADE DE NEGÓCIO:
Representar a estrutura da SPI (secretaria, subsecretarias, diretorias,
coordenadorias) e grupos de trabalho. Os setores funcionam como grupos de
acesso na ACL (lista de controle de acesso), definindo quem vê o quê.

CONTEXTO NO SISTEMA:
Usado pela ACL (models/acl), pelo RH (cargos pertencem a um setor e o
organograma), pelo módulo Setores (schemas/setores.py) e por vários módulos
que filtram dados por setor. Ligado à tabela usuarios.

===============================================================================
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.banco import Base, agora_utc


class Setor(Base):
    """Setor institucional ou grupo sistêmico, com hierarquia opcional (setor pai) e líder.

    Cada classe que herda de `Base` vira uma tabela. `Mapped[...]` declara o tipo da coluna em
    Python e `mapped_column(...)` os detalhes no banco (tipo SQL, chave estrangeira, padrão).
    `ativo = False` desativa o setor sem apagar o histórico ligado a ele.
    """
    __tablename__ = "setores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    # Hierarquia: RESTRICT impede excluir um setor que ainda tenha subordinados
    setor_pai_id: Mapped[int | None] = mapped_column(ForeignKey("setores.id", ondelete="RESTRICT"), index=True)
    # Líder do setor; se o usuário for excluído, o setor fica sem líder (SET NULL)
    lider_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    # Sistêmico: grupo de acesso sem correspondência na estrutura institucional (ex.: "Auditores")
    sistemico: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Estrutura do RH: sigla e tipo da unidade (secretaria, subsecretaria, diretoria, coordenadoria...), só para rotular o organograma
    sigla: Mapped[str | None] = mapped_column(String(30))
    tipo_unidade: Mapped[str | None] = mapped_column(String(30))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc, onupdate=agora_utc)


# Índice funcional criado fora da classe porque usa uma expressão (lower) e não uma coluna simples.
# Nome único sem diferenciar maiúsculas/minúsculas ("TI" e "ti" seriam o mesmo setor)
Index("ux_setores_nome_minusculo", func.lower(Setor.nome), unique=True)


class MembroSetor(Base):
    """Associação usuário ↔ setor (tabela de ligação muitos-para-muitos).

    Uma pessoa pode estar em vários setores (ex.: no seu setor institucional e num grupo
    sistêmico) e um setor tem várias pessoas. Excluir o setor ou o usuário apaga o vínculo (CASCADE).
    """
    __tablename__ = "membros_setor"

    # Chave primária composta: o mesmo usuário não entra duas vezes no mesmo setor
    setor_id: Mapped[int] = mapped_column(ForeignKey("setores.id", ondelete="CASCADE"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora_utc)
