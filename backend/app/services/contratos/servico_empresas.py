# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de cadastro de empresas e prepostos.
"""Empresas contratadas e prepostos: listagem com busca ampla, cadastro e exclusão.

Toda gravação é registrada na auditoria (alterações campo a campo, "de → para").
"""

import uuid

from sqlalchemy import Select, asc, desc, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.contratos import Contrato, EmpresaContratada, PrepostoEmpresa
from app.models.usuario import Usuario
from app.schemas.contratos.empresas import (
    ContratoDaEmpresa,
    DetalheEmpresa,
    GravacaoEmpresa,
    GravacaoPreposto,
    LeituraPreposto,
    OpcaoEmpresa,
    PaginaEmpresas,
    ResumoEmpresa,
)
from app.schemas.contratos.validadores import somente_digitos
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.servico_auditoria import auditar, auditar_alteracoes

# Colunas aceitas na ordenação da listagem (textos comparados em minúsculas)
ORDENACOES = {
    "cnpj": EmpresaContratada.cnpj,
    "razao_social": func.lower(EmpresaContratada.razao_social),
    "nome_fantasia": func.lower(EmpresaContratada.nome_fantasia),
    "endereco": func.lower(EmpresaContratada.endereco),
}


def obter_empresa(sessao: Session, empresa_id: uuid.UUID) -> EmpresaContratada:
    """Empresa pelo id, ou `RegistroNaoEncontrado` (vira 404)."""
    empresa = sessao.get(EmpresaContratada, empresa_id)
    if empresa is None:
        raise RegistroNaoEncontrado("Empresa")
    return empresa


def _filtrar(consulta: Select, busca: str | None) -> Select:
    """Pesquisa em qualquer dado da empresa, dos prepostos e dos contratos."""
    termo = (busca or "").strip().lower()
    if not termo:
        return consulta
    # Os dígitos do termo servem para achar CNPJ/CPF digitados com ou sem máscara
    padrao = f"%{termo}%"
    digitos = somente_digitos(termo)
    # Cada condição é uma forma de a empresa "combinar" com a busca; basta uma (OR).
    # `exists()` procura em tabelas relacionadas (prepostos, contratos) sem duplicar linhas.
    condicoes = [
        func.lower(EmpresaContratada.razao_social).like(padrao),
        func.lower(EmpresaContratada.nome_fantasia).like(padrao),
        func.lower(EmpresaContratada.endereco).like(padrao),
        exists().where(
            PrepostoEmpresa.empresa_id == EmpresaContratada.id,
            or_(func.lower(PrepostoEmpresa.nome).like(padrao), func.lower(PrepostoEmpresa.email).like(padrao)),
        ),
        exists().where(
            Contrato.empresa_id == EmpresaContratada.id,
            or_(func.lower(Contrato.apelido).like(padrao), func.lower(Contrato.objeto).like(padrao)),
        ),
    ]
    if digitos:
        condicoes.append(EmpresaContratada.cnpj.like(f"%{digitos}%"))
        condicoes.append(exists().where(PrepostoEmpresa.empresa_id == EmpresaContratada.id, PrepostoEmpresa.cpf.like(f"%{digitos}%")))
    # Termo no formato NNN/AAAA: procura também pelo número do contrato
    numero = _numero_contrato(termo)
    if numero:
        condicoes.append(
            exists().where(Contrato.empresa_id == EmpresaContratada.id, Contrato.sequencial == numero[0], Contrato.ano == numero[1])
        )
    return consulta.where(or_(*condicoes))


def _numero_contrato(termo: str) -> tuple[int, int] | None:
    """Interpreta "12/2026" como (sequencial 12, ano 2026); qualquer outra coisa → None."""
    partes = termo.split("/")
    if len(partes) == 2 and all(p.isdigit() for p in partes) and len(partes[1]) == 4:
        return int(partes[0]), int(partes[1])
    return None


def _contratos_por_empresa(sessao: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ContratoDaEmpresa]]:
    """Números dos contratos de várias empresas em uma consulta: {empresa_id: [contratos]}."""
    resultado: dict[uuid.UUID, list[ContratoDaEmpresa]] = {i: [] for i in ids}
    if not ids:
        return resultado
    linhas = sessao.execute(
        select(Contrato.id, Contrato.empresa_id, Contrato.sequencial, Contrato.ano)
        .where(Contrato.empresa_id.in_(ids))
        .order_by(Contrato.ano.desc(), Contrato.sequencial.desc())
    )
    for contrato_id, empresa_id, sequencial, ano in linhas:
        resultado[empresa_id].append(ContratoDaEmpresa(id=contrato_id, numero=f"{sequencial:03d}/{ano:04d}"))
    return resultado


def listar_empresas(
    sessao: Session, busca: str | None, ordenar: str, direcao: str, pagina: int, tamanho_pagina: int
) -> PaginaEmpresas:
    """Página da listagem de empresas, com prepostos e contratos de cada uma."""
    consulta = _filtrar(select(EmpresaContratada), busca)
    # Total de resultados (antes de paginar)
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    ordem = asc if direcao == "asc" else desc
    # `selectinload` carrega os prepostos de todas as empresas da página em uma consulta extra só;
    # o id no final da ordenação deixa a paginação estável quando há valores repetidos
    empresas = list(
        sessao.scalars(
            consulta.options(selectinload(EmpresaContratada.prepostos))
            .order_by(ordem(ORDENACOES[ordenar]), EmpresaContratada.id)
            .offset((pagina - 1) * tamanho_pagina)
            .limit(tamanho_pagina)
        )
    )
    contratos = _contratos_por_empresa(sessao, [e.id for e in empresas])
    return PaginaEmpresas(
        itens=[
            ResumoEmpresa(
                id=e.id,
                cnpj=e.cnpj,
                razao_social=e.razao_social,
                nome_fantasia=e.nome_fantasia,
                endereco=e.endereco,
                ativa=e.ativa,
                prepostos=[p.nome for p in e.prepostos],
                contratos=contratos[e.id],
            )
            for e in empresas
        ],
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
    )


def opcoes_empresas(sessao: Session, incluir_inativas: bool) -> list[OpcaoEmpresa]:
    """Empresas para o seletor do cadastro de contrato (por padrão, só as ativas)."""
    consulta = select(EmpresaContratada).order_by(func.lower(EmpresaContratada.razao_social))
    if not incluir_inativas:
        consulta = consulta.where(EmpresaContratada.ativa.is_(True))
    return [OpcaoEmpresa.model_validate(e, from_attributes=True) for e in sessao.scalars(consulta)]


def detalhar_empresa(sessao: Session, empresa_id: uuid.UUID) -> DetalheEmpresa:
    """Detalhe completo de uma empresa."""
    empresa = obter_empresa(sessao, empresa_id)
    return DetalheEmpresa(
        id=empresa.id,
        cnpj=empresa.cnpj,
        razao_social=empresa.razao_social,
        nome_fantasia=empresa.nome_fantasia,
        endereco=empresa.endereco,
        ativa=empresa.ativa,
        prepostos=[LeituraPreposto.model_validate(p, from_attributes=True) for p in empresa.prepostos],
        contratos=_contratos_por_empresa(sessao, [empresa.id])[empresa.id],
        criado_em=empresa.criado_em,
        atualizado_em=empresa.atualizado_em,
    )


def _cnpj_em_uso(sessao: Session, cnpj: str, empresa_id: uuid.UUID | None) -> bool:
    """Indica se o CNPJ já pertence a outra empresa (ignora a própria, na alteração)."""
    existente = sessao.scalar(select(EmpresaContratada.id).where(EmpresaContratada.cnpj == cnpj))
    return existente is not None and existente != empresa_id


def _dados(empresa: EmpresaContratada) -> dict:
    """Retrato dos campos da empresa, usado para auditar o "antes" e o "depois"."""
    return {c: getattr(empresa, c) for c in ("cnpj", "razao_social", "nome_fantasia", "endereco", "ativa")}


def criar_empresa(sessao: Session, dados: GravacaoEmpresa, autor: Usuario) -> EmpresaContratada:
    """Cadastra a empresa (CNPJ único)."""
    if _cnpj_em_uso(sessao, dados.cnpj, None):
        raise ErroRegraContrato("Já existe uma empresa com este CNPJ.", conflito=True)
    empresa = EmpresaContratada(**dados.model_dump())
    sessao.add(empresa)
    sessao.flush()
    auditar(sessao, autor.login, "contrato.empresa.criar", f"Empresa {empresa.razao_social}", autor_id=autor.id,
            alvo_tipo="empresa", alvo_id=empresa.id, dados=_dados(empresa))
    sessao.commit()
    return empresa


def alterar_empresa(sessao: Session, empresa_id: uuid.UUID, dados: GravacaoEmpresa, autor: Usuario) -> EmpresaContratada:
    """Altera a empresa e audita só os campos que mudaram."""
    empresa = obter_empresa(sessao, empresa_id)
    if _cnpj_em_uso(sessao, dados.cnpj, empresa.id):
        raise ErroRegraContrato("Já existe uma empresa com este CNPJ.", conflito=True)
    antes = _dados(empresa)
    for campo, valor in dados.model_dump().items():
        setattr(empresa, campo, valor)
    auditar_alteracoes(sessao, autor.login, autor.id, "contrato.empresa.alterar", "empresa", empresa.id,
                       f"Empresa {empresa.razao_social}", antes, _dados(empresa))
    sessao.commit()
    return empresa


def excluir_empresa(sessao: Session, empresa_id: uuid.UUID, autor: Usuario) -> None:
    """Exclui a empresa; com contratos, só é possível inativá-la."""
    empresa = obter_empresa(sessao, empresa_id)
    if sessao.scalar(select(func.count()).where(Contrato.empresa_id == empresa.id)):
        raise ErroRegraContrato("A empresa possui contratos e não pode ser excluída. Inative-a.", conflito=True)
    auditar(sessao, autor.login, "contrato.empresa.excluir", f"Empresa {empresa.razao_social}", autor_id=autor.id,
            alvo_tipo="empresa", alvo_id=empresa.id, dados=_dados(empresa))
    sessao.delete(empresa)
    sessao.commit()


def _obter_preposto(sessao: Session, empresa_id: uuid.UUID, preposto_id: uuid.UUID) -> PrepostoEmpresa:
    """Preposto pelo id, desde que pertença à empresa informada."""
    preposto = sessao.get(PrepostoEmpresa, preposto_id)
    if preposto is None or preposto.empresa_id != empresa_id:
        raise RegistroNaoEncontrado("Preposto")
    return preposto


def _cpf_em_uso(sessao: Session, empresa_id: uuid.UUID, cpf: str, preposto_id: uuid.UUID | None) -> bool:
    """Indica se o CPF já pertence a outro preposto da mesma empresa."""
    existente = sessao.scalar(
        select(PrepostoEmpresa.id).where(PrepostoEmpresa.empresa_id == empresa_id, PrepostoEmpresa.cpf == cpf)
    )
    return existente is not None and existente != preposto_id


def salvar_preposto(
    sessao: Session, empresa_id: uuid.UUID, dados: GravacaoPreposto, autor: Usuario, preposto_id: uuid.UUID | None = None
) -> PrepostoEmpresa:
    """Cria (sem `preposto_id`) ou altera um preposto."""
    empresa = obter_empresa(sessao, empresa_id)
    preposto = _obter_preposto(sessao, empresa_id, preposto_id) if preposto_id else PrepostoEmpresa(empresa_id=empresa.id)
    if _cpf_em_uso(sessao, empresa.id, dados.cpf, preposto_id):
        raise ErroRegraContrato("Já existe um preposto com este CPF nesta empresa.", conflito=True)
    # Valores anteriores (vazios quando o preposto é novo) para a auditoria
    antes = {c: getattr(preposto, c, None) for c in dados.model_fields}
    for campo, valor in dados.model_dump().items():
        setattr(preposto, campo, valor)
    if preposto_id is None:
        sessao.add(preposto)
    # Rede de segurança: se duas pessoas gravarem o mesmo CPF ao mesmo tempo, o banco recusa
    try:
        sessao.flush()
    except IntegrityError as erro:
        sessao.rollback()
        raise ErroRegraContrato("Já existe um preposto com este CPF nesta empresa.", conflito=True) from erro
    # Na auditoria, os campos ficam identificados pelo preposto (ex.: preposto.<id>.nome)
    auditar_alteracoes(sessao, autor.login, autor.id, "contrato.preposto.salvar", "empresa", empresa.id,
                       f"Preposto {preposto.nome} ({empresa.razao_social})",
                       {f"preposto.{preposto.id}.{c}": v for c, v in antes.items()},
                       {f"preposto.{preposto.id}.{c}": getattr(preposto, c) for c in dados.model_fields})
    sessao.commit()
    return preposto


def excluir_preposto(sessao: Session, empresa_id: uuid.UUID, preposto_id: uuid.UUID, autor: Usuario) -> None:
    """Exclui um preposto, registrando CPF e nome na auditoria."""
    preposto = _obter_preposto(sessao, empresa_id, preposto_id)
    auditar(sessao, autor.login, "contrato.preposto.excluir", f"Preposto {preposto.nome}", autor_id=autor.id,
            alvo_tipo="empresa", alvo_id=empresa_id, dados={"cpf": preposto.cpf, "nome": preposto.nome})
    sessao.delete(preposto)
    sessao.commit()
