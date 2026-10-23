# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras da trilha de admissão: chamado no GLPI, documentos, resolução, número no Protocolo, publicação, e-mail, posse e entrada no SGI.
"""Admissão (Fase 3 do RH).

Trilha, na ordem (cada etapa só abre depois da anterior):
`chamado` (GLPI) → `documentos` (envio ao Portal de Indicações: aqui só o registro e o comprovante) → `resolucao` (texto da máscara, editável) →
`protocolo` (número reservado no tipo de Resolução) → `publicacao` (PDF do D.O.E. anexado ao número; **o e-mail "Sua nomeação foi publicada", com o PDF, sai sozinho** ao registrar a publicação) →
`posse` (data e termo) → `concluida` (a pessoa já tem conta: assume o cargo e o histórico registra).
"""

import re
import uuid
from datetime import date, datetime
from html import escape
from io import BytesIO
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import FUSO_SAO_PAULO, agora_utc, hoje_sao_paulo
from app.core.configuracao import obter_configuracao
from app.models.anexo import Anexo
from app.models.protocolo import NumeroProtocolo, SequenciaProtocolo, TipoProtocolo
from app.models.rh_admissao import Admissao, AdmissaoDocumento, ChecklistRh, ModeloRh
from app.models.rh_cargos import Cargo
from app.models.rh_pre_cadastro import PreCadastro
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.schemas.rh_admissao import (
    SOLICITACOES, DocumentoAdmissao, EtapaAdmissao, LeituraAdmissao, LinkChamado, ResumoAdmissao, TipoProtocoloResolucao,
)
from app.core.erros import ErroApi
from app.services import modelo_email, servico_anexos, servico_integracao_glpi, servico_protocolo, servico_smtp
from app.services.glpi.cliente_formulario import ClienteFormularioGlpi, PerguntaFormulario
from app.services.glpi.cliente_glpi import ErroGlpi
from app.services.cliente_smtp import AnexoEmail, Mensagem
from app.services.contratacoes import html_blocos
from app.services.contratos.servico_importacao_xlsx import normalizar
from app.services import servico_diretorio
from app.services.contratacoes.conteudo import ErroConteudo, sanitizar, texto_do_html
from app.services.documentos.pdf import DocumentoPdf
from app.services.rh import rh_mascara, servico_cargos, servico_historico, servico_modelos
from app.services.rh.servico_pre_cadastro import so_digitos
from app.services.servico_auditoria import auditar
from app.services.servico_smtp import SemServidorAtivo

ETAPAS = (
    ("chamado", "Chamado no GLPI"), ("documentos", "Documentos"), ("resolucao", "Resolução"), ("protocolo", "Número no Protocolo"),
    ("publicacao", "Publicação no D.O.E."), ("posse", "Posse"), ("concluida", "Entrada no SGI"),
)
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


class AdmissaoNaoEncontrada(Exception):
    """Admissão (ou documento) inexistente (vira 404)."""


class ErroAdmissao(Exception):
    """Regra da admissão violada; `conflito` indica 409 em vez de 400."""

    def __init__(self, mensagem: str, conflito: bool = False):
        super().__init__(mensagem)
        self.conflito = conflito


# --- Apoio -----------------------------------------------------------------------------------------------

def _obter(sessao: Session, admissao_id: int) -> Admissao:
    admissao = sessao.get(Admissao, admissao_id)
    if admissao is None:
        raise AdmissaoNaoEncontrada()
    return admissao


def _ficha(sessao: Session, admissao: Admissao) -> PreCadastro:
    return sessao.get(PreCadastro, admissao.pre_cadastro_id)


def _numero(sessao: Session, admissao: Admissao) -> NumeroProtocolo | None:
    return sessao.get(NumeroProtocolo, admissao.numero_protocolo_id) if admissao.numero_protocolo_id else None


def _rotulo_numero(numero: NumeroProtocolo | None) -> str | None:
    return servico_protocolo.formatar_numero(numero.numero, numero.sequencia.exercicio) if numero else None


def etapa_atual(admissao: Admissao) -> str:
    """Primeira etapa ainda não feita."""
    if admissao.status == "concluida":
        return "concluida"
    feitas = (
        ("chamado", admissao.chamado_em), ("documentos", admissao.documentos_concluidos_em), ("resolucao", admissao.resolucao_gerada_em),
        ("protocolo", admissao.protocolo_em), ("publicacao", admissao.publicacao_registrada_em), ("posse", admissao.posse_em),
    )
    return next((chave for chave, quando in feitas if quando is None), "concluida")


def _exigir_em_andamento(admissao: Admissao) -> None:
    if admissao.status != "andamento":
        raise ErroAdmissao("A admissão já foi concluída ou cancelada.", conflito=True)


def _exigir_etapa(admissao: Admissao, chave: str) -> None:
    """A etapa precisa ser a atual ou uma já feita (para ajustes); etapas à frente ficam bloqueadas."""
    _exigir_em_andamento(admissao)
    ordem = [c for c, _ in ETAPAS]
    if ordem.index(chave) > ordem.index(etapa_atual(admissao)):
        raise ErroAdmissao(f"Conclua antes a etapa \"{dict(ETAPAS)[etapa_atual(admissao)]}\".", conflito=True)


def _limpar(html: str) -> str:
    """HTML do editor sanitizado (sem script nem evento)."""
    try:
        return sanitizar(html)
    except ErroConteudo as erro:
        raise ErroAdmissao(str(erro)) from erro


def data_extenso(dia: date) -> str:
    return f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def _br(dia: date | None) -> str:
    return dia.strftime("%d/%m/%Y") if dia else ""


def _cpf_formatado(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf


def valores(sessao: Session, admissao: Admissao) -> dict[str, str]:
    """Valores dos placeholders para esta admissão (o que ainda não existe fica vazio e sai como `—`)."""
    ficha, cargo = _ficha(sessao, admissao), sessao.get(Cargo, admissao.cargo_id)
    setor = sessao.get(Setor, cargo.setor_id)
    numero = _numero(sessao, admissao)
    return {
        "nome": ficha.nome_completo, "login": ficha.login_proposto or "", "cpf": _cpf_formatado(ficha.cpf), "rg": ficha.rg_numero or ficha.cin, "rs": ficha.rs_pv,
        "cargo": cargo.rotulo, "denominacao": cargo.denominacao, "classificacao": cargo.classificacao, "setor": setor.nome, "siglasetor": setor.sigla or "",
        "datainicio": _br(ficha.inicio_previsto), "dataposse": _br(admissao.posse_em),
        "numeroresolucao": f"{numero.numero:03d}" if numero else "", "anoresolucao": str(numero.sequencia.exercicio) if numero else "",
        "datapublicacao": _br(admissao.publicado_em), "hoje": data_extenso(hoje_sao_paulo()), "linksistema": obter_configuracao().url_publica,
    }


def _documento(doc: AdmissaoDocumento) -> DocumentoAdmissao:
    return DocumentoAdmissao(id=doc.id, descricao=doc.descricao, obrigatorio=doc.obrigatorio, enviado_em=doc.enviado_em, enviado_por_nome=doc.enviado_por_nome,
                             registrado_em=doc.registrado_em, tem_comprovante=doc.comprovante_anexo_id is not None, observacao=doc.observacao)


def _resumo(sessao: Session, admissao: Admissao) -> dict:
    ficha, cargo = _ficha(sessao, admissao), sessao.get(Cargo, admissao.cargo_id)
    etapa = etapa_atual(admissao)
    return dict(id=admissao.id, ficha_id=ficha.id, nome=ficha.nome_completo, login_proposto=ficha.login_proposto, cargo_rotulo=cargo.rotulo,
                setor_nome=sessao.get(Setor, cargo.setor_id).nome, status=admissao.status, etapa=etapa, etapa_rotulo=dict(ETAPAS)[etapa], atualizado_em=admissao.atualizado_em)


def leitura(sessao: Session, admissao: Admissao) -> LeituraAdmissao:
    ficha, numero = _ficha(sessao, admissao), _numero(sessao, admissao)
    atual = etapa_atual(admissao)
    quando = {"chamado": admissao.chamado_em, "documentos": admissao.documentos_concluidos_em, "resolucao": admissao.resolucao_gerada_em, "protocolo": admissao.protocolo_em,
              "publicacao": admissao.publicado_em or admissao.publicacao_registrada_em, "posse": admissao.posse_em, "concluida": admissao.concluida_em}
    etapas, achou_atual = [], False
    for chave, rotulo in ETAPAS:
        if quando[chave] is not None or (chave == "concluida" and admissao.status == "concluida"):
            estado = "feita"
        elif not achou_atual and chave == atual:
            estado, achou_atual = "atual", True
        else:
            estado = "pendente"
        etapas.append(EtapaAdmissao(chave=chave, rotulo=rotulo, estado=estado, em=quando[chave]))
    return LeituraAdmissao(
        **_resumo(sessao, admissao), etapas=etapas, solicitacoes={k: bool((admissao.solicitacoes or {}).get(k)) for k in SOLICITACOES},
        chamado_glpi_id=admissao.chamado_glpi_id, chamado_url=admissao.chamado_url, chamado_links=[LinkChamado(**l) for l in (admissao.chamado_links or [])], tem_foto=admissao.foto_anexo_id is not None, documentos=[_documento(d) for d in admissao.documentos],
        resolucao_html=admissao.resolucao_html, numero_protocolo_id=admissao.numero_protocolo_id, numero_protocolo=_rotulo_numero(numero), publicado_em=admissao.publicado_em,
        tem_publicacao=bool(numero and numero.anexo_id), email_enviado_em=admissao.email_enviado_em, email_erro=admissao.email_erro, email_destino=ficha.email_pessoal or None,
        posse_em=admissao.posse_em, termo_html=admissao.termo_html, concluida_em=admissao.concluida_em, conta_vinculada=ficha.usuario_id is not None, usuario_id=ficha.usuario_id,
    )


def obter(sessao: Session, admissao_id: int) -> LeituraAdmissao:
    return leitura(sessao, _obter(sessao, admissao_id))


def listar(sessao: Session, status: str | None = None, busca: str | None = None) -> list[ResumoAdmissao]:
    consulta = select(Admissao).order_by(Admissao.atualizado_em.desc())
    if status:
        consulta = consulta.where(Admissao.status == status)
    itens = [ResumoAdmissao(**_resumo(sessao, a)) for a in sessao.scalars(consulta)]
    for palavra in (busca or "").lower().split():
        itens = [i for i in itens if palavra in f"{i.nome} {i.login_proposto or ''} {i.cargo_rotulo} {i.setor_nome}".lower()]
    return itens


# --- Início e cancelamento -----------------------------------------------------------------------------

def _checklist_do_cargo(sessao: Session, cargo: Cargo) -> list[tuple[str, bool]]:
    """Itens dos checklists ativos que valem para a classificação do cargo (grupo + nível; cargo sem classificação só entra nos que marcam "outros"), sem repetir descrição."""
    itens: dict[str, bool] = {}
    for lista in sessao.scalars(select(ChecklistRh).where(ChecklistRh.ativo.is_(True)).order_by(ChecklistRh.id)):
        vale = lista.aplica_a_outros if cargo.grupo is None or cargo.nivel is None else any(c.grupo == cargo.grupo and c.nivel == cargo.nivel for c in lista.classificacoes)
        if vale:
            for item in lista.itens:
                itens.setdefault(item.descricao, item.obrigatorio)
    return list(itens.items())


def iniciar(sessao: Session, ficha_id: int, autor: Usuario) -> LeituraAdmissao:
    ficha = sessao.get(PreCadastro, ficha_id)
    if ficha is None:
        raise AdmissaoNaoEncontrada()
    if ficha.status not in ("rascunho", "aguardando_conta"):
        raise ErroAdmissao("Só fichas em rascunho ou aguardando a conta iniciam uma admissão.", conflito=True)
    if not ficha.login_proposto:
        raise ErroAdmissao("Informe o login proposto na ficha antes de iniciar a admissão.")
    if ficha.cargo_id is None:
        raise ErroAdmissao("Escolha o cargo pretendido (uma vaga de RH > Cargos) na ficha antes de iniciar a admissão.")
    cargo = sessao.get(Cargo, ficha.cargo_id)
    if cargo.vigente is not None:
        raise ErroAdmissao("O cargo pretendido já está ocupado.", conflito=True)
    if sessao.scalar(select(Admissao.id).where(Admissao.cargo_id == cargo.id, Admissao.status == "andamento")) is not None:
        raise ErroAdmissao("Já existe uma admissão em andamento para este cargo.", conflito=True)
    if sessao.scalar(select(Admissao.id).where(Admissao.pre_cadastro_id == ficha.id)) is not None:
        raise ErroAdmissao("Esta ficha já tem uma admissão.", conflito=True)
    admissao = Admissao(pre_cadastro_id=ficha.id, cargo_id=cargo.id, criado_por_id=autor.id)
    for ordem, (descricao, obrigatorio) in enumerate(_checklist_do_cargo(sessao, cargo)):
        admissao.documentos.append(AdmissaoDocumento(descricao=descricao, obrigatorio=obrigatorio, ordem=ordem))
    if not admissao.documentos:
        # Sem checklist para o tipo do cargo, a etapa de documentos não trava a trilha
        admissao.documentos_concluidos_em = None
    sessao.add(admissao)
    sessao.flush()
    auditar(sessao, autor.login, "rh.admissao.iniciar", ficha.nome_completo, autor_id=autor.id, dados={"admissao_id": admissao.id, "cargo": cargo.rotulo})
    sessao.commit()
    return leitura(sessao, admissao)


def cancelar(sessao: Session, admissao_id: int, autor: Usuario) -> LeituraAdmissao:
    admissao = _obter(sessao, admissao_id)
    _exigir_em_andamento(admissao)
    numero = _numero(sessao, admissao)
    if numero is not None and numero.anexo_id is None and numero.anulado_em is None:
        # Número reservado e sem documento: volta para a fila (quem reservou foi o RH, que tem a administração)
        servico_protocolo.liberar(sessao, numero.id, "Admissão cancelada", autor, ignorar_dono=True)
    admissao.status = "cancelada"
    auditar(sessao, autor.login, "rh.admissao.cancelar", _ficha(sessao, admissao).nome_completo, autor_id=autor.id, dados={"admissao_id": admissao.id})
    sessao.commit()
    return leitura(sessao, admissao)


# --- 1. Formulário de nomeação do GLPI ----------------------------------------------------------------

# Pergunta do formulário (título na tela do GLPI) de cada serviço que o RH marca; o formulário abre os chamados e e-mails dos seus destinos
PERGUNTAS_SOLICITACOES = {
    "rede": "Criar usuário de rede", "email": "Criar e-mail corporativo", "sei": "Criar acesso ao SEI", "compras_sp": "Criar acesso ao Compras SP",
    "equipamento": "Provisionar equipamento de trabalho", "estacao": "Preparo da estação", "cracha": "Solicitar crachá", "telefone": "Provisionar telefone", "mobiliario": "Provisionar mobiliário",
}


# Perguntas de texto preenchidas com a ficha e as duas de observação (a primeira é Sim/Não): o diagnóstico confere que todas existem no formulário real
TITULOS_TEXTO = ("Nome", "RG", "CPF", "Cargo", "Lotação", "Data de início", "Usuário espelho", "Registo do Servidor (RS)")
TITULO_TEM_OBSERVACAO, TITULO_OBSERVACOES = "Alguma observação adicional?", "Observações adicionais"


def conferir_perguntas(perguntas: list[PerguntaFormulario]) -> list[str]:
    """Problemas do formulário real em relação ao que o SGI preenche (vazio = tudo certo): pergunta ausente ou escolha sem Sim/Não."""
    por_titulo = {normalizar(p.rotulo): p for p in perguntas}
    problemas = [f"falta a pergunta \"{t}\"" for t in (*TITULOS_TEXTO, *PERGUNTAS_SOLICITACOES.values(), TITULO_TEM_OBSERVACAO, TITULO_OBSERVACOES) if normalizar(t) not in por_titulo]
    for titulo in (*PERGUNTAS_SOLICITACOES.values(), TITULO_TEM_OBSERVACAO):
        pergunta = por_titulo.get(normalizar(titulo))
        if pergunta is not None and {normalizar(r) for _, r in pergunta.opcoes} != {"sim", "nao"}:
            problemas.append(f"a pergunta \"{titulo}\" não tem exatamente as opções Sim e Não")
    return problemas


def _cliente_formulario(sessao: Session) -> tuple[ClienteFormularioGlpi, int]:
    """Cliente web do GLPI com a conta de serviço da integração e o id do formulário de nomeações."""
    config = servico_integracao_glpi.obter(sessao)
    if not config.ativo or not config.url_base:
        raise ErroApi(503, "A integração com o GLPI não está ativa. Ative em Administração > Integração GLPI.", "integracao_desativada")
    try:
        usuario, senha = servico_integracao_glpi.credencial_web(config)
    except ErroGlpi as erro:
        raise ErroApi(503, erro.mensagem, "integracao_desativada") from erro
    return ClienteFormularioGlpi(config.url_base, usuario, senha), config.formulario_nomeacao_id


def _opcao(pergunta: PerguntaFormulario, sim: bool) -> str:
    alvo = "sim" if sim else "nao"
    valor = next((v for v, rotulo in pergunta.opcoes if normalizar(rotulo) == alvo), None)
    if valor is None:
        raise ErroAdmissao(f"A pergunta \"{pergunta.rotulo}\" do formulário do GLPI não tem a opção {'Sim' if sim else 'Não'}: o formulário mudou.")
    return valor


def respostas_do_formulario(sessao: Session, admissao: Admissao, perguntas: list[PerguntaFormulario], solicitacoes: dict[str, bool], observacoes: str, usuario_espelho: str) -> dict[int, str]:
    """Respostas da ficha para as perguntas do formulário, achadas pelo **título** (os ids não são fixos no código). Pergunta obrigatória sem dado é erro claro."""
    ficha, cargo = _ficha(sessao, admissao), sessao.get(Cargo, admissao.cargo_id)
    setor = sessao.get(Setor, cargo.setor_id)
    por_titulo = {normalizar(p.rotulo): p for p in perguntas}

    def achar(titulo: str) -> PerguntaFormulario:
        pergunta = por_titulo.get(normalizar(titulo))
        if pergunta is None:
            raise ErroAdmissao(f"O formulário do GLPI não tem mais a pergunta \"{titulo}\": ele mudou. Avise a TI.")
        return pergunta

    textos = {
        "Nome": ficha.nome_completo, "RG": ficha.rg_numero or ficha.cin, "CPF": ficha.cpf, "Cargo": cargo.rotulo, "Lotação": setor.nome,
        "Data de início": ficha.inicio_previsto.isoformat() if ficha.inicio_previsto else "", "Usuário espelho": usuario_espelho.strip(),
        # Campo numérico do GLPI: só os dígitos da matrícula (ex.: "123456-7" → 1234567)
        "Registo do Servidor (RS)": so_digitos(ficha.rs_pv),
    }
    respostas: dict[int, str] = {}
    for titulo, valor in textos.items():
        pergunta = achar(titulo)
        if valor:
            respostas[pergunta.id] = valor
        elif pergunta.obrigatoria:
            raise ErroAdmissao(f"Complete na ficha o dado pedido pelo formulário do GLPI: {titulo}.")
    for chave, titulo in PERGUNTAS_SOLICITACOES.items():
        pergunta = achar(titulo)
        respostas[pergunta.id] = _opcao(pergunta, bool(solicitacoes.get(chave)))
    # O login proposto vai na observação (o formulário não tem campo próprio): a TI cria exatamente esse login
    linhas = [f"Login de rede proposto: {ficha.login_proposto}"] if ficha.login_proposto else []
    if ficha.email_pessoal:
        linhas.append(f"E-mail pessoal: {ficha.email_pessoal}")
    if observacoes.strip():
        linhas.append(observacoes.strip())
    pergunta_tem = achar(TITULO_TEM_OBSERVACAO)
    respostas[pergunta_tem.id] = _opcao(pergunta_tem, bool(linhas))
    if linhas:
        respostas[achar(TITULO_OBSERVACOES).id] = "\n".join(linhas)
    return respostas


TITULO_FOTO = "Foto"
TIPOS_FOTO = {b"\x89PNG\r\n\x1a\n": ("image/png", ".png"), b"\xff\xd8\xff": ("image/jpeg", ".jpg")}


def definir_foto(sessao: Session, admissao_id: int, origem: BinaryIO, autor: Usuario) -> LeituraAdmissao:
    """Foto da pessoa (PNG ou JPG, até 5 MB): vai no formulário do GLPI (se ainda não foi enviado) e vira a foto do Diretório quando a conta existir."""
    admissao = _obter(sessao, admissao_id)
    _exigir_em_andamento(admissao)
    dados = origem.read(servico_diretorio.TAMANHO_MAXIMO_FOTO + 1)
    if len(dados) > servico_diretorio.TAMANHO_MAXIMO_FOTO:
        raise ErroAdmissao("A foto excede 5 MB.")
    tipo = next((v for k, v in TIPOS_FOTO.items() if dados.startswith(k)), None)
    if tipo is None:
        raise ErroAdmissao("Formato não aceito. Envie a foto em PNG ou JPG.")
    try:
        from io import BytesIO as _Bytes
        from PIL import Image

        Image.open(_Bytes(dados)).verify()
    except Exception as erro:  # arquivo com cabeçalho de imagem, mas corrompido
        raise ErroAdmissao("Não foi possível ler a foto: o arquivo está corrompido.") from erro
    antigo = sessao.get(Anexo, admissao.foto_anexo_id) if admissao.foto_anexo_id else None
    anexo = servico_anexos.guardar_arquivo_gerado(sessao, dados, f"foto-admissao-{admissao.id}{tipo[1]}", tipo[0], "rh-foto-admissao", autor.id)
    if antigo is not None:
        servico_anexos.descartar(antigo)
    sessao.flush()
    admissao.foto_anexo_id = anexo.id
    auditar(sessao, autor.login, "rh.admissao.foto", _ficha(sessao, admissao).nome_completo, autor_id=autor.id, dados={"admissao_id": admissao.id})
    ficha = _ficha(sessao, admissao)
    if ficha.usuario_id is not None:
        aplicar_foto_na_conta(sessao, admissao, sessao.get(Usuario, ficha.usuario_id), autor)
    sessao.commit()
    return leitura(sessao, admissao)


def remover_foto(sessao: Session, admissao_id: int, autor: Usuario) -> LeituraAdmissao:
    admissao = _obter(sessao, admissao_id)
    _exigir_em_andamento(admissao)
    antigo = sessao.get(Anexo, admissao.foto_anexo_id) if admissao.foto_anexo_id else None
    if antigo is not None:
        servico_anexos.descartar(antigo)
    admissao.foto_anexo_id = None
    sessao.commit()
    return leitura(sessao, admissao)


def anexo_foto(sessao: Session, admissao_id: int) -> Anexo:
    admissao = _obter(sessao, admissao_id)
    anexo = sessao.get(Anexo, admissao.foto_anexo_id) if admissao.foto_anexo_id else None
    if anexo is None or anexo.excluido_em is not None:
        raise AdmissaoNaoEncontrada()
    return anexo


def aplicar_foto_na_conta(sessao: Session, admissao: Admissao, usuario: Usuario | None, autor: Usuario | None = None) -> bool:
    """Põe a foto da admissão como foto do Diretório (intranet) da pessoa, sem commit. Não troca uma foto que a própria pessoa enviou (`foto_origem = upload` de outra origem)."""
    anexo = sessao.get(Anexo, admissao.foto_anexo_id) if admissao.foto_anexo_id else None
    if usuario is None or anexo is None or anexo.excluido_em is not None:
        return False
    if usuario.foto_anexo_id is not None and usuario.foto_anexo_id == getattr(admissao, "_foto_aplicada_id", None):
        return False
    try:
        servico_diretorio.definir_foto(sessao, usuario, servico_anexos.caminho(anexo).read_bytes(), "upload", autor.id if autor else None)
    except servico_diretorio.ErroDiretorio:
        return False
    return True


def aplicar_foto_pela_ficha(sessao: Session, ficha_id: int, usuario: Usuario) -> bool:
    """Chamado quando a conta aparece (ligação ficha ↔ conta): se a admissão da ficha tem foto, ela vira a foto da pessoa na intranet (sem commit)."""
    admissao = sessao.scalar(select(Admissao).where(Admissao.pre_cadastro_id == ficha_id))
    return aplicar_foto_na_conta(sessao, admissao, usuario) if admissao is not None else False


def _links(corpo: dict, url_base: str) -> list[dict[str, str]]:
    """Links dos itens criados (o GLPI devolve `links_to_created_items`): texto do link e endereço absoluto."""
    saida: list[dict[str, str]] = []
    for item in (corpo.get("links_to_created_items") or []):
        texto_item = str(item)
        achado = re.search(r'href="([^"]+)"[^>]*>(.*?)</a>', texto_item, re.S)
        url, rotulo = (achado.group(1), re.sub(r"<[^>]+>", "", achado.group(2)).strip()) if achado else (texto_item, texto_item)
        if url.startswith("/"):
            url = url_base.rstrip("/") + url
        saida.append({"url": url, "texto": rotulo or url})
    return saida


def abrir_chamado(sessao: Session, admissao_id: int, solicitacoes: dict[str, bool], observacoes: str, autor: Usuario, usuario_espelho: str = "") -> LeituraAdmissao:
    """Preenche e envia o formulário "CGP - Nomeações" do GLPI com os dados da ficha; o próprio formulário abre os chamados e dispara os e-mails dos seus destinos."""
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "chamado")
    if admissao.chamado_em is not None:
        raise ErroAdmissao("O formulário desta admissão já foi enviado ao GLPI.", conflito=True)
    ficha = _ficha(sessao, admissao)
    faltam = [r for r, v in (("nome", ficha.nome_completo), ("CPF", ficha.cpf), ("RG ou CIN", ficha.rg_numero or ficha.cin), ("data prevista de início", ficha.inicio_previsto)) if not v]
    if faltam:
        raise ErroAdmissao("Complete na ficha: " + ", ".join(faltam) + ".")
    desconhecidas = set(solicitacoes) - set(SOLICITACOES)
    if desconhecidas:
        raise ErroAdmissao("Serviço desconhecido no formulário: " + ", ".join(sorted(desconhecidas)) + ".")
    cliente, formulario_id = _cliente_formulario(sessao)
    try:
        with cliente as glpi:
            perguntas, _ = glpi.perguntas(formulario_id)
            respostas = respostas_do_formulario(sessao, admissao, perguntas, solicitacoes, observacoes, usuario_espelho)
            arquivos: dict[int, list[dict]] = {}
            foto = sessao.get(Anexo, admissao.foto_anexo_id) if admissao.foto_anexo_id else None
            pergunta_foto = next((p for p in perguntas if normalizar(p.rotulo) == normalizar(TITULO_FOTO) and p.uploader), None)
            if foto is not None and pergunta_foto is not None:
                arquivos[pergunta_foto.id] = [glpi.subir_arquivo(pergunta_foto, foto.nome_original, servico_anexos.caminho(foto).read_bytes(), foto.tipo_conteudo)]
            corpo = glpi.enviar(formulario_id, respostas, arquivos)
    except ErroGlpi as erro:
        raise ErroApi(502, f"Não foi possível enviar o formulário ao GLPI: {erro.mensagem} Tente de novo em instantes.", "glpi_indisponivel") from erro
    links = _links(corpo, servico_integracao_glpi.obter(sessao).url_base)
    admissao.solicitacoes = {k: bool(solicitacoes.get(k)) for k in SOLICITACOES}
    admissao.chamado_links, admissao.chamado_em = links, agora_utc()
    achado = re.search(r"id=(\d+)", links[0]["url"]) if links else None
    admissao.chamado_glpi_id, admissao.chamado_url = (int(achado.group(1)) if achado else None), (links[0]["url"] if links else None)
    auditar(sessao, autor.login, "rh.admissao.chamado", ficha.nome_completo, f"formulário {formulario_id}; {len(links)} item(ns) criado(s)", autor_id=autor.id, dados={"admissao_id": admissao.id})
    sessao.commit()
    return leitura(sessao, admissao)


# --- 2. Documentos (Portal de Indicações: só o registro e o comprovante) ----------------------------------

def _doc(admissao: Admissao, doc_id: int) -> AdmissaoDocumento:
    doc = next((d for d in admissao.documentos if d.id == doc_id), None)
    if doc is None:
        raise AdmissaoNaoEncontrada()
    return doc


def registrar_documento(sessao: Session, admissao_id: int, doc_id: int, enviado_em: date, observacao: str, comprovante: tuple[BytesIO, str] | None, autor: Usuario) -> LeituraAdmissao:
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "documentos")
    doc = _doc(admissao, doc_id)
    if enviado_em > hoje_sao_paulo():
        raise ErroAdmissao("A data de envio não pode ser futura.")
    if comprovante is not None:
        try:
            doc.comprovante_anexo_id = servico_anexos.guardar_arquivo(sessao, comprovante[0], comprovante[1], "rh-comprovante", autor.id).id
        except servico_anexos.ErroAnexo as erro:
            raise ErroAdmissao(str(erro)) from erro
    doc.enviado_em, doc.observacao = enviado_em, observacao.strip()[:500]
    doc.enviado_por_id, doc.enviado_por_nome, doc.registrado_em = autor.id, autor.nome_completo or autor.login, agora_utc()
    auditar(sessao, autor.login, "rh.admissao.documento", doc.descricao, autor_id=autor.id, dados={"admissao_id": admissao.id})
    sessao.commit()
    return leitura(sessao, admissao)


def desfazer_documento(sessao: Session, admissao_id: int, doc_id: int, autor: Usuario) -> LeituraAdmissao:
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "documentos")
    if admissao.documentos_concluidos_em is not None:
        raise ErroAdmissao("A etapa de documentos já foi concluída.", conflito=True)
    doc = _doc(admissao, doc_id)
    doc.enviado_em, doc.enviado_por_id, doc.enviado_por_nome, doc.registrado_em, doc.comprovante_anexo_id, doc.observacao = None, None, "", None, None, ""
    sessao.commit()
    return leitura(sessao, admissao)


def concluir_documentos(sessao: Session, admissao_id: int, autor: Usuario) -> LeituraAdmissao:
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "documentos")
    pendentes = [d.descricao for d in admissao.documentos if d.obrigatorio and d.enviado_em is None]
    if pendentes:
        raise ErroAdmissao("Falta registrar o envio de: " + "; ".join(pendentes) + ".")
    admissao.documentos_concluidos_em = admissao.documentos_concluidos_em or agora_utc()
    auditar(sessao, autor.login, "rh.admissao.documentos_concluidos", _ficha(sessao, admissao).nome_completo, autor_id=autor.id, dados={"admissao_id": admissao.id})
    sessao.commit()
    return leitura(sessao, admissao)


def comprovante(sessao: Session, admissao_id: int, doc_id: int):
    """Anexo do comprovante (para o download)."""
    from app.models.anexo import Anexo

    doc = _doc(_obter(sessao, admissao_id), doc_id)
    anexo = sessao.get(Anexo, doc.comprovante_anexo_id) if doc.comprovante_anexo_id else None
    if anexo is None:
        raise AdmissaoNaoEncontrada()
    return anexo


# --- 3. Resolução -----------------------------------------------------------------------------------------

def gerar_resolucao(sessao: Session, admissao_id: int, autor: Usuario, html: str | None = None) -> LeituraAdmissao:
    """Cria o texto da resolução a partir do modelo (ou grava o texto editado). O texto guarda os placeholders: número, datas e nomes entram na hora de gerar o PDF."""
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "resolucao")
    if html is None:
        html = servico_modelos.obter(sessao, "resolucao_nomeacao").html
    html = _limpar(html)
    ruins = rh_mascara.invalidos(html)
    if ruins:
        raise ErroAdmissao("Placeholders não permitidos: " + ", ".join(ruins) + ".")
    if admissao.numero_protocolo_id is not None and admissao.publicacao_registrada_em is not None:
        raise ErroAdmissao("A resolução já foi publicada e não pode mais ser alterada.", conflito=True)
    admissao.resolucao_html = html
    admissao.resolucao_gerada_em = admissao.resolucao_gerada_em or agora_utc()
    auditar(sessao, autor.login, "rh.admissao.resolucao", _ficha(sessao, admissao).nome_completo, autor_id=autor.id, dados={"admissao_id": admissao.id})
    sessao.commit()
    return leitura(sessao, admissao)


def _pdf(sessao: Session, admissao: Admissao, titulo: str, mascara: str, marca: str, autor: str) -> bytes:
    from app.services.contratos.portaria_documento import _flowables

    texto = rh_mascara.preencher(mascara, valores(sessao, admissao))
    documento = DocumentoPdf(titulo=titulo, subtitulo=_ficha(sessao, admissao).nome_completo, paisagem=False, autor=autor, marca_dagua=marca)
    documento.blocos.extend(_flowables(html_blocos.blocos(texto)))
    return documento.gerar()


def resolucao_pdf(sessao: Session, admissao_id: int, autor: Usuario) -> tuple[bytes, str]:
    """PDF da resolução. Com a publicação registrada sai limpo; antes disso, com a marca d'água MINUTA."""
    admissao = _obter(sessao, admissao_id)
    if not admissao.resolucao_html:
        raise ErroAdmissao("Gere o texto da resolução primeiro.")
    publicada = admissao.publicacao_registrada_em is not None
    return _pdf(sessao, admissao, "Resolução de nomeação", admissao.resolucao_html, "" if publicada else "MINUTA", autor.nome_completo or autor.login), "resolucao.pdf"


def resolucao_para_copiar(sessao: Session, admissao_id: int) -> tuple[str, str]:
    """Texto da resolução com os placeholders preenchidos: (HTML formatado, texto simples), para colar no SEI."""
    admissao = _obter(sessao, admissao_id)
    if not admissao.resolucao_html:
        raise ErroAdmissao("Gere o texto da resolução primeiro.")
    html = _limpar(rh_mascara.preencher(admissao.resolucao_html, valores(sessao, admissao)))
    return html, texto_do_html(html)


# --- 4. Número no Protocolo ----------------------------------------------------------------------------------

def tipos_de_resolucao(sessao: Session) -> list[TipoProtocoloResolucao]:
    """Tipos do Protocolo cujo nome começa com "Resolu" (ex.: "Resoluções SPI 1")."""
    ano = hoje_sao_paulo().year
    saida = []
    for tipo in sessao.scalars(select(TipoProtocolo).where(TipoProtocolo.nome_chave.like("resolu%")).order_by(TipoProtocolo.nome_chave)):
        saida.append(TipoProtocoloResolucao(id=tipo.id, nome=tipo.nome, tem_faixa_no_ano=any(s.exercicio == ano for s in tipo.sequencias)))
    return saida


def reservar_numero(sessao: Session, admissao_id: int, tipo_id: uuid.UUID, autor: Usuario) -> LeituraAdmissao:
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "protocolo")
    if admissao.numero_protocolo_id is not None:
        raise ErroAdmissao("O número já foi reservado.", conflito=True)
    ano = hoje_sao_paulo().year
    tipo = sessao.get(TipoProtocolo, tipo_id)
    if tipo is None or not tipo.nome_chave.startswith("resolu"):
        raise ErroAdmissao("Escolha um tipo de Resolução do Protocolo.")
    sequencia = sessao.scalar(select(SequenciaProtocolo).where(SequenciaProtocolo.tipo_id == tipo.id, SequenciaProtocolo.exercicio == ano))
    if sequencia is None:
        raise ErroAdmissao(f"O Protocolo não tem faixa de numeração de \"{tipo.nome}\" para {ano}: peça à administração do Protocolo para cadastrá-la.")
    ficha = _ficha(sessao, admissao)
    try:
        numero = servico_protocolo.proximo(sessao, sequencia.id, f"Resolução de nomeação de {ficha.nome_completo}", None, autor, fora_da_reserva=True)
    except servico_protocolo.ErroProtocolo as erro:
        raise ErroAdmissao(str(erro), conflito=erro.status == 409) from erro
    admissao.numero_protocolo_id, admissao.protocolo_em = numero.id, agora_utc()
    auditar(sessao, autor.login, "rh.admissao.protocolo", ficha.nome_completo, _rotulo_numero(numero), autor_id=autor.id, dados={"admissao_id": admissao.id})
    sessao.commit()
    return leitura(sessao, admissao)


# --- 5. Publicação -------------------------------------------------------------------------------------------

def validar_anexo_no_numero(sessao: Session, numero_id: uuid.UUID, nome_arquivo: str) -> None:
    """Número de uma admissão: só aceita PDF (é a publicação no D.O.E.). Chamado pelo Protocolo antes de anexar."""
    admissao = sessao.scalar(select(Admissao).where(Admissao.numero_protocolo_id == numero_id, Admissao.status == "andamento"))
    if admissao is not None and not (nome_arquivo or "").lower().endswith(".pdf"):
        raise ErroAdmissao("A publicação da resolução deve ser enviada em PDF.", conflito=True)


def publicar_pelo_protocolo(sessao: Session, numero: NumeroProtocolo, autor: Usuario) -> None:
    """Se o número é de uma admissão em andamento, o PDF anexado a ele registra a publicação (sem commit). A data nasce como hoje; o RH ajusta."""
    admissao = sessao.scalar(select(Admissao).where(Admissao.numero_protocolo_id == numero.id, Admissao.status == "andamento"))
    if admissao is None or admissao.publicacao_registrada_em is not None:
        return
    admissao.publicacao_registrada_em, admissao.publicado_em = agora_utc(), admissao.publicado_em or hoje_sao_paulo()
    ficha = _ficha(sessao, admissao)
    auditar(sessao, autor.login, "rh.admissao.publicacao", ficha.nome_completo, _rotulo_numero(numero), autor_id=autor.id, dados={"admissao_id": admissao.id})
    _tentar_email(sessao, admissao)


def registrar_publicacao(sessao: Session, admissao_id: int, origem: BytesIO, nome_arquivo: str, publicado_em: date, autor: Usuario) -> LeituraAdmissao:
    """O RH anexa o PDF do D.O.E. ao número do Protocolo (o que registra a publicação) e informa a data da publicação."""
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "publicacao")
    numero = _numero(sessao, admissao)
    if numero is None:
        raise ErroAdmissao("Reserve o número no Protocolo antes de registrar a publicação.")
    if publicado_em > hoje_sao_paulo():
        raise ErroAdmissao("A data da publicação não pode ser futura.")
    admissao.publicado_em = publicado_em  # antes do anexo: o gancho do Protocolo registra a publicação e envia o e-mail já com esta data
    try:
        servico_protocolo.anexar(sessao, numero.id, origem, nome_arquivo, autor, ignorar_dono=True)
    except servico_protocolo.ErroProtocolo as erro:
        sessao.rollback()
        raise ErroAdmissao(str(erro), conflito=erro.status == 409) from erro
    admissao = _obter(sessao, admissao_id)
    admissao.publicado_em = publicado_em
    sessao.commit()
    return leitura(sessao, admissao)


def ajustar_data_publicacao(sessao: Session, admissao_id: int, publicado_em: date, autor: Usuario) -> LeituraAdmissao:
    """Corrige a data quando o PDF foi anexado direto no Protocolo (a data nasce como o dia do anexo)."""
    admissao = _obter(sessao, admissao_id)
    _exigir_em_andamento(admissao)
    if admissao.publicacao_registrada_em is None:
        raise ErroAdmissao("A publicação ainda não foi registrada.")
    if publicado_em > hoje_sao_paulo():
        raise ErroAdmissao("A data da publicação não pode ser futura.")
    admissao.publicado_em = publicado_em
    sessao.commit()
    return leitura(sessao, admissao)


def anexo_publicacao(sessao: Session, admissao_id: int):
    numero = _numero(sessao, _obter(sessao, admissao_id))
    if numero is None or numero.anexo is None:
        raise AdmissaoNaoEncontrada()
    return numero.anexo


# --- E-mail "Sua nomeação foi publicada" (automático ao registrar a publicação) -------------------------------------

def _enviar_email_nomeacao(sessao: Session, admissao: Admissao) -> None:
    """Envia o e-mail de nomeação ao e-mail pessoal da ficha, com o PDF da publicação (sem commit). `ErroAdmissao` se não der."""
    ficha, numero = _ficha(sessao, admissao), _numero(sessao, admissao)
    if not ficha.email_pessoal:
        raise ErroAdmissao("A ficha não tem e-mail pessoal para enviar a nomeação.")
    modelo: ModeloRh = servico_modelos.obter(sessao, "email_nomeacao_publicada")
    dados = valores(sessao, admissao)
    corpo = rh_mascara.preencher(modelo.html, dados)
    assunto = rh_mascara.preencher(modelo.assunto or "Sua nomeação foi publicada", dados).replace("&amp;", "&")
    html = modelo_email.pagina(assunto, corpo, sobretitulo="Coordenadoria de Gestão de Pessoas")
    anexos = []
    if numero is not None and numero.anexo is not None:
        anexos.append(AnexoEmail(nome=f"nomeacao-{servico_protocolo.formatar_numero(numero.numero, numero.sequencia.exercicio).replace('/', '-')}.pdf",
                                 conteudo=servico_anexos.caminho(numero.anexo).read_bytes()))
    try:
        resultado = servico_smtp.enviar_email(sessao, Mensagem(para=[ficha.email_pessoal], assunto=assunto, texto=html_blocos_texto(corpo), html=html, anexos=anexos))
    except SemServidorAtivo as erro:
        raise ErroAdmissao(str(erro)) from erro
    if not resultado.sucesso:
        raise ErroAdmissao(f"Não foi possível enviar o e-mail: {resultado.mensagem}")
    admissao.email_enviado_em, admissao.email_erro = agora_utc(), None
    auditar(sessao, "sistema", "rh.admissao.email", ficha.nome_completo, f"para {ficha.email_pessoal}", dados={"admissao_id": admissao.id})


def _tentar_email(sessao: Session, admissao: Admissao) -> None:
    """Envio automático ao registrar a publicação: falha de e-mail nunca desfaz a publicação; o motivo fica guardado e o RH pode reenviar."""
    if admissao.email_enviado_em is not None:
        return
    try:
        _enviar_email_nomeacao(sessao, admissao)
    except ErroAdmissao as erro:
        admissao.email_erro = str(erro)[:500]
    except Exception as erro:  # noqa: BLE001 - SMTP, disco ou modelo: qualquer falha vira aviso, não derruba a publicação
        admissao.email_erro = f"Falha inesperada no envio ({type(erro).__name__})."


def reenviar_email(sessao: Session, admissao_id: int, autor: Usuario) -> LeituraAdmissao:
    """Reenvia o e-mail de nomeação quando o envio automático falhou (ou a ficha ganhou o e-mail depois)."""
    admissao = _obter(sessao, admissao_id)
    _exigir_em_andamento(admissao)
    if admissao.publicacao_registrada_em is None:
        raise ErroAdmissao("O e-mail sai quando a publicação for registrada.")
    if admissao.email_enviado_em is not None:
        raise ErroAdmissao("O e-mail desta admissão já foi enviado.", conflito=True)
    try:
        _enviar_email_nomeacao(sessao, admissao)
    except ErroAdmissao as erro:
        admissao.email_erro = str(erro)[:500]
        sessao.commit()
        raise
    auditar(sessao, autor.login, "rh.admissao.email_reenviado", _ficha(sessao, admissao).nome_completo, autor_id=autor.id, dados={"admissao_id": admissao.id})
    sessao.commit()
    return leitura(sessao, admissao)


def html_blocos_texto(html: str) -> str:
    """Texto simples do HTML (o e-mail leva sempre as duas versões)."""
    from lxml import html as lxml_html

    return " ".join(lxml_html.fromstring(f"<div>{html}</div>").text_content().split())


# --- 7. Posse ------------------------------------------------------------------------------------------------------

def registrar_posse(sessao: Session, admissao_id: int, posse_em: date, autor: Usuario) -> LeituraAdmissao:
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "posse")
    if admissao.publicado_em and posse_em < admissao.publicado_em:
        raise ErroAdmissao("A posse não pode ser anterior à publicação.")
    admissao.posse_em = posse_em
    if admissao.termo_html is None:
        admissao.termo_html = servico_modelos.obter(sessao, "termo_posse").html
    auditar(sessao, autor.login, "rh.admissao.posse", _ficha(sessao, admissao).nome_completo, autor_id=autor.id, dados={"admissao_id": admissao.id, "posse_em": posse_em.isoformat()})
    sessao.commit()
    return leitura(sessao, admissao)


def salvar_termo(sessao: Session, admissao_id: int, html: str, autor: Usuario) -> LeituraAdmissao:
    admissao = _obter(sessao, admissao_id)
    _exigir_em_andamento(admissao)
    if admissao.posse_em is None:
        raise ErroAdmissao("Registre a data da posse antes de editar o termo.")
    html = _limpar(html)
    ruins = rh_mascara.invalidos(html)
    if ruins:
        raise ErroAdmissao("Placeholders não permitidos: " + ", ".join(ruins) + ".")
    admissao.termo_html = html
    sessao.commit()
    return leitura(sessao, admissao)


def termo_pdf(sessao: Session, admissao_id: int, autor: Usuario) -> tuple[bytes, str]:
    admissao = _obter(sessao, admissao_id)
    if admissao.posse_em is None or not admissao.termo_html:
        raise ErroAdmissao("Registre a data da posse para gerar o termo.")
    return _pdf(sessao, admissao, "Termo de posse", admissao.termo_html, "", autor.nome_completo or autor.login), "termo-de-posse.pdf"


# --- 8. Entrada no SGI ---------------------------------------------------------------------------------------------

def concluir(sessao: Session, admissao_id: int, autor: Usuario) -> LeituraAdmissao:
    """Fecha a admissão: a pessoa (que já tem conta) assume o cargo na data da posse e o histórico funcional registra o fato."""
    admissao = _obter(sessao, admissao_id)
    _exigir_etapa(admissao, "concluida")
    ficha, numero = _ficha(sessao, admissao), _numero(sessao, admissao)
    if ficha.usuario_id is None:
        raise ErroAdmissao(f"A conta de {ficha.login_proposto} ainda não apareceu no AD/SGI. Assim que a TI criar a conta, a ficha se liga a ela e a admissão pode ser concluída.", conflito=True)
    ato = f"Resolução SPI nº {_rotulo_numero(numero)}" if numero else ""
    try:
        servico_cargos.ocupar(sessao, admissao.cargo_id, ficha.usuario_id, autor, inicio=admissao.posse_em, ato=ato)
    except (servico_cargos.ErroRegraCargo, servico_cargos.CargoNaoEncontrado) as erro:
        sessao.rollback()
        raise ErroAdmissao(str(erro) or "Não foi possível alocar a pessoa no cargo.", conflito=True) from erro
    if sessao.get(Usuario, ficha.usuario_id).foto_anexo_id is None:
        aplicar_foto_na_conta(sessao, admissao, sessao.get(Usuario, ficha.usuario_id), autor)
    admissao.status, admissao.concluida_em = "concluida", agora_utc()
    ficha_cargo = sessao.get(Cargo, admissao.cargo_id)
    servico_historico.registrar(
        sessao, ficha.usuario_id, "admissao", f"Admissão concluída: {ficha_cargo.rotulo}",
        f"Posse em {_br(admissao.posse_em)}. {ato}. Publicada no D.O.E. em {_br(admissao.publicado_em)}.", autor, origem=("admissao", admissao.id), dados={"admissao_id": admissao.id},
    )
    # Os documentos enviados na admissão entram no histórico da pessoa (um fato por documento, na data do envio)
    for doc in admissao.documentos:
        if doc.enviado_em is not None:
            servico_historico.registrar(
                sessao, ficha.usuario_id, "documento", f"Documento enviado: {doc.descricao}", doc.observacao, None, quando=datetime(doc.enviado_em.year, doc.enviado_em.month, doc.enviado_em.day, 12, tzinfo=FUSO_SAO_PAULO),
                origem=("admissao_documento", doc.id), autor_nome=doc.enviado_por_nome or "RH", dados={"admissao_id": admissao.id},
            )
    auditar(sessao, autor.login, "rh.admissao.concluir", ficha.nome_completo, autor_id=autor.id, dados={"admissao_id": admissao.id})
    sessao.commit()
    return leitura(sessao, admissao)
