"""
===============================================================================
ARQUIVO: servico_parametros.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Ler e gravar os parâmetros do módulo de Contratos (linha única na tabela
contratos_parametros) e entregar cada valor ao resto do código.

RESUMO TÉCNICO:
Dois jeitos de ler:
- parametros(sessao): a linha do banco (criada com os padrões se não existir),
  para a tela e para quem já tem sessão;
- valor(nome): só o número, para código sem sessão à mão (cálculos, tarefas).
  Usa um cache de poucos segundos (a API roda com mais de um processo) e, se o
  banco falhar, devolve o padrão: um parâmetro nunca derruba uma tela.
salvar grava só o que mudou, audita e limpa o cache do processo.

FINALIDADE DE NEGÓCIO:
Permite ao administrador ajustar prazos e limites usados nos alertas e nas
regras dos contratos (ex.: dias de atraso, dias para pagamento vencendo) sem
mexer no código, com registro de quem mudou o quê.

CONTEXTO NO SISTEMA:
Usado pela tela de Parâmetros de Contratos (rotas de contratos), por
servico_painel e demais serviços que chamam valor(...). Modelo
ParametrosContratos e PADROES em models.contratos.parametros; auditoria via
servico_auditoria.

===============================================================================
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
# Cache por processo: "ate" é o instante (time.monotonic) em que expira; "valores" guarda o dicionário lido
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
        # flush grava a linha nesta transação sem fazer commit (quem chamou decide quando confirmar)
        sessao.flush()
    return linha


def parametros(sessao: Session) -> ParametrosContratos:
    """Parâmetros atuais (linha do banco)."""
    return _linha(sessao)


def valor(nome: str) -> Any:
    """Valor atual de um parâmetro, sem precisar de sessão (cache curto; padrão se o banco falhar)."""
    # time.monotonic não volta no tempo se o relógio do servidor for ajustado: seguro para medir validade
    agora = time.monotonic()
    # Cache vazio ou vencido: lê de novo numa sessão própria (FabricaSessao abre e fecha a conexão no `with`)
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
    # Compara campo a campo e guarda "de/para" só do que mudou, para a auditoria
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
    # Os outros processos da API verão o novo valor quando o cache deles vencer (até VALIDADE_CACHE segundos)
    limpar_cache()
    return leitura(sessao)
