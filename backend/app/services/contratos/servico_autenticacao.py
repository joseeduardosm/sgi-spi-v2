# Criado por José Eduardo Santana Martins
# Este arquivo serve para autenticar os PDFs gerados (Folha de autenticação com código e hash) e para verificar a autenticidade depois.
"""Autenticação de PDFs gerados pelo sistema.

Cada PDF autenticado ganha, no fim, uma **Folha de autenticação** com: o código de verificação (início do SHA-256 do conteúdo, sem a folha), o
SHA-256 completo, quem gerou e quando, a lista de quem deu ciência e como conferir. O arquivo completo (com a folha) é registrado em
`contratos_documentos_autenticados` com o seu próprio SHA-256: enviar o PDF para verificação confere se ele é exatamente o gerado pelo sistema, e
digitar o código mostra os dados do registro. **Não é assinatura digital**: prova a origem e a integridade do arquivo gerado, não a identidade de
quem assina por fora (a assinatura da contratada continua sendo feita no gov.br e enviada de volta).
"""

import hashlib
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.anexo import Anexo
from app.models.contratos import Competencia, Contrato, DocumentoAutenticado
from app.services import servico_anexos
from app.services.documentos.pdf import DocumentoPdf

FUSO = ZoneInfo("America/Sao_Paulo")
TAMANHO_CODIGO = 16
TIPOS = {"avaliacao": "Relatório de avaliação dos serviços", "memoria_medicao": "Memória de cálculo da medição", "consolidado": "Documento consolidado da competência"}


def _codigo(sha256: str) -> str:
    """Código curto e legível: 16 caracteres do hash, em quatro grupos (ex.: `A1B2-C3D4-E5F6-0718`)."""
    base = sha256[:TAMANHO_CODIGO].upper()
    return "-".join(base[i:i + 4] for i in range(0, TAMANHO_CODIGO, 4))


def _normalizar_codigo(texto: str) -> str:
    return "".join(c for c in texto.upper() if c.isalnum())


def _hora(momento: datetime) -> str:
    return momento.astimezone(FUSO).strftime("%d/%m/%Y %H:%M")


def _folha(tipo: str, contrato: Contrato, competencia: Competencia | None, autor: str, gerado_em: datetime, sha256: str, ciencias: list[dict]) -> bytes:
    """Página de autenticação, na mesma orientação dos demais documentos do sistema."""
    documento = DocumentoPdf("Folha de autenticação", f"Contrato {contrato.numero}" + (f" · Competência {competencia.competencia:%m/%Y}" if competencia else ""), autor=autor)
    documento.secao("Documento").campos([
        ("Documento", TIPOS.get(tipo, tipo)), ("Contrato", f"{contrato.numero} — {contrato.apelido}" if contrato.apelido else contrato.numero),
        ("Competência", competencia.numero_competencia if competencia else "—"), ("Gerado por", autor),
        ("Gerado em", _hora(gerado_em)), ("Código de verificação", _codigo(sha256)),
    ])
    documento.secao("Impressão digital (SHA-256 do conteúdo)").paragrafo(sha256)
    documento.secao("Ciências registradas")
    if ciencias:
        documento.tabela(["Nome", "Papel", "Ciência em"], [[c["nome"], c["papel"], c["em"]] for c in ciencias], larguras=[4, 3, 2])
    else:
        documento.paragrafo("Nenhuma ciência registrada até a geração deste documento.")
    documento.secao("Como conferir").paragrafo(
        "Acesse o SGI SPI, em Contratos › Verificar documento, e informe o código de verificação ou envie este PDF. O sistema confirma se o arquivo é "
        "exatamente o que foi gerado, quando e por quem. Esta folha não é uma assinatura digital: a assinatura da contratada é feita à parte, no gov.br.")
    return documento.gerar()


def hash_composicao(componentes: list[tuple[str, str]]) -> str:
    """SHA-256 da composição de um consolidado: a lista ordenada de (título, SHA-256 de cada arquivo incluído). Muda se qualquer documento mudar."""
    return hashlib.sha256("\n".join(f"{titulo}|{sha}" for titulo, sha in componentes).encode()).hexdigest()


def folha_consolidado(contrato: Contrato, competencia: Competencia, autor: str, gerado_em: datetime, sha_composicao: str, componentes: list[tuple[str, str]],
                      ciencias: list[dict]) -> bytes:
    """Folha de autenticação do consolidado: código, hash da composição, o SHA-256 de cada documento incluído e quem deu ciência.

    Não depende de numeração de páginas (o índice já traz as páginas); só dos arquivos incluídos."""
    documento = DocumentoPdf("Folha de autenticação", f"Contrato {contrato.numero} · Competência {competencia.competencia:%m/%Y}", autor=autor)
    documento.secao("Documento consolidado").campos([
        ("Contrato", f"{contrato.numero} — {contrato.apelido}" if contrato.apelido else contrato.numero), ("Competência", competencia.numero_competencia),
        ("Gerado por", autor), ("Gerado em", _hora(gerado_em)), ("Código de verificação", _codigo(sha_composicao)), ("Documentos incluídos", str(len(componentes))),
    ])
    documento.secao("Impressão digital da composição (SHA-256)").paragrafo(sha_composicao)
    documento.secao("Documentos incluídos e o SHA-256 de cada arquivo")
    documento.tabela(["Nº", "Documento", "SHA-256 do arquivo"], [[str(i), titulo, sha or "gerado ao montar o consolidado"] for i, (titulo, sha) in enumerate(componentes, start=1)],
                     larguras=[0.5, 5, 7])
    documento.secao("Ciências registradas")
    if ciencias:
        documento.tabela(["Nome", "Papel", "Ciência em"], [[c["nome"], c["papel"], c["em"]] for c in ciencias], larguras=[4, 3, 2])
    else:
        documento.paragrafo("Nenhuma ciência registrada até a geração deste documento.")
    documento.secao("Como conferir").paragrafo(
        "Acesse o SGI SPI, em Contratos › Verificar documento, e informe o código de verificação ou envie este PDF: o sistema confirma se o arquivo é exatamente "
        "o gerado, quando e por quem. O SHA-256 de cada documento incluído permite conferir os arquivos originais anexados. Esta folha não é uma assinatura digital.")
    return documento.gerar()


def retrato_ciencias(ciencias: list[dict]) -> list[dict]:
    """Ciências no formato guardado e impresso: nome, papel (rótulo) e data/hora em São Paulo."""
    from app.services.contratos.documentos_execucao import PAPEIS

    def quando(valor) -> str:
        if isinstance(valor, str):
            try:
                valor = datetime.fromisoformat(valor)
            except ValueError:
                return valor
        return _hora(valor) if isinstance(valor, datetime) else str(valor)

    return [{"nome": c["nome"], "papel": PAPEIS.get(c["papel"], c["papel"]), "em": quando(c["em"])} for c in ciencias]


def registrar(sessao: Session, anexo: Anexo, sha_conteudo: str, tipo: str, contrato: Contrato, competencia: Competencia | None, autor_nome: str,
              gerado_em: datetime, ciencias: list[dict]) -> DocumentoAutenticado:
    """Registra a autenticação de um PDF já guardado (o `sha256` do anexo é o do arquivo completo)."""
    registro = DocumentoAutenticado(
        codigo=_codigo(sha_conteudo), sha256_conteudo=sha_conteudo, sha256_final=anexo.sha256, tipo=tipo, contrato_id=contrato.id,
        competencia_id=competencia.id if competencia else None, anexo_id=anexo.id, gerado_por_nome=autor_nome, gerado_em=gerado_em, ciencias=ciencias,
    )
    sessao.add(registro)
    return registro


def guardar_autenticado(
    sessao: Session, conteudo: bytes, nome: str, categoria: str, tipo: str, contrato: Contrato, competencia: Competencia | None, autor_id: int | None,
    autor_nome: str, ciencias: list[dict],
) -> Anexo:
    """Acrescenta a Folha de autenticação ao PDF, guarda o arquivo completo e registra a autenticação. Devolve o anexo gravado.

    `ciencias`: [{"nome", "papel", "em"}] com `em` já formatado (texto) ou datetime."""
    gerado_em = agora_utc()
    sha_conteudo = hashlib.sha256(conteudo).hexdigest()
    retrato = retrato_ciencias(ciencias)
    folha = _folha(tipo, contrato, competencia, autor_nome, gerado_em, sha_conteudo, retrato)
    escritor = PdfWriter()
    for parte in (conteudo, folha):
        for pagina in PdfReader(BytesIO(parte)).pages:
            escritor.add_page(pagina)
    saida = BytesIO()
    escritor.write(saida)
    final = saida.getvalue()
    anexo = servico_anexos.guardar_pdf_gerado(sessao, final, nome, categoria, autor_id, contrato_id=contrato.id)
    sessao.flush()
    registrar(sessao, anexo, sha_conteudo, tipo, contrato, competencia, autor_nome, gerado_em, retrato)
    return anexo


def verificar(sessao: Session, codigo: str | None = None, conteudo: bytes | None = None) -> dict:
    """Confere um código de verificação ou um PDF enviado. Devolve `{"valido": bool, "motivo", "documento": {...} | None}`.

    Com o arquivo: vale só se o SHA-256 dele for exatamente o de um documento gerado pelo sistema. Com o código: mostra o registro (o código sozinho
    não prova que o arquivo na mão da pessoa é o original)."""
    registro: DocumentoAutenticado | None = None
    if conteudo is not None:
        registro = sessao.scalar(select(DocumentoAutenticado).where(DocumentoAutenticado.sha256_final == hashlib.sha256(conteudo).hexdigest()))
        if registro is None:
            return {"valido": False, "motivo": "Este arquivo não corresponde a nenhum documento gerado pelo sistema (foi alterado ou não é um original).", "documento": None}
    elif codigo:
        alvo = _normalizar_codigo(codigo)
        registro = next((r for r in sessao.scalars(select(DocumentoAutenticado)) if _normalizar_codigo(r.codigo) == alvo), None) if len(alvo) == TAMANHO_CODIGO else None
        if registro is None:
            return {"valido": False, "motivo": "Código de verificação não encontrado.", "documento": None}
    else:
        return {"valido": False, "motivo": "Informe o código de verificação ou envie o PDF.", "documento": None}
    contrato = sessao.get(Contrato, registro.contrato_id)
    competencia = sessao.get(Competencia, registro.competencia_id) if registro.competencia_id else None
    return {
        "valido": True,
        "motivo": "Arquivo idêntico ao gerado pelo sistema." if conteudo is not None else "Código encontrado. Para provar que o arquivo é o original, envie o PDF.",
        "documento": {
            "tipo": TIPOS.get(registro.tipo, registro.tipo), "contrato_id": registro.contrato_id, "contrato_numero": contrato.numero if contrato else "",
            "competencia": competencia.numero_competencia if competencia else None, "gerado_por": registro.gerado_por_nome, "gerado_em": registro.gerado_em,
            "codigo": registro.codigo, "sha256": registro.sha256_final, "ciencias": registro.ciencias or [],
        },
    }
