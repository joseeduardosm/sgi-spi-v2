# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler o XML da nota fiscal (NF-e e NFS-e) e extrair os dados usados na conferência de tributos.
"""Leitura do XML da nota fiscal, com detecção automática do formato.

Formatos aceitos:
- **NF-e** (modelo 55, `http://www.portalfiscal.inf.br/nfe`), com ou sem o protocolo de autorização (`nfeProc`);
- **NFS-e Padrão Nacional** (`http://www.sped.fazenda.gov.br/nfse`);
- **NFS-e da Prefeitura de São Paulo** (`http://www.prefeitura.sp.gov.br/nfe`).

O resultado (`DadosNota`) é normalizado: os mesmos campos para qualquer formato. Campo que não existe no
formato fica `None` e a tela mostra "não informado na nota". Valores monetários vêm como texto com 2 casas.

Segurança: o XML vem da contratada. Documentos com `DOCTYPE` são recusados (nenhuma nota fiscal usa, e é por ali
que entram entidades externas e expansões maliciosas); o expat da biblioteca padrão não busca entidades externas.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from xml.etree import ElementTree

from app.services.contratos.erros import ErroRegraContrato

NS_NFE = "http://www.portalfiscal.inf.br/nfe"
NS_NFSE_NACIONAL = "http://www.sped.fazenda.gov.br/nfse"
NS_NFSE_SP = "http://www.prefeitura.sp.gov.br/nfe"
TRIBUTOS = ("ir", "inss", "iss", "pis", "cofins", "csll")
TAMANHO_MAXIMO = 5 * 1024 * 1024


@dataclass
class Participante:
    cnpj: str | None = None
    razao_social: str | None = None
    inscricao_municipal: str | None = None


@dataclass
class ItemNota:
    descricao: str
    quantidade: str | None = None
    valor_unitario: str | None = None
    valor_total: str | None = None


@dataclass
class DadosNota:
    """Dados da nota fiscal lidos do XML, iguais para NF-e e NFS-e."""
    modelo: str  # "nfe", "nfse_nacional" ou "nfse_sp"
    modelo_rotulo: str
    numero: str | None = None
    serie: str | None = None
    chave: str | None = None
    emissao: str | None = None  # AAAA-MM-DD
    competencia: str | None = None  # AAAA-MM-DD (NFS-e); a NF-e não tem
    autorizada: bool | None = None
    situacao: str | None = None
    emitente: Participante = field(default_factory=Participante)
    tomador: Participante = field(default_factory=Participante)
    valor_bruto: str | None = None
    valor_liquido: str | None = None
    codigo_servico: str | None = None
    discriminacao: str | None = None
    itens: list[ItemNota] = field(default_factory=list)
    retencoes: dict[str, str] = field(default_factory=lambda: dict.fromkeys(TRIBUTOS, "0.00"))
    informacoes_complementares: str | None = None

    def como_dict(self) -> dict[str, Any]:
        """Formato JSON gravado na competência e devolvido à tela."""
        return asdict(self)


# --- Utilitários (ignoram o namespace: comparam só o nome local das tags) -------------------------

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _filho(no: ElementTree.Element | None, *caminho: str) -> ElementTree.Element | None:
    """Desce pelos nomes locais; `None` se algum não existir."""
    for nome in caminho:
        if no is None:
            return None
        no = next((f for f in no if _local(f.tag) == nome), None)
    return no


def _busca(no: ElementTree.Element | None, nome: str) -> ElementTree.Element | None:
    """Primeiro descendente com o nome local (em qualquer profundidade)."""
    if no is None:
        return None
    return next((e for e in no.iter() if _local(e.tag) == nome), None)


def _texto(no: ElementTree.Element | None, *caminho: str) -> str | None:
    alvo = _filho(no, *caminho) if caminho else no
    if alvo is None or alvo.text is None:
        return None
    return " ".join(alvo.text.split()) or None


def _texto_busca(no: ElementTree.Element | None, nome: str) -> str | None:
    return _texto(_busca(no, nome))


def _valor(texto: str | None) -> str | None:
    """Número do XML (ponto decimal) como texto com 2 casas; ilegível vira `None`."""
    if texto is None:
        return None
    try:
        return f"{Decimal(texto.strip()).quantize(Decimal('0.01')):.2f}"
    except InvalidOperation:
        return None


def _quantidade(texto: str | None) -> str | None:
    if texto is None:
        return None
    try:
        return f"{Decimal(texto.strip()).normalize():f}"
    except InvalidOperation:
        return None


def _data(texto: str | None) -> str | None:
    """Data AAAA-MM-DD a partir de data ou data/hora ISO (com ou sem fuso)."""
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto.strip().replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(texto.strip()[:10]).isoformat()
        except ValueError:
            return None


def _digitos(texto: str | None) -> str | None:
    return "".join(c for c in texto if c.isdigit()) or None if texto else None


def _participante(no: ElementTree.Element | None, *, nome: str = "xNome") -> Participante:
    documento = _texto(_filho(no, "CNPJ")) or _texto(_filho(no, "CPF")) or _texto(_filho(no, "CPFCNPJ", "CNPJ")) or _texto(_filho(no, "CPFCNPJ", "CPF"))
    return Participante(cnpj=_digitos(documento), razao_social=_texto(_filho(no, nome)), inscricao_municipal=_texto(_filho(no, "IM")))


# --- Leitura -------------------------------------------------------------------------------------

def ler_nota(conteudo: bytes) -> DadosNota:
    """Lê o XML e devolve os dados normalizados. Lança `ErroRegraContrato` se não for uma nota reconhecida."""
    if not conteudo or not conteudo.strip():
        raise ErroRegraContrato("O XML da nota fiscal está vazio.")
    if len(conteudo) > TAMANHO_MAXIMO:
        raise ErroRegraContrato("O XML da nota fiscal passa de 5 MB.")
    if b"<!DOCTYPE" in conteudo[:4096].upper() or b"<!ENTITY" in conteudo.upper():
        raise ErroRegraContrato("XML recusado: a nota fiscal não pode conter DOCTYPE nem entidades.")
    try:
        raiz = ElementTree.fromstring(conteudo)
    except ElementTree.ParseError as erro:
        raise ErroRegraContrato(f"O arquivo não é um XML válido ({erro}).") from erro
    namespace = raiz.tag[1:].split("}", 1)[0] if raiz.tag.startswith("{") else ""
    if namespace == NS_NFE or _busca(raiz, "infNFe") is not None:
        return _ler_nfe(raiz)
    if namespace == NS_NFSE_NACIONAL or _busca(raiz, "infNFSe") is not None:
        return _ler_nfse_nacional(raiz)
    if namespace == NS_NFSE_SP or _busca(raiz, "ChaveNFe") is not None:
        return _ler_nfse_sp(raiz)
    raise ErroRegraContrato("XML não reconhecido: envie o XML da NF-e ou da NFS-e (Padrão Nacional ou Prefeitura de São Paulo).")


def _ler_nfe(raiz: ElementTree.Element) -> DadosNota:
    inf = _busca(raiz, "infNFe")
    if inf is None:
        raise ErroRegraContrato("XML de NF-e sem o grupo infNFe.")
    ide = _filho(inf, "ide")
    total = _filho(inf, "total")
    ret = _filho(total, "retTrib")
    protocolo = _busca(raiz, "infProt")
    chave = _texto(protocolo, "chNFe") or (inf.get("Id") or "").removeprefix("NFe") or None
    status = _texto(protocolo, "cStat")
    itens = [
        ItemNota(
            descricao=_texto(_filho(det, "prod"), "xProd") or "",
            quantidade=_quantidade(_texto(_filho(det, "prod"), "qCom")),
            valor_unitario=_quantidade(_texto(_filho(det, "prod"), "vUnCom")),
            valor_total=_valor(_texto(_filho(det, "prod"), "vProd")),
        )
        for det in inf if _local(det.tag) == "det"
    ]
    # Código de serviço só existe quando a NF-e tem itens de serviço (grupo ISSQN)
    codigo = next((_texto(_filho(det, "imposto", "ISSQN"), "cListServ") for det in inf if _local(det.tag) == "det"
                   and _filho(det, "imposto", "ISSQN") is not None), None)
    retencoes = {
        "ir": _valor(_texto(ret, "vIRRF")), "inss": _valor(_texto(ret, "vRetPrev")), "pis": _valor(_texto(ret, "vRetPIS")),
        "cofins": _valor(_texto(ret, "vRetCOFINS")), "csll": _valor(_texto(ret, "vRetCSLL")),
        "iss": _valor(_texto(_filho(total, "ISSQNtot"), "vISSRet")),
    }
    return DadosNota(
        modelo="nfe", modelo_rotulo="NF-e (modelo 55)",
        numero=_texto(ide, "nNF"), serie=_texto(ide, "serie"), chave=chave,
        emissao=_data(_texto(ide, "dhEmi") or _texto(ide, "dEmi")),
        autorizada=(status == "100") if status else None,
        situacao=_texto(protocolo, "xMotivo") or ("Sem protocolo de autorização no XML" if protocolo is None else None),
        emitente=_participante(_filho(inf, "emit")), tomador=_participante(_filho(inf, "dest")),
        valor_bruto=_valor(_texto(_filho(total, "ICMSTot"), "vNF")),
        codigo_servico=codigo,
        discriminacao="\n".join(i.descricao for i in itens) or None, itens=itens,
        retencoes={t: retencoes.get(t) or "0.00" for t in TRIBUTOS},
        informacoes_complementares=_texto(_filho(inf, "infAdic"), "infCpl"),
    )


def _ler_nfse_nacional(raiz: ElementTree.Element) -> DadosNota:
    inf = _busca(raiz, "infNFSe")
    dps = _busca(raiz, "infDPS")
    if inf is None:
        raise ErroRegraContrato("XML de NFS-e Nacional sem o grupo infNFSe.")
    servico = _filho(dps, "serv")
    trib = _filho(dps, "valores", "trib")
    federal = _filho(trib, "tribFed")
    piscofins = _filho(federal, "piscofins")
    # PIS/COFINS só contam como retidos quando tpRetPisCofins indica retenção (1)
    pis_cofins_retidos = _texto(piscofins, "tpRetPisCofins") == "1"
    iss_retido = _texto(_filho(trib, "tribMun"), "tpRetISSQN") in ("2", "3")
    retencoes = {
        "ir": _valor(_texto(federal, "vRetIRRF")), "inss": _valor(_texto(federal, "vRetCP")), "csll": _valor(_texto(federal, "vRetCSLL")),
        "pis": _valor(_texto(piscofins, "vPis")) if pis_cofins_retidos else None,
        "cofins": _valor(_texto(piscofins, "vCofins")) if pis_cofins_retidos else None,
        "iss": _valor(_texto(_filho(inf, "valores"), "vISSQN")) if iss_retido else None,
    }
    emitente = _participante(_filho(inf, "emit"))
    if not emitente.cnpj:
        emitente = _participante(_filho(dps, "prest"))
    return DadosNota(
        modelo="nfse_nacional", modelo_rotulo="NFS-e Padrão Nacional",
        numero=_texto(inf, "nNFSe"), serie=_texto(dps, "serie"), chave=(inf.get("Id") or "").removeprefix("NFS") or None,
        emissao=_data(_texto(dps, "dhEmi") or _texto(inf, "dhProc")), competencia=_data(_texto(dps, "dCompet")),
        autorizada=True, situacao="NFS-e emitida",
        emitente=emitente, tomador=_participante(_filho(dps, "toma")),
        valor_bruto=_valor(_texto(_filho(dps, "valores", "vServPrest"), "vServ") or _texto_busca(dps, "vServ")),
        valor_liquido=_valor(_texto(_filho(inf, "valores"), "vLiq")),
        codigo_servico=_texto(_filho(servico, "cServ"), "cTribNac") or _texto(_filho(servico, "cServ"), "cTribMun"),
        discriminacao=_texto(_filho(servico, "cServ"), "xDescServ"),
        retencoes={t: retencoes.get(t) or "0.00" for t in TRIBUTOS},
        informacoes_complementares=_texto(_filho(servico, "infoCompl"), "xInfComp"),
    )


def _ler_nfse_sp(raiz: ElementTree.Element) -> DadosNota:
    nota = raiz if _local(raiz.tag) == "NFe" else _busca(raiz, "NFe")
    if nota is None:
        raise ErroRegraContrato("XML da NFS-e de São Paulo sem o grupo NFe.")
    chave = _filho(nota, "ChaveNFe")
    status = _texto(nota, "StatusNFe")
    retencoes = {
        "ir": _valor(_texto(nota, "ValorIR")), "inss": _valor(_texto(nota, "ValorINSS")), "pis": _valor(_texto(nota, "ValorPIS")),
        "cofins": _valor(_texto(nota, "ValorCOFINS")), "csll": _valor(_texto(nota, "ValorCSLL")),
        "iss": _valor(_texto(nota, "ValorISS")) if (_texto(nota, "ISSRetido") or "").lower() == "true" else None,
    }
    return DadosNota(
        modelo="nfse_sp", modelo_rotulo="NFS-e Prefeitura de São Paulo",
        numero=_texto(chave, "NumeroNFe"), chave=_texto(chave, "CodigoVerificacao"),
        emissao=_data(_texto(nota, "DataEmissaoNFe")), competencia=_data(_texto(nota, "DataFatoGeradorNFe")),
        autorizada=(status != "C") if status else None, situacao={"N": "Normal", "C": "Cancelada", "E": "Extraviada"}.get(status or "", status),
        emitente=Participante(cnpj=_digitos(_texto(_filho(nota, "CPFCNPJPrestador"), "CNPJ") or _texto(_filho(nota, "CPFCNPJPrestador"), "CPF")),
                              razao_social=_texto(nota, "RazaoSocialPrestador"), inscricao_municipal=_texto(chave, "InscricaoPrestador")),
        tomador=Participante(cnpj=_digitos(_texto(_filho(nota, "CPFCNPJTomador"), "CNPJ") or _texto(_filho(nota, "CPFCNPJTomador"), "CPF")),
                             razao_social=_texto(nota, "RazaoSocialTomador")),
        valor_bruto=_valor(_texto(nota, "ValorServicos")),
        codigo_servico=_texto(nota, "CodigoServico"), discriminacao=_texto(nota, "Discriminacao"),
        retencoes={t: retencoes.get(t) or "0.00" for t in TRIBUTOS},
    )
