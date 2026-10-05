# Criado por José Eduardo Santana Martins
# Este arquivo serve para falar com a API REST do GLPI (abrir sessão, achar usuário e criar chamado).
"""Cliente da API REST do GLPI (`/apirest.php`).

Uso (sempre em `with`, que abre e encerra a sessão):

    with ClienteGlpi(url_base, app_token, user_token) as glpi:
        usuario_id = glpi.buscar_usuario("maria.silva")
        chamado = glpi.criar_chamado({...})

O servidor fala com o GLPI; o navegador nunca vê os tokens. Qualquer falha de rede ou resposta de erro vira `ErroGlpi`
com uma mensagem curta (o detalhe técnico vai para o log, não para a tela).
"""

import json
import logging
import ssl
import time

import httpx

registro = logging.getLogger("sgi_spi.glpi")
TEMPO_LIMITE_SEGUNDOS = 15


class ErroGlpi(Exception):
    """Falha ao falar com o GLPI (rede, autenticação ou regra do GLPI)."""

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class ClienteGlpi:
    """Sessão na API do GLPI com o `user_token` da conta de serviço (e o `App-Token`, quando o cliente de API exige)."""

    def __init__(self, url_base: str, app_token: str, user_token: str, transporte: httpx.BaseTransport | None = None) -> None:
        self._base = url_base.rstrip("/") + "/apirest.php"
        self._app_token = app_token
        self._user_token = user_token
        # Certificado conferido sempre, com o repositório do SISTEMA (onde está a CA interna do órgão); o `certifi` padrão do httpx não a conhece
        self._http = httpx.Client(timeout=TEMPO_LIMITE_SEGUNDOS, verify=ssl.create_default_context(), transport=transporte)
        self._sessao: str | None = None
        self.latencia_ms = 0

    # --- sessão -------------------------------------------------------------------------------

    def __enter__(self) -> "ClienteGlpi":
        inicio = time.monotonic()
        cabecalhos = {"Authorization": f"user_token {self._user_token}"}
        if self._app_token:
            cabecalhos["App-Token"] = self._app_token
        resposta = self._chamar("GET", "/initSession", cabecalhos=cabecalhos, sessao=False)
        self._sessao = resposta.get("session_token") if isinstance(resposta, dict) else None
        if not self._sessao:
            raise ErroGlpi("O GLPI não abriu a sessão da integração.")
        self.latencia_ms = round((time.monotonic() - inicio) * 1000)
        return self

    def __exit__(self, *_: object) -> None:
        try:
            if self._sessao:
                self._chamar("GET", "/killSession")
        except ErroGlpi:
            pass  # encerrar a sessão é só limpeza; o erro não importa
        finally:
            self._http.close()

    # --- operações ----------------------------------------------------------------------------

    def buscar_usuario(self, valor: str, por_email: bool = False) -> int | None:
        """Id do usuário no GLPI pelo login (campo 1) ou pelo e-mail (campo 5); `None` se não existir.

        O GLPI 11 não casa o login com `equals`; por isso a busca é por `contains` e só vale o resultado **idêntico**
        (sem diferenciar maiúsculas), para `jesmartins` nunca pegar `xjesmartins`.
        """
        valor = (valor or "").strip()
        if not valor:
            return None
        campo = "5" if por_email else "1"
        consulta = {
            "criteria[0][field]": campo,
            "criteria[0][searchtype]": "contains",
            "criteria[0][value]": valor,
            "forcedisplay[0]": "1",
            "forcedisplay[1]": "2",
            "range": "0-49",
        }
        resposta = self._chamar("GET", "/search/User", parametros=consulta)
        for linha in (resposta.get("data") or []) if isinstance(resposta, dict) else []:
            achado = linha.get(campo)
            # No e-mail o GLPI pode devolver mais de um valor (lista); basta um igual
            candidatos = achado if isinstance(achado, list) else [achado]
            if any(str(c or "").strip().lower() == valor.lower() for c in candidatos):
                try:
                    return int(linha["2"])
                except (KeyError, TypeError, ValueError):
                    return None
        return None

    def listar_localizacoes(self) -> list[tuple[int, str]]:
        """Localizações do GLPI como (id, nome completo, ex.: `05º Andar > Lado B`), em ordem alfabética (a pergunta "Local do Problema" do formulário)."""
        consulta = {"forcedisplay[0]": "1", "forcedisplay[1]": "2", "range": "0-999"}
        resposta = self._chamar("GET", "/search/Location", parametros=consulta)
        locais = []
        for linha in (resposta.get("data") or []) if isinstance(resposta, dict) else []:
            try:
                locais.append((int(linha["2"]), str(linha["1"])))
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(locais, key=lambda l: l[1].lower())

    def criar_chamado(self, dados: dict, anexos: list[tuple[str, bytes, str]] | None = None) -> int:
        """Cria o chamado e devolve o número dele no GLPI.

        Com `anexos` [(nome, conteúdo, tipo)], o chamado é criado já com os arquivos (envio multipart com `_filename`, como a tela do GLPI faz):
        o perfil da conta de serviço não tem direito de ligar documentos depois, mas pode anexá-los na criação.
        """
        if anexos:
            entrada = {**dados, "_filename": [nome for nome, _, _ in anexos]}
            arquivos = {"uploadManifest": (None, json.dumps({"input": entrada}), "application/json")}
            arquivos.update({f"filename[{n}]": (nome, conteudo, tipo) for n, (nome, conteudo, tipo) in enumerate(anexos)})
            resposta = self._chamar("POST", "/Ticket", arquivos=arquivos)
        else:
            resposta = self._chamar("POST", "/Ticket", json={"input": dados})
        try:
            return int(resposta["id"])
        except (KeyError, TypeError, ValueError):
            registro.error("Resposta inesperada do GLPI ao criar o chamado: %s", resposta)
            raise ErroGlpi("O GLPI não confirmou a criação do chamado.") from None

    # --- baixo nível --------------------------------------------------------------------------

    def _chamar(self, metodo: str, caminho: str, *, cabecalhos: dict | None = None, parametros: dict | None = None,
                json: dict | None = None, arquivos: dict | None = None, sessao: bool = True):
        cab = dict(cabecalhos or {})
        if sessao and self._sessao:
            cab["Session-Token"] = self._sessao
            if self._app_token:
                cab["App-Token"] = self._app_token
        try:
            resposta = self._http.request(metodo, self._base + caminho, headers=cab, params=parametros, json=json, files=arquivos)
        except httpx.HTTPError as erro:
            registro.warning("Falha de rede com o GLPI (%s %s): %s", metodo, caminho, erro)
            raise ErroGlpi("Não foi possível falar com o GLPI.") from erro
        if resposta.status_code >= 400:
            registro.warning("GLPI respondeu %s em %s %s: %s", resposta.status_code, metodo, caminho, resposta.text[:300])
            raise ErroGlpi(_mensagem(resposta))
        try:
            return resposta.json()
        except ValueError:
            return {}


def _mensagem(resposta: httpx.Response) -> str:
    """Mensagem curta para o erro do GLPI (o GLPI responde `["ERRO_CODIGO", "texto"]`)."""
    try:
        corpo = resposta.json()
        if isinstance(corpo, list) and len(corpo) > 1:
            texto = str(corpo[1])
            if "ERROR_API_DISABLED" in str(corpo[0]) or "desativada" in texto.lower():
                return "A API do GLPI está desativada."
            if resposta.status_code in (401, 403):
                return "O GLPI recusou as credenciais da integração."
            return f"O GLPI recusou o pedido: {texto[:150]}"
    except ValueError:
        pass
    if resposta.status_code in (401, 403):
        return "O GLPI recusou as credenciais da integração."
    return f"O GLPI respondeu com erro {resposta.status_code}."
