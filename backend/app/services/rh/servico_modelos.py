# Criado por José Eduardo Santana Martins
# Este arquivo serve para os modelos editáveis do RH (resolução de nomeação, e-mail de nomeação publicada, termo de posse e boas-vindas): padrões, leitura e gravação.
"""Modelos do RH (RH > Modelos). Cada tipo tem um texto padrão criado na primeira consulta; o RH edita depois."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rh_admissao import TIPOS_MODELO, ModeloRh
from app.models.usuario import Usuario
from app.services.contratacoes.conteudo import ErroConteudo, sanitizar
from app.services.rh import rh_mascara
from app.services.servico_auditoria import auditar

PADROES: dict[str, tuple[str, str, str]] = {
    "resolucao_nomeacao": (
        "Resolução de nomeação", "",
        "<h2>RESOLUÇÃO SPI Nº #numeroresolucao, DE #anoresolucao</h2>"
        "<p>O Secretário de Parcerias em Investimentos, no uso de suas atribuições legais, resolve:</p>"
        "<p>Artigo 1º – Designar <strong>#nome</strong>, RG #rg, CPF #cpf, para exercer o cargo de <strong>#cargo</strong>, na unidade #setor, a partir de #datainicio.</p>"
        "<p>Artigo 2º – Esta resolução entra em vigor na data de sua publicação.</p>"
        "<p>São Paulo, #hoje.</p>",
    ),
    "email_nomeacao_publicada": (
        "E-mail: sua nomeação foi publicada", "Sua nomeação foi publicada",
        "<p>Olá, #nome.</p>"
        "<p>Informamos que a sua nomeação para o cargo de <strong>#cargo</strong>, na unidade #setor, foi publicada no Diário Oficial do Estado em #datapublicacao "
        "(Resolução SPI nº #numeroresolucao/#anoresolucao). O PDF da publicação segue em anexo.</p>"
        "<p>O próximo passo é a sua posse, prevista para #dataposse. A Coordenadoria de Gestão de Pessoas entrará em contato com as orientações.</p>",
    ),
    "termo_posse": (
        "Termo de posse", "",
        "<h2>TERMO DE POSSE</h2>"
        "<p>Aos #dataposse, na Secretaria de Parcerias em Investimentos, tomou posse <strong>#nome</strong>, RG #rg, CPF #cpf, no cargo de <strong>#cargo</strong>, "
        "na unidade #setor, nomeado(a) pela Resolução SPI nº #numeroresolucao/#anoresolucao, publicada no Diário Oficial do Estado em #datapublicacao.</p>"
        "<p>O(A) empossado(a) declara conhecer os deveres e as responsabilidades do cargo e assume o compromisso de cumpri-los.</p>",
    ),
    "boas_vindas": (
        "Boas-vindas ao SGI SPI", "Boas-vindas à SPI",
        "<p>Olá, #nome! Seja bem-vindo(a) à Secretaria de Parcerias em Investimentos.</p>"
        "<p>Você ocupa o cargo de <strong>#cargo</strong>, na unidade #setor. Seu login é <strong>#login</strong>.</p>"
        "<p>O primeiro passo é completar o seu cadastro: confira seus dados e, se quiser, conte um pouco sobre você na bio.</p>",
    ),
}


class ErroModelo(Exception):
    """Modelo inválido (vira 400)."""


def garantir(sessao: Session) -> None:
    """Cria os modelos padrão que ainda não existem."""
    existentes = set(sessao.scalars(select(ModeloRh.tipo)))
    for tipo in TIPOS_MODELO:
        if tipo not in existentes:
            nome, assunto, html = PADROES[tipo]
            sessao.add(ModeloRh(tipo=tipo, nome=nome, assunto=assunto, html=html))
    sessao.commit()


def listar(sessao: Session) -> list[ModeloRh]:
    garantir(sessao)
    ordem = {t: i for i, t in enumerate(TIPOS_MODELO)}
    return sorted(sessao.scalars(select(ModeloRh)), key=lambda m: ordem.get(m.tipo, 99))


def obter(sessao: Session, tipo: str) -> ModeloRh:
    garantir(sessao)
    modelo = sessao.scalar(select(ModeloRh).where(ModeloRh.tipo == tipo))
    if modelo is None:
        raise ErroModelo("Modelo não encontrado.")
    return modelo


def salvar(sessao: Session, tipo: str, assunto: str, html: str, autor: Usuario) -> ModeloRh:
    modelo = obter(sessao, tipo)
    try:
        html = sanitizar(html)
    except ErroConteudo as erro:
        raise ErroModelo(str(erro)) from erro
    if not html.strip():
        raise ErroModelo("O texto do modelo não pode ficar vazio.")
    ruins = rh_mascara.invalidos(html) + rh_mascara.invalidos(assunto)
    if ruins:
        raise ErroModelo("Placeholders não permitidos: " + ", ".join(dict.fromkeys(ruins)) + ".")
    modelo.assunto = assunto.strip()
    modelo.html = html
    modelo.atualizado_por_id = autor.id
    auditar(sessao, autor.login, "rh.modelo.salvar", modelo.nome, autor_id=autor.id, dados={"tipo": tipo})
    sessao.commit()
    return modelo


def restaurar(sessao: Session, tipo: str, autor: Usuario) -> ModeloRh:
    """Volta ao texto padrão."""
    modelo = obter(sessao, tipo)
    _, assunto, html = PADROES[tipo]
    modelo.assunto, modelo.html, modelo.atualizado_por_id = assunto, html, autor.id
    auditar(sessao, autor.login, "rh.modelo.restaurar", modelo.nome, autor_id=autor.id, dados={"tipo": tipo})
    sessao.commit()
    return modelo
