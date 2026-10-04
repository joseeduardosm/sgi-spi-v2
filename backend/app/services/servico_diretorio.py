# Criado por José Eduardo Santana Martins
# Este arquivo serve para concentrar as regras do Diretório: ramais em cartões, aniversariantes, favoritos, fotos e mural de parabéns.
"""Regras do Diretório (`/api/diretorio`).

- **Ramais:** usuários ativos com nome e ramal. A busca ignora acentos e maiúsculas (feita em Python: são poucas centenas de pessoas
  e o SQLite dos testes não tem `unaccent`). Quem está de férias aprovadas hoje ganha o selo automaticamente, calculado pela data atual.
- **Aniversariantes:** dia, semana (hoje + 6 dias) ou mês; o ano de nascimento nunca sai. Quem optou por ocultar não aparece.
- **Mural:** um recado por autor e por ano; aberto para novos recados só no dia do aniversário (depois fica só para leitura). O aniversariante é avisado pelas mensagens internas.
- **Foto:** upload (reduzida a 400 px, JPEG) ou importada do LDAP; o upload do usuário nunca é sobrescrito pelo AD.
"""

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import date
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.anexo import Anexo
from app.models.diretorio import FavoritoDiretorio, ParabensAniversario
from app.models.rh import Afastamento
from app.models.usuario import Usuario
from app.schemas.diretorio import Aniversariante, Contato, ContatoDetalhe, ContatoResumo, OpcoesFiltro, PaginaContatos, Parabens
from app.services import servico_anexos, servico_mensagens

CATEGORIA_FOTO = "usuario-foto"
LADO_FOTO = 400
TAMANHO_MAXIMO_FOTO = 5 * 1024 * 1024


class ErroDiretorio(Exception):
    """Regra do diretório violada; `status` e `codigo` seguem o contrato de erros da API."""

    def __init__(self, mensagem: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(mensagem)
        self.status, self.codigo = status, codigo


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para a busca."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c)).casefold().strip()


def foto_url(usuario: Usuario) -> str | None:
    """Caminho da foto; o `v` muda a cada troca para o navegador não usar a antiga em cache."""
    return f"/api/diretorio/fotos/{usuario.id}?v={usuario.foto_anexo_id.hex[:8]}" if usuario.foto_anexo_id else None


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def _whatsapp(celular: str) -> str:
    digitos = "".join(c for c in celular or "" if c.isdigit())
    if not digitos:
        return ""
    if len(digitos) in (10, 11) and not digitos.startswith("55"):
        digitos = "55" + digitos
    return f"https://wa.me/{digitos}"


def _local(usuario: Usuario) -> str:
    andar = (usuario.andar or "").strip()
    if andar.casefold() in ("terreo", "térreo"):
        andar = "Térreo"
    elif andar and "andar" not in andar.casefold():
        andar = f"{andar} andar"
    predio = (usuario.predio or "").strip()
    return " - ".join(p for p in (andar, predio) if p)


# ---------------------------------------------------------------------------------------------
# Ramais
# ---------------------------------------------------------------------------------------------


def _ativos_com_ramal(sessao: Session) -> list[Usuario]:
    consulta = select(Usuario).where(Usuario.ativo.is_(True), Usuario.nome_completo != "", Usuario.ramal != "")
    return list(sessao.scalars(consulta))


def _ferias_hoje(sessao: Session, ids: list[int], hoje: date) -> dict[int, tuple[date, date]]:
    """Férias aprovadas que cobrem `hoje`. Fora do período (antes ou depois) não há selo."""
    if not ids:
        return {}
    consulta = select(Afastamento.usuario_id, Afastamento.inicio, Afastamento.fim).where(
        Afastamento.tipo == "ferias", Afastamento.status == "aprovado", Afastamento.inicio <= hoje, Afastamento.fim >= hoje,
        Afastamento.usuario_id.in_(ids),
    )
    ferias: dict[int, tuple[date, date]] = {}
    for usuario_id, inicio, fim in sessao.execute(consulta):
        if usuario_id not in ferias or fim > ferias[usuario_id][1]:
            ferias[usuario_id] = (inicio, fim)
    return ferias


def _contato(u: Usuario, favoritos: set[int], ferias: dict[int, tuple[date, date]]) -> Contato:
    inicio, fim = ferias.get(u.id, (None, None))
    return Contato(
        id=u.id, nome=_nome(u), cargo=u.cargo, ramal=u.ramal, foto_url=foto_url(u), setor=u.departamento, email=u.email, celular=u.celular,
        whatsapp_url=_whatsapp(u.celular), linkedin=u.linkedin or "", andar=u.andar, predio=u.predio, local=_local(u), favorito=u.id in favoritos,
        ferias_inicio=inicio, ferias_fim=fim,
    )


def _favoritos(sessao: Session, usuario: Usuario) -> set[int]:
    return set(sessao.scalars(select(FavoritoDiretorio.favorito_id).where(FavoritoDiretorio.usuario_id == usuario.id)))


@dataclass
class FiltrosRamais:
    busca: str = ""
    setor: str | None = None
    andar: str | None = None
    predio: str | None = None
    somente_favoritos: bool = False
    em_ferias: bool = False


def listar_ramais(sessao: Session, usuario: Usuario, filtros: FiltrosRamais, pagina: int, tamanho: int, hoje: date | None = None) -> PaginaContatos:
    """Lista paginada: favoritos primeiro, depois ordem alfabética."""
    hoje = hoje or date.today()
    favoritos = _favoritos(sessao, usuario)
    pessoas = _ativos_com_ramal(sessao)
    ferias = _ferias_hoje(sessao, [p.id for p in pessoas], hoje)
    termos = normalizar(filtros.busca).split()

    def confere(p: Usuario) -> bool:
        if filtros.setor and p.departamento != filtros.setor:
            return False
        if filtros.andar and p.andar != filtros.andar:
            return False
        if filtros.predio and p.predio != filtros.predio:
            return False
        if filtros.somente_favoritos and p.id not in favoritos:
            return False
        if filtros.em_ferias and p.id not in ferias:
            return False
        palheiro = normalizar(" ".join((p.nome_completo, p.cargo, p.departamento, p.ramal, p.email, p.andar, p.predio, p.login)))
        return all(t in palheiro for t in termos)

    selecionadas = sorted((p for p in pessoas if confere(p)), key=lambda p: (p.id not in favoritos, normalizar(_nome(p))))
    inicio = (pagina - 1) * tamanho
    return PaginaContatos(
        itens=[_contato(p, favoritos, ferias) for p in selecionadas[inicio:inicio + tamanho]], total=len(selecionadas), pagina=pagina, tamanho=tamanho
    )


def opcoes_filtro(sessao: Session) -> OpcoesFiltro:
    pessoas = _ativos_com_ramal(sessao)
    def valores(campo: str) -> list[str]:
        return sorted({getattr(p, campo) for p in pessoas if getattr(p, campo)}, key=normalizar)
    return OpcoesFiltro(setores=valores("departamento"), andares=valores("andar"), predios=valores("predio"))


def _resumo(u: Usuario) -> ContatoResumo:
    return ContatoResumo(id=u.id, nome=_nome(u), cargo=u.cargo, ramal=u.ramal, foto_url=foto_url(u))


def obter_contato(sessao: Session, usuario: Usuario, contato_id: int, hoje: date | None = None) -> Usuario:
    """Usuário ativo que aparece no diretório, ou `ErroDiretorio` 404."""
    alvo = sessao.get(Usuario, contato_id)
    if alvo is None or not alvo.ativo or not alvo.nome_completo or not alvo.ramal:
        raise ErroDiretorio("Contato não encontrado.", 404, "nao_encontrado")
    return alvo


def detalhe_contato(sessao: Session, usuario: Usuario, contato_id: int, hoje: date | None = None) -> ContatoDetalhe:
    hoje = hoje or date.today()
    alvo = obter_contato(sessao, usuario, contato_id)
    base = _contato(alvo, _favoritos(sessao, usuario), _ferias_hoje(sessao, [alvo.id], hoje))
    chefe = sessao.get(Usuario, alvo.gestor_id) if alvo.gestor_id else None
    equipe = sessao.scalars(select(Usuario).where(Usuario.gestor_id == alvo.id, Usuario.ativo.is_(True)))
    return ContatoDetalhe(
        **base.model_dump(), chefia=_resumo(chefe) if chefe and chefe.ativo else None,
        equipe=sorted((_resumo(p) for p in equipe), key=lambda r: normalizar(r.nome)),
    )


def alternar_favorito(sessao: Session, usuario: Usuario, contato_id: int, favoritar: bool) -> None:
    obter_contato(sessao, usuario, contato_id)
    existe = sessao.get(FavoritoDiretorio, (usuario.id, contato_id))
    if favoritar and existe is None:
        sessao.add(FavoritoDiretorio(usuario_id=usuario.id, favorito_id=contato_id))
    elif not favoritar and existe is not None:
        sessao.delete(existe)
    sessao.commit()


def vcard(alvo: Usuario) -> str:
    """Cartão no formato vCard 3.0 (abre em celulares e no Outlook)."""
    def esc(t: str) -> str:
        return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    nome = _nome(alvo)
    linhas = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{esc(nome)}", f"N:{esc(nome)};;;;"]
    if alvo.departamento:
        linhas.append(f"ORG:Secretaria de Parcerias em Investimentos;{esc(alvo.departamento)}")
    else:
        linhas.append("ORG:Secretaria de Parcerias em Investimentos")
    if alvo.cargo:
        linhas.append(f"TITLE:{esc(alvo.cargo)}")
    if alvo.ramal:
        linhas.append(f"TEL;TYPE=WORK,VOICE:{esc(alvo.ramal)}")
    if alvo.celular:
        linhas.append(f"TEL;TYPE=CELL:{esc(alvo.celular)}")
    if alvo.email:
        linhas.append(f"EMAIL;TYPE=WORK:{esc(alvo.email)}")
    if _local(alvo):
        linhas.append(f"ADR;TYPE=WORK:;;{esc(_local(alvo))};;;;")
    linhas.append("END:VCARD")
    return "\r\n".join(linhas) + "\r\n"


# ---------------------------------------------------------------------------------------------
# Aniversariantes
# ---------------------------------------------------------------------------------------------


def data_no_ano(nascimento: date, ano: int) -> date:
    """Data do aniversário no ano; quem nasceu em 29/02 comemora em 28/02 nos anos comuns."""
    try:
        return nascimento.replace(year=ano)
    except ValueError:
        return date(ano, 2, 28)


def ocorrencia_mais_proxima(nascimento: date, hoje: date) -> date:
    """Aniversário (no ano anterior, atual ou seguinte) mais perto de hoje: define a janela do mural e o ano do recado."""
    return min((data_no_ano(nascimento, hoje.year + d) for d in (-1, 0, 1)), key=lambda x: abs((x - hoje).days))


def _proximo(nascimento: date, hoje: date) -> date:
    esta = data_no_ano(nascimento, hoje.year)
    return esta if esta >= hoje else data_no_ano(nascimento, hoje.year + 1)


def listar_aniversariantes(sessao: Session, usuario: Usuario, periodo: str, hoje: date | None = None) -> list[Aniversariante]:
    """`dia` = hoje; `semana` = hoje e os 6 dias seguintes; `mes` = todo o mês corrente (inclui dias que já passaram)."""
    hoje = hoje or date.today()
    pessoas = sessao.scalars(
        select(Usuario).where(Usuario.ativo.is_(True), Usuario.data_nascimento.is_not(None), Usuario.ocultar_aniversario.is_(False))
    )
    escolhidos: list[tuple[Usuario, date, int]] = []
    for p in pessoas:
        if periodo == "mes":
            data = data_no_ano(p.data_nascimento, hoje.year)
            if data.month == hoje.month:
                escolhidos.append((p, data, (data - hoje).days))
        else:
            data = _proximo(p.data_nascimento, hoje)
            faltam = (data - hoje).days
            if faltam <= (0 if periodo == "dia" else 6):
                escolhidos.append((p, data, faltam))
    escolhidos.sort(key=lambda t: (t[1], normalizar(_nome(t[0]))))
    ids = [p.id for p, _, _ in escolhidos]
    totais: dict[tuple[int, int], int] = {}
    meus: set[tuple[int, int]] = set()
    if ids:
        for alvo, ano, qtd in sessao.execute(
            select(ParabensAniversario.aniversariante_id, ParabensAniversario.ano, func.count()).where(ParabensAniversario.aniversariante_id.in_(ids))
            .group_by(ParabensAniversario.aniversariante_id, ParabensAniversario.ano)
        ):
            totais[(alvo, ano)] = qtd
        meus = set(sessao.execute(select(ParabensAniversario.aniversariante_id, ParabensAniversario.ano).where(
            ParabensAniversario.aniversariante_id.in_(ids), ParabensAniversario.autor_id == usuario.id)).tuples())
    resultado = []
    for p, data, faltam in escolhidos:
        ano = ocorrencia_mais_proxima(p.data_nascimento, hoje).year
        resultado.append(Aniversariante(
            id=p.id, nome=_nome(p), cargo=p.cargo, setor=p.departamento, ramal=p.ramal, email=p.email, foto_url=foto_url(p),
            dia=data.day, mes=data.month, e_hoje=faltam == 0, dias_restantes=faltam, total_parabens=totais.get((p.id, ano), 0),
            ja_parabenizei=(p.id, ano) in meus, pode_parabenizar=p.id != usuario.id and _mural_aberto(p, hoje),
        ))
    return resultado


def _mural_aberto(alvo: Usuario, hoje: date) -> bool:
    # O recado só pode ser escrito no próprio dia do aniversário (depois, o mural continua visível para leitura)
    return alvo.data_nascimento is not None and data_no_ano(alvo.data_nascimento, hoje.year) == hoje


def _aniversariante(sessao: Session, alvo_id: int) -> Usuario:
    alvo = sessao.get(Usuario, alvo_id)
    if alvo is None or not alvo.ativo or alvo.data_nascimento is None or alvo.ocultar_aniversario:
        raise ErroDiretorio("Aniversariante não encontrado.", 404, "nao_encontrado")
    return alvo


def mural(sessao: Session, usuario: Usuario, alvo_id: int, hoje: date | None = None) -> list[Parabens]:
    hoje = hoje or date.today()
    alvo = _aniversariante(sessao, alvo_id)
    ano = ocorrencia_mais_proxima(alvo.data_nascimento, hoje).year
    recados = sessao.scalars(select(ParabensAniversario).where(
        ParabensAniversario.aniversariante_id == alvo.id, ParabensAniversario.ano == ano).order_by(ParabensAniversario.criado_em))
    return [Parabens(id=r.id, autor_id=r.autor_id, autor_nome=r.autor_nome, texto=r.texto, criado_em=r.criado_em, meu=r.autor_id == usuario.id)
            for r in recados]


def parabenizar(sessao: Session, usuario: Usuario, alvo_id: int, texto: str, hoje: date | None = None) -> Parabens:
    """Grava o recado e avisa o aniversariante por mensagem interna."""
    hoje = hoje or date.today()
    alvo = _aniversariante(sessao, alvo_id)
    if alvo.id == usuario.id:
        raise ErroDiretorio("Você não pode deixar recado no seu próprio mural.")
    if not _mural_aberto(alvo, hoje):
        raise ErroDiretorio("Só é possível deixar parabéns no dia do aniversário.")
    texto = texto.strip()
    if not texto:
        raise ErroDiretorio("Escreva o recado.")
    ano = ocorrencia_mais_proxima(alvo.data_nascimento, hoje).year
    if sessao.scalar(select(ParabensAniversario.id).where(
            ParabensAniversario.aniversariante_id == alvo.id, ParabensAniversario.autor_id == usuario.id, ParabensAniversario.ano == ano)):
        raise ErroDiretorio("Você já deixou um recado para esta pessoa. Exclua o anterior para escrever outro.", 409, "conflito")
    recado = ParabensAniversario(aniversariante_id=alvo.id, autor_id=usuario.id, autor_nome=_nome(usuario), ano=ano, texto=texto)
    sessao.add(recado)
    servico_mensagens.notificar(
        sessao, [alvo.id], f"{_nome(usuario)} deixou um recado de aniversário para você", f"{texto}\n\n— {_nome(usuario)}",
        chave=f"parabens:{alvo.id}:{usuario.id}:{ano}", link="/", autor=None,
    )
    sessao.commit()
    return Parabens(id=recado.id, autor_id=usuario.id, autor_nome=recado.autor_nome, texto=texto, criado_em=recado.criado_em, meu=True)


def apagar_parabens(sessao: Session, usuario: Usuario, alvo_id: int, hoje: date | None = None) -> None:
    hoje = hoje or date.today()
    alvo = _aniversariante(sessao, alvo_id)
    ano = ocorrencia_mais_proxima(alvo.data_nascimento, hoje).year
    apagados = sessao.execute(delete(ParabensAniversario).where(
        ParabensAniversario.aniversariante_id == alvo.id, ParabensAniversario.autor_id == usuario.id, ParabensAniversario.ano == ano)).rowcount
    if not apagados:
        raise ErroDiretorio("Você não tem recado nesse mural.", 404, "nao_encontrado")
    sessao.commit()


def corpo_parabens_automatico(nome: str) -> str:
    """Texto institucional enviado no dia do aniversário."""
    return (
        f"{nome},\n\nA Secretaria de Parcerias em Investimentos parabeniza você por mais um ano de vida.\n\n"
        "Desejamos que esta data seja marcada por alegria, saúde, prosperidade e muitas realizações.\n\n"
        "Agradecemos sua dedicação e sua contribuição para o serviço público.\n\nFeliz aniversário!"
    )


def enviar_parabens_do_dia(sessao: Session, hoje: date | None = None) -> list:
    """Mensagem interna (com e-mail) para quem faz aniversário hoje. Sem repetir no mesmo dia. Devolve as mensagens criadas (já com commit)."""
    hoje = hoje or date.today()
    criadas = []
    pessoas = sessao.scalars(select(Usuario).where(
        Usuario.ativo.is_(True), Usuario.data_nascimento.is_not(None), Usuario.ocultar_aniversario.is_(False)))
    for p in pessoas:
        if data_no_ano(p.data_nascimento, hoje.year) != hoje:
            continue
        m = servico_mensagens.notificar(
            sessao, [p.id], "Feliz aniversário!", corpo_parabens_automatico(_nome(p)), chave=f"aniversario:{p.id}:{hoje.isoformat()}", link="/", email=True,
        )
        if m is not None:
            criadas.append(m)
    sessao.commit()
    return criadas


# ---------------------------------------------------------------------------------------------
# Foto e preferências
# ---------------------------------------------------------------------------------------------


def _reduzir(dados: bytes) -> bytes:
    """Recorta em quadrado, reduz a 400 px e regrava em JPEG (descarta metadados e qualquer conteúdo estranho)."""
    try:
        imagem = Image.open(BytesIO(dados))
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as erro:
        raise ErroDiretorio("O arquivo não é uma imagem válida (envie PNG ou JPG).") from erro
    saida = BytesIO()
    ImageOps.fit(imagem, (LADO_FOTO, LADO_FOTO)).save(saida, "JPEG", quality=85)
    return saida.getvalue()


def definir_foto(sessao: Session, alvo: Usuario, dados: bytes, origem: str, enviado_por_id: int | None) -> None:
    """Grava a foto do usuário (sem commit). O anexo antigo sofre exclusão lógica."""
    if len(dados) > TAMANHO_MAXIMO_FOTO:
        raise ErroDiretorio("A foto excede 5 MB.")
    if dados[:8] != b"\x89PNG\r\n\x1a\n" and dados[:3] != b"\xff\xd8\xff":
        raise ErroDiretorio("Formato não aceito. Envie PNG ou JPG.")
    anexo = servico_anexos.guardar_arquivo_gerado(sessao, _reduzir(dados), f"foto-{alvo.id}.jpg", "image/jpeg", CATEGORIA_FOTO, enviado_por_id)
    antigo = sessao.get(Anexo, alvo.foto_anexo_id) if alvo.foto_anexo_id else None
    if antigo is not None:
        servico_anexos.descartar(antigo)
    sessao.flush()
    alvo.foto_anexo_id, alvo.foto_origem = anexo.id, origem


def remover_foto(sessao: Session, alvo: Usuario) -> None:
    antigo = sessao.get(Anexo, alvo.foto_anexo_id) if alvo.foto_anexo_id else None
    if antigo is not None:
        servico_anexos.descartar(antigo)
    # Marca "upload" sem foto: o AD não volta a preencher uma foto que a pessoa removeu de propósito
    alvo.foto_anexo_id, alvo.foto_origem = None, "upload"
    sessao.commit()


def importar_foto_ldap(sessao: Session, alvo: Usuario, dados: bytes) -> bool:
    """Aplica a `thumbnailPhoto` do AD, sem tocar em foto enviada ou removida pelo próprio usuário. Devolve se houve mudança."""
    if alvo.foto_origem == "upload":
        return False
    try:
        reduzida = _reduzir(dados)
    except ErroDiretorio:
        return False  # foto inválida no AD não derruba a sincronização
    atual = sessao.get(Anexo, alvo.foto_anexo_id) if alvo.foto_anexo_id else None
    if atual is not None and atual.excluido_em is None and atual.sha256 == hashlib.sha256(reduzida).hexdigest():
        return False  # mesma foto da última sincronização: não grava de novo
    definir_foto(sessao, alvo, dados, "ldap", None)
    return True


def anexo_da_foto(sessao: Session, contato_id: int) -> Anexo:
    alvo = sessao.get(Usuario, contato_id)
    anexo = sessao.get(Anexo, alvo.foto_anexo_id) if alvo is not None and alvo.foto_anexo_id else None
    if anexo is None or anexo.excluido_em is not None:
        raise ErroDiretorio("Foto não encontrada.", 404, "nao_encontrado")
    return anexo
