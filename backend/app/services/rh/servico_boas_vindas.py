# Criado por José Eduardo Santana Martins
# Este arquivo serve para as boas-vindas do primeiro acesso (aviso na tela e e-mail) e para a bio opcional da pessoa.
"""Primeiro acesso e bio (Fase 4 do RH).

- **Boas-vindas:** quem entra pela primeira vez (conta do AD ainda sem `boas_vindas_em`) vê um aviso com o texto do modelo "Boas-vindas" e recebe o mesmo texto por
  e-mail, uma única vez. Quem já usava o sistema antes foi marcado como "já viu" pela migração. Depois do aviso a tela leva ao cadastro (perfil).
- **Bio:** texto livre opcional (idade, formação, experiências...). Só entra na busca e no cartão de contato quando a pessoa libera (`bio_visivel`).
"""

from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.usuario import OrigemUsuario, Usuario
from app.schemas.rh_boas_vindas import BioLeitura, BoasVindas
from app.services import modelo_email, servico_smtp
from app.services.cliente_smtp import Mensagem
from app.services.rh import rh_mascara, servico_modelos
from app.services.rh.servico_admissao import html_blocos_texto
from app.services.servico_auditoria import auditar
from app.services.servico_smtp import SemServidorAtivo

LIMITE_BIO = 3000


def _pendente(usuario: Usuario) -> bool:
    return usuario.boas_vindas_em is None and usuario.origem in (OrigemUsuario.LDAP, OrigemUsuario.LOCAL_LDAP)


def _valores(usuario: Usuario) -> dict[str, str]:
    return {"nome": usuario.nome_completo or usuario.login, "login": usuario.login, "cargo": usuario.cargo, "setor": usuario.departamento, "linksistema": obter_configuracao().url_publica}


def consultar(sessao: Session, usuario: Usuario) -> BoasVindas:
    """O aviso de boas-vindas (se ainda for o caso). Na primeira consulta envia também o e-mail, uma vez; falha de e-mail não impede o aviso."""
    if not _pendente(usuario):
        return BoasVindas(pendente=False)
    modelo = servico_modelos.obter(sessao, "boas_vindas")
    valores = _valores(usuario)
    corpo = rh_mascara.preencher(modelo.html, valores)
    assunto = (rh_mascara.preencher(modelo.assunto or "Boas-vindas à SPI", valores)).replace("&amp;", "&")
    if usuario.boas_vindas_email_em is None and usuario.email:
        html = modelo_email.pagina(assunto, corpo, link_url=f"{obter_configuracao().url_publica}/perfil", rotulo_link="Completar meu cadastro", sobretitulo="Coordenadoria de Gestão de Pessoas")
        try:
            resultado = servico_smtp.enviar_email(sessao, Mensagem(para=[usuario.email], assunto=assunto, texto=html_blocos_texto(corpo), html=html))
            if resultado.sucesso:
                usuario.boas_vindas_email_em = agora_utc()
                sessao.commit()
        except SemServidorAtivo:
            pass
    return BoasVindas(pendente=True, titulo=assunto, html=corpo, nome=valores["nome"])


def confirmar(sessao: Session, usuario: Usuario) -> None:
    if usuario.boas_vindas_em is None:
        usuario.boas_vindas_em = agora_utc()
        auditar(sessao, usuario.login, "rh.boas_vindas.confirmar", usuario.login, autor_id=usuario.id)
        sessao.commit()


def ler_bio(usuario: Usuario) -> BioLeitura:
    return BioLeitura(bio_texto=usuario.bio_texto or "", bio_visivel=bool(usuario.bio_visivel))


def salvar_bio(sessao: Session, usuario: Usuario, texto: str, visivel: bool) -> BioLeitura:
    usuario.bio_texto, usuario.bio_visivel = texto.strip()[:LIMITE_BIO], visivel and bool(texto.strip())
    auditar(sessao, usuario.login, "rh.bio.salvar", usuario.login, f"visível={usuario.bio_visivel}", autor_id=usuario.id)
    sessao.commit()
    return ler_bio(usuario)
