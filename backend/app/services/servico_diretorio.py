"""
===============================================================================
ARQUIVO: servico_diretorio.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Concentrar as regras do Diretório (/api/diretorio): ramais em cartões,
aniversariantes, favoritos, curtidas, fotos e mural de parabéns.

RESUMO TÉCNICO:
Ramais: usuários ativos com nome e ramal; a busca ignora acentos e
maiúsculas e é feita em Python (são poucas centenas de pessoas e o SQLite dos
testes não tem unaccent). Quem está de férias aprovadas hoje ganha o selo.
Aniversariantes: dia, semana (hoje + 6 dias) ou mês, sem expor o ano. Mural:
um recado por autor e por ano, aberto só no dia do aniversário. Foto: upload
reduzido a 400 px em JPEG (Pillow) ou importada do LDAP; o upload do usuário
nunca é sobrescrito pelo AD (Active Directory).

FINALIDADE DE NEGÓCIO:
Substitui a antiga lista de ramais da SPI por um diretório vivo: achar um
colega, ligar, mandar WhatsApp, salvar o contato (vCard) e manter a
integração da equipe com aniversários e recados.

CONTEXTO NO SISTEMA:
Usado pelas rotas do Diretório e pela busca global (servico_busca). Lê
Usuario e Afastamento (férias do RH), grava FavoritoDiretorio, CurtidaContato
e ParabensAniversario, guarda fotos por servico_anexos e avisa pelas
notificações internas. A sincronização LDAP chama importar_foto_ldap.

===============================================================================
"""

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import date
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.banco import hoje_sao_paulo
from app.models.anexo import Anexo
from app.models.diretorio import CurtidaContato, FavoritoDiretorio, ParabensAniversario
from app.models.rh import Afastamento
from app.models.usuario import OrigemUsuario, Usuario
from app.schemas.diretorio import Aniversariante, Contato, ContatoDetalhe, ContatoResumo, OpcoesFiltro, PaginaContatos, Parabens
from app.services import servico_anexos, notificacoes

# Categoria do anexo das fotos, lado do quadrado em pixels e limite do upload.
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
    # NFKD separa a letra do acento ("é" vira "e" + acento); depois os acentos
    # (caracteres "combining") são descartados e casefold deixa tudo minúsculo.
    return "".join(c for c in unicodedata.normalize("NFKD", texto or "") if not unicodedata.combining(c)).casefold().strip()


def foto_url(usuario: Usuario) -> str | None:
    """Caminho da foto; o `v` muda a cada troca para o navegador não usar a antiga em cache."""
    return f"/api/diretorio/fotos/{usuario.id}?v={usuario.foto_anexo_id.hex[:8]}" if usuario.foto_anexo_id else None


def _nome(usuario: Usuario) -> str:
    """Nome para exibição: o nome completo ou, se faltar, o login."""
    return usuario.nome_completo or usuario.login


def _whatsapp(celular: str) -> str:
    """Link do WhatsApp (wa.me) a partir do celular; acrescenta o DDI 55 quando faltar."""
    digitos = "".join(c for c in celular or "" if c.isdigit())
    if not digitos:
        return ""
    if len(digitos) in (10, 11) and not digitos.startswith("55"):
        digitos = "55" + digitos
    return f"https://wa.me/{digitos}"


def _local(usuario: Usuario) -> str:
    """Texto "andar - prédio" do cartão (ex.: "5º andar - Bloco A", "Térreo")."""
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
    """Usuários que aparecem no diretório: ativos, com nome completo e ramal preenchidos."""
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
    # Se houver mais de um período de férias cobrindo hoje, fica o que termina depois.
    ferias: dict[int, tuple[date, date]] = {}
    for usuario_id, inicio, fim in sessao.execute(consulta):
        if usuario_id not in ferias or fim > ferias[usuario_id][1]:
            ferias[usuario_id] = (inicio, fim)
    return ferias


def _contato(u: Usuario, favoritos: set[int], ferias: dict[int, tuple[date, date]]) -> Contato:
    """Converte o usuário no cartão de contato (Contato) usado pela tela."""
    inicio, fim = ferias.get(u.id, (None, None))
    return Contato(
        id=u.id, nome=_nome(u), cargo=u.cargo, ramal=u.ramal, foto_url=foto_url(u), setor=u.departamento, email=u.email, celular=u.celular,
        whatsapp_url=_whatsapp(u.celular), linkedin=u.linkedin or "", andar=u.andar, predio=u.predio, local=_local(u), favorito=u.id in favoritos,
        ferias_inicio=inicio, ferias_fim=fim,
    )


def _favoritos(sessao: Session, usuario: Usuario) -> set[int]:
    """Ids dos colegas que o usuário marcou como favoritos."""
    return set(sessao.scalars(select(FavoritoDiretorio.favorito_id).where(FavoritoDiretorio.usuario_id == usuario.id)))


@dataclass
class FiltrosRamais:
    """Filtros da tela de ramais (busca livre, setor, andar, prédio, favoritos, férias).

    Dataclass: classe simples só com dados; o Python gera o construtor sozinho.
    """
    busca: str = ""
    setor: str | None = None
    andar: str | None = None
    predio: str | None = None
    somente_favoritos: bool = False
    em_ferias: bool = False


def listar_ramais(sessao: Session, usuario: Usuario, filtros: FiltrosRamais, pagina: int, tamanho: int, hoje: date | None = None) -> PaginaContatos:
    """Lista paginada: favoritos primeiro, depois ordem alfabética."""
    hoje = hoje or hoje_sao_paulo()
    favoritos = _favoritos(sessao, usuario)
    pessoas = _ativos_com_ramal(sessao)
    ferias = _ferias_hoje(sessao, [p.id for p in pessoas], hoje)
    termos = normalizar(filtros.busca).split()

    def confere(p: Usuario) -> bool:
        """True se a pessoa passa em todos os filtros e contém todas as palavras da busca."""
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
        # "Palheiro" = todos os campos pesquisáveis num só texto normalizado; cada
        # palavra digitada precisa aparecer em algum lugar dele.
        palheiro = normalizar(" ".join((p.nome_completo, p.cargo, p.departamento, p.ramal, p.email, p.andar, p.predio, p.login)))
        return all(t in palheiro for t in termos)

    # Ordenação: "p.id not in favoritos" é False para favoritos, e False vem antes
    # de True; dentro de cada grupo, ordem alfabética sem acentos.
    selecionadas = sorted((p for p in pessoas if confere(p)), key=lambda p: (p.id not in favoritos, normalizar(_nome(p))))
    inicio = (pagina - 1) * tamanho
    return PaginaContatos(
        itens=[_contato(p, favoritos, ferias) for p in selecionadas[inicio:inicio + tamanho]], total=len(selecionadas), pagina=pagina, tamanho=tamanho
    )


def opcoes_filtro(sessao: Session) -> OpcoesFiltro:
    """Valores distintos de setor, andar e prédio para preencher os filtros da tela."""
    pessoas = _ativos_com_ramal(sessao)
    def valores(campo: str) -> list[str]:
        return sorted({getattr(p, campo) for p in pessoas if getattr(p, campo)}, key=normalizar)
    return OpcoesFiltro(setores=valores("departamento"), andares=valores("andar"), predios=valores("predio"))


def _resumo(u: Usuario) -> ContatoResumo:
    """Versão curta do contato (usada em chefia, equipe e lista de quem curtiu)."""
    return ContatoResumo(id=u.id, nome=_nome(u), cargo=u.cargo, ramal=u.ramal, foto_url=foto_url(u))


def obter_contato(sessao: Session, usuario: Usuario, contato_id: int, hoje: date | None = None) -> Usuario:
    """Usuário ativo que aparece no diretório, ou `ErroDiretorio` 404."""
    alvo = sessao.get(Usuario, contato_id)
    if alvo is None or not alvo.ativo or not alvo.nome_completo or not alvo.ramal:
        raise ErroDiretorio("Contato não encontrado.", 404, "nao_encontrado")
    return alvo


def detalhe_contato(sessao: Session, usuario: Usuario, contato_id: int, hoje: date | None = None) -> ContatoDetalhe:
    """Cartão completo: dados do contato, chefia, equipe, biografia (se visível) e curtidas."""
    hoje = hoje or hoje_sao_paulo()
    alvo = obter_contato(sessao, usuario, contato_id)
    base = _contato(alvo, _favoritos(sessao, usuario), _ferias_hoje(sessao, [alvo.id], hoje))
    chefe = sessao.get(Usuario, alvo.gestor_id) if alvo.gestor_id else None
    # Contas locais (de sistema, como "TV TI") não são pessoas da equipe: ficam fora, como no organograma
    equipe = sessao.scalars(select(Usuario).where(Usuario.gestor_id == alvo.id, Usuario.ativo.is_(True), Usuario.origem != OrigemUsuario.LOCAL))
    return ContatoDetalhe(
        **base.model_dump(), chefia=_resumo(chefe) if chefe and chefe.ativo else None,
        equipe=sorted((_resumo(p) for p in equipe), key=lambda r: normalizar(r.nome)), bio=(alvo.bio_texto or None) if alvo.bio_visivel else None,
        **_curtidas(sessao, usuario, alvo),
    )


def _curtidas(sessao: Session, usuario: Usuario, alvo: Usuario) -> dict:
    """Total, se o usuário curtiu e, **só para o dono do cartão**, quem curtiu."""
    autores = list(sessao.scalars(select(Usuario).join(CurtidaContato, CurtidaContato.autor_id == Usuario.id).where(CurtidaContato.contato_id == alvo.id)))
    dono = usuario.id == alvo.id
    return {
        "curtidas": len(autores), "curtido": any(a.id == usuario.id for a in autores), "pode_curtir": not dono,
        "curtido_por": sorted((_resumo(a) for a in autores), key=lambda r: normalizar(r.nome)) if dono else None,
    }


def alternar_curtida(sessao: Session, usuario: Usuario, contato_id: int, curtir: bool) -> None:
    """Curtir ou descurtir o cartão de um colega (idempotente). O dono recebe aviso em janela e no sino só na primeira curtida de cada pessoa."""
    alvo = obter_contato(sessao, usuario, contato_id)
    if alvo.id == usuario.id:
        raise ErroDiretorio("Você não pode curtir o seu próprio cartão.", 400, "invalido")
    # A chave composta (contato, autor) identifica a curtida; get() procura por ela.
    existe = sessao.get(CurtidaContato, (alvo.id, usuario.id))
    if curtir and existe is None:
        sessao.add(CurtidaContato(contato_id=alvo.id, autor_id=usuario.id))
        # A chave é por pessoa: descurtir e curtir de novo não avisa outra vez
        notificacoes.notificar(
            sessao, [alvo.id], f"{_nome(usuario)} curtiu o seu cartão de contato", f"{_nome(usuario)} curtiu o seu cartão no Diretório de ramais.",
            chave=f"curtida-cartao:{alvo.id}:{usuario.id}", link="/ramais", abrir_em_janela=True, autor=None, evento="diretorio.curtida_cartao")
    elif not curtir and existe is not None:
        sessao.delete(existe)
    sessao.commit()


def alternar_favorito(sessao: Session, usuario: Usuario, contato_id: int, favoritar: bool) -> None:
    """Marca ou desmarca o colega como favorito (idempotente: repetir não muda nada)."""
    obter_contato(sessao, usuario, contato_id)
    existe = sessao.get(FavoritoDiretorio, (usuario.id, contato_id))
    if favoritar and existe is None:
        sessao.add(FavoritoDiretorio(usuario_id=usuario.id, favorito_id=contato_id))
    elif not favoritar and existe is not None:
        sessao.delete(existe)
    sessao.commit()


def vcard(alvo: Usuario) -> str:
    """Cartão no formato vCard 3.0 (abre em celulares e no Outlook)."""
    # Escapa os caracteres especiais do formato vCard (barra invertida, ponto e vírgula, vírgula e quebra de linha).
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
    """Próximo aniversário a partir de hoje (o deste ano, se ainda não passou; senão o do ano que vem)."""
    esta = data_no_ano(nascimento, hoje.year)
    return esta if esta >= hoje else data_no_ano(nascimento, hoje.year + 1)


def listar_aniversariantes(sessao: Session, usuario: Usuario, periodo: str, hoje: date | None = None) -> list[Aniversariante]:
    """`dia` = hoje; `semana` = hoje e os 6 dias seguintes; `mes` = todo o mês corrente (inclui dias que já passaram)."""
    hoje = hoje or hoje_sao_paulo()
    pessoas = sessao.scalars(
        select(Usuario).where(Usuario.ativo.is_(True), Usuario.data_nascimento.is_not(None), Usuario.ocultar_aniversario.is_(False))
    )
    escolhidos: list[tuple[Usuario, date, int]] = []
    # "mes": todos do mês corrente, inclusive quem já fez aniversário (dias negativos).
    # "dia"/"semana": próximo aniversário daqui a 0 dias, ou até 6 dias.
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
    # Duas consultas para a tela: total de recados por (aniversariante, ano) e em
    # quais murais o usuário já deixou recado.
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
    """Aniversariante visível (ativo, com data e sem opção de ocultar), ou 404."""
    alvo = sessao.get(Usuario, alvo_id)
    if alvo is None or not alvo.ativo or alvo.data_nascimento is None or alvo.ocultar_aniversario:
        raise ErroDiretorio("Aniversariante não encontrado.", 404, "nao_encontrado")
    return alvo


def mural(sessao: Session, usuario: Usuario, alvo_id: int, hoje: date | None = None) -> list[Parabens]:
    """Recados do mural do aniversário mais próximo (o ano é o dessa ocorrência)."""
    hoje = hoje or hoje_sao_paulo()
    alvo = _aniversariante(sessao, alvo_id)
    ano = ocorrencia_mais_proxima(alvo.data_nascimento, hoje).year
    recados = sessao.scalars(select(ParabensAniversario).where(
        ParabensAniversario.aniversariante_id == alvo.id, ParabensAniversario.ano == ano).order_by(ParabensAniversario.criado_em))
    return [Parabens(id=r.id, autor_id=r.autor_id, autor_nome=r.autor_nome, texto=r.texto, criado_em=r.criado_em, meu=r.autor_id == usuario.id)
            for r in recados]


def parabenizar(sessao: Session, usuario: Usuario, alvo_id: int, texto: str, hoje: date | None = None) -> Parabens:
    """Grava o recado e avisa o aniversariante por mensagem interna."""
    hoje = hoje or hoje_sao_paulo()
    alvo = _aniversariante(sessao, alvo_id)
    # Validações: não escrever no próprio mural, só no dia do aniversário, texto
    # não vazio e um recado por autor e por ano.
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
    notificacoes.notificar(
        sessao, [alvo.id], f"{_nome(usuario)} deixou um recado de aniversário para você", f"{texto}\n\n— {_nome(usuario)}",
        chave=f"parabens:{alvo.id}:{usuario.id}:{ano}", link="/", autor=None, evento="diretorio.recado_aniversario")
    sessao.commit()
    return Parabens(id=recado.id, autor_id=usuario.id, autor_nome=recado.autor_nome, texto=texto, criado_em=recado.criado_em, meu=True)


def apagar_parabens(sessao: Session, usuario: Usuario, alvo_id: int, hoje: date | None = None) -> None:
    """Apaga o recado do próprio usuário no mural do ano corrente do aniversário."""
    hoje = hoje or hoje_sao_paulo()
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
        "Feliz aniversário! 🎉\n\n"
        "A Secretaria de Parcerias em Investimentos deseja a você um novo ciclo repleto de saúde, alegrias e realizações pessoais e profissionais.\n\n"
        "Agradecemos por fazer parte da nossa equipe e contribuir com seu trabalho e dedicação.\n\n"
        "Que seu dia seja especial e que não faltem motivos para celebrar!\n\n"
        "Secretaria de Parcerias em Investimentos - SPI"
    )


def enviar_parabens_do_dia(sessao: Session, hoje: date | None = None) -> list:
    """Mensagem interna (com e-mail) para quem faz aniversário hoje. Sem repetir no mesmo dia. Devolve as mensagens criadas (já com commit)."""
    hoje = hoje or hoje_sao_paulo()
    criadas = []
    # Executado pela tarefa diária de notificações. A chave com a data impede
    # mandar duas vezes no mesmo dia (notificar devolve None se a chave já existe).
    pessoas = sessao.scalars(select(Usuario).where(
        Usuario.ativo.is_(True), Usuario.data_nascimento.is_not(None), Usuario.ocultar_aniversario.is_(False)))
    for p in pessoas:
        if data_no_ano(p.data_nascimento, hoje.year) != hoje:
            continue
        m = notificacoes.notificar(
            sessao, [p.id], "Feliz aniversário! 🎉", corpo_parabens_automatico(_nome(p)), chave=f"aniversario:{p.id}:{hoje.isoformat()}", link="/",
            evento="diretorio.feliz_aniversario",
            # Modal na próxima vez que a pessoa abre o sistema e e-mail sempre, sem depender da preferência de canais
            abrir_em_janela=True, forcar_email=True)
        if m is not None:
            criadas.append(m)
    sessao.commit()
    return criadas


# ---------------------------------------------------------------------------------------------
# Foto e preferências
# ---------------------------------------------------------------------------------------------


def _reduzir(dados: bytes) -> bytes:
    """Recorta em quadrado, reduz a 400 px e regrava em JPEG (descarta metadados e qualquer conteúdo estranho)."""
    # Pillow (PIL): exif_transpose corrige a rotação de fotos de celular e
    # convert("RGB") tira transparência, que o JPEG não aceita.
    try:
        imagem = Image.open(BytesIO(dados))
        imagem = ImageOps.exif_transpose(imagem).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as erro:
        raise ErroDiretorio("O arquivo não é uma imagem válida (envie PNG ou JPG).") from erro
    saida = BytesIO()
    # ImageOps.fit recorta o centro em quadrado e redimensiona para 400 x 400.
    ImageOps.fit(imagem, (LADO_FOTO, LADO_FOTO)).save(saida, "JPEG", quality=85)
    return saida.getvalue()


def definir_foto(sessao: Session, alvo: Usuario, dados: bytes, origem: str, enviado_por_id: int | None) -> None:
    """Grava a foto do usuário (sem commit). O anexo antigo sofre exclusão lógica."""
    if len(dados) > TAMANHO_MAXIMO_FOTO:
        raise ErroDiretorio("A foto excede 5 MB.")
    # Confere a "assinatura" dos primeiros bytes: PNG ou JPEG verdadeiros.
    if dados[:8] != b"\x89PNG\r\n\x1a\n" and dados[:3] != b"\xff\xd8\xff":
        raise ErroDiretorio("Formato não aceito. Envie PNG ou JPG.")
    anexo = servico_anexos.guardar_arquivo_gerado(sessao, _reduzir(dados), f"foto-{alvo.id}.jpg", "image/jpeg", CATEGORIA_FOTO, enviado_por_id)
    antigo = sessao.get(Anexo, alvo.foto_anexo_id) if alvo.foto_anexo_id else None
    if antigo is not None:
        servico_anexos.descartar(antigo)
    # flush grava o novo anexo no banco (sem commit) antes de apontar o usuário para ele.
    sessao.flush()
    alvo.foto_anexo_id, alvo.foto_origem = anexo.id, origem


def remover_foto(sessao: Session, alvo: Usuario) -> None:
    """Remove a foto do usuário (o anexo sofre exclusão lógica) e grava na hora."""
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
    # sha256 é a "impressão digital" do arquivo: igual significa a mesma foto.
    if atual is not None and atual.excluido_em is None and atual.sha256 == hashlib.sha256(reduzida).hexdigest():
        return False  # mesma foto da última sincronização: não grava de novo
    definir_foto(sessao, alvo, dados, "ldap", None)
    return True


def anexo_da_foto(sessao: Session, contato_id: int) -> Anexo:
    """Anexo da foto do contato, para a rota que serve a imagem; 404 se não houver."""
    alvo = sessao.get(Usuario, contato_id)
    anexo = sessao.get(Anexo, alvo.foto_anexo_id) if alvo is not None and alvo.foto_anexo_id else None
    if anexo is None or anexo.excluido_em is not None:
        raise ErroDiretorio("Foto não encontrada.", 404, "nao_encontrado")
    return anexo
