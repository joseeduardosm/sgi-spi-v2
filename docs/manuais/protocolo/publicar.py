#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para publicar o manual do Módulo Protocolo no BookStack (capítulo, páginas e imagens), pela API.
"""Publica (ou atualiza) o manual do Protocolo no BookStack.

Uso:
    python3 publicar.py                 # cria o capítulo "Módulo Protocolo" no livro "sgi-spi" e as páginas, com as imagens
    python3 publicar.py --livro-slug sgi-spi --capitulo "Módulo Protocolo"

Credencial: um token de API do BookStack de um usuário que possa criar e editar páginas (Meu perfil › Tokens de API; o perfil precisa da
permissão "Acessar a API do sistema"). Guarde `ID:SEGREDO` na primeira linha de `~/.bookstack-token` (ou aponte a variável
`BOOKSTACK_TOKEN_ARQUIVO`). O token da integração de leitura do portal NÃO serve: ele só lê.

Alternativa sem token: defina BOOKSTACK_USUARIO e BOOKSTACK_SENHA (login pelo formulário; a sessão vale na API).

Idempotente: se o capítulo ou uma página já existir (mesmo nome), a página é atualizada e as imagens são enviadas de novo.
Cada `[[nome]]` nas páginas HTML vira a imagem `imagens/nome.png`.
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import http.cookiejar
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BASE = os.environ.get("BOOKSTACK_URL", "https://instrucoes.spi.sp.gov.br").rstrip("/") + "/api"
PAGINAS = [
    ("1-visao-geral.html", "Protocolo: visão geral"),
    ("2-reservar-numero.html", "Reservar um número e anexar o documento"),
    ("3-historico-sigilo-contratos.html", "Linha do tempo, sigilo e vínculo com contratos"),
    ("4-administracao.html", "Administração do Protocolo"),
    ("5-painel-exportacao-avisos.html", "Painel, exportação e avisos"),
]
LEGENDAS = {"r": "Tela do SGI SPI", "a": "Tela do SGI SPI", "l": "Tela do SGI SPI", "p": "Tela do SGI SPI", "c": "Tela do SGI SPI",
            "e": "Relatório em PDF gerado pelo SGI SPI", "v": "Tela do SGI SPI"}


def token() -> str:
    caminho = Path(os.environ.get("BOOKSTACK_TOKEN_ARQUIVO", Path.home() / ".bookstack-token"))
    if not caminho.is_file():
        sys.exit(f"Token não encontrado em {caminho}. Veja as instruções no começo deste arquivo.")
    return caminho.read_text().splitlines()[0].strip()


TOKEN = None
ABRIDOR = None


def entrar_por_sessao(usuario: str, senha: str) -> None:
    """Alternativa ao token: entra pelo formulário de login (BookStack aceita a sessão na API) com BOOKSTACK_USUARIO e BOOKSTACK_SENHA."""
    global ABRIDOR
    ABRIDOR = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    raiz = BASE[:-4]
    pagina = ABRIDOR.open(raiz + "/login", timeout=60).read().decode()
    csrf = re.search(r'name="_token"\s+value="([^"]+)"', pagina) or re.search(r'value="([^"]+)"\s+name="_token"', pagina)
    dados = urllib.parse.urlencode({"_token": csrf.group(1) if csrf else "", "username": usuario, "password": senha}).encode()
    resposta = ABRIDOR.open(urllib.request.Request(raiz + "/login", data=dados), timeout=60)
    if "/login" in resposta.geturl():
        sys.exit("Login recusado pelo BookStack.")


def chamar(metodo, caminho, dados=None, arquivo=None, campos=None):
    cab = {} if ABRIDOR else {"Authorization": f"Token {TOKEN}"}
    corpo = None
    if arquivo:
        limite = uuid.uuid4().hex
        partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in (campos or {}).items()]
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="image"; filename="{os.path.basename(arquivo)}"\r\nContent-Type: image/png\r\n\r\n'.encode()
                      + open(arquivo, "rb").read() + b"\r\n")
        corpo = b"".join(partes) + f"--{limite}--\r\n".encode()
        cab["Content-Type"] = f"multipart/form-data; boundary={limite}"
    elif dados is not None:
        corpo = json.dumps(dados).encode()
        cab["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + caminho, data=corpo, headers=cab, method=metodo)
    try:
        with (ABRIDOR.open(req, timeout=120) if ABRIDOR else urllib.request.urlopen(req, timeout=120)) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as erro:
        sys.exit(f"{metodo} {caminho}: {erro.code} {erro.read()[:500]}")


def main() -> None:
    global TOKEN
    parser = argparse.ArgumentParser()
    parser.add_argument("--livro-slug", default="sgi-spi")
    parser.add_argument("--capitulo", default="Módulo Protocolo")
    args = parser.parse_args()
    if os.environ.get("BOOKSTACK_USUARIO"):
        entrar_por_sessao(os.environ["BOOKSTACK_USUARIO"], os.environ["BOOKSTACK_SENHA"])
    else:
        TOKEN = token()
    livro = next((b for b in chamar("GET", "/books?count=500")["data"] if b["slug"] == args.livro_slug), None)
    if livro is None:
        sys.exit(f"Livro '{args.livro_slug}' não encontrado.")
    detalhe = chamar("GET", f"/books/{livro['id']}")
    capitulo = next((c for c in detalhe.get("contents", []) if c["type"] == "chapter" and c["name"] == args.capitulo), None)
    if capitulo is None:
        capitulo = chamar("POST", "/chapters", {"book_id": livro["id"], "name": args.capitulo, "description":
                          "Manual do Módulo Protocolo do SGI SPI: reserva de números, documentos, sigilo, vínculo com contratos, administração, painel e avisos."})
        existentes = {}
    else:
        existentes = {p["name"]: p for p in chamar("GET", f"/chapters/{capitulo['id']}").get("pages", [])}
    print("capítulo", capitulo["id"], capitulo["slug"])
    for arquivo, nome in PAGINAS:
        fonte = (AQUI / "paginas" / arquivo).read_text(encoding="utf-8")
        pagina = existentes.get(nome) or chamar("POST", "/pages", {"chapter_id": capitulo["id"], "name": nome, "html": "<p>Em elaboração.</p>"})
        imagens = {}
        for marcador in dict.fromkeys(re.findall(r"\[\[([\w-]+)\]\]", fonte)):
            imagens[marcador] = chamar("POST", "/image-gallery", arquivo=str(AQUI / "imagens" / f"{marcador}.png"),
                                       campos={"type": "gallery", "uploaded_to": pagina["id"], "name": marcador + ".png"})

        def trocar(m):
            img = imagens[m.group(1)]
            alt = html.escape(LEGENDAS.get(m.group(1)[0], "Imagem") + " – " + m.group(1))
            exibicao = (img.get("thumbs") or {}).get("display") or img["url"]
            return f'<p><a href="{img["url"]}" target="_blank" rel="noopener"><img src="{exibicao}" alt="{alt}"></a></p>'

        chamar("PUT", f"/pages/{pagina['id']}", {"html": re.sub(r"\[\[([\w-]+)\]\]", trocar, fonte)})
        print("página", pagina["id"], nome, "-", len(imagens), "imagens")
    print(f"{BASE[:-4]}/books/{livro['slug']}/chapter/{capitulo['slug']}")


if __name__ == "__main__":
    main()
