# Criado por José Eduardo Santana Martins
# Este arquivo serve para falar com a API REST do BookStack (somente leitura): listas, livros, páginas, busca e imagens.
"""Cliente da API REST do BookStack (`/api`).

Uso (sempre em `with`, que fecha a conexão):

    with ClienteBookstack(url_base, token_id, token_segredo) as bookstack:
        livros = bookstack.listar("/books")
        pagina = bookstack.obter("/pages/12")

O servidor fala com o BookStack; o navegador nunca vê o token. Qualquer falha de rede ou resposta de erro vira `ErroBookstack`
com uma mensagem curta (o detalhe técnico vai para o log, não para a tela).
"""

import logging
import ssl
import time

import httpx

registro = logging.getLogger("sgi_spi.bookstack")
TEMPO_LIMITE_SEGUNDOS = 15
# Tamanho máximo de uma imagem repassada ao navegador
TAMANHO_MAXIMO_IMAGEM = 15 * 1024 * 1024
# O BookStack devolve no máximo 500 itens por página de listagem
TAMANHO_PAGINA = 500


class ErroBookstack(Exception):
    """Falha ao falar com o BookStack (rede, credenciais ou regra do BookStack)."""

    def __init__(self, mensagem: str, nao_encontrado: bool = False) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.nao_encontrado = nao_encontrado


class ClienteBookstack:
    """Acesso à API do BookStack com o token (ID + segredo) de uma conta de serviço só de leitura."""

    def __init__(self, url_base: str, token_id: str, token_segredo: str, transporte: httpx.BaseTransport | None = None) -> None:
        self.base = url_base.rstrip("/")
        self._cabecalhos = {"Authorization": f"Token {token_id}:{token_segredo}", "Accept": "application/json"}
        # Certificado conferido sempre, com o repositório do SISTEMA (onde está a CA interna do órgão)
        self._http = httpx.Client(timeout=TEMPO_LIMITE_SEGUNDOS, verify=ssl.create_default_context(), transport=transporte)
        self.latencia_ms = 0

    def __enter__(self) -> "ClienteBookstack":
        return self

    def __exit__(self, *_: object) -> None:
        self._http.close()

    # --- operações ----------------------------------------------------------------------------

    def testar(self) -> int:
        """Pede uma listagem mínima; devolve quantos livros a conta de serviço enxerga."""
        inicio = time.monotonic()
        resposta = self.obter("/books", {"count": 1})
        self.latencia_ms = round((time.monotonic() - inicio) * 1000)
        return int(resposta.get("total", 0)) if isinstance(resposta, dict) else 0

    def obter(self, caminho: str, parametros: dict | None = None):
        """GET em `/api<caminho>`; devolve o JSON."""
        resposta = self._pedir(self.base + "/api" + caminho, parametros)
        try:
            return resposta.json()
        except ValueError:
            raise ErroBookstack("O BookStack respondeu algo que não é JSON.") from None

    def listar(self, caminho: str, parametros: dict | None = None) -> list[dict]:
        """Todos os itens de uma listagem (percorre as páginas de 500 em 500)."""
        itens: list[dict] = []
        deslocamento = 0
        while True:
            resposta = self.obter(caminho, {**(parametros or {}), "count": TAMANHO_PAGINA, "offset": deslocamento})
            lote = resposta.get("data", []) if isinstance(resposta, dict) else []
            itens.extend(lote)
            deslocamento += len(lote)
            if not lote or deslocamento >= int(resposta.get("total", 0)):
                return itens

    def baixar_imagem(self, caminho: str) -> tuple[bytes, str]:
        """Baixa uma imagem de `/uploads/...` da própria instância; devolve (bytes, tipo)."""
        resposta = self._pedir(self.base + caminho, None)
        tipo = resposta.headers.get("content-type", "").split(";")[0].strip().lower()
        if not tipo.startswith("image/"):
            raise ErroBookstack("O endereço não é uma imagem.", nao_encontrado=True)
        if len(resposta.content) > TAMANHO_MAXIMO_IMAGEM:
            raise ErroBookstack("Imagem grande demais.")
        return resposta.content, tipo

    # --- baixo nível --------------------------------------------------------------------------

    def _pedir(self, url: str, parametros: dict | None) -> httpx.Response:
        try:
            resposta = self._http.get(url, headers=self._cabecalhos, params=parametros)
        except httpx.HTTPError as erro:
            registro.warning("Falha de rede com o BookStack (%s): %s", url, erro)
            raise ErroBookstack("Não foi possível falar com o BookStack.") from erro
        if resposta.status_code >= 400:
            registro.warning("BookStack respondeu %s em %s: %s", resposta.status_code, url, resposta.text[:300])
            if resposta.status_code == 404:
                raise ErroBookstack("Conteúdo não encontrado no BookStack.", nao_encontrado=True)
            if resposta.status_code in (401, 403):
                raise ErroBookstack("O BookStack recusou as credenciais da integração (ou a conta de serviço não pode ler isto).")
            raise ErroBookstack(f"O BookStack respondeu com erro {resposta.status_code}.")
        return resposta
