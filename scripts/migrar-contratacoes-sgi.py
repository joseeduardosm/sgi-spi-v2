#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para migrar as Contratações (ETP e TR) do SGI SPI (10.23.1.220) para o módulo Contratações do SGI SPI.
"""Migra as Contratações (ETP e TR) do SGI SPI (10.23.1.220) para o módulo Contratações.

Lê o pacote gerado por `scripts/extrair-contratacoes-sgi.py` e carrega documentos, seções, itens (com o HTML sanitizado), a tabela
do TR, as revisões (propostas aplicadas ou não) e os comentários importados do Word.

- usuários (criador, autores de revisão) são convertidos pelo `usuarios.csv`, casando login ou id externo (AD); quem não existe aqui
  é criado inativo, sem senha;
- cada documento ganha a versão "Migrado do SGI" (a foto da árvore na migração; o histórico de edições começa aí, pois o sistema
  antigo não guardava o conteúdo anterior);
- cada registro guarda `origem_sgi_id`: a carga pode ser repetida com `--substituir` (para um corte final) sem duplicar;
- o recurso ACL `contratacoes` é criado com UMA regra (MODIFICACAO para quem criou documentos no SGI); recurso ACL sem nenhuma
  regra fica aberto a todos, por isso nunca é criado vazio. Quem só consulta recebe acesso por compartilhamento no documento;
- nenhum aviso ou e-mail é disparado. No SGI antigo todos viam todos os documentos; aqui só o criador e a administração, e o criador
  compartilha com quem precisar.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-contratacoes-sgi.py <pacote>                 # ensaio: carrega, confere e desfaz
    .venv/bin/python ../scripts/migrar-contratacoes-sgi.py <pacote> --gravar        # grava de verdade
    ... --gravar --substituir   # apaga antes o que veio de uma carga anterior (mesmos ids) e recarrega
"""

import argparse
import csv
import glob
import sys
import uuid
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
csv.field_size_limit(sys.maxsize)

from sqlalchemy import func, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.acl import NivelAcl, RecursoAcl, RegraAcl  # noqa: E402
from app.models.contratacoes import (  # noqa: E402
    ComentarioImportado, DocumentoContratacao, ItemContratacao, LinhaTabelaTr, RevisaoItem, SecaoContratacao,
)
from app.models.usuario import OrigemUsuario, Usuario  # noqa: E402
from app.services.contratacoes import conteudo, versoes  # noqa: E402

TIPOS_DOC = {"etp": "etp", "tr": "tr"}
SITUACOES = {"draft": "rascunho", "inreview": "em_revisao", "review": "em_revisao", "completed": "concluido", "concluded": "concluido"}
TIPOS_ITEM = {"item": "item", "subitem": "subitem", "inciso": "inciso", "alinea": "alinea", "subsection": "subsecao"}
avisos: list[str] = []


class Pacote:
    def __init__(self, pasta: Path):
        self.pasta = pasta

    def tabela(self, nome: str) -> list[dict[str, str]]:
        arquivos = glob.glob(str(self.pasta / "dados" / f"*_{nome}.csv"))
        if not arquivos:
            return []
        with open(arquivos[0], encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))


def texto(v: str | None) -> str:
    return v or ""


def nulo(v: str | None) -> str | None:
    return v if v not in (None, "") else None


def id_(v: str | None) -> uuid.UUID | None:
    return uuid.UUID(v) if nulo(v) else None


def booleano(v: str | None) -> bool:
    return (v or "").lower() in ("t", "true", "1")


def instante(v: str | None) -> datetime | None:
    if not nulo(v):
        return None
    v = v.replace(" ", "T", 1)
    if v[-3] in "+-" and v[-6] != ":" and ":" not in v[-3:]:
        v += ":00"
    return datetime.fromisoformat(v)


def conteudo_do_item(texto_: str, html: str | None) -> tuple[str, str | None]:
    try:
        return conteudo.normalizar(texto_, html)
    except conteudo.ErroConteudo:
        avisos.append("conteúdo grande demais ou inválido: guardado só como texto")
        return (texto_ or "")[: conteudo.LIMITE_CONTEUDO], None


def migrar(pacote: Pacote, sessao) -> dict:
    contador = Counter()
    documentos, secoes, itens = pacote.tabela("procurement_documents"), pacote.tabela("procurement_sections"), pacote.tabela("procurement_items")
    linhas_tr, revisoes, comentarios = pacote.tabela("procurement_tr_table_items"), pacote.tabela("procurement_item_reviews"), pacote.tabela("procurement_imported_comments")

    # Usuários: Id do SGI → id local (mesmo critério das outras migrações)
    locais = list(sessao.scalars(select(Usuario)))
    por_login = {u.login.lower(): u for u in locais}
    por_externo = {u.id_externo.lower(): u for u in locais if u.id_externo}
    with open(pacote.pasta / "usuarios.csv", encoding="utf-8", newline="") as f:
        sgi_usuarios = {r["Id"]: r for r in csv.DictReader(f)}
    mapa: dict[str, int | None] = {}

    def usuario(v: str | None) -> int | None:
        if not nulo(v):
            return None
        if v in mapa:
            return mapa[v]
        origem = sgi_usuarios.get(v)
        if origem is None:
            avisos.append(f"usuário {v} do SGI não está no usuarios.csv: ficou sem responsável (o nome foi mantido)")
            mapa[v] = None
            return None
        local = por_login.get(texto(origem["Username"]).lower()) or por_externo.get(texto(origem["ExternalId"]).lower())
        if local is None and "ldap" not in texto(origem["Origin"]).lower() and booleano(origem["IsSuperuser"]):
            local = next((u for u in locais if u.superusuario and u.origem == OrigemUsuario.LOCAL), None)
        if local is None:
            ldap = "ldap" in texto(origem["Origin"]).lower()
            local = Usuario(
                login=origem["Username"], hash_senha=None, ativo=False, superusuario=False,
                origem=OrigemUsuario.LDAP if ldap else OrigemUsuario.LOCAL, id_externo=nulo(origem["ExternalId"]),
                nome_completo=texto(origem["FullName"])[:200], email=texto(origem["Email"])[:254],
                departamento=texto(origem["Department"])[:150], cargo=texto(origem["JobTitle"])[:150],
            )
            sessao.add(local)
            sessao.flush()
            por_login[local.login.lower()] = local
            avisos.append(f"usuário {local.login} criado inativo (veio do SGI e não existe aqui)")
        mapa[v] = local.id
        return local.id

    criadores: set[int] = set()
    docs_locais: list[DocumentoContratacao] = []
    for d in documentos:
        tipo = TIPOS_DOC.get(d["Type"].lower())
        if tipo is None:
            avisos.append(f"documento {d['Id']} com tipo desconhecido «{d['Type']}»: ignorado")
            continue
        situacao = SITUACOES.get(d["Status"].lower().replace("_", ""), "rascunho")
        criador = usuario(d["CreatorUserId"])
        if criador:
            criadores.add(criador)
        doc = DocumentoContratacao(
            id=id_(d["Id"]), tipo=tipo, nome=texto(d["Name"]).strip()[:300] or "Sem nome", processo=texto(d["ProcessNumber"])[:100], link_sei=nulo(d["SeiUrl"]),
            situacao=situacao, criador_id=criador, atualizado_por_id=usuario(d["UpdatedByUserId"]), origem_sgi_id=d["Id"],
            criado_em=instante(d["CreatedAt"]), atualizado_em=instante(d["UpdatedAt"]),
        )
        sessao.add(doc)
        docs_locais.append(doc)
        contador["documentos"] += 1
    sessao.flush()
    validos = {d.id for d in docs_locais}

    for s in secoes:
        if id_(s["DocumentId"]) not in validos:
            continue
        sessao.add(SecaoContratacao(id=id_(s["Id"]), documento_id=id_(s["DocumentId"]), ordem=int(s["Order"]), titulo=texto(s["Title"])[:300], origem_sgi_id=s["Id"]))
        contador["secoes"] += 1
    sessao.flush()
    secoes_ok = {id_(s["Id"]) for s in secoes if id_(s["DocumentId"]) in validos}

    # Itens: pais antes dos filhos (a chave estrangeira é da própria tabela), um nível por vez
    por_id = {i["Id"]: i for i in itens if id_(i["SectionId"]) in secoes_ok}
    profundidade: dict[str, int] = {}

    def nivel(i: dict) -> int:
        if i["Id"] not in profundidade:
            pai = nulo(i["ParentId"])
            profundidade[i["Id"]] = 0 if not pai or pai not in por_id else nivel(por_id[pai]) + 1
        return profundidade[i["Id"]]

    for i in por_id.values():
        nivel(i)
    for n in range(max(profundidade.values(), default=0) + 1):
        for i in [x for x in por_id.values() if profundidade[x["Id"]] == n]:
            tipo = TIPOS_ITEM.get(i["Type"].lower(), "item")
            if i["Type"].lower() not in TIPOS_ITEM:
                avisos.append(f"item {i['Id']} com tipo desconhecido «{i['Type']}»: virou item")
            texto_, html = conteudo_do_item(texto(i["Content"]), nulo(i["ContentHtml"]))
            sessao.add(ItemContratacao(
                id=id_(i["Id"]), secao_id=id_(i["SectionId"]), pai_id=id_(i["ParentId"]) if nulo(i["ParentId"]) in por_id else None, tipo=tipo, ordem=int(i["Order"]),
                conteudo=texto_, conteudo_html=html, precisa_revisao=booleano(i["NeedsReview"]), origem_sgi_id=i["Id"], atualizado_em=instante(i["UpdatedAt"]),
            ))
            contador["itens"] += 1
        sessao.flush()

    for t in linhas_tr:
        if t["ItemId"] not in por_id:
            continue
        sessao.add(LinhaTabelaTr(
            id=id_(t["Id"]), item_id=id_(t["ItemId"]), ordem=int(t["Order"]), descricao=texto(t["Description"]), siafisico=texto(t["Siafisico"])[:60],
            catser_catmat=texto(t["CatserCatmat"])[:60], unidade=texto(t["UnitOfMeasure"])[:60], quantidade_mensal=Decimal(t["MonthlyQuantity"] or 0),
            quantidade_objeto=Decimal(t["ObjectQuantity"] or 0), origem_sgi_id=t["Id"]))
        contador["linhas_tabela"] += 1

    for r in revisoes:
        if r["ItemId"] not in por_id:
            continue
        autor, aplicou = usuario(r["AuthorUserId"]), usuario(r["AppliedByUserId"])
        aplicada_em = instante(r["AppliedAt"])
        proposto, proposto_html = nulo(r["ProposedContent"]), nulo(r["ProposedContentHtml"])
        sessao.add(RevisaoItem(
            id=id_(r["Id"]), item_id=id_(r["ItemId"]), autor_id=autor, autor_nome=texto(r["AuthorName"])[:200], comentario=texto(r["Comment"]),
            conteudo_original=texto(r["OriginalContent"]), conteudo_original_html=nulo(r["OriginalContentHtml"]), conteudo_proposto=proposto,
            conteudo_proposto_html=proposto_html, aplicada_em=aplicada_em, aplicada_por_id=aplicou, aplicada_por_nome=nulo(r["AppliedByName"]),
            resolvida_em=aplicada_em, resolvida_por_nome=nulo(r["AppliedByName"]) if aplicada_em else None, origem_sgi_id=r["Id"], criada_em=instante(r["CreatedAt"])))
        contador["revisoes"] += 1
        contador["revisoes_aplicadas"] += bool(aplicada_em)

    for c in comentarios:
        if c["ItemId"] not in por_id:
            continue
        sessao.add(ComentarioImportado(
            id=id_(c["Id"]), item_id=id_(c["ItemId"]), id_externo=texto(c["ExternalId"])[:60], autor=texto(c["AuthorName"])[:200], iniciais=nulo(c["AuthorInitials"]),
            comentado_em=instante(c["CommentedAt"]), comentario=texto(c["Comment"]), trecho=texto(c["AnchorText"]), abrange_mais=booleano(c["SpansAdditionalContent"]),
            origem_sgi_id=c["Id"]))
        contador["comentarios_importados"] += 1
    sessao.flush()

    # A foto da árvore na migração: ponto de partida do histórico
    sessao.expire_all()
    for doc in docs_locais:
        doc = sessao.get(DocumentoContratacao, doc.id)
        versoes.registrar(sessao, doc, "migracao", None, "Migrado do SGI SPI antigo (10.23.1.220)")
        contador["versoes"] += 1

    # ACL: recurso `contratacoes` com UMA regra (nunca vazio, senão o recurso fica aberto a todos)
    recurso = sessao.scalar(select(RecursoAcl).where(func.lower(RecursoAcl.slug) == "contratacoes"))
    if recurso is None:
        recurso = RecursoAcl(nome="Contratações", slug="contratacoes", descricao="ETP e TR com revisão e histórico de versões.", url_base="/contratacoes", ativo=True)
        sessao.add(recurso)
        sessao.flush()
    if criadores and not sessao.scalar(select(func.count(RegraAcl.id)).where(RegraAcl.recurso_id == recurso.id)):
        regra = RegraAcl(recurso_id=recurso.id, nivel=NivelAcl.MODIFICACAO)
        regra.usuarios = [sessao.get(Usuario, u) for u in sorted(criadores)]
        sessao.add(regra)
        contador["regra_acl_usuarios"] = len(criadores)
    elif not criadores:
        avisos.append("nenhum criador mapeado: o recurso ACL `contratacoes` NÃO tem regra (fica aberto a todos); crie uma regra na tela de ACL")
    sessao.flush()
    return dict(contador)


def conferir(pacote: Pacote, sessao) -> list[str]:
    problemas = []
    docs = [id_(d["Id"]) for d in pacote.tabela("procurement_documents")]
    esperado = {
        "documentos": (DocumentoContratacao, len(docs)),
        "secoes": (SecaoContratacao, len(pacote.tabela("procurement_sections"))),
        "itens": (ItemContratacao, len(pacote.tabela("procurement_items"))),
        "linhas da tabela do TR": (LinhaTabelaTr, len(pacote.tabela("procurement_tr_table_items"))),
        "revisões": (RevisaoItem, len(pacote.tabela("procurement_item_reviews"))),
        "comentários importados": (ComentarioImportado, len(pacote.tabela("procurement_imported_comments"))),
    }
    for nome, (modelo, quantos) in esperado.items():
        carregados = sessao.scalar(select(func.count()).select_from(modelo).where(modelo.origem_sgi_id.is_not(None)))
        if carregados != quantos:
            problemas.append(f"{nome} carregados {carregados} ≠ pacote {quantos}")
    aplicadas = sessao.scalar(select(func.count(RevisaoItem.id)).where(RevisaoItem.origem_sgi_id.is_not(None), RevisaoItem.aplicada_em.is_not(None)))
    if aplicadas != sum(1 for r in pacote.tabela("procurement_item_reviews") if nulo(r["AppliedAt"])):
        problemas.append("quantidade de propostas aplicadas diferente do pacote")
    return problemas


def limpar_carga(pacote: Pacote, sessao) -> int:
    """Apaga o que veio de uma carga anterior deste pacote (mesmos ids). Recusa se o documento já foi editado aqui."""
    ids = [id_(d["Id"]) for d in pacote.tabela("procurement_documents")]
    editados = sessao.scalar(select(func.count(DocumentoContratacao.id)).where(DocumentoContratacao.id.in_(ids), DocumentoContratacao.ultima_edicao_em.is_not(None)))
    if editados:
        sys.exit(f"ERRO: {editados} documento(s) já foram editados AQUI; --substituir apagaria essas edições. Nada foi feito.")
    removidos = sessao.execute(DocumentoContratacao.__table__.delete().where(DocumentoContratacao.id.in_(ids))).rowcount
    sessao.flush()
    return removidos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pacote", type=Path)
    parser.add_argument("--gravar", action="store_true", help="grava; sem esta opção é só um ensaio (tudo é desfeito)")
    parser.add_argument("--substituir", action="store_true", help="apaga antes o que veio de uma carga anterior deste pacote")
    args = parser.parse_args()
    pacote = Pacote(args.pacote)

    with FabricaSessao() as sessao:
        ids = [id_(r["Id"]) for r in pacote.tabela("procurement_documents")]
        existentes = sessao.scalar(select(func.count()).select_from(DocumentoContratacao).where(DocumentoContratacao.id.in_(ids)))
        if existentes and args.substituir:
            print(f"Carga anterior removida ({limpar_carga(pacote, sessao)} documento(s)).")
        elif existentes:
            sys.exit(f"ERRO: {existentes} documento(s) deste pacote já estão no banco. Use --substituir para recarregar.")
        contagem = migrar(pacote, sessao)
        sessao.expire_all()
        problemas = conferir(pacote, sessao)
        print("Carga:", contagem)
        for aviso in sorted(set(avisos)):
            print("  aviso:", aviso)
        if problemas:
            print("CONFERÊNCIA COM DIVERGÊNCIAS:")
            for p in problemas:
                print("  -", p)
        else:
            print("Conferência: documentos, seções, itens, tabela do TR, revisões (e aplicadas) e comentários batem com o SGI.")
        if not args.gravar or problemas:
            sessao.rollback()
            if args.gravar:
                sys.exit("Nada foi gravado por causa das divergências.")
            print("Ensaio: nada foi gravado.")
            return
        sessao.commit()
        print("Gravado.")


if __name__ == "__main__":
    main()
