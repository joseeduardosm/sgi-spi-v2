# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras da árvore de localizações do Patrimônio: salas, setor e responsável, inativação.
"""Localizações do Patrimônio.

A árvore tem até cinco níveis (prédio, andar, lado, sala e um nível reservado). A estrutura é gerada na migração; aqui ficam as salas
extras, o setor/responsável de cada sala e a inativação. O código da sala junta andar, lado e número (`05A03`, `00B15`, `-1A01`): o usuário
só digita o número, porque andar e lado vêm do nível de cima.
"""

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.patrimonio import Bem, Localizacao
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services.patrimonio.base import ErroPatrimonio, registrar_evento

PADRAO_CODIGO_SALA = re.compile(r"^-?\d{1,2}[AB]\d{2}$")
# Sala com este setor recebe os bens inservíveis
NOME_SETOR_DEPOSITO = "depósito inservível"
# Sala "NECESSÁRIO ATUALIZAR": onde ficam os bens ainda sem local (vindos do GLPI) até o levantamento dizer em que sala estão
CODIGO_SEM_LOCAL = "ATUALIZAR"


def formatar_codigo(andar: int, lado: str, numero: int) -> str:
    """Andar com dois dígitos (o subsolo, -1, fica "-1"), lado A/B e número com dois dígitos: 05A03, 00B15, -1A01."""
    return f"{andar:02d}{lado}{numero:02d}"


def listar(sessao: Session, incluir_inativas: bool = True) -> list[Localizacao]:
    """Todos os nós, ordenados por andar, lado e código (o frontend monta a árvore pelo `pai_id`)."""
    consulta = select(Localizacao).order_by(Localizacao.andar.asc().nulls_first(), Localizacao.lado.asc().nulls_first(), Localizacao.codigo.asc().nulls_first(), Localizacao.nome)
    if not incluir_inativas:
        consulta = consulta.where(Localizacao.ativo.is_(True))
    return list(sessao.scalars(consulta))


def obter(sessao: Session, localizacao_id: uuid.UUID) -> Localizacao:
    local = sessao.get(Localizacao, localizacao_id)
    if local is None:
        raise ErroPatrimonio("Localização não encontrada.", 404, "nao_encontrado")
    return local


def exigir_sala(sessao: Session, localizacao_id: uuid.UUID, *, ativa: bool = True) -> Localizacao:
    """A localização precisa ser uma sala (e estar ativa, quando se vai colocar bem nela)."""
    local = obter(sessao, localizacao_id)
    if local.tipo != "sala":
        raise ErroPatrimonio("Escolha uma sala (o bem fica sempre em uma sala).")
    if ativa and not local.ativo:
        raise ErroPatrimonio("A sala está inativa.", 409, "sala_inativa")
    return local


def eh_sem_local(sala: Localizacao) -> bool:
    """A sala é a "NECESSÁRIO ATUALIZAR": o bem que está nela ainda não foi localizado."""
    return sala.codigo == CODIGO_SEM_LOCAL


def eh_deposito_inservivel(sala: Localizacao) -> bool:
    return sala.setor is not None and sala.setor.nome.strip().lower() == NOME_SETOR_DEPOSITO


def criar_area_comum(sessao: Session, andar_id: uuid.UUID, nome: str, sigla: str = "H") -> Localizacao:
    """Cria uma área comum (hall dos elevadores, copa, escada...) direto no andar, fora da numeração A/B e sem lado.

    O código junta o andar e a sigla (`05H`, `-1H`): é único e nunca cai no padrão das salas numeradas (`05A03`); na tela aparece o nome.
    Como toda sala, precisa de setor e responsável antes do primeiro bem.
    """
    andar = obter(sessao, andar_id)
    if andar.tipo != "andar" or andar.andar is None:
        raise ErroPatrimonio("A área comum é criada dentro de um andar.")
    nome = (nome or "").strip()
    sigla = (sigla or "").strip().upper()
    if not nome or len(nome) > 200:
        raise ErroPatrimonio("Informe o nome da área comum (até 200 caracteres).")
    if not re.fullmatch(r"[A-Z]{1,4}", sigla):
        raise ErroPatrimonio("A sigla tem de 1 a 4 letras (ex.: H para o hall).")
    codigo = f"{andar.andar:02d}{sigla}"
    if sessao.scalar(select(Localizacao.id).where(Localizacao.codigo == codigo)) is not None:
        raise ErroPatrimonio(f"Já existe a sala {codigo}.", 409, "conflito")
    sala = Localizacao(id=uuid.uuid4(), pai_id=andar.id, tipo="sala", nome=nome, codigo=codigo, andar=andar.andar, lado=None, ativo=True)
    sessao.add(sala)
    sessao.commit()
    return sala


def criar_sala(sessao: Session, lado_id: uuid.UUID, numero: int) -> Localizacao:
    """Cria uma sala extra no lado informado. O código vem do andar e do lado do nível de cima."""
    lado = obter(sessao, lado_id)
    if lado.tipo != "lado" or lado.andar is None or lado.lado is None:
        raise ErroPatrimonio("A sala é criada dentro de um lado (A ou B) de um andar.")
    if not 1 <= numero <= 99:
        raise ErroPatrimonio("O número da sala vai de 1 a 99.")
    codigo = formatar_codigo(lado.andar, lado.lado, numero)
    if sessao.scalar(select(Localizacao.id).where(Localizacao.codigo == codigo)) is not None:
        raise ErroPatrimonio(f"Já existe a sala {codigo}.", 409, "conflito")
    sala = Localizacao(id=uuid.uuid4(), pai_id=lado.id, tipo="sala", nome=codigo, codigo=codigo, andar=lado.andar, lado=lado.lado, ativo=True)
    sessao.add(sala)
    sessao.commit()
    return sala


def definir_dados_sala(sessao: Session, sala_id: uuid.UUID, setor_id: int | None, responsavel_id: int | None, autor: Usuario, *, administra: bool) -> Localizacao:
    """Setor e responsável da sala.

    No primeiro cadastro de bem ali, quem tem MODIFICACAO informa os dados (só enquanto faltam); depois, só o controle total altera.
    Trocar o responsável atualiza **todos** os bens da sala de uma vez, com registro no histórico de cada um.
    """
    sala = exigir_sala(sessao, sala_id, ativa=False)
    ja_tem_dados = sala.setor_id is not None and sala.responsavel_id is not None
    if ja_tem_dados and not administra:
        raise ErroPatrimonio("Só o controle total altera o setor e o responsável de uma sala que já os tem.", 403, "acl_negado")
    if setor_id is not None and sessao.get(Setor, setor_id) is None:
        raise ErroPatrimonio("Setor não encontrado.", 404, "nao_encontrado")
    novo_responsavel = sessao.get(Usuario, responsavel_id) if responsavel_id is not None else None
    if responsavel_id is not None and novo_responsavel is None:
        raise ErroPatrimonio("Responsável não encontrado.", 404, "nao_encontrado")
    mudou_responsavel = sala.responsavel_id != responsavel_id
    sala.setor_id, sala.responsavel_id = setor_id, responsavel_id
    if mudou_responsavel:
        for bem in sessao.scalars(select(Bem).where(Bem.localizacao_id == sala.id, Bem.situacao != "baixado")):
            registrar_evento(sessao, bem, "responsavel", autor, campo="responsavel", anterior=bem.responsavel_id, novo=responsavel_id,
                             texto=f"Responsável da sala {sala.codigo} alterado")
            bem.responsavel_id = responsavel_id
    sessao.commit()
    return sala


def atualizar_sala(sessao: Session, sala_id: uuid.UUID, *, nome: str | None, ativo: bool | None) -> Localizacao:
    sala = obter(sessao, sala_id)
    if nome is not None and nome.strip():
        sala.nome = nome.strip()[:200]
    if ativo is not None:
        sala.ativo = ativo
    sessao.commit()
    return sala


def excluir_sala(sessao: Session, sala_id: uuid.UUID) -> None:
    """Sala com bens vinculados não pode ser excluída, só inativada."""
    sala = exigir_sala(sessao, sala_id, ativa=False)
    if sessao.scalar(select(func.count(Bem.id)).where(Bem.localizacao_id == sala.id)):
        raise ErroPatrimonio("A sala tem bens vinculados: só pode ser inativada.", 409, "conflito")
    sessao.delete(sala)
    sessao.commit()


def ids_da_subarvore(sessao: Session, raiz_id: uuid.UUID) -> list[uuid.UUID]:
    """Ids do nó e de todos os descendentes (para filtrar os bens de um andar ou lado)."""
    todos = {l.id: l.pai_id for l in sessao.execute(select(Localizacao.id, Localizacao.pai_id)).all()}
    resultado, pendentes = [raiz_id], [raiz_id]
    while pendentes:
        atual = pendentes.pop()
        filhos = [i for i, pai in todos.items() if pai == atual]
        resultado.extend(filhos)
        pendentes.extend(filhos)
    return resultado


def rotulo_curto(sala: Localizacao) -> str:
    """"5º andar › 05A03 — Setor Financeiro": o prédio e o lado não aparecem (o código já mostra o lado)."""
    if sala.andar is None:
        return sala.nome
    andar = "Subsolo" if sala.andar == -1 else "Térreo" if sala.andar == 0 else f"{sala.andar}º andar"
    setor = f" — {sala.setor.nome}" if sala.setor is not None else ""
    # Sala com código no padrão (05A03) mostra o código; as especiais (Inservíveis, Importado do GLPI) mostram o nome
    padrao = sala.codigo is not None and re.fullmatch(r"-?\d{1,2}[AB]\d{2}", sala.codigo) is not None
    return f"{andar} › {sala.codigo if padrao else sala.nome}{setor}"
