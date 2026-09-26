# Criado por José Eduardo Santana Martins
# Este arquivo serve para enviar os e-mails do contrato à equipe e ao preposto (diário de bordo e medição).
"""E-mails do contrato à equipe de gestão/fiscalização e aos prepostos da contratada.

- **Ocorrência do diário de bordo:** relato, data, quem registrou e se haverá glosa (itens e quantidades).
- **Medição concluída:** memória de cálculo e diário do período em PDF, pedindo a emissão da nota fiscal
  em até 48 horas.

Os envios rodam em segundo plano (depois da resposta da API), com sessão própria, e gravam o resultado
(destinatários, sucesso ou erro) para a tela mostrar e permitir reenviar. As respostas vão para a equipe
(Reply-To), nunca para a caixa de envio do servidor SMTP.
"""

import uuid
from datetime import timedelta
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import FabricaSessao, agora_utc
from app.core.configuracao import obter_configuracao
from app.models.contratos import Competencia, Contrato, OcorrenciaDiario
from app.models.usuario import Usuario
from app.services import servico_anexos, servico_smtp
from app.services.cliente_smtp import AnexoEmail, Mensagem, ResultadoSmtp
from app.services.contratos import servico_diario
from app.services.contratos.documentos_execucao import PAPEIS, data_hora, moeda, quantidade
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado, SemPermissaoContrato
from app.services.contratos.servico_contratos import designacoes_vigentes, exigir_edicao, obter_contrato
from app.services.servico_smtp import SemServidorAtivo

PRAZO_NOTA_FISCAL = timedelta(hours=48)


def emails_da_equipe(sessao: Session, contrato: Contrato) -> list[str]:
    """E-mails dos integrantes vigentes da equipe (usados como destinatários e como Reply-To)."""
    ids = {d.usuario_id for d in designacoes_vigentes(contrato)}
    if not ids:
        return []
    return _unicos(u.email for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids))) if u.email)


def emails_dos_prepostos(contrato: Contrato) -> list[str]:
    """E-mails dos prepostos ativos da empresa contratada."""
    return _unicos(p.email for p in contrato.empresa.prepostos if p.ativo and p.email)


def destinatarios(sessao: Session, contrato: Contrato) -> list[str]:
    """Equipe vigente + prepostos ativos, sem repetição."""
    return _unicos([*emails_da_equipe(sessao, contrato), *emails_dos_prepostos(contrato)])


def _unicos(emails) -> list[str]:
    """Remove repetidos (sem diferenciar maiúsculas), mantendo a ordem."""
    vistos, lista = set(), []
    for email in emails:
        chave = email.strip().lower()
        if chave and chave not in vistos:
            vistos.add(chave)
            lista.append(email.strip())
    return lista


def _enviar(
    sessao: Session, contrato: Contrato, assunto: str, texto: str, html: str, anexos: list[AnexoEmail] | None = None,
    para: list[str] | None = None, cc: list[str] | None = None,
) -> tuple[list[str], ResultadoSmtp]:
    """Envia pelo servidor SMTP ativo; sem destinatários ou sem servidor, devolve falha com a explicação.

    Sem `para`, vai à equipe vigente e aos prepostos ativos. Devolve todos os destinatários (Para + Cc).
    """
    para = _unicos(para if para is not None else destinatarios(sessao, contrato))
    cc = [e for e in _unicos(cc or []) if e.lower() not in {p.lower() for p in para}]
    todos = [*para, *cc]
    if not para:
        return todos, ResultadoSmtp(False, 0, "Nenhum destinatário com e-mail: cadastre o e-mail dos usuários (perfil) e dos prepostos.")
    mensagem = Mensagem(para=para, cc=cc, assunto=assunto, texto=texto, html=html, responder_para=emails_da_equipe(sessao, contrato),
                        anexos=anexos or [])
    try:
        return todos, servico_smtp.enviar_email(sessao, mensagem)
    except SemServidorAtivo as erro:
        return todos, ResultadoSmtp(False, 0, str(erro))


def _link(contrato: Contrato, competencia: Competencia, etapa: str) -> str:
    """Link direto para a etapa da competência no sistema."""
    base = obter_configuracao().url_publica.rstrip("/")
    return f"{base}/contratos/{contrato.id}/execucao/{competencia.identificador}?etapa={etapa}"


def _assunto_competencia(contrato: Contrato, competencia: Competencia, texto: str) -> str:
    """Padrão "Contrato NNN/AAAA - MM/AAAA - texto" (diferença de reajuste usa o rótulo)."""
    rotulo = f"{competencia.competencia:%m/%Y}" if competencia.tipo == "regular" and not competencia.parte else competencia.numero_competencia
    return f"Contrato {contrato.numero} - {rotulo} - {texto}"


def _gravar_email(competencia: Competencia, prefixo: str, para: list[str], resultado: ResultadoSmtp) -> None:
    setattr(competencia, f"{prefixo}_enviado_em", agora_utc())
    setattr(competencia, f"{prefixo}_ok", resultado.sucesso)
    setattr(competencia, f"{prefixo}_destinatarios", para)
    setattr(competencia, f"{prefixo}_erro", None if resultado.sucesso else resultado.mensagem)


# --- Nota fiscal juntada e retenção conferida ------------------------------------------------------

def mensagem_nf(contrato: Contrato, competencia: Competencia) -> tuple[str, str, str]:
    """E-mail ao Financeiro: "Foi juntada a nota fiscal para conferência de tributação pelo setor competente"."""
    link = _link(contrato, competencia, "retencao")
    assunto = _assunto_competencia(contrato, competencia, "Nota fiscal anexada no sistema")
    notas = [[f"NF {competencia.nf_numero}", moeda(competencia.nf_valor_bruto)]]
    if competencia.nf_adicional_valor_bruto is not None:
        notas.append([f"NF adicional {competencia.nf_adicional_numero}", moeda(competencia.nf_adicional_valor_bruto)])
    texto = "\n".join([
        "Foi juntada a nota fiscal para conferência de tributação pelo setor competente:",
        link,
        "",
        f"Contrato: {contrato.numero}{' — ' + contrato.apelido if contrato.apelido else ''}",
        f"Contratada: {contrato.empresa.razao_social}",
        f"Competência: {competencia.numero_competencia}",
        *[f"{n}: {v}" for n, v in notas],
    ])
    html = _html(assunto, [
        "<p>Foi juntada a nota fiscal para conferência de tributação pelo setor competente:</p>",
        f"<p><a href=\"{escape(link)}\" style=\"display:inline-block;padding:10px 16px;background:#b0222e;color:#fff;border-radius:6px;"
        f"text-decoration:none;font-weight:bold\">Abrir a retenção de tributos</a><br><small>{escape(link)}</small></p>",
        _tabela_html(["Campo", "Valor"], [
            ["Contrato", contrato.numero + (f" — {contrato.apelido}" if contrato.apelido else "")],
            ["Contratada", contrato.empresa.razao_social],
            ["Competência", competencia.numero_competencia],
            *notas,
        ]),
    ])
    return assunto, texto, html


def notificar_nf(competencia_id: uuid.UUID) -> None:
    """E-mail da NF juntada: Para = Financeiro, Cc = equipe (segundo plano, sessão própria)."""
    from app.services.contratos.servico_retencao import usuarios_financeiro

    with FabricaSessao() as sessao:
        competencia = sessao.get(Competencia, competencia_id)
        if competencia is None or competencia.nf_concluida_em is None:
            return
        contrato = obter_contrato(sessao, competencia.contrato_id)
        competencia = next(c for c in contrato.competencias if c.id == competencia_id)
        financeiro = _unicos(u.email for u in usuarios_financeiro(sessao) if u.email)
        assunto, texto, html = mensagem_nf(contrato, competencia)
        if not financeiro:
            para, resultado = emails_da_equipe(sessao, contrato), ResultadoSmtp(
                False, 0, f"Nenhum usuário do Financeiro com e-mail (setor \"{obter_configuracao().setor_financeiro}\" e filhos): "
                "inclua os membros em Setores ou ajuste o Departamento no perfil.")
        else:
            para, resultado = _enviar(sessao, contrato, assunto, texto, html, para=financeiro, cc=emails_da_equipe(sessao, contrato))
        _gravar_email(competencia, "email_nf", para, resultado)
        sessao.commit()


def mensagem_retencao(contrato: Contrato, competencia: Competencia) -> tuple[str, str, str]:
    """E-mail à equipe: retenções conferidas, com o link para a próxima etapa."""
    # Próxima etapa em aberto (CADIN/checklist, se ainda pendentes; senão, o consolidado)
    link = _link(contrato, competencia, competencia.etapa_atual)
    assunto = _assunto_competencia(contrato, competencia, "Retenções tributárias conferidas")
    tributos = ("ir", "inss", "iss", "pis", "cofins", "csll")
    linhas = []
    for prefixo, rotulo, bruto in (("nf_", f"NF {competencia.nf_numero}", competencia.nf_valor_bruto),
                                   ("nf_adicional_", f"NF adicional {competencia.nf_adicional_numero}", competencia.nf_adicional_valor_bruto)):
        if bruto is None:
            continue
        retido = sum((getattr(competencia, f"{prefixo}retencao_{t}") or 0 for t in tributos), 0)
        detalhe = ", ".join(f"{t.upper()} {moeda(getattr(competencia, f'{prefixo}retencao_{t}'))}" for t in tributos
                            if getattr(competencia, f"{prefixo}retencao_{t}"))
        linhas.append([rotulo, moeda(bruto), detalhe or "sem retenções", moeda(bruto - retido)])
    texto = "\n".join([
        f"As retenções tributárias da competência {competencia.numero_competencia} do contrato {contrato.numero} já foram conferidas "
        f"e salvas no sistema por {competencia.retencao_por_nome} em {data_hora(competencia.retencao_concluida_em)}.",
        "",
        *[f"{n}: bruto {b} · retenções: {r} · líquido {l}" for n, b, r, l in linhas],
        "",
        f"Próxima etapa: {link}",
    ])
    html = _html(assunto, [
        f"<p>As retenções tributárias já foram conferidas e salvas no sistema por <b>{escape(competencia.retencao_por_nome)}</b> em "
        f"{escape(data_hora(competencia.retencao_concluida_em))}.</p>",
        _tabela_html(["Nota", "Bruto", "Retenções", "Líquido a pagar"], linhas),
        f"<p><a href=\"{escape(link)}\" style=\"display:inline-block;padding:10px 16px;background:#b0222e;color:#fff;border-radius:6px;"
        f"text-decoration:none;font-weight:bold\">Ir para a próxima etapa</a><br><small>{escape(link)}</small></p>",
    ])
    return assunto, texto, html


def notificar_retencao(competencia_id: uuid.UUID) -> None:
    """E-mail da retenção conferida: Para = equipe (segundo plano, sessão própria)."""
    with FabricaSessao() as sessao:
        competencia = sessao.get(Competencia, competencia_id)
        if competencia is None or competencia.retencao_concluida_em is None:
            return
        contrato = obter_contrato(sessao, competencia.contrato_id)
        competencia = next(c for c in contrato.competencias if c.id == competencia_id)
        assunto, texto, html = mensagem_retencao(contrato, competencia)
        para, resultado = _enviar(sessao, contrato, assunto, texto, html, para=emails_da_equipe(sessao, contrato))
        _gravar_email(competencia, "email_retencao", para, resultado)
        sessao.commit()


def exigir_reenvio(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, autor: Usuario, tipo: str) -> None:
    """Reenvio do e-mail da NF (quem edita o contrato) ou da retenção (quem pode conferir), só depois da etapa feita."""
    from app.services.contratos.servico_retencao import pode_conferir

    contrato = obter_contrato(sessao, contrato_id)
    competencia = next((c for c in contrato.competencias if c.id == competencia_id), None)
    if competencia is None:
        raise RegistroNaoEncontrado("Competência")
    if tipo == "nf":
        exigir_edicao(sessao, contrato, autor)
        if competencia.nf_concluida_em is None:
            raise ErroRegraContrato("O e-mail da nota fiscal só é enviado depois de juntada a nota.")
    else:
        if not pode_conferir(sessao, contrato, autor):
            raise SemPermissaoContrato("Somente o Financeiro, a equipe do contrato ou o SuperRoot reenviam este e-mail.")
        if competencia.retencao_concluida_em is None:
            raise ErroRegraContrato("O e-mail da retenção só é enviado depois de conferidas as retenções.")


def _html(titulo: str, blocos: list[str]) -> str:
    """Corpo HTML simples (tabelas inline, sem imagens), legível em qualquer cliente de e-mail."""
    corpo = "".join(blocos)
    return (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#32383f;max-width:720px\">"
        f"<h2 style=\"color:#b0222e;font-size:18px;margin:0 0 12px\">{escape(titulo)}</h2>{corpo}"
        "<p style=\"color:#8e99a6;font-size:12px;margin-top:24px\">Mensagem automática do portal Contratos SPI. "
        "Para responder, use \"Responder a todos\": a resposta vai para a equipe do contrato.</p></div>"
    )


def _tabela_html(cabecalho: list[str], linhas: list[list[str]]) -> str:
    th = "".join(f"<th style=\"text-align:left;padding:6px 8px;background:#f6e7e8\">{escape(c)}</th>" for c in cabecalho)
    tr = "".join("<tr>" + "".join(f"<td style=\"padding:6px 8px;border-top:1px solid #eee\">{escape(v)}</td>" for v in linha) + "</tr>" for linha in linhas)
    return f"<table style=\"border-collapse:collapse;margin:8px 0 12px\"><tr>{th}</tr>{tr}</table>"


# --- Ocorrência do diário de bordo ---------------------------------------------------------------

def mensagem_ocorrencia(contrato: Contrato, ocorrencia: OcorrenciaDiario) -> tuple[str, str, str]:
    """Assunto, texto e HTML do e-mail de uma ocorrência."""
    assunto = f"[Diário de bordo] Contrato {contrato.numero} — ocorrência de {ocorrencia.data_ocorrencia:%d/%m/%Y}"
    papel = PAPEIS.get(ocorrencia.registrada_por_papel, "")
    autor = ocorrencia.registrada_por_nome + (f" ({papel})" if papel else "")
    competencia = servico_diario.competencia_da_data(contrato, ocorrencia.data_ocorrencia)
    glosas = [[g.descricao_item, quantidade(g.quantidade)] for g in ocorrencia.glosas]
    aviso = (
        f"A medição da competência {competencia.numero_competencia} já foi concluída: a glosa só será aplicada se a medição for reaberta."
        if ocorrencia.possui_glosa and competencia and competencia.medicao_concluida_em else ""
    )
    linhas_texto = [
        f"Contrato: {contrato.numero}{' — ' + contrato.apelido if contrato.apelido else ''}",
        f"Contratada: {contrato.empresa.razao_social}",
        f"Data da ocorrência: {ocorrencia.data_ocorrencia:%d/%m/%Y}",
        f"Registrada por: {autor} em {data_hora(ocorrencia.criado_em)}",
        "",
        "Ocorrência:",
        ocorrencia.descricao,
        "",
        f"Haverá glosa: {'Sim' if ocorrencia.possui_glosa else 'Não'}",
        *[f"  - {item}: {qtd}" for item, qtd in glosas],
    ]
    if competencia and ocorrencia.possui_glosa:
        linhas_texto.append(f"Competência afetada: {competencia.numero_competencia}")
    if aviso:
        linhas_texto += ["", aviso]
    blocos = [
        _tabela_html(["Campo", "Valor"], [
            ["Contrato", contrato.numero + (f" — {contrato.apelido}" if contrato.apelido else "")],
            ["Contratada", contrato.empresa.razao_social],
            ["Data da ocorrência", f"{ocorrencia.data_ocorrencia:%d/%m/%Y}"],
            ["Registrada por", f"{autor} em {data_hora(ocorrencia.criado_em)}"],
        ]),
        f"<p><b>Ocorrência</b><br>{escape(ocorrencia.descricao).replace(chr(10), '<br>')}</p>",
        f"<p><b>Haverá glosa:</b> {'Sim' if ocorrencia.possui_glosa else 'Não'}"
        + (f" (competência {escape(competencia.numero_competencia)})" if competencia and ocorrencia.possui_glosa else "") + "</p>",
    ]
    if glosas:
        blocos.append(_tabela_html(["Item", "Quantidade glosada"], glosas))
    if aviso:
        blocos.append(f"<p style=\"color:#7a2129\">{escape(aviso)}</p>")
    return assunto, "\n".join(linhas_texto), _html(f"Diário de bordo — contrato {contrato.numero}", blocos)


def notificar_ocorrencia(ocorrencia_id: uuid.UUID) -> None:
    """Envia o e-mail da ocorrência e grava o resultado (roda em segundo plano, com sessão própria)."""
    with FabricaSessao() as sessao:
        ocorrencia = sessao.get(OcorrenciaDiario, ocorrencia_id)
        if ocorrencia is None:
            return
        contrato = obter_contrato(sessao, ocorrencia.contrato_id)
        assunto, texto, html = mensagem_ocorrencia(contrato, ocorrencia)
        para, resultado = _enviar(sessao, contrato, assunto, texto, html)
        ocorrencia.email_enviado_em = agora_utc()
        ocorrencia.email_ok = resultado.sucesso
        ocorrencia.email_destinatarios = para
        ocorrencia.email_erro = None if resultado.sucesso else resultado.mensagem
        sessao.commit()


# --- Medição concluída ---------------------------------------------------------------------------

def mensagem_medicao(contrato: Contrato, competencia: Competencia, enviado_em) -> tuple[str, str, str]:
    """Assunto, texto e HTML do e-mail da medição concluída (pede a NF em até 48 h)."""
    from app.services.contratos.servico_competencias import saldos_da_medicao, total_medido

    rotulo = competencia.numero_competencia
    limite = enviado_em + PRAZO_NOTA_FISCAL
    total = total_medido(competencia)
    saldos = saldos_da_medicao(contrato, competencia)
    itens = [
        [i.descricao, quantidade(i.quantidade_medida), quantidade(saldos[i.id].glosas), moeda(i.quantidade_medida * i.valor_unitario)]
        for i in competencia.itens
    ]
    assunto = f"Contrato {contrato.numero} — medição {rotulo} concluída: emitir nota fiscal"
    pedido = (
        f"Solicitamos à {contrato.empresa.razao_social} a emissão da nota fiscal com base nesta medição, "
        f"no valor de {moeda(total)}, em até 48 horas (até {data_hora(limite)})."
    )
    texto = "\n".join([
        f"Contrato: {contrato.numero}{' — ' + contrato.apelido if contrato.apelido else ''}",
        f"Contratada: {contrato.empresa.razao_social}",
        f"Competência: {rotulo} (período {competencia.periodo_inicio:%d/%m/%Y} a {competencia.periodo_fim:%d/%m/%Y})",
        f"Total medido: {moeda(total)}",
        "",
        pedido,
        "",
        "Itens medidos (quantidade medida · glosa no período · subtotal):",
        *[f"  - {d}: {m} · glosa {g} · {s}" for d, m, g, s in itens],
        "",
        "Anexos: memória de cálculo da medição e diário de bordo do período (PDF).",
    ])
    html = _html(f"Medição {rotulo} concluída — contrato {contrato.numero}", [
        _tabela_html(["Campo", "Valor"], [
            ["Contrato", contrato.numero + (f" — {contrato.apelido}" if contrato.apelido else "")],
            ["Contratada", contrato.empresa.razao_social],
            ["Competência", f"{rotulo} ({competencia.periodo_inicio:%d/%m/%Y} a {competencia.periodo_fim:%d/%m/%Y})"],
            ["Total medido", moeda(total)],
        ]),
        f"<p style=\"background:#fff8e6;border-left:3px solid #e0a526;padding:10px 12px\"><b>{escape(pedido)}</b></p>",
        _tabela_html(["Item", "Medido", "Glosa no período", "Subtotal"], itens),
        "<p>Anexos: memória de cálculo da medição e diário de bordo do período (PDF).</p>",
    ])
    return assunto, texto, html


def anexos_medicao(contrato: Contrato, competencia: Competencia) -> list[AnexoEmail]:
    """Memória de cálculo (última versão) e diário de bordo do período da competência."""
    anexos = []
    if competencia.memorias:
        memoria = competencia.memorias[-1]
        anexos.append(AnexoEmail(f"memoria_medicao_{contrato.numero.replace('/', '_')}_{competencia.identificador}.pdf",
                                 servico_anexos.caminho(memoria.anexo).read_bytes()))
    diario = servico_diario.gerar_pdf(contrato, competencia.periodo_inicio, competencia.periodo_fim)
    anexos.append(AnexoEmail(f"diario_de_bordo_{contrato.numero.replace('/', '_')}_{competencia.identificador}.pdf", diario))
    return anexos


def exigir_reenvio_medicao(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, autor: Usuario) -> None:
    """Reenvio: quem pode editar o contrato, e só com a medição concluída."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    competencia = next((c for c in contrato.competencias if c.id == competencia_id), None)
    if competencia is None:
        raise RegistroNaoEncontrado("Competência")
    if competencia.medicao_concluida_em is None:
        raise ErroRegraContrato("O e-mail da medição só é enviado depois de concluída a medição.")


def exigir_reenvio_ocorrencia(sessao: Session, contrato_id: uuid.UUID, ocorrencia_id: uuid.UUID, autor: Usuario) -> None:
    """Reenvio do e-mail de uma ocorrência: quem pode editar o contrato."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    servico_diario.obter_ocorrencia(contrato, ocorrencia_id)


def notificar_medicao(competencia_id: uuid.UUID) -> None:
    """Envia o e-mail da medição concluída e grava o resultado (segundo plano, sessão própria)."""
    with FabricaSessao() as sessao:
        competencia = sessao.get(Competencia, competencia_id)
        if competencia is None or competencia.medicao_concluida_em is None:
            return
        contrato = obter_contrato(sessao, competencia.contrato_id)
        competencia = next(c for c in contrato.competencias if c.id == competencia_id)
        agora = agora_utc()
        assunto, texto, html = mensagem_medicao(contrato, competencia, agora)
        try:
            anexos = anexos_medicao(contrato, competencia)
        except OSError as erro:
            para, resultado = [], ResultadoSmtp(False, 0, f"Não foi possível ler a memória de cálculo: {erro}")
        else:
            para, resultado = _enviar(sessao, contrato, assunto, texto, html, anexos)
        competencia.email_medicao_enviado_em = agora
        competencia.email_medicao_ok = resultado.sucesso
        competencia.email_medicao_destinatarios = para
        competencia.email_medicao_erro = None if resultado.sucesso else resultado.mensagem
        sessao.commit()
