# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler uma análise salva no SIGEO (Oracle BI / OBIEE) pelo web service SOAP: logon, execução da análise e logoff.
"""Cliente SOAP mínimo do OBIEE (SIGEO), com `httpx` + `lxml` (o mesmo que a biblioteca pyobiee faz, sem dependências extras).

- `nQSessionService.logon` devolve o `sessionID`;
- `xmlViewService.executeXMLQuery` executa a análise salva (`reportPath`) e devolve um rowset XML (`<Row><Column0>…`) com o cabeçalho
  em `saw-sql:columnHeading`;
- `nQSessionService.logoff` encerra a sessão.
Só lê: não altera nada no SIGEO.
"""

import time
from xml.sax.saxutils import escape

import httpx
from lxml import etree

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_V6 = "urn://oracle.bi.webservices/v6"
NS_ROWSET = "urn:schemas-microsoft-com:xml-analysis:rowset"
NS_SQL = "urn:saw-sql"


class ErroSigeo(Exception):
    """Falha ao falar com o SIGEO (rede, credencial, análise inexistente…), com mensagem para a tela."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


def _envelope(corpo: str) -> bytes:
    return (f'<?xml version="1.0" encoding="utf-8"?><soapenv:Envelope xmlns:soapenv="{NS_SOAP}" xmlns:v6="{NS_V6}">'
            f"<soapenv:Header/><soapenv:Body>{corpo}</soapenv:Body></soapenv:Envelope>").encode("utf-8")


class ClienteObiee:
    """Sessão no OBIEE. Use com `with`: o logoff acontece na saída."""

    def __init__(self, url_base: str, usuario: str, senha: str, tempo_limite: float = 180) -> None:
        self.url = url_base.rstrip("/").split("?")[0] + "?SoapImpl="
        self._usuario, self._senha = usuario, senha
        self._http = httpx.Client(timeout=tempo_limite)
        self.sessao: str | None = None
        self.latencia_ms: int | None = None

    def __enter__(self) -> "ClienteObiee":
        inicio = time.monotonic()
        resposta = self._chamar("nQSessionService", f"<v6:logon><v6:name>{escape(self._usuario)}</v6:name><v6:password>{escape(self._senha)}</v6:password></v6:logon>")
        no = resposta.find(f".//{{{NS_V6}}}sessionID")
        if no is None or not (no.text or "").strip():
            raise ErroSigeo("O SIGEO não devolveu a sessão: confira usuário e senha.")
        self.sessao = no.text.strip()
        self.latencia_ms = int((time.monotonic() - inicio) * 1000)
        return self

    def __exit__(self, *_exc) -> None:
        try:
            if self.sessao:
                self._chamar("nQSessionService", f"<v6:logoff><v6:sessionID>{self.sessao}</v6:sessionID></v6:logoff>")
        except ErroSigeo:
            pass
        finally:
            self._http.close()

    def _chamar(self, servico: str, corpo: str) -> etree._Element:
        try:
            r = self._http.post(self.url + servico, content=_envelope(corpo), headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "#"})
        except httpx.HTTPError as erro:
            raise ErroSigeo(f"Não foi possível acessar o SIGEO ({type(erro).__name__}).") from erro
        try:
            xml = etree.fromstring(r.content)
        except etree.XMLSyntaxError as erro:
            raise ErroSigeo(f"O SIGEO respondeu algo que não é XML (HTTP {r.status_code}).") from erro
        falha = xml.find(f".//{{{NS_SOAP}}}Fault")
        if falha is not None:
            texto = (falha.findtext("faultstring") or "").strip()
            if "uthentication" in texto or "logon" in texto.lower() or "password" in texto.lower():
                raise ErroSigeo("O SIGEO recusou o usuário ou a senha.")
            raise ErroSigeo(f"O SIGEO recusou a consulta: {texto[:200]}")
        return xml

    def executar_analise(self, caminho: str, maximo_linhas: int = 20000) -> list[dict[str, str]]:
        """Executa a análise salva e devolve as linhas como dicionários {coluna: valor} (o nome da coluna vem do cabeçalho da análise)."""
        corpo = (f"<v6:executeXMLQuery><v6:report><v6:reportPath>{escape(caminho)}</v6:reportPath></v6:report>"
                 "<v6:outputFormat>SAWRowsetSchemaAndData</v6:outputFormat>"
                 f"<v6:executionOptions><v6:async>false</v6:async><v6:maxRowsPerPage>{maximo_linhas}</v6:maxRowsPerPage><v6:refresh>true</v6:refresh>"
                 "<v6:presentationInfo>true</v6:presentationInfo><v6:type>x</v6:type></v6:executionOptions>"
                 f"<v6:sessionID>{self.sessao}</v6:sessionID></v6:executeXMLQuery>")
        resposta = self._chamar("xmlViewService", corpo)
        rowset = resposta.findtext(f".//{{{NS_V6}}}rowset") or ""
        return ler_rowset(rowset)


def ler_rowset(texto: str) -> list[dict[str, str]]:
    """Converte o rowset do OBIEE (XML dentro do SOAP) em linhas {coluna: valor}. Colunas sem valor ficam como "" (o OBIEE omite a tag)."""
    if not texto.strip():
        return []
    raiz = etree.fromstring(texto.encode("utf-8"))
    cabecalhos: dict[str, str] = {}
    for elemento in raiz.iter("{http://www.w3.org/2001/XMLSchema}element"):
        nome, titulo = elemento.get("name"), elemento.get(f"{{{NS_SQL}}}columnHeading")
        if nome and titulo:
            cabecalhos[nome] = titulo
    linhas = []
    for linha in raiz.iter(f"{{{NS_ROWSET}}}Row"):
        registro = dict.fromkeys(cabecalhos.values(), "")
        for coluna in linha:
            chave = etree.QName(coluna).localname
            registro[cabecalhos.get(chave, chave)] = (coluna.text or "").strip()
        linhas.append(registro)
    return linhas
