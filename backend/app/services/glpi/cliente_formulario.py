# Criado por José Eduardo Santana Martins
# Este arquivo serve para entrar no GLPI pela tela web com a conta de serviço e ler/enviar um formulário nativo do GLPI 11 (a API REST não envia formulários).
"""Cliente web do GLPI para formulários nativos (GLPI 11).

O GLPI 11 só recebe o envio de um formulário pela tela web (`POST /Form/SubmitAnswers`), com sessão autenticada e token CSRF. O token da API REST não serve
(não é um identificador de sessão web). Este cliente:

1. abre a tela de login, lê os campos (`login_name` e `login_password` no GLPI 11) e o token CSRF, e entra com a conta de serviço;
2. abre `/Form/Render/<id>` e devolve as perguntas (`answers_<id>`), o tipo do campo, o rótulo e as opções de resposta;
3. (envio) manda as respostas; o próprio formulário dispara os chamados e e-mails configurados nos seus destinos.

O certificado do GLPI é sempre conferido, com o repositório do SISTEMA (onde está a CA interna do órgão).
"""

import re
import ssl
from dataclasses import dataclass, field
from html.parser import HTMLParser

import httpx

from app.services.glpi.cliente_glpi import ErroGlpi

TEMPO_LIMITE_SEGUNDOS = 30


@dataclass
class PerguntaFormulario:
    """Uma pergunta do formulário como a tela a mostra."""
    id: int
    nome: str = ""  # nome do campo enviado (`answers_42[]` nas de escolha, `answers_44` nas demais)
    rotulo: str = ""  # título da pergunta (o `<h3>` da tela)
    tipo: str = ""  # text, number, radio, textarea, file...
    obrigatoria: bool = False
    opcoes: list[tuple[str, str]] = field(default_factory=list)  # (valor enviado, rótulo da opção)
    uploader: str = ""  # perguntas de arquivo: nome do campo de upload (`_uploader_answers_85`)


class _LeitorLogin(HTMLParser):
    """Campos da tela de login do GLPI: usuário (`login_name` no GLPI 11; `field…` com nome sorteado nas versões anteriores), senha, token CSRF e campos escondidos."""

    def __init__(self) -> None:
        super().__init__()
        self.usuario: str | None = None
        self.senha: str | None = None
        self.ocultos: dict[str, str] = {}
        self.csrf: str | None = None
        self.autenticacao: str | None = None

    def handle_starttag(self, tag: str, atributos: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in atributos}
        if tag == "meta" and a.get("property") == "glpi:csrf_token":
            self.csrf = a.get("content")
        if tag == "select" and a.get("name") == "auth":
            self.autenticacao = ""
        if tag == "input":
            nome, tipo = a.get("name", ""), a.get("type", "text")
            if tipo == "hidden" and nome:
                self.ocultos[nome] = a.get("value", "")
                if nome == "_glpi_csrf_token":
                    self.csrf = a.get("value")
            elif tipo == "password" and nome and self.senha is None:
                self.senha = nome
            elif tipo == "text" and (nome == "login_name" or nome.startswith("field")) and self.usuario is None:
                self.usuario = nome


class _LeitorFormulario(HTMLParser):
    """Perguntas (`answers_<id>`) de `/Form/Render/<id>`: título (`<h3>`), tipo do campo, obrigatoriedade e opções de escolha (`<label><input radio><span>texto</span></label>`)."""

    def __init__(self) -> None:
        super().__init__()
        self.perguntas: dict[int, PerguntaFormulario] = {}
        self.csrf: str | None = None
        self._titulo: list[str] | None = None
        self._ultimo_titulo = ""
        self._em_rotulo = False
        self._texto_rotulo: list[str] = []
        self._opcao_pendente: tuple[PerguntaFormulario, str] | None = None

    def handle_starttag(self, tag: str, atributos: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in atributos}
        if tag == "meta" and a.get("property") == "glpi:csrf_token":
            self.csrf = a.get("content")
        if tag == "h3" and "modal-title" not in a.get("class", ""):
            self._titulo = []  # o título de um modal de ajuda (ex.: "Tipos de Documentos") não é título de pergunta
        if tag == "label":
            self._em_rotulo, self._texto_rotulo, self._opcao_pendente = True, [], None
        if tag in ("input", "textarea", "select"):
            nome = a.get("name", "")
            upload = re.match(r"^_uploader_answers_(\d+)\[\]$", nome)
            if upload:
                numero = int(upload.group(1))
                pergunta = self.perguntas.setdefault(numero, PerguntaFormulario(id=numero, rotulo=self._ultimo_titulo))
                pergunta.uploader = f"_uploader_answers_{numero}"
                pergunta.tipo = pergunta.tipo or "file"  # texto longo também tem upload (imagens no editor): só vira "file" se não há outro campo
                return
            correspondencia = re.match(r"^answers_(\d+)(\[\])?$", nome)
            if not correspondencia:
                return
            numero = int(correspondencia.group(1))
            pergunta = self.perguntas.setdefault(numero, PerguntaFormulario(id=numero, rotulo=self._ultimo_titulo))
            tipo = a.get("type") or tag
            if tipo == "hidden":
                return  # o campo escondido vazio que acompanha as escolhas
            pergunta.nome = nome
            pergunta.tipo = tipo
            if "required" in a or a.get("aria-required") == "true":
                pergunta.obrigatoria = True
            if tipo == "radio":
                self._opcao_pendente = (pergunta, a.get("value", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self._titulo is not None:
            self._ultimo_titulo = " ".join(" ".join(self._titulo).replace("*", " ").split())
            self._titulo = None
        if tag == "label" and self._em_rotulo:
            self._em_rotulo = False
            if self._opcao_pendente is not None:
                pergunta, valor = self._opcao_pendente
                pergunta.opcoes.append((valor, " ".join("".join(self._texto_rotulo).split())))
                self._opcao_pendente = None

    def handle_data(self, dado: str) -> None:
        if self._titulo is not None:
            self._titulo.append(dado)
        if self._em_rotulo:
            self._texto_rotulo.append(dado)

    def lista(self) -> list[PerguntaFormulario]:
        return [self.perguntas[i] for i in sorted(self.perguntas)]


class ClienteFormularioGlpi:
    """Sessão web da conta de serviço no GLPI, para ler e enviar formulários nativos."""

    def __init__(self, url_base: str, usuario: str, senha: str, transporte: httpx.BaseTransport | None = None) -> None:
        self._raiz = url_base.rstrip("/")
        self._usuario, self._senha = usuario, senha
        self._http = httpx.Client(timeout=TEMPO_LIMITE_SEGUNDOS, verify=ssl.create_default_context(), transport=transporte, follow_redirects=False)
        self._csrf: str | None = None
        self._perguntas: list[PerguntaFormulario] = []

    def __enter__(self) -> "ClienteFormularioGlpi":
        self._entrar()
        return self

    def __exit__(self, *_: object) -> None:
        try:
            self._http.get(f"{self._raiz}/front/logout.php", params={"noAUTO": 1})
        except httpx.HTTPError:
            pass  # sair é só limpeza
        finally:
            self._http.close()

    def _pedir(self, metodo: str, caminho: str, **opcoes) -> httpx.Response:
        try:
            return self._http.request(metodo, f"{self._raiz}{caminho}", **opcoes)
        except httpx.HTTPError as erro:
            raise ErroGlpi(f"Não foi possível falar com o GLPI ({type(erro).__name__}).") from erro

    def _entrar(self) -> None:
        pagina = self._pedir("GET", "/")
        leitor = _LeitorLogin()
        leitor.feed(pagina.text)
        if not (leitor.usuario and leitor.senha):
            raise ErroGlpi("Não foi possível ler a tela de login do GLPI.")
        dados = {**leitor.ocultos, leitor.usuario: self._usuario, leitor.senha: self._senha, "submit": ""}
        if leitor.autenticacao is not None:
            dados["auth"] = "local"
        resposta = self._pedir("POST", "/front/login.php", data=dados, headers={"Referer": f"{self._raiz}/"})
        destino = resposta.headers.get("location", "")
        # Login recusado volta para a tela de login com `error=`; login certo redireciona para dentro do GLPI
        if resposta.status_code not in (301, 302, 303) or "error=" in destino or destino.rstrip("/") in ("", self._raiz):
            raise ErroGlpi("O GLPI recusou o login da conta de serviço. Confira o usuário e a senha em Administração > Integração GLPI.")

    def perguntas(self, formulario_id: int) -> tuple[list[PerguntaFormulario], str | None]:
        """(perguntas, token CSRF) do formulário, como a tela de preenchimento mostra."""
        resposta = self._pedir("GET", f"/Form/Render/{formulario_id}")
        if resposta.status_code != 200:
            raise ErroGlpi(f"O GLPI não abriu o formulário {formulario_id} (HTTP {resposta.status_code}). A conta de serviço precisa ter acesso a ele.")
        leitor = _LeitorFormulario()
        leitor.feed(resposta.text)
        self._csrf = leitor.csrf
        self._perguntas = leitor.lista()
        return self._perguntas, leitor.csrf

    def html_do_formulario(self, formulario_id: int) -> str:
        """HTML bruto da tela de preenchimento (diagnóstico)."""
        return self._pedir("GET", f"/Form/Render/{formulario_id}").text

    def subir_arquivo(self, pergunta: PerguntaFormulario, nome: str, conteudo: bytes, tipo_mime: str) -> dict:
        """Envia o arquivo à área temporária do GLPI (`/ajax/fileupload.php`, como o formulário faz ao escolher o arquivo) e devolve o que ele registrou (`name`, `prefix`, `tag`...).
        O arquivo só passa a valer quando o formulário é enviado com ele (`enviar(..., arquivos=...)`)."""
        if not pergunta.uploader:
            raise ErroGlpi(f"A pergunta \"{pergunta.rotulo}\" do formulário não aceita arquivo.")
        if not self._csrf:
            raise ErroGlpi("Abra o formulário (perguntas) antes de enviar arquivos.")
        resposta = self._pedir("POST", "/ajax/fileupload.php", files={f"{pergunta.uploader}[]": (nome, conteudo, tipo_mime)}, data={"name": pergunta.uploader, "showfilesize": "true"},
                               headers={"X-Glpi-Csrf-Token": self._csrf, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = None
        if resposta.status_code != 200 or not isinstance(corpo, dict):
            raise ErroGlpi(f"O GLPI recusou o arquivo \"{nome}\" (HTTP {resposta.status_code}).")
        arquivos = next((v for v in corpo.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [])
        enviado = arquivos[0] if arquivos else {}
        if enviado.get("error") or not enviado.get("name"):
            raise ErroGlpi(f"O GLPI recusou o arquivo \"{nome}\": {enviado.get('error') or 'resposta inesperada'}.")
        return enviado

    def enviar(self, formulario_id: int, respostas: dict[int, str], arquivos: dict[int, list[dict]] | None = None) -> dict:
        """Envia o formulário (id da pergunta → valor; nas de escolha, o valor é a chave da opção). O GLPI dispara os destinos do formulário (chamados e e-mails).
        Os campos vão como o navegador os manda (`answers_42[]` com o campo escondido vazio antes). `arquivos`: id da pergunta de arquivo → retornos de `subir_arquivo`.
        Devolve os links dos itens criados."""
        if not self._csrf or not self._perguntas:
            self.perguntas(formulario_id)
        nomes = {p.id: p.nome for p in self._perguntas}
        desconhecidas = sorted(set(respostas) - set(nomes))
        if desconhecidas:
            raise ErroGlpi(f"O formulário {formulario_id} não tem as perguntas {desconhecidas}: ele mudou no GLPI.")
        dados: dict[str, str | list[str]] = {"forms_id": str(formulario_id)}
        for pergunta_id, valor in respostas.items():
            nome = nomes[pergunta_id]
            dados[nome] = ["", valor] if nome.endswith("[]") else valor
        for pergunta_id, enviados in (arquivos or {}).items():
            for i, arquivo in enumerate(enviados):
                dados[f"_answers_{pergunta_id}[{i}]"] = arquivo["name"]
                dados[f"_prefix_answers_{pergunta_id}[{i}]"] = arquivo.get("prefix", "")
                dados[f"_tag_answers_{pergunta_id}[{i}]"] = arquivo.get("tag", "")
        resposta = self._pedir("POST", "/Form/SubmitAnswers", data=dados, headers={"X-Glpi-Csrf-Token": self._csrf or "", "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
        try:
            corpo = resposta.json()
        except ValueError:
            corpo = {}
        if resposta.status_code != 200:
            erros = corpo.get("errors") if isinstance(corpo, dict) else None
            raise ErroGlpi(f"O GLPI recusou o envio do formulário (HTTP {resposta.status_code})." + (f" {' '.join(map(str, erros))}" if erros else ""))
        return corpo
