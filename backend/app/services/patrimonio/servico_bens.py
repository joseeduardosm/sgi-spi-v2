# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras de cadastro, consulta e alteração dos bens do Patrimônio (histórico por campo, fotos, ajuste de local).
"""Bens do Patrimônio.

- Cadastro com idempotência por `id_cliente` (o reenvio de um cadastro feito offline não duplica o bem).
- A sala precisa ter setor e responsável (informados no primeiro cadastro ali); o bem herda o responsável da sala.
- Toda alteração grava um evento por campo (anterior e novo, autor, origem) no histórico, que não se apaga.
- O local só muda por movimentação; o controle total pode ajustar direto, com motivo obrigatório (também registrado).
- O bem baixado nunca é excluído, mas não pode mais ser editado nem movimentado.
"""

import calendar
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, BinaryIO

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import hoje_sao_paulo
from app.models.patrimonio import Bem, EventoPatrimonio, FotoBem, GrupoMaterial, ItemMovimentacao, Localizacao, Movimentacao, PrefixoChapa
from app.models.usuario import Usuario
from app.services import servico_anexos
from app.services.patrimonio import depreciacao, servico_localizacoes, servico_parametros
from app.services.patrimonio.base import LIMITE_UFESP, ErroPatrimonio, parametro, registrar_evento

SITUACOES_CADASTRO = ("ativo", "em_manutencao")
ORIGENS = ("proprio", "terceiros")
MAXIMO_FOTOS = 3
EXTENSOES_FOTO = (".png", ".jpg", ".jpeg")
# Campos que o formulário do bem pode alterar (local, responsável e situação seguem fluxos próprios)
CAMPOS_EDITAVEIS = (
    "chapa", "descricao", "conservacao", "situacao", "origem", "grupo_id", "uge", "ua", "divisao", "valor_aquisicao", "valor_atual", "data_aquisicao",
    "garantia_meses", "marca", "modelo", "numero_serie", "nota_fiscal", "fornecedor", "observacoes",
)
CAMPOS_TEXTO = ("uge", "ua", "divisao", "marca", "modelo", "numero_serie", "nota_fiscal", "fornecedor", "observacoes")
OPCOES_AO_CARREGAR = (selectinload(Bem.localizacao).selectinload(Localizacao.setor), selectinload(Bem.grupo), selectinload(Bem.fotos), selectinload(Bem.responsavel))


def adicionar_meses(data: date, meses: int) -> date:
    """Soma meses a uma data (o dia vira o último do mês quando o mês de destino é mais curto)."""
    total = data.year * 12 + data.month - 1 + meses
    ano, mes = divmod(total, 12)
    return date(ano, mes + 1, min(data.day, calendar.monthrange(ano, mes + 1)[1]))


def garantia_fim(bem: Bem) -> date | None:
    """Fim da garantia = data de aquisição + meses de garantia; sem a data de aquisição a garantia é indefinida."""
    if bem.data_aquisicao is None or bem.garantia_meses is None:
        return None
    return adicionar_meses(bem.data_aquisicao, bem.garantia_meses)


def situacao_garantia(bem: Bem, hoje: date | None = None) -> str:
    """indefinida, vigente ou vencida."""
    fim = garantia_fim(bem)
    if fim is None:
        return "indefinida"
    return "vigente" if fim >= (hoje or hoje_sao_paulo()) else "vencida"


def vence_em_90_dias(bem: Bem, hoje: date | None = None) -> bool:
    fim = garantia_fim(bem)
    hoje = hoje or hoje_sao_paulo()
    return fim is not None and 0 <= (fim - hoje).days <= 90


def valor_efetivo(bem: Bem, hoje: date | None = None) -> Decimal | None:
    """Nos painéis vale o valor atual informado no bem (normalmente o do SAM); sem ele, o valor calculado pela depreciação."""
    if bem.valor_atual is not None:
        return bem.valor_atual
    if bem.grupo is None:
        return None
    deprecia = bem.grupo.deprecia and bem.origem != "terceiros"
    return depreciacao.valor_calculado(bem.valor_aquisicao, bem.grupo.residual_percentual, bem.grupo.vida_util_meses, bem.data_aquisicao, hoje or hoje_sao_paulo(), deprecia)


def avisos(sessao: Session, bem: Bem) -> list[str]:
    """Avisos do cadastro: pendência contábil e regra estadual de patrimoniável (abaixo de 45 UFESP e vida útil menor que dois anos)."""
    resultado = []
    if bem.dados_contabeis_pendentes:
        resultado.append("Dados contábeis pendentes: o bem entra na contagem, mas fica fora dos totais de valor.")
    if bem.valor_aquisicao is not None and bem.grupo is not None and bem.grupo.vida_util_meses is not None:
        limite = Decimal(parametro(sessao, "ufesp")) * LIMITE_UFESP
        if bem.valor_aquisicao < limite and bem.grupo.vida_util_meses < 24:
            resultado.append("Pela regra estadual (valor abaixo de 45 UFESP e vida útil menor que dois anos), o bem não é patrimoniável.")
    return resultado


def obter(sessao: Session, bem_id: uuid.UUID) -> Bem:
    bem = sessao.scalar(select(Bem).where(Bem.id == bem_id).options(*OPCOES_AO_CARREGAR))
    if bem is None:
        raise ErroPatrimonio("Bem não encontrado.", 404, "nao_encontrado")
    return bem


SITUACOES_VALIDAS = {"ativo", "em_manutencao", "inservivel", "extraviado", "baixado"}


def montar_chapa(sessao: Session, prefixo: str | None, numero: str | None) -> str | None:
    """Junta prefixo e número: só dígitos viram 6 dígitos com zeros à esquerda (231 → 000231); outro texto fica como digitado.

    Sem prefixo a chapa é devolvida como veio. Se o número já começa com o prefixo escolhido (leitura de código, colagem), o prefixo não repete.
    """
    numero = (numero or "").strip()
    if not numero:
        return None
    prefixo = (prefixo or "").strip().upper()
    if not prefixo:
        return numero
    if not sessao.scalar(select(PrefixoChapa.id).where(PrefixoChapa.codigo == prefixo, PrefixoChapa.ativo.is_(True))):
        raise ErroPatrimonio(f"Prefixo {prefixo} inexistente ou inativo.", 404, "nao_encontrado")
    if numero.upper().startswith(prefixo) and len(numero) > len(prefixo):
        numero = numero[len(prefixo):].strip()
    if numero.isdigit():
        numero = numero.zfill(6)
    return (prefixo + numero)[:60]


def obter_por_chapa(sessao: Session, chapa: str) -> Bem:
    """Leitura de QR/código de barras ou texto digitado: acha o bem pela chapa ou, se não houver, pelo número de série (sem diferenciar maiúsculas).

    Só dígitos (etiqueta antiga) tenta antes com o prefixo padrão. O número de série pode se repetir entre bens: com mais de um, pede a chapa (`409 ambiguo`).
    """
    texto = chapa.strip()
    bem = sessao.scalar(select(Bem).where(Bem.chapa_chave == texto.lower()).options(*OPCOES_AO_CARREGAR))
    if bem is None and texto.isdigit():
        padrao = servico_parametros.prefixo_padrao(sessao)
        if padrao:
            bem = sessao.scalar(select(Bem).where(Bem.chapa_chave == (padrao + texto.zfill(6)).lower()).options(*OPCOES_AO_CARREGAR))
    if bem is None and texto:
        com_serie = list(sessao.scalars(select(Bem).where(func.lower(Bem.numero_serie) == texto.lower()).options(*OPCOES_AO_CARREGAR).limit(2)))
        if len(com_serie) > 1:
            raise ErroPatrimonio("Há mais de um bem com este número de série: use a chapa ou escolha o bem na lista.", 409, "ambiguo")
        bem = com_serie[0] if com_serie else None
    if bem is None:
        raise ErroPatrimonio("Nenhum bem com esta chapa ou número de série.", 404, "nao_encontrado")
    return bem


def _busca_da_palavra(sessao: Session, termo: str):
    """Condição de uma palavra da busca em todas as informações do bem (o local pega a sala e tudo o que está dentro dela: andar, lado, prédio)."""
    texto = lambda c: func.lower(func.coalesce(c, ""))  # noqa: E731
    campos = [texto(Bem.chapa), texto(Bem.descricao), texto(Bem.numero_serie), texto(Bem.marca), texto(Bem.modelo), texto(Bem.fornecedor), texto(Bem.nota_fiscal),
              texto(Bem.uge), texto(Bem.ua), texto(Bem.divisao), texto(Bem.observacoes)]
    condicao = or_(*[c.like(termo) for c in campos])
    grupos = select(GrupoMaterial.id).where(or_(texto(GrupoMaterial.nome).like(termo), texto(GrupoMaterial.codigo).like(termo)))
    responsaveis = select(Usuario.id).where(or_(texto(Usuario.nome_completo).like(termo), texto(Usuario.login).like(termo)))
    locais = list(sessao.scalars(select(Localizacao.id).where(or_(texto(Localizacao.codigo).like(termo), texto(Localizacao.nome).like(termo))).limit(40)))
    ids_locais: set = set()
    for local_id in locais:
        ids_locais |= set(servico_localizacoes.ids_da_subarvore(sessao, local_id))
    condicao = or_(condicao, Bem.grupo_id.in_(grupos), Bem.responsavel_id.in_(responsaveis))
    if ids_locais:
        condicao = or_(condicao, Bem.localizacao_id.in_(ids_locais))
    return condicao


def _filtros(
    sessao: Session, *, q: str | None, situacao: str | None, localizacao_id: uuid.UUID | None, grupo_id: uuid.UUID | None, conservacao: int | None,
    garantia: str | None, contabeis_pendentes: bool | None, incluir_baixados: bool,
):
    condicoes = []
    if situacao:
        # Aceita uma situação ou várias separadas por vírgula (ex.: "inservivel,extraviado")
        situacoes = [s.strip() for s in situacao.split(",") if s.strip()]
        if not situacoes or any(s not in SITUACOES_VALIDAS for s in situacoes):
            raise ErroPatrimonio("Situação inválida.")
        condicoes.append(Bem.situacao.in_(situacoes) if len(situacoes) > 1 else Bem.situacao == situacoes[0])
    elif not incluir_baixados:
        condicoes.append(Bem.situacao != "baixado")
    if q and q.strip():
        # Cada palavra precisa aparecer em algum campo do bem (chapa, série, descrição, marca, modelo, local, grupo, responsável, fornecedor, nota fiscal, UGE/UA/divisão,
        # observações): "notebook dell 05A01" acha os notebooks Dell daquela sala. Palavras separadas por espaço se somam (E).
        for palavra in q.strip().lower().split():
            condicoes.append(_busca_da_palavra(sessao, f"%{palavra}%"))
    if localizacao_id:
        condicoes.append(Bem.localizacao_id.in_(servico_localizacoes.ids_da_subarvore(sessao, localizacao_id)))
    if grupo_id:
        condicoes.append(Bem.grupo_id == grupo_id)
    if conservacao:
        condicoes.append(Bem.conservacao == conservacao)
    if contabeis_pendentes:
        condicoes.append(or_(Bem.grupo_id.is_(None), Bem.valor_aquisicao.is_(None), Bem.data_aquisicao.is_(None)))
    return condicoes


# Colunas da lista que o servidor sabe ordenar (a ordem vale para todas as páginas, não só para a que está na tela)
ORDENAVEIS = (
    "chapa", "descricao", "sala", "situacao", "conservacao", "grupo", "valor_aquisicao", "valor_atual", "data_aquisicao", "garantia", "responsavel", "marca", "modelo",
    "numero_serie", "uge", "ua", "divisao", "nota_fiscal", "fornecedor", "criado_em", "origem", "observacoes", "atualizado_em", "baixado_em",
)


def _expressao_de_ordem(coluna: str):
    """Expressão SQL da coluna; `None` quando a coluna depende de cálculo (garantia) e é ordenada em Python."""
    texto = lambda c: func.lower(func.coalesce(c, ""))  # noqa: E731
    return {
        "chapa": func.lower(Bem.chapa), "descricao": func.lower(Bem.descricao), "sala": Localizacao.codigo, "situacao": Bem.situacao, "conservacao": Bem.conservacao,
        "grupo": func.lower(GrupoMaterial.nome), "valor_aquisicao": Bem.valor_aquisicao, "valor_atual": Bem.valor_atual, "data_aquisicao": Bem.data_aquisicao,
        "responsavel": func.lower(Usuario.nome_completo), "marca": texto(Bem.marca), "modelo": texto(Bem.modelo), "numero_serie": texto(Bem.numero_serie),
        "uge": texto(Bem.uge), "ua": texto(Bem.ua), "divisao": texto(Bem.divisao), "nota_fiscal": texto(Bem.nota_fiscal), "fornecedor": texto(Bem.fornecedor),
        "criado_em": Bem.criado_em, "origem": Bem.origem, "observacoes": texto(Bem.observacoes), "atualizado_em": Bem.atualizado_em, "baixado_em": Bem.baixado_em,
    }.get(coluna)


def listar(
    sessao: Session, *, q: str | None = None, situacao: str | None = None, localizacao_id: uuid.UUID | None = None, grupo_id: uuid.UUID | None = None,
    conservacao: int | None = None, garantia: str | None = None, contabeis_pendentes: bool | None = None, incluir_baixados: bool = False,
    pagina: int = 1, tamanho: int = 30, ordenar_por: str = "chapa", direcao: str = "asc",
) -> tuple[list[Bem], int]:
    """Lista paginada e ordenável. Os filtros e a ordem por garantia (derivada de data e meses) são aplicados depois da consulta."""
    if ordenar_por not in ORDENAVEIS:
        raise ErroPatrimonio(f"Coluna de ordenação inválida: {ordenar_por}.")
    decrescente = direcao == "desc"
    condicoes = _filtros(sessao, q=q, situacao=situacao, localizacao_id=localizacao_id, grupo_id=grupo_id, conservacao=conservacao, garantia=garantia,
                         contabeis_pendentes=contabeis_pendentes, incluir_baixados=incluir_baixados)
    consulta = select(Bem).where(*condicoes).options(*OPCOES_AO_CARREGAR)
    expressao = _expressao_de_ordem(ordenar_por)
    if expressao is None or garantia:
        # Garantia (ou filtro de garantia): traz tudo, filtra/ordena em Python e fatia a página
        todos = list(sessao.scalars(consulta.order_by(func.lower(Bem.chapa))))
        if garantia:
            todos = [b for b in todos if situacao_garantia(b) == garantia]
        if ordenar_por == "garantia":
            # Sem data de fim da garantia (indefinida) vai sempre para o fim, qualquer que seja o sentido
            com = sorted([b for b in todos if garantia_fim(b)], key=lambda b: garantia_fim(b), reverse=decrescente)
            todos = com + [b for b in todos if not garantia_fim(b)]
        elif expressao is not None:
            chave = {"sala": lambda b: b.localizacao.codigo or "", "grupo": lambda b: (b.grupo.nome.lower() if b.grupo else "\uffff"), "responsavel": lambda b: (b.responsavel.nome_completo.lower() if b.responsavel else "\uffff")}.get(ordenar_por, lambda b: (str(getattr(b, ordenar_por) or "")).lower())
            todos.sort(key=chave, reverse=decrescente)
        inicio = (pagina - 1) * tamanho
        return todos[inicio:inicio + tamanho], len(todos)
    if ordenar_por == "sala":
        consulta = consulta.join(Localizacao, Localizacao.id == Bem.localizacao_id)
    elif ordenar_por == "grupo":
        consulta = consulta.outerjoin(GrupoMaterial, GrupoMaterial.id == Bem.grupo_id)
    elif ordenar_por == "responsavel":
        consulta = consulta.outerjoin(Usuario, Usuario.id == Bem.responsavel_id)
    ordem = expressao.desc() if decrescente else expressao.asc()
    # Vazios no fim e, em empate, a chapa decide (a ordem fica estável entre as páginas)
    consulta = consulta.order_by(ordem.nulls_last(), func.lower(Bem.chapa))
    total = sessao.scalar(select(func.count(Bem.id)).where(*condicoes)) or 0
    return list(sessao.scalars(consulta.offset((pagina - 1) * tamanho).limit(tamanho))), total


def sugerir_descricoes(sessao: Session, texto: str, limite: int = 8) -> list[str]:
    """Descrições já cadastradas que casam com o texto (para o autocompletar do cadastro e favorecer a padronização).

    Começar pelo texto vale mais que apenas conter; depois, as mais usadas. Descrições iguais (sem diferenciar maiúsculas) viram uma só,
    na grafia mais usada.
    """
    termo = texto.strip().lower()
    if len(termo) < 2:
        return []
    linhas = sessao.execute(
        select(func.lower(Bem.descricao), Bem.descricao, func.count(Bem.id)).where(func.lower(Bem.descricao).like(f"%{termo}%")).group_by(func.lower(Bem.descricao), Bem.descricao)
    ).all()
    # Junta as grafias da mesma descrição somando os usos e guardando a mais frequente
    por_chave: dict[str, dict] = {}
    for chave, grafia, usos in linhas:
        item = por_chave.setdefault(chave, {"usos": 0, "melhor": (0, grafia)})
        item["usos"] += usos
        if usos > item["melhor"][0]:
            item["melhor"] = (usos, grafia)
    ordenadas = sorted(por_chave.items(), key=lambda kv: (not kv[0].startswith(termo), -kv[1]["usos"], kv[0]))
    return [i["melhor"][1] for _, i in ordenadas[:limite]]


def _normalizar(dados: dict[str, Any]) -> dict[str, Any]:
    limpo = {}
    for campo, valor in dados.items():
        if isinstance(valor, str):
            valor = valor.strip() or None
        limpo[campo] = valor
    return limpo


def _validar(sessao: Session, dados: dict[str, Any]) -> None:
    if "conservacao" in dados and not (isinstance(dados["conservacao"], int) and 1 <= dados["conservacao"] <= 5):
        raise ErroPatrimonio("O estado de conservação vai de 1 (péssimo) a 5 (ótimo).")
    if "origem" in dados and dados["origem"] not in ORIGENS:
        raise ErroPatrimonio("A origem é \"próprio\" ou \"terceiros\".")
    for campo in ("valor_aquisicao", "valor_atual"):
        if dados.get(campo) is not None and dados[campo] < 0:
            raise ErroPatrimonio("Os valores não podem ser negativos.")
    if dados.get("garantia_meses") is not None and dados["garantia_meses"] < 0:
        raise ErroPatrimonio("Os meses de garantia não podem ser negativos.")
    if dados.get("grupo_id") is not None and sessao.get(GrupoMaterial, dados["grupo_id"]) is None:
        raise ErroPatrimonio("Grupo de material não encontrado.", 404, "nao_encontrado")


def criar(sessao: Session, dados: dict[str, Any], autor: Usuario, *, origem: str | None = None) -> tuple[Bem, bool]:
    """Cadastra o bem. Devolve `(bem, criado)`: `criado` é falso quando o `id_cliente` já tinha sido enviado (reenvio offline)."""
    id_cliente = dados.pop("id_cliente", None)
    if id_cliente:
        existente = sessao.scalar(select(Bem).where(Bem.id_cliente == id_cliente).options(*OPCOES_AO_CARREGAR))
        if existente is not None:
            return existente, False
    dados = _normalizar(dados)
    prefixo = dados.pop("prefixo", None)
    chapa, descricao = montar_chapa(sessao, prefixo, dados.get("chapa")), dados.get("descricao")
    dados["chapa"] = chapa
    if not descricao:
        raise ErroPatrimonio("Informe a descrição do material.")
    # Sem patrimônio, o bem se identifica pelo número de série
    if not chapa and not dados.get("numero_serie"):
        raise ErroPatrimonio("Informe a chapa ou, se o bem não tem patrimônio, o número de série.")
    sala = servico_localizacoes.exigir_sala(sessao, dados["localizacao_id"])
    if sala.setor_id is None or sala.responsavel_id is None:
        raise ErroPatrimonio("A sala ainda não tem setor e responsável: informe-os antes de cadastrar o primeiro bem.", 409, "sala_sem_responsavel")
    if dados.get("situacao", "ativo") not in SITUACOES_CADASTRO:
        raise ErroPatrimonio("No cadastro, a situação só pode ser Ativo ou Em manutenção.")
    dados.setdefault("situacao", "ativo")
    dados.setdefault("origem", "proprio")
    _validar(sessao, dados)
    chave = chapa.lower() if chapa else None
    if chave and sessao.scalar(select(Bem.id).where(Bem.chapa_chave == chave)) is not None:
        raise ErroPatrimonio(f"Já existe um bem com a chapa {chapa}.", 409, "conflito")
    campos = {c: dados.get(c) for c in CAMPOS_EDITAVEIS if c not in ("chapa",)}
    bem = Bem(id=uuid.uuid4(), id_cliente=id_cliente, chapa=chapa, chapa_chave=chave, localizacao_id=sala.id, responsavel_id=sala.responsavel_id,
              criado_por_id=autor.id, **campos)
    sessao.add(bem)
    sessao.flush()
    registrar_evento(sessao, bem, "cadastrou", autor, texto=f"Cadastrado na sala {sala.codigo}", origem=origem, dados={"sala_id": str(sala.id), "sala": sala.codigo})
    sessao.commit()
    return obter(sessao, bem.id), True


def _exigir_editavel(bem: Bem) -> None:
    if bem.situacao == "baixado":
        raise ErroPatrimonio("O bem baixado não pode mais ser editado.", 409, "bem_baixado")


def atualizar(sessao: Session, bem_id: uuid.UUID, dados: dict[str, Any], autor: Usuario, *, origem: str | None = None) -> Bem:
    """Altera os campos enviados e grava um evento por campo que mudou."""
    bem = obter(sessao, bem_id)
    _exigir_editavel(bem)
    prefixo = dados.get("prefixo")
    dados = _normalizar({c: v for c, v in dados.items() if c in CAMPOS_EDITAVEIS})
    if dados.get("chapa"):
        dados["chapa"] = montar_chapa(sessao, prefixo, dados["chapa"])
    if "situacao" in dados:
        if dados["situacao"] not in SITUACOES_CADASTRO:
            raise ErroPatrimonio("A situação só muda para Ativo ou Em manutenção por aqui (inservível, extraviado e baixa têm fluxo próprio).")
        if bem.situacao not in SITUACOES_CADASTRO:
            raise ErroPatrimonio("Inservíveis e extraviados só voltam a Ativo pela reversão do controle total.", 409, "conflito")
    if "chapa" in dados:
        # Pode ficar sem chapa se o bem tiver número de série
        if not dados["chapa"] and not (dados.get("numero_serie") if "numero_serie" in dados else bem.numero_serie):
            raise ErroPatrimonio("Informe a chapa ou, se o bem não tem patrimônio, o número de série.")
        if dados["chapa"] and sessao.scalar(select(Bem.id).where(Bem.chapa_chave == dados["chapa"].lower(), Bem.id != bem.id)) is not None:
            raise ErroPatrimonio(f"Já existe um bem com a chapa {dados['chapa']}.", 409, "conflito")
    if "descricao" in dados and not dados["descricao"]:
        raise ErroPatrimonio("A descrição é obrigatória.")
    _validar(sessao, dados)
    for campo, novo in dados.items():
        antigo = getattr(bem, campo)
        if antigo == novo:
            continue
        registrar_evento(sessao, bem, "alterou", autor, campo=campo, anterior=antigo, novo=novo, origem=origem)
        setattr(bem, campo, novo)
        if campo == "chapa":
            bem.chapa_chave = novo.lower() if novo else None
    sessao.commit()
    return obter(sessao, bem.id)


def em_movimentacao(sessao: Session, bem_id: uuid.UUID) -> bool:
    """O bem está numa movimentação aberta (pendente ou autorizada) e ainda não foi recebido."""
    return sessao.scalar(
        select(func.count(ItemMovimentacao.id)).join(Movimentacao).where(
            ItemMovimentacao.bem_id == bem_id, ItemMovimentacao.recebido_em.is_(None), Movimentacao.status.in_(("pendente", "autorizada")))) > 0


def exigir_movimentavel(sessao: Session, bem: Bem, destino: Localizacao | None = None) -> None:
    """Regras comuns a toda mudança de local (movimentação e ajuste direto)."""
    if bem.situacao == "baixado":
        raise ErroPatrimonio(f"O bem {bem.chapa} está baixado e não pode ser movimentado.", 409, "bem_baixado")
    if bem.situacao == "extraviado":
        raise ErroPatrimonio(f"O bem {bem.chapa} está extraviado e não pode ser movimentado.", 409, "bem_extraviado")
    if bem.classificacao_pendente:
        raise ErroPatrimonio(f"O bem {bem.chapa} está com classificação pendente e não pode ser movimentado.", 409, "classificacao_pendente")
    if em_movimentacao(sessao, bem.id):
        raise ErroPatrimonio(f"O bem {bem.chapa} já está em outra movimentação em andamento.", 409, "em_movimentacao")
    if destino is not None:
        if bem.situacao == "inservivel" and not servico_localizacoes.eh_deposito_inservivel(destino):
            raise ErroPatrimonio(f"O bem inservível {bem.chapa} só pode ir para uma sala do setor \"Depósito inservível\".", 409, "destino_invalido")
        if bem.localizacao_id == destino.id:
            raise ErroPatrimonio(f"O bem {bem.chapa} já está nesta sala.", 409, "mesmo_local")


def mover_para(sessao: Session, bem: Bem, destino: Localizacao, autor: Usuario, tipo_evento: str, texto: str, dados: dict, origem: str | None = None) -> None:
    """Muda o local do bem na hora: passa a ter o responsável da sala de destino e grava o trajeto (sem commit)."""
    origem_sala = bem.localizacao
    registrar_evento(sessao, bem, tipo_evento, autor, campo="localizacao", anterior=origem_sala.codigo, novo=destino.codigo, texto=texto, origem=origem,
                     dados={**dados, "de": origem_sala.codigo, "de_id": str(origem_sala.id), "para": destino.codigo, "para_id": str(destino.id)})
    if bem.responsavel_id != destino.responsavel_id:
        registrar_evento(sessao, bem, "responsavel", autor, campo="responsavel", anterior=bem.responsavel_id, novo=destino.responsavel_id, origem=origem,
                         texto=f"Passou ao responsável da sala {destino.codigo}")
        bem.responsavel_id = destino.responsavel_id
    bem.localizacao_id = destino.id
    bem.localizacao = destino


def ajustar_local(sessao: Session, bem_id: uuid.UUID, destino_id: uuid.UUID, motivo: str, autor: Usuario, *, origem: str | None = None) -> Bem:
    """Ajuste direto do local (só o controle total; a rota confere). Motivo obrigatório e registrado no histórico."""
    if not motivo or not motivo.strip():
        raise ErroPatrimonio("Informe o motivo do ajuste de local.")
    bem = obter(sessao, bem_id)
    destino = servico_localizacoes.exigir_sala(sessao, destino_id)
    if destino.responsavel_id is None:
        raise ErroPatrimonio("A sala de destino ainda não tem setor e responsável.", 409, "sala_sem_responsavel")
    exigir_movimentavel(sessao, bem, destino)
    mover_para(sessao, bem, destino, autor, "ajustou_local", f"Ajuste direto de local: {motivo.strip()}", {"motivo": motivo.strip(), "autorizador": autor.login}, origem)
    sessao.commit()
    return obter(sessao, bem.id)


def localizar(sessao: Session, bem_id: uuid.UUID, destino_id: uuid.UUID, autor: Usuario, *, origem: str | None = None) -> Bem:
    """Levantamento inicial: informa a sala de um bem que ainda está "sem local" (quem tem Modificação pode; não precisa de aprovação).

    Só vale enquanto o bem está na sala "NECESSÁRIO ATUALIZAR"; depois disso, mudar de sala é movimentação (ou ajuste do controle total).
    """
    bem = obter(sessao, bem_id)
    if not servico_localizacoes.eh_sem_local(bem.localizacao):
        raise ErroPatrimonio(f"O bem {bem.rotulo} já tem sala: para mudar de sala, registre uma movimentação.", 409, "bem_ja_localizado")
    destino = servico_localizacoes.exigir_sala(sessao, destino_id)
    if servico_localizacoes.eh_sem_local(destino):
        raise ErroPatrimonio("Escolha a sala onde o bem está.")
    if destino.responsavel_id is None:
        raise ErroPatrimonio("A sala de destino ainda não tem setor e responsável.", 409, "sala_sem_responsavel")
    exigir_movimentavel(sessao, bem, destino)
    mover_para(sessao, bem, destino, autor, "localizou", "Localizado no levantamento inicial", {"autorizador": autor.login}, origem)
    sessao.commit()
    return obter(sessao, bem.id)


def adicionar_foto(sessao: Session, bem_id: uuid.UUID, origem_arquivo: BinaryIO, nome: str, autor: Usuario) -> Bem:
    bem = obter(sessao, bem_id)
    _exigir_editavel(bem)
    if len(bem.fotos) >= MAXIMO_FOTOS:
        raise ErroPatrimonio(f"Cada bem aceita até {MAXIMO_FOTOS} fotos.", 409, "limite_fotos")
    if not nome.lower().endswith(EXTENSOES_FOTO):
        raise ErroPatrimonio("A foto deve ser PNG ou JPG.")
    try:
        anexo = servico_anexos.guardar_arquivo(sessao, origem_arquivo, nome, "patrimonio-foto", autor.id)
    except servico_anexos.ErroAnexo as erro:
        raise ErroPatrimonio(str(erro)) from erro
    sessao.flush()
    sessao.add(FotoBem(id=uuid.uuid4(), bem_id=bem.id, anexo_id=anexo.id, ordem=len(bem.fotos)))
    registrar_evento(sessao, bem, "alterou", autor, campo="fotos", novo=nome, texto="Foto adicionada")
    sessao.commit()
    # A sessão não expira os objetos no commit: sem isto a lista de fotos já carregada voltaria sem a foto nova
    sessao.expire(bem, ["fotos"])
    return obter(sessao, bem.id)


def remover_foto(sessao: Session, bem_id: uuid.UUID, foto_id: uuid.UUID, autor: Usuario) -> Bem:
    bem = obter(sessao, bem_id)
    _exigir_editavel(bem)
    foto = next((f for f in bem.fotos if f.id == foto_id), None)
    if foto is None:
        raise ErroPatrimonio("Foto não encontrada.", 404, "nao_encontrado")
    servico_anexos.descartar(foto.anexo)
    sessao.delete(foto)
    registrar_evento(sessao, bem, "alterou", autor, campo="fotos", anterior=foto.anexo.nome_original, texto="Foto removida")
    sessao.commit()
    sessao.expire(bem, ["fotos"])
    return obter(sessao, bem.id)


def historico(sessao: Session, bem_id: uuid.UUID, campo: str | None = None) -> list[EventoPatrimonio]:
    """Linha do tempo (todos os eventos) ou só o histórico de um campo, do mais recente ao mais antigo."""
    obter(sessao, bem_id)
    consulta = select(EventoPatrimonio).where(EventoPatrimonio.bem_id == bem_id)
    if campo:
        consulta = consulta.where(EventoPatrimonio.campo == campo)
    return list(sessao.scalars(consulta.order_by(EventoPatrimonio.ocorrido_em.desc())))


def trajeto(sessao: Session, bem_id: uuid.UUID) -> list[EventoPatrimonio]:
    """Todos os locais por onde o bem passou (cadastro, movimentações e ajustes), do mais antigo ao mais recente."""
    obter(sessao, bem_id)
    return list(sessao.scalars(select(EventoPatrimonio).where(
        EventoPatrimonio.bem_id == bem_id, EventoPatrimonio.tipo.in_(("cadastrou", "moveu", "ajustou_local", "localizou", "reverteu"))).order_by(EventoPatrimonio.ocorrido_em)))
