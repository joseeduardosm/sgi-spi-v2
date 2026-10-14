# Criado por José Eduardo Santana Martins
# Este arquivo serve para os grupos de material (vida útil e residual) e os parâmetros editáveis do Patrimônio (valor da UFESP).
import re
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.patrimonio import Bem, GrupoMaterial, ParametroPatrimonio, PrefixoChapa
from app.services.patrimonio.base import PARAMETROS_PADRAO, ErroPatrimonio, parametro


def listar_grupos(sessao: Session, incluir_inativos: bool = False) -> list[GrupoMaterial]:
    consulta = select(GrupoMaterial).order_by(func.lower(GrupoMaterial.nome))
    if not incluir_inativos:
        consulta = consulta.where(GrupoMaterial.ativo.is_(True))
    return list(sessao.scalars(consulta))


def _validar(dados: dict) -> None:
    if dados.get("vida_util_meses") is not None and dados["vida_util_meses"] <= 0:
        raise ErroPatrimonio("A vida útil deve ser maior que zero (em meses).")
    residual = dados.get("residual_percentual")
    if residual is not None and not Decimal(0) <= residual <= Decimal(100):
        raise ErroPatrimonio("O residual vai de 0 a 100%.")


def criar_grupo(sessao: Session, dados: dict) -> GrupoMaterial:
    _validar(dados)
    codigo, nome = (dados.get("codigo") or "").strip(), (dados.get("nome") or "").strip()
    if not codigo or not nome:
        raise ErroPatrimonio("Informe o código e o nome do grupo.")
    if sessao.scalar(select(GrupoMaterial.id).where(func.lower(GrupoMaterial.codigo) == codigo.lower())) is not None:
        raise ErroPatrimonio(f"Já existe o grupo {codigo}.", 409, "conflito")
    grupo = GrupoMaterial(id=uuid.uuid4(), codigo=codigo, nome=nome, vida_util_meses=dados.get("vida_util_meses"),
                          residual_percentual=dados.get("residual_percentual", Decimal("10")), deprecia=dados.get("deprecia", True), ativo=True)
    sessao.add(grupo)
    sessao.commit()
    return grupo


def atualizar_grupo(sessao: Session, grupo_id: uuid.UUID, dados: dict) -> GrupoMaterial:
    grupo = sessao.get(GrupoMaterial, grupo_id)
    if grupo is None:
        raise ErroPatrimonio("Grupo não encontrado.", 404, "nao_encontrado")
    _validar(dados)
    for campo in ("nome", "vida_util_meses", "residual_percentual", "deprecia", "ativo"):
        if campo in dados:
            setattr(grupo, campo, dados[campo])
    sessao.commit()
    return grupo


def excluir_grupo(sessao: Session, grupo_id: uuid.UUID) -> None:
    grupo = sessao.get(GrupoMaterial, grupo_id)
    if grupo is None:
        raise ErroPatrimonio("Grupo não encontrado.", 404, "nao_encontrado")
    if sessao.scalar(select(func.count(Bem.id)).where(Bem.grupo_id == grupo.id)):
        raise ErroPatrimonio("O grupo tem bens vinculados: só pode ser inativado.", 409, "conflito")
    sessao.delete(grupo)
    sessao.commit()


def obter_parametros(sessao: Session) -> dict[str, str]:
    return {chave: parametro(sessao, chave) for chave in PARAMETROS_PADRAO}


def salvar_parametros(sessao: Session, dados: dict[str, str]) -> dict[str, str]:
    for chave, valor in dados.items():
        if chave not in PARAMETROS_PADRAO:
            raise ErroPatrimonio(f"Parâmetro desconhecido: {chave}.")
        try:
            if Decimal(str(valor)) <= 0:
                raise ValueError
        except Exception as erro:
            raise ErroPatrimonio("O valor da UFESP deve ser um número maior que zero.") from erro
        linha = sessao.get(ParametroPatrimonio, chave)
        if linha is None:
            sessao.add(ParametroPatrimonio(chave=chave, valor=str(valor)))
        else:
            linha.valor = str(valor)
    sessao.commit()
    return obter_parametros(sessao)


# --- Prefixos da chapa ---------------------------------------------------------------------------

def listar_prefixos(sessao: Session, incluir_inativos: bool = False) -> list[PrefixoChapa]:
    """Prefixos em ordem alfabética, com o padrão primeiro."""
    consulta = select(PrefixoChapa).order_by(PrefixoChapa.padrao.desc(), PrefixoChapa.codigo)
    if not incluir_inativos:
        consulta = consulta.where(PrefixoChapa.ativo.is_(True))
    return list(sessao.scalars(consulta))


def prefixo_padrao(sessao: Session) -> str | None:
    return sessao.scalar(select(PrefixoChapa.codigo).where(PrefixoChapa.padrao.is_(True), PrefixoChapa.ativo.is_(True)))


def criar_prefixo(sessao: Session, codigo: str) -> PrefixoChapa:
    codigo = (codigo or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,20}", codigo):
        raise ErroPatrimonio("O prefixo só pode ter letras e números (sem espaços), até 20 caracteres.")
    if sessao.scalar(select(PrefixoChapa.id).where(PrefixoChapa.codigo == codigo)) is not None:
        raise ErroPatrimonio(f"Já existe o prefixo {codigo}.", 409, "conflito")
    prefixo = PrefixoChapa(id=uuid.uuid4(), codigo=codigo, padrao=False, ativo=True)
    sessao.add(prefixo)
    sessao.commit()
    return prefixo


def atualizar_prefixo(sessao: Session, prefixo_id: uuid.UUID, dados: dict) -> PrefixoChapa:
    prefixo = sessao.get(PrefixoChapa, prefixo_id)
    if prefixo is None:
        raise ErroPatrimonio("Prefixo não encontrado.", 404, "nao_encontrado")
    ativo = dados.get("ativo", prefixo.ativo)
    padrao = dados.get("padrao", prefixo.padrao)
    if padrao and not ativo:
        raise ErroPatrimonio("O prefixo padrão precisa estar ativo.", 409, "conflito")
    if prefixo.padrao and not padrao:
        raise ErroPatrimonio("Escolha outro prefixo como padrão em vez de desmarcar este.", 409, "conflito")
    if padrao and not prefixo.padrao:
        for outro in sessao.scalars(select(PrefixoChapa).where(PrefixoChapa.padrao.is_(True))):
            outro.padrao = False
        sessao.flush()
    prefixo.ativo, prefixo.padrao = ativo, padrao
    sessao.commit()
    return prefixo


def excluir_prefixo(sessao: Session, prefixo_id: uuid.UUID) -> None:
    prefixo = sessao.get(PrefixoChapa, prefixo_id)
    if prefixo is None:
        raise ErroPatrimonio("Prefixo não encontrado.", 404, "nao_encontrado")
    if prefixo.padrao:
        raise ErroPatrimonio("O prefixo padrão não pode ser excluído: escolha outro como padrão antes.", 409, "conflito")
    if sessao.scalar(select(func.count(Bem.id)).where(Bem.chapa_chave.like(prefixo.codigo.lower() + "%"))):
        raise ErroPatrimonio("Há bens com chapa deste prefixo: ele só pode ser inativado.", 409, "conflito")
    sessao.delete(prefixo)
    sessao.commit()
