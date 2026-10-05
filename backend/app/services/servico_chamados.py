# Criado por José Eduardo Santana Martins
# Este arquivo serve para abrir chamados no GLPI em nome do usuário, com os dados do cadastro dele.
"""Abertura de chamado pelo SGI.

O usuário escreve só o assunto e a descrição; o resto vem do cadastro (nome, setor, superior imediato, e-mail, telefone,
celular se houver, andar e lado). O chamado é criado no GLPI pela API REST, com o próprio usuário como solicitante
(achado pelo login, depois pelo e-mail), e termina com a assinatura "Aberto pelo SGI".
"""

from datetime import timedelta
from html import escape
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.erros import ErroApi
from app.models.integracao_glpi import ChamadoGlpi
from app.models.usuario import Usuario
from app.schemas.chamados import ChamadoAberto, DadosSolicitante, ListaChamados
from app.services import servico_integracao_glpi as integracao
from app.services.glpi.cliente_glpi import ClienteGlpi, ErroGlpi
from app.services.servico_anexos import FORMATOS_GERAIS
from app.services.servico_auditoria import auditar

# Quantos chamados cada usuário pode abrir por hora (evita enxurrada por engano ou abuso)
LIMITE_POR_HORA = 5
ASSINATURA = "Aberto pelo SGI"

# Anexos do chamado: só os tipos que o GLPI aceita enviar, conferidos pelo conteúdo (como nos anexos do SGI)
MAXIMO_ANEXOS = 5
TAMANHO_MAXIMO_ANEXO = 5 * 1024 * 1024
EXTENSOES_ANEXO = (".png", ".jpg", ".jpeg", ".pdf", ".docx", ".xlsx", ".csv")


def validar_anexos(arquivos: list[tuple[str, bytes]]) -> list[tuple[str, bytes, str]]:
    """Confere os anexos (quantidade, tipo, tamanho e assinatura do conteúdo) e devolve (nome, conteúdo, tipo MIME)."""
    if len(arquivos) > MAXIMO_ANEXOS:
        raise ErroApi(422, f"Anexe no máximo {MAXIMO_ANEXOS} arquivos.", "anexo_invalido")
    saida = []
    for nome, conteudo in arquivos:
        nome = Path(nome or "anexo").name[:120]
        extensao = Path(nome).suffix.lower()
        if extensao not in EXTENSOES_ANEXO:
            raise ErroApi(422, f"Formato não aceito ({extensao or 'sem extensão'}): envie PNG, JPG, PDF, Word (.docx), Excel (.xlsx) ou CSV.", "anexo_invalido")
        if not conteudo:
            raise ErroApi(422, f"O arquivo {nome} está vazio.", "anexo_invalido")
        if len(conteudo) > TAMANHO_MAXIMO_ANEXO:
            raise ErroApi(422, f"O arquivo {nome} passa de {TAMANHO_MAXIMO_ANEXO // (1024 * 1024)} MB.", "anexo_invalido")
        tipo, assinaturas = FORMATOS_GERAIS[extensao]
        if assinaturas and not any(conteudo.startswith(a) for a in assinaturas):
            raise ErroApi(422, f"O conteúdo de {nome} não corresponde a um arquivo {extensao[1:].upper()}.", "anexo_invalido")
        saida.append((nome, conteudo, tipo.split(";")[0]))
    return saida


def _andar_lado(andar: str, lado: str) -> str:
    """"5º andar - A": o andar (número ganha "º andar") e o lado, quando informados."""
    if andar.isdigit():
        andar = f"{andar}º andar"
    return " - ".join(p for p in (andar, lado) if p)


def dados_do_solicitante(sessao: Session, usuario: Usuario) -> DadosSolicitante:
    """Dados do cadastro do usuário que vão no chamado.

    Vale o que o usuário **informou por último**: se há alteração do perfil ainda aguardando validação da CGP, o valor
    proposto (temporário) é o usado, para o chamado sair completo mesmo no primeiro cadastro; sem proposta, vale o valor em vigor.
    Os campos que vêm de proposta ainda não validada ficam em `aguardando_validacao` (a tela e o texto do chamado avisam).
    """
    from app.services.rh.servico_cadastro import valores_pendentes  # import local: o RH importa o serviço de usuários

    propostos = valores_pendentes(sessao, usuario.id)
    aguardando: list[str] = []

    def valor(campo: str) -> str:
        if campo in propostos and str(propostos[campo] or "").strip():
            aguardando.append(campo)
            return str(propostos[campo]).strip()
        return (getattr(usuario, campo) or "").strip()

    andar, predio = valor("andar"), valor("predio")
    gestor_id = propostos["gestor_id"] if propostos.get("gestor_id") else usuario.gestor_id
    if propostos.get("gestor_id"):
        aguardando.append("gestor_id")
    superior = sessao.get(Usuario, gestor_id) if gestor_id else None
    return DadosSolicitante(
        nome=valor("nome_completo") or usuario.login,
        setor=valor("departamento"),
        superior_imediato=(superior.nome_completo or superior.login) if superior else "",
        email=valor("email"),
        telefone=valor("ramal"),
        celular=valor("celular"),
        andar_lado=_andar_lado(andar, predio),
        aguardando_validacao=sorted(set(aguardando)),
    )


def montar_conteudo(assunto: str, descricao: str, local: str, dados: DadosSolicitante, sem_cadastro: bool = False) -> str:
    """HTML do chamado no formato do formulário "Informática" do GLPI (`1) Assunto`, `2) Descrição de Problema`, `3) Local do Problema`),
    seguido dos dados do solicitante e da assinatura "Aberto pelo SGI". Todo texto digitado é escapado."""
    paragrafos = "\n".join(f"<p>{escape(linha)}</p>" for linha in descricao.splitlines() if linha.strip())
    formulario = (f"<p><b>1) Assunto</b>: {escape(assunto)}<br><b>2) Descrição de Problema</b>: {paragrafos}"
                  f"<br><b>3) Local do Problema</b>: {escape(local)}<br></p>")
    linhas = [("Nome", dados.nome), ("Setor", dados.setor), ("Superior imediato", dados.superior_imediato), ("E-mail", dados.email),
              ("Telefone", dados.telefone), ("Celular", dados.celular), ("Andar - Lado", dados.andar_lado)]
    # Celular só aparece quando preenchido; os demais campos sem valor mostram "—" para a TI ver que falta no cadastro
    tabela = "".join(f"<tr><td><b>{rotulo}</b></td><td>{escape(valor) if valor else '—'}</td></tr>" for rotulo, valor in linhas if rotulo != "Celular" or valor)
    aviso = "<p><i>Solicitante sem cadastro no GLPI: respostas por e-mail.</i></p>" if sem_cadastro else ""
    if dados.aguardando_validacao:
        aviso += "<p><i>Alguns dados do solicitante ainda aguardam validação da CGP (informados por ele, não conferidos).</i></p>"
    return f"{formulario}<hr><h3>Dados do solicitante</h3><table>{tabela}</table>{aviso}<p><i>{ASSINATURA}</i></p>"


def _exigir_limite(sessao: Session, usuario: Usuario) -> None:
    """Recusa (429) se o usuário já abriu `LIMITE_POR_HORA` chamados na última hora."""
    desde = agora_utc() - timedelta(hours=1)
    abertos = sessao.scalar(select(func.count()).select_from(ChamadoGlpi).where(ChamadoGlpi.usuario_id == usuario.id, ChamadoGlpi.aberto_em >= desde)) or 0
    if abertos >= LIMITE_POR_HORA:
        raise ErroApi(429, f"Você já abriu {LIMITE_POR_HORA} chamados na última hora. Aguarde um pouco ou acompanhe os que já abriu.", "limite_excedido")


def listar_locais(sessao: Session) -> list[tuple[int, str]]:
    """Localizações do GLPI para a pergunta "Local do Problema" (sessão rápida na API; erro do GLPI vira 502)."""
    config = integracao.obter(sessao)
    if not config.ativo or not (config.url_base and config.user_token_cifrado):
        raise ErroApi(503, "A abertura de chamados pelo SGI não está disponível no momento. Abra o chamado direto no GLPI.", "integracao_desativada")
    try:
        app_token, user_token = integracao.tokens(config)
        with ClienteGlpi(config.url_base, app_token, user_token) as glpi:
            return glpi.listar_localizacoes()
    except ErroGlpi as erro:
        raise ErroApi(502, f"Não foi possível carregar os locais agora: {erro.mensagem}", "glpi_indisponivel") from erro


def abrir(sessao: Session, usuario: Usuario, assunto: str, descricao: str, local_id: int, arquivos: list[tuple[str, bytes]] | None = None) -> ChamadoAberto:
    """Cria o chamado no GLPI como o formulário "Informática" faz: título `<prefixo> | <assunto>`, usuário como requerente, grupo atribuído,
    SLAs, localização e conteúdo `1) Assunto … 2) Descrição … 3) Local`. Falha do GLPI vira 502 (o texto não se perde: a tela continua aberta)."""
    config = integracao.obter(sessao)
    if not config.ativo or not (config.url_base and config.user_token_cifrado):
        raise ErroApi(503, "A abertura de chamados pelo SGI não está disponível no momento. Abra o chamado direto no GLPI.", "integracao_desativada")
    anexos = validar_anexos(arquivos or [])
    _exigir_limite(sessao, usuario)
    dados = dados_do_solicitante(sessao, usuario)
    falhas: list[str] = []
    try:
        app_token, user_token = integracao.tokens(config)
        with ClienteGlpi(config.url_base, app_token, user_token) as glpi:
            local = dict(glpi.listar_localizacoes()).get(local_id)
            if local is None:
                raise ErroApi(422, "Escolha um local válido.", "validacao")
            glpi_usuario = glpi.buscar_usuario(usuario.login) or glpi.buscar_usuario(dados.email, por_email=True)
            titulo = f"{config.prefixo_titulo} | {assunto}" if config.prefixo_titulo else assunto
            entrada: dict = {
                "name": titulo, "content": montar_conteudo(assunto, descricao, local, dados, sem_cadastro=glpi_usuario is None),
                "type": config.tipo_padrao, "urgency": config.urgencia_padrao, "impact": 3, "requesttypes_id": config.origem_id,
                "locations_id": local_id, "entities_id": 0,
            }
            # Como o formulário: grupo atribuído (o chamado já nasce "Em atendimento (atribuído)"), SLAs e modelo de chamado
            if config.grupo_atribuido_id:
                entrada["_groups_id_assign"] = config.grupo_atribuido_id
            if config.sla_atendimento_id:
                entrada["slas_id_tto"] = config.sla_atendimento_id
            if config.sla_solucao_id:
                entrada["slas_id_ttr"] = config.sla_solucao_id
            if config.template_id:
                entrada["tickettemplates_id"] = config.template_id
            if glpi_usuario:
                # Requerente = o próprio usuário (com aviso por e-mail ligado, como no formulário); quem "abriu" no GLPI passa a ser ele também
                entrada["_users_id_requester"] = glpi_usuario
                entrada["_users_id_requester_notif"] = {"use_notification": [1], "alternative_email": [""]}
                entrada["users_id_recipient"] = glpi_usuario
            elif dados.email:
                # Sem cadastro no GLPI: o e-mail do usuário recebe as respostas
                entrada["_users_id_requester"] = 0
                entrada["_users_id_requester_notif"] = {"use_notification": [1], "alternative_email": [dados.email]}
            try:
                numero = glpi.criar_chamado(entrada, anexos)
            except ErroGlpi:
                if not anexos:
                    raise
                # O GLPI recusou algum anexo: o chamado é aberto mesmo assim, sem eles, e a tela avisa quais não foram
                numero = glpi.criar_chamado(entrada)
                falhas = [nome for nome, _, _ in anexos]
    except ErroGlpi as erro:
        raise ErroApi(502, f"Não foi possível abrir o chamado agora: {erro.mensagem} Seu texto foi mantido; tente de novo em instantes.", "glpi_indisponivel") from erro
    url = f"{config.url_base.rstrip('/')}/front/ticket.form.php?id={numero}"
    sessao.add(ChamadoGlpi(usuario_id=usuario.id, glpi_id=numero, assunto=assunto, url=url))
    auditar(sessao, usuario.login, "chamado.abrir", f"Chamado GLPI #{numero}", f"{assunto} (local: {local}; anexos: {len(anexos) - len(falhas)}/{len(anexos)})", autor_id=usuario.id, alvo_tipo="chamado", alvo_id=str(numero))
    sessao.commit()
    return ChamadoAberto(glpi_id=numero, assunto=assunto, url=url, aberto_em=agora_utc(), anexos_enviados=len(anexos) - len(falhas), anexos_com_falha=falhas)


def listar(sessao: Session, usuario: Usuario, limite: int = 20) -> ListaChamados:
    """Últimos chamados que o usuário abriu pelo SGI."""
    linhas = sessao.scalars(select(ChamadoGlpi).where(ChamadoGlpi.usuario_id == usuario.id).order_by(ChamadoGlpi.aberto_em.desc()).limit(limite))
    return ListaChamados(itens=[ChamadoAberto(glpi_id=c.glpi_id, assunto=c.assunto, url=c.url, aberto_em=c.aberto_em) for c in linhas])
