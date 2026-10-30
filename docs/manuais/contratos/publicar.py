#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para publicar o manual do Módulo Contratos (Processo Financeiro, prorrogação, reajuste e as versões retroativas) no BookStack (capítulo, páginas e imagens), pela API.
"""Publica (ou atualiza) as páginas novas do Módulo RH no BookStack, no capítulo que já existe.

Uso:
    python3 publicar.py --verificar     # confere que todo [[marcador]] tem imagem e legenda, sem acessar o BookStack
    python3 publicar.py                 # cria (ou atualiza) as páginas no capítulo "Módulo Contratos" do livro "sgi-spi", com as imagens

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
    ("1-processo-financeiro.html", "Processo Financeiro: o que é, como pedir e como o Financeiro preenche"),
    ("2-prorrogacao.html", "Prorrogação do contrato"),
    ("3-reajuste.html", "Reajuste do contrato"),
    ("4-vigencia-retroativa.html", "Vigência retroativa: voltar o contrato no tempo"),
    ("5-reajuste-retroativo.html", "Reajuste retroativo"),
]
PRIORIDADE_INICIAL = 20  # depois das páginas que já existem no capítulo
LEGENDAS = {}
PADRAO_LEGENDA = "Tela do SGI SPI"


def legendas_numeradas(nome: str) -> str:
    """Lista numerada que explica as marcações (setas e números) desenhadas na imagem, lida de `legendas.json`."""
    arquivo = AQUI / "legendas.json"
    itens = json.loads(arquivo.read_text(encoding="utf-8")).get(nome, []) if arquivo.is_file() else []
    itens = [i for i in itens if i.get("texto")]
    if not itens:
        return ""
    return "<ol>" + "".join(f'<li value="{i["n"]}">{html.escape(i["texto"])}</li>' for i in itens) + "</ol>"


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


def verificar() -> None:
    """Todo [[marcador]] precisa de imagem em imagens/ e de legenda em legendas.json."""
    legendas = json.loads((AQUI / "legendas.json").read_text(encoding="utf-8"))
    problemas = []
    usados = set()
    for arquivo, _ in PAGINAS:
        for marcador in re.findall(r"\[\[([\w-]+)\]\]", (AQUI / "paginas" / arquivo).read_text(encoding="utf-8")):
            usados.add(marcador)
            if not (AQUI / "imagens" / f"{marcador}.png").is_file():
                problemas.append(f"{arquivo}: falta a imagem {marcador}.png")
            if not legendas.get(marcador):
                problemas.append(f"{arquivo}: falta a legenda de {marcador}")
    sem_uso = sorted(p.stem for p in (AQUI / "imagens").glob("*.png") if p.stem not in usados)
    print(f"{len(usados)} imagens usadas nas {len(PAGINAS)} páginas.", "Problemas:" if problemas else "Tudo certo.", *problemas, sep="\n  " if problemas else " ")
    if sem_uso:
        print("Imagens sem uso nas páginas:", ", ".join(sem_uso))


def main() -> None:
    global TOKEN
    parser = argparse.ArgumentParser()
    parser.add_argument("--livro-slug", default="sgi-spi")
    parser.add_argument("--capitulo", default="Módulo Contratos")
    parser.add_argument("--verificar", action="store_true")
    args = parser.parse_args()
    if args.verificar:
        verificar()
        return
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
        capitulo = chamar("POST", "/chapters", {"book_id": livro["id"], "name": args.capitulo, "description": "Manual do Módulo Contratos do SGI SPI."})
        existentes = {}
    else:
        existentes = {p["name"]: p for p in chamar("GET", f"/chapters/{capitulo['id']}").get("pages", [])}
    print("capítulo", capitulo["id"], capitulo["slug"])
    for indice, (arquivo, nome) in enumerate(PAGINAS):
        fonte = (AQUI / "paginas" / arquivo).read_text(encoding="utf-8")
        pagina = existentes.get(nome) or chamar("POST", "/pages", {"chapter_id": capitulo["id"], "name": nome, "html": "<p>Em elaboração.</p>", "priority": PRIORIDADE_INICIAL + indice})
        imagens = {}
        for marcador in dict.fromkeys(re.findall(r"\[\[([\w-]+)\]\]", fonte)):
            imagens[marcador] = chamar("POST", "/image-gallery", arquivo=str(AQUI / "imagens" / f"{marcador}.png"),
                                       campos={"type": "gallery", "uploaded_to": pagina["id"], "name": marcador + ".png"})

        def trocar(m):
            img = imagens[m.group(1)]
            alt = html.escape(LEGENDAS.get(m.group(1), PADRAO_LEGENDA) + " – " + m.group(1))
            exibicao = (img.get("thumbs") or {}).get("display") or img["url"]
            return f'<p><a href="{img["url"]}" target="_blank" rel="noopener"><img src="{exibicao}" alt="{alt}"></a></p>' + legendas_numeradas(m.group(1))

        chamar("PUT", f"/pages/{pagina['id']}", {"html": re.sub(r"\[\[([\w-]+)\]\]", trocar, fonte), "priority": PRIORIDADE_INICIAL + indice})
        print("página", pagina["id"], nome, "-", len(imagens), "imagens")
    print(f"{BASE[:-4]}/books/{livro['slug']}/chapter/{capitulo['slug']}")


if __name__ == "__main__":
    main()
