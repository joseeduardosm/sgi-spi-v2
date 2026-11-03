# Criado por José Eduardo Santana Martins
# Este arquivo serve para os campos adicionais por categoria: cadastro, herança, validação das respostas e máscara do dado pessoal.
"""Campos adicionais dos Chamados (substituem os formulários simples do GLPI, sem construtor visual).

- Um campo cadastrado numa categoria vale para ela e para todas as subcategorias (ex.: "Ramal" em TELEFONIA aparece em todas).
- Tipos: texto, texto longo, número, data, lista (opções) e sim/não.
- **Condição** simples: o campo só aparece (e só é exigido) quando outro campo tem um valor (`{"campo_id": ..., "igual": "Sim"}`).
- **Dado pessoal** (CPF, RG, telefone pessoal): quem não atende o chamado vê mascarado (`***.456.789-**`); quem atende pede o valor
  completo numa rota própria, e cada consulta fica na auditoria (LGPD).
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chamados import TIPOS_CAMPO, CampoChamados, CategoriaChamados, Chamado, ValorCampoChamado
from app.services.chamados.parametros import ErroParametro, obter_categoria

TAMANHO_MAXIMO = 4000


def herdados(categoria: CategoriaChamados) -> list[CampoChamados]:
    """Campos ativos da categoria e das categorias acima dela, dos mais gerais (raiz) para os mais específicos; em cada nível, pela `ordem` e depois pela ordem de cadastro."""
    linha = []
    atual: CategoriaChamados | None = categoria
    while atual is not None:
        linha.append(atual)
        atual = atual.pai
    campos: list[CampoChamados] = []
    for nivel in reversed(linha):
        campos.extend(sorted((c for c in nivel.campos if c.ativo), key=lambda c: (c.ordem, c.criado_em)))
    return campos


def visivel(campo: CampoChamados, respostas: dict[uuid.UUID, str]) -> bool:
    """O campo aparece? Sem condição, sempre; com condição, quando o outro campo tem o valor pedido."""
    if not campo.condicao:
        return True
    try:
        outro = uuid.UUID(str(campo.condicao.get("campo_id")))
    except ValueError:
        return True
    return (respostas.get(outro) or "").strip().lower() == str(campo.condicao.get("igual", "")).strip().lower()


def validar_respostas(categoria: CategoriaChamados, brutas: dict[str, object]) -> dict[uuid.UUID, str]:
    """Confere as respostas da abertura e devolve só as dos campos visíveis, já normalizadas em texto."""
    from app.services.chamados.servico import ErroChamado

    campos = herdados(categoria)
    por_id = {c.id: c for c in campos}
    respostas: dict[uuid.UUID, str] = {}
    for chave, valor in (brutas or {}).items():
        try:
            campo_id = uuid.UUID(str(chave))
        except ValueError:
            raise ErroChamado("Campo adicional inválido.") from None
        if campo_id not in por_id:
            raise ErroChamado("Há um campo que não pertence a esta categoria. Recarregue a página e tente de novo.")
        texto = "" if valor is None else str(valor).strip()
        if texto:
            respostas[campo_id] = texto
    finais: dict[uuid.UUID, str] = {}
    for campo in campos:
        if not visivel(campo, respostas):
            continue
        texto = respostas.get(campo.id, "")
        if not texto:
            if campo.obrigatorio:
                raise ErroChamado(f"Preencha o campo \"{campo.rotulo}\".", 400, "campo_obrigatorio")
            continue
        finais[campo.id] = _normalizar(campo, texto)
    return finais


def _normalizar(campo: CampoChamados, texto: str) -> str:
    from app.services.chamados.servico import ErroChamado

    if len(texto) > TAMANHO_MAXIMO:
        raise ErroChamado(f"O campo \"{campo.rotulo}\" passou do tamanho máximo.")
    if campo.tipo == "texto" and len(texto) > 300:
        raise ErroChamado(f"O campo \"{campo.rotulo}\" aceita até 300 caracteres.")
    if campo.tipo == "numero":
        if not re.fullmatch(r"-?\d+([.,]\d+)?", texto):
            raise ErroChamado(f"O campo \"{campo.rotulo}\" aceita só números.")
        return texto.replace(",", ".")
    if campo.tipo == "data":
        try:
            return date.fromisoformat(texto).isoformat()
        except ValueError:
            raise ErroChamado(f"Data inválida em \"{campo.rotulo}\".") from None
    if campo.tipo == "lista" and texto not in (campo.opcoes or []):
        raise ErroChamado(f"Escolha uma das opções de \"{campo.rotulo}\".")
    if campo.tipo == "sim_nao":
        if texto.lower() not in ("sim", "não", "nao"):
            raise ErroChamado(f"Responda sim ou não em \"{campo.rotulo}\".")
        return "Sim" if texto.lower() == "sim" else "Não"
    return texto


def mascarar(valor: str) -> str:
    """Esconde o meio do valor: mantém só os dígitos/letras do meio visíveis o suficiente para conferir (ex.: CPF `***.456.789-**`)."""
    if len(valor) <= 4:
        return "*" * len(valor)
    inicio, fim = len(valor) // 4, len(valor) - len(valor) // 4
    return "".join(ch if (inicio <= i < fim or not ch.isalnum()) else "*" for i, ch in enumerate(valor))


# ---------------------------------------------------------------------------------------------
# Cadastro (Parâmetros)
# ---------------------------------------------------------------------------------------------

@dataclass
class DadosCampo:
    rotulo: str
    tipo: str
    obrigatorio: bool = False
    dado_pessoal: bool = False
    ajuda: str | None = None
    opcoes: list[str] | None = None
    condicao: dict | None = None
    ordem: int = 0
    ativo: bool = True


def obter_campo(sessao: Session, campo_id: uuid.UUID) -> CampoChamados:
    campo = sessao.get(CampoChamados, campo_id)
    if campo is None:
        raise ErroParametro("Campo não encontrado.", 404, "nao_encontrado")
    return campo


def salvar_campo(sessao: Session, categoria_id: uuid.UUID, campo_id: uuid.UUID | None, dados: DadosCampo) -> CampoChamados:
    categoria = obter_categoria(sessao, categoria_id)
    if not dados.rotulo.strip():
        raise ErroParametro("Informe o rótulo do campo.")
    if dados.tipo not in TIPOS_CAMPO:
        raise ErroParametro("Tipo de campo inválido.")
    opcoes = [o.strip() for o in (dados.opcoes or []) if o and o.strip()]
    if dados.tipo == "lista" and len(opcoes) < 2:
        raise ErroParametro("Uma lista precisa de pelo menos duas opções.")
    if dados.condicao:
        try:
            alvo = uuid.UUID(str(dados.condicao.get("campo_id")))
        except ValueError:
            raise ErroParametro("Condição inválida: escolha o campo.") from None
        if alvo == campo_id or alvo not in {c.id for c in herdados(categoria)}:
            raise ErroParametro("A condição precisa apontar para outro campo desta categoria (ou de uma categoria acima).")
    campo = obter_campo(sessao, campo_id) if campo_id else CampoChamados(categoria_id=categoria.id)
    if campo_id and campo.categoria_id != categoria.id:
        raise ErroParametro("Campo não encontrado.", 404, "nao_encontrado")
    campo.rotulo, campo.tipo, campo.obrigatorio, campo.dado_pessoal = dados.rotulo.strip(), dados.tipo, dados.obrigatorio, dados.dado_pessoal
    campo.ajuda = (dados.ajuda or "").strip() or None
    campo.opcoes = opcoes if dados.tipo == "lista" else None
    campo.condicao = dados.condicao or None
    campo.ordem, campo.ativo = dados.ordem, dados.ativo
    if campo_id is None:
        sessao.add(campo)
    sessao.flush()
    return campo


def excluir_campo(sessao: Session, categoria_id: uuid.UUID, campo_id: uuid.UUID) -> None:
    """Exclui o campo que nenhum chamado respondeu; respondido, recusa (o histórico guarda a resposta): desative."""
    campo = obter_campo(sessao, campo_id)
    if campo.categoria_id != categoria_id:
        raise ErroParametro("Campo não encontrado.", 404, "nao_encontrado")
    if sessao.scalar(select(ValorCampoChamado.chamado_id).where(ValorCampoChamado.campo_id == campo.id).limit(1)) is not None:
        raise ErroParametro("Este campo já foi respondido em chamados e faz parte do histórico deles. Desative-o em vez de excluir.", 409, "em_uso")
    sessao.delete(campo)
    sessao.flush()


def respostas_do_chamado(chamado: Chamado) -> list[ValorCampoChamado]:
    """Respostas na ordem dos campos."""
    return sorted(chamado.valores, key=lambda v: (v.campo.ordem, v.campo.criado_em))
