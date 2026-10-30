# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler e gravar os parâmetros do módulo de contratos e entregar cada valor ao resto do código.
"""Parâmetros de Contratos (linha única em `contratos_parametros`).

Dois jeitos de ler:
- `parametros(sessao)`: a linha do banco (cria com os padrões se não existir), para a tela e para quem já tem sessão;
- `valor(nome)`: só o número, para o código que não tem sessão à mão (cálculos, tarefas). Usa um cache de poucos segundos
  (a API roda com mais de um processo) e, se o banco falhar, devolve o padrão: um parâmetro nunca derruba uma tela.
"""

import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.banco import FabricaSessao, agora_utc
from app.models.contratos.parametros import PADROES, ParametrosContratos
from app.models.usuario import Usuario
from app.schemas.contratos.parametros import GravacaoParametrosContratos, LeituraParametrosContratos
from app.services.servico_auditoria import auditar

# Segundos que um valor lido fica em memória (depois de salvar, o processo que salvou já vê o novo valor na hora)
VALIDADE_CACHE = 30
_cache: dict[str, Any] = {"ate": 0.0, "valores": None}


def limpar_cache() -> None:
    """Esquece os valores lidos (usado ao salvar e nos testes)."""
    _cache["ate"], _cache["valores"] = 0.0, None


def _linha(sessao: Session) -> ParametrosContratos:
    """A linha única; se ainda não existir (banco novo ou de teste), nasce com os valores padrão."""
    linha = sessao.get(ParametrosContratos, 1)
    if linha is None:
        linha = ParametrosContratos(id=1, **PADROES)
        sessao.add(linha)
        sessao.flush()
    return linha


def parametros(sessao: Session) -> ParametrosContratos:
    """Parâmetros atuais (linha do banco)."""
    return _linha(sessao)


def valor(nome: str) -> Any:
    """Valor atual de um parâmetro, sem precisar de sessão (cache curto; padrão se o banco falhar)."""
    agora = time.monotonic()
    if _cache["valores"] is None or agora >= _cache["ate"]:
        try:
            with FabricaSessao() as sessao:
                linha = sessao.get(ParametrosContratos, 1)
                valores = {campo: getattr(linha, campo) for campo in PADROES} if linha is not None else dict(PADROES)
        except Exception:  # noqa: BLE001 - parâmetro nunca derruba a tela: cai nos valores de fábrica
            valores = dict(PADROES)
        _cache["valores"], _cache["ate"] = valores, agora + VALIDADE_CACHE
    return _cache["valores"][nome]


def leitura(sessao: Session) -> LeituraParametrosContratos:
    """Parâmetros atuais para a API, com os padrões de fábrica ao lado."""
    linha = _linha(sessao)
    dados = {campo: getattr(linha, campo) for campo in PADROES}
    return LeituraParametrosContratos(**dados, atualizado_por_nome=linha.atualizado_por_nome, atualizado_em=linha.atualizado_em,
                                      padroes=GravacaoParametrosContratos(**PADROES))


def salvar(sessao: Session, dados: GravacaoParametrosContratos, autor: Usuario) -> LeituraParametrosContratos:
    """Grava os parâmetros e audita só o que mudou (`contratos.parametros`)."""
    linha = _linha(sessao)
    mudancas = {}
    for campo in PADROES:
        novo, antigo = getattr(dados, campo), getattr(linha, campo)
        if novo != antigo:
            mudancas[campo] = {"de": str(antigo), "para": str(novo)}
            setattr(linha, campo, novo)
    if mudancas:
        linha.atualizado_por_nome, linha.atualizado_em = autor.login, agora_utc()
        auditar(sessao, autor.login, "contratos.parametros", "Parâmetros de Contratos", autor_id=autor.id, dados={"campos": mudancas})
    sessao.commit()
    limpar_cache()
    return leitura(sessao)
