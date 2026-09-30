#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para migrar as notícias e os atalhos do portal do 10.23.1.243 para o Módulo Notícias do SGI SPI.
"""Migra o portal de notícias do 10.23.1.243 para o Módulo Notícias.

Lê o pacote de `scripts/extrair-noticias-243.py`:
- `PUBLICADA`/`AGENDADA` → `aprovada` (aprovador "Migração 10.23.1.243"), com a data de publicação original;
  `RASCUNHO` → `rascunho`;
- o texto puro vira parágrafos HTML; o slug sai do título;
- capa: proporção entre 1,9 e 2,1 → recorte 2:1 central; outras → modo "imagem inteira" (sem cortar a arte);
- anexos pelo `servico_anexos` (formato conferido pelo conteúdo);
- categoria sugerida por palavras do título (pode ser trocada depois na gestão);
- atalhos com a imagem; endereços relativos do 243 viram endereços completos da intranet antiga.
Nenhum aviso é disparado.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-noticias-243.py <pacote>                  # ensaio: carrega, confere e desfaz
    .venv/bin/python ../scripts/migrar-noticias-243.py <pacote> --gravar         # grava
    ... --gravar --substituir   # apaga antes o que veio de uma carga anterior (notícias da migração e atalhos)
"""

import argparse
import csv
import sys
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.core.banco import FabricaSessao, agora_utc  # noqa: E402
from app.models.noticias import AnexoNoticia, AtalhoPortal, CategoriaNoticia, Noticia, RevisaoNoticia  # noqa: E402
from app.services import servico_anexos  # noqa: E402
from app.services.noticias import imagens  # noqa: E402
from app.services.noticias.sanitizacao import texto_para_html  # noqa: E402
from app.services.noticias.servico_noticias import _slug_unico  # noqa: E402

AUTOR = "Portal 10.23.1.243"
APROVADOR = "Migração 10.23.1.243"
URL_ANTIGA = "http://intranet.spi.sp.gov.br"
# Palavras do título → categoria (sugestão; a primeira que casar vale)
CATEGORIAS = [
    ("Integridade", ("integridade", "corrupcao", "conflito de interesses", "nepotismo", "brindes", "presentes", "valores da administracao",
                     "etica", "assedio", "respeito", "estatuto", "eleitoral")),
    ("Saúde e bem-estar", ("saude", "vacina", "setembro amarelo", "agosto lilas", "cuidado", "escutar", "mulher segura")),
    ("Campanhas", ("campanha", "agasalho")),
    ("Tecnologia", ("tecnologia", "intranet", "sistema", "intermitencia", "dados atualizados", "sppatri", "imposto de renda")),
    ("Eventos", ("torcida", "espaco de convivencia", "palestra", "evento")),
]


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()


def _instante(v: str | None) -> datetime | None:
    if not v:
        return None
    v = v.replace(" ", "T", 1)
    if v[-3] in "+-" and ":" not in v[-3:]:
        v += ":00"
    return datetime.fromisoformat(v)


def _categoria(sessao, titulo: str) -> CategoriaNoticia | None:
    alvo = _sem_acento(titulo)
    for nome, palavras in CATEGORIAS:
        if any(p in alvo for p in palavras):
            return sessao.scalar(select(CategoriaNoticia).where(CategoriaNoticia.nome == nome))
    return None


def _capa(sessao, noticia: Noticia, arquivo: Path) -> str:
    conteudo = arquivo.read_bytes()
    figura, tipo = imagens.abrir(conteudo)
    proporcao = figura.width / figura.height
    noticia.capa_modo = "recortar" if 1.9 <= proporcao <= 2.1 else "inteira"
    original = servico_anexos.guardar_arquivo_gerado(sessao, conteudo, arquivo.name, tipo, "noticia-capa", None)
    versoes, usado = imagens.versoes_capa(figura, noticia.capa_modo, None)
    noticia.capa_anexo_id, noticia.capa_recorte = original.id, usado
    noticia.capa_versoes = {t: str(servico_anexos.guardar_arquivo_gerado(sessao, v, f"capa-{t}.webp", "image/webp", "noticia-capa-versao", None).id)
                            for t, v in versoes.items()}
    return noticia.capa_modo


def migrar(pacote: Path, sessao) -> dict:
    contagem = {"noticias": 0, "aprovadas": 0, "rascunhos": 0, "anexos": 0, "atalhos": 0, "capa_recortar": 0, "capa_inteira": 0, "sem_categoria": 0}
    avisos = []
    for r in csv.DictReader(open(pacote / "noticias_noticia.csv", encoding="utf-8", newline="")):
        situacao = "rascunho" if r["status"] == "RASCUNHO" else "aprovada"
        publicar = _instante(r["data_publicacao"])
        categoria = _categoria(sessao, r["titulo"])
        noticia = Noticia(
            slug=_slug_unico(sessao, r["titulo"]), titulo=r["titulo"][:220], linha_fina="", corpo_html=texto_para_html(r["texto_noticia"]),
            categoria_id=categoria.id if categoria else None, situacao=situacao, publicar_em=publicar,
            fixada=r["fixada"] in ("t", "true", "True"), capa_alt=r["titulo"][:300], autor_nome=AUTOR,
            aprovado_por_nome=APROVADOR if situacao == "aprovada" else None, aprovado_em=publicar if situacao == "aprovada" else None,
            versao=1, criado_em=_instante(r["criado_em"]) or agora_utc(),
        )
        sessao.add(noticia)
        sessao.flush()
        contagem["capa_" + _capa(sessao, noticia, pacote / "midia" / r["imagem_destaque"])] += 1
        if r["anexo_pdf"]:
            arquivo = pacote / "midia" / r["anexo_pdf"]
            try:
                anexo = servico_anexos.guardar_arquivo(sessao, BytesIO(arquivo.read_bytes()), arquivo.name, "noticia-anexo", None)
                noticia.anexos.append(AnexoNoticia(anexo_id=anexo.id, ordem=0))
                contagem["anexos"] += 1
            except servico_anexos.ErroAnexo as erro:
                avisos.append(f"anexo recusado em \"{r['titulo']}\": {erro}")
        sessao.add(RevisaoNoticia(noticia_id=noticia.id, versao=1, descricao="Migrada do 10.23.1.243", titulo=noticia.titulo,
                                  linha_fina="", corpo_html=noticia.corpo_html, autor_nome=APROVADOR, criado_em=agora_utc()))
        contagem["noticias"] += 1
        contagem["aprovadas" if situacao == "aprovada" else "rascunhos"] += 1
        contagem["sem_categoria"] += categoria is None
    for r in csv.DictReader(open(pacote / "atalhos_atalho.csv", encoding="utf-8", newline="")):
        url = r["url"] if r["url"].startswith("http") else URL_ANTIGA + r["url"]
        atalho = AtalhoPortal(titulo=r["titulo"][:80], url=url[:500], ativo=r["ativo"] in ("t", "true"), nova_aba=True,
                              ordem=contagem["atalhos"], criado_em=_instante(r["criado_em"]) or agora_utc())
        if r["imagem"]:
            arquivo = pacote / "midia" / r["imagem"]
            figura, tipo = imagens.abrir(arquivo.read_bytes())
            atalho.imagem_anexo_id = servico_anexos.guardar_arquivo_gerado(sessao, arquivo.read_bytes(), arquivo.name, tipo, "portal-atalho", None).id
            atalho.imagem_exibicao_id = servico_anexos.guardar_arquivo_gerado(sessao, imagens.versao_atalho(figura), "atalho.webp", "image/webp",
                                                                              "portal-atalho", None).id
        sessao.add(atalho)
        contagem["atalhos"] += 1
    sessao.flush()
    return contagem | {"avisos": avisos}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pacote", type=Path)
    parser.add_argument("--gravar", action="store_true", help="grava; sem esta opção é só um ensaio (tudo é desfeito)")
    parser.add_argument("--substituir", action="store_true", help="apaga antes as notícias migradas e os atalhos")
    args = parser.parse_args()
    with FabricaSessao() as sessao:
        existentes = sessao.scalar(select(func.count()).select_from(Noticia).where(Noticia.autor_nome == AUTOR))
        if existentes and not args.substituir:
            sys.exit(f"ERRO: {existentes} notícia(s) desta migração já estão no banco. Use --substituir para recarregar.")
        if existentes:
            for n in sessao.scalars(select(Noticia).where(Noticia.autor_nome == AUTOR)):
                sessao.delete(n)
            for a in sessao.scalars(select(AtalhoPortal)):
                sessao.delete(a)
            sessao.flush()
            print(f"Carga anterior removida ({existentes} notícia(s)).")
        resultado = migrar(args.pacote, sessao)
        avisos = resultado.pop("avisos")
        print("Carga:", resultado)
        for a in avisos:
            print("  aviso:", a)
        esperado = sum(1 for _ in csv.DictReader(open(args.pacote / "noticias_noticia.csv", encoding="utf-8", newline="")))
        if resultado["noticias"] != esperado:
            sessao.rollback()
            sys.exit(f"Conferência falhou: {resultado['noticias']} carregadas × {esperado} no pacote.")
        print(f"Conferência: {esperado} notícias e {resultado['atalhos']} atalhos, iguais ao pacote.")
        if not args.gravar:
            sessao.rollback()
            print("Ensaio: nada foi gravado no banco (rode o ensaio com ANEXOS_DIRETORIO apontando para uma pasta temporária).")
            return
        sessao.commit()
        print("Gravado.")


if __name__ == "__main__":
    main()
