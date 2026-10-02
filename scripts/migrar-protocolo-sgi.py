#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para migrar o Protocolo do SGI SPI (10.23.1.220) para o Módulo Protocolo do SGI SPI.
"""Migra o Protocolo do SGI SPI (10.23.1.220) para o Módulo Protocolo.

Lê o pacote gerado por `scripts/extrair-protocolo-sgi.py` e carrega tipos, números (reservas, finalidade, responsável, datas) e
documentos anexados.

- cada tipo vira uma **sequência do exercício** (ano da primeira reserva; sem reservas, o ano do pacote) com a mesma faixa;
- usuários (`ReservedByUserId`) são convertidos pelo `usuarios.csv`, casando login ou id externo (AD); quem não existe aqui é
  criado inativo, sem senha;
- a linha do tempo nasce dos dados: "reservou" (data da reserva) e "anexou" (data do uso);
- cada registro guarda `origem_sgi_id`: a carga pode ser repetida com `--substituir` (para um corte final) sem duplicar;
- o recurso ACL `protocolo` é criado com UMA regra (MODIFICACAO para quem já reservou números no SGI); recurso ACL sem nenhuma
  regra fica aberto a todos, por isso nunca é criado vazio. CONTROLE_TOTAL fica com o SuperRoot (a administração concede mais
  na tela de ACL);
- nenhum aviso ou e-mail é disparado.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-protocolo-sgi.py <pacote>                 # ensaio: carrega, confere e desfaz
    .venv/bin/python ../scripts/migrar-protocolo-sgi.py <pacote> --gravar        # grava de verdade
    ... --gravar --substituir   # apaga antes o que veio de uma carga anterior (mesmos ids) e recarrega
"""

import argparse
import csv
import glob
import hashlib
import shutil
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
csv.field_size_limit(sys.maxsize)

from sqlalchemy import func, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.acl import NivelAcl, RecursoAcl, RegraAcl  # noqa: E402
from app.models.anexo import Anexo  # noqa: E402
from app.models.protocolo import EventoProtocolo, NumeroProtocolo, SequenciaProtocolo, TipoProtocolo  # noqa: E402
from app.models.usuario import OrigemUsuario, Usuario  # noqa: E402
from app.services import servico_anexos  # noqa: E402

CATEGORIA_ANEXO = "protocolo-documento"
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


def migrar(pacote: Pacote, sessao) -> dict:
    contador = Counter()
    tipos, numeros, anexos = pacote.tabela("protocol_document_types"), pacote.tabela("protocol_numbers"), pacote.tabela("stored_attachments")

    # Usuários: Id do SGI → id local (mesmo critério da migração de tarefas)
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
            avisos.append(f"usuário {v} do SGI não está no usuarios.csv: a reserva ficou sem responsável (o nome foi mantido)")
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

    # Documentos (metadados; o arquivo é copiado no fim, só quando grava)
    for r in anexos:
        sessao.add(Anexo(id=id_(r["Id"]), nome_original=r["OriginalName"][:255], chave_armazenamento=r["StorageKey"],
                         tipo_conteudo=texto(r["ContentType"]) or "application/octet-stream", sha256=r["Sha256"].lower(), tamanho=int(r["Size"]),
                         categoria=CATEGORIA_ANEXO, enviado_por_id=usuario(r["UploadedByUserId"]),
                         excluido_em=instante(r.get("DeletedAt")), criado_em=instante(r["CreatedAt"])))
        contador["anexos"] += 1
    sessao.flush()

    por_tipo: dict[str, list[dict]] = {}
    for r in numeros:
        por_tipo.setdefault(r["DocumentTypeId"], []).append(r)
    ano_pacote = max((instante(r["CreatedAt"]).year for r in tipos), default=datetime.now().year)

    for t in tipos:
        linhas = por_tipo.get(t["Id"], [])
        reservas = [instante(n["ReservedAt"]) for n in linhas if nulo(n["ReservedAt"])]
        exercicio = min(reservas).year if reservas else ano_pacote
        tipo = TipoProtocolo(id=id_(t["Id"]), nome=t["Name"].strip()[:200], nome_chave=t["Name"].strip().lower()[:200], origem_sgi_id=t["Id"],
                             criado_em=instante(t["CreatedAt"]))
        sequencia = SequenciaProtocolo(tipo_id=tipo.id, exercicio=exercicio, inicio=int(t["RangeStart"]), fim=int(t["RangeEnd"]))
        for n in sorted(linhas, key=lambda x: int(x["Number"])):
            reservado_em, usado_em = instante(n["ReservedAt"]), instante(n["UsedAt"])
            dono = usuario(n["ReservedByUserId"])
            numero = NumeroProtocolo(
                id=id_(n["Id"]), numero=int(n["Number"]), finalidade=texto(n["Purpose"]), reservado_por_id=dono, reservado_por_nome=texto(n["ReservedByName"])[:200],
                reservado_em=reservado_em, anexo_id=id_(n["AttachmentId"]), usado_em=usado_em, origem_sgi_id=n["Id"],
            )
            if reservado_em:
                numero.eventos.append(EventoProtocolo(tipo="reservou", autor_id=dono, autor_nome=texto(n["ReservedByName"])[:200], texto="Reservou o número (migrado do SGI)",
                                                     dados={"finalidade": texto(n["Purpose"])}, ocorrido_em=reservado_em))
            if usado_em:
                numero.eventos.append(EventoProtocolo(tipo="anexou", autor_id=dono, autor_nome=texto(n["ReservedByName"])[:200], texto="Anexou o documento (migrado do SGI)",
                                                     ocorrido_em=usado_em))
            sequencia.numeros.append(numero)
            contador["numeros"] += 1
            contador["reservados"] += bool(reservado_em)
            contador["utilizados"] += bool(numero.anexo_id)
        tipo.sequencias.append(sequencia)
        sessao.add(tipo)
        contador["tipos"] += 1
    sessao.flush()

    # ACL: recurso `protocolo` com UMA regra (nunca vazio, senão o recurso fica aberto a todos)
    donos = sorted({u for u in mapa.values() if u is not None})
    recurso = sessao.scalar(select(RecursoAcl).where(func.lower(RecursoAcl.slug) == "protocolo"))
    if recurso is None:
        recurso = RecursoAcl(nome="Protocolo", slug="protocolo", descricao="Reserva e utilização de números de documentos.", url_base="/protocolo", ativo=True)
        sessao.add(recurso)
        sessao.flush()
    if donos and not sessao.scalar(select(func.count(RegraAcl.id)).where(RegraAcl.recurso_id == recurso.id)):
        regra = RegraAcl(recurso_id=recurso.id, nivel=NivelAcl.MODIFICACAO)
        regra.usuarios = [sessao.get(Usuario, u) for u in donos]
        sessao.add(regra)
        contador["regra_acl_usuarios"] = len(donos)
    elif not donos:
        avisos.append("nenhum usuário com reserva: o recurso ACL `protocolo` NÃO tem regra (fica aberto a todos); crie uma regra na tela de ACL")
    sessao.flush()
    return dict(contador)


def conferir(pacote: Pacote, sessao) -> list[str]:
    problemas = []
    tipos, numeros, anexos = pacote.tabela("protocol_document_types"), pacote.tabela("protocol_numbers"), pacote.tabela("stored_attachments")
    ids_tipos = [id_(t["Id"]) for t in tipos]
    if sessao.scalar(select(func.count(TipoProtocolo.id)).where(TipoProtocolo.id.in_(ids_tipos))) != len(tipos):
        problemas.append("quantidade de tipos diferente do pacote")
    carregados = sessao.scalar(select(func.count(NumeroProtocolo.id)).where(NumeroProtocolo.origem_sgi_id.is_not(None)))
    if carregados != len(numeros):
        problemas.append(f"números carregados {carregados} ≠ pacote {len(numeros)}")
    reservados = sessao.scalar(select(func.count(NumeroProtocolo.id)).where(NumeroProtocolo.origem_sgi_id.is_not(None), NumeroProtocolo.reservado_em.is_not(None)))
    if reservados != sum(1 for n in numeros if nulo(n["ReservedAt"])):
        problemas.append("quantidade de reservas diferente do pacote")
    usados = sessao.scalar(select(func.count(NumeroProtocolo.id)).where(NumeroProtocolo.origem_sgi_id.is_not(None), NumeroProtocolo.anexo_id.is_not(None)))
    if usados != sum(1 for n in numeros if nulo(n["AttachmentId"])):
        problemas.append("quantidade de números utilizados diferente do pacote")
    if sessao.scalar(select(func.count(Anexo.id)).where(Anexo.id.in_([id_(r["Id"]) for r in anexos]))) != len(anexos):
        problemas.append("quantidade de anexos diferente do pacote")
    return problemas


def copiar_arquivos(pacote: Pacote) -> tuple[int, list[str]]:
    destino = servico_anexos.diretorio_anexos()
    copiados, problemas = 0, []
    for r in pacote.tabela("stored_attachments"):
        origem = pacote.pasta / "anexos" / r["StorageKey"]
        if not origem.is_file():
            problemas.append(f"arquivo ausente no pacote: {r['StorageKey']}")
            continue
        if hashlib.sha256(origem.read_bytes()).hexdigest() != r["Sha256"].lower():
            problemas.append(f"SHA-256 divergente: {r['StorageKey']}")
            continue
        alvo = destino / r["StorageKey"]
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if not alvo.exists():
            shutil.copy2(origem, alvo)
        copiados += 1
    return copiados, problemas


def limpar_carga(pacote: Pacote, sessao) -> int:
    """Apaga o que veio de uma carga anterior deste pacote (mesmos ids). Recusa se já houve movimento feito aqui nesses tipos."""
    ids = [id_(t["Id"]) for t in pacote.tabela("protocol_document_types")]
    local = sessao.scalar(select(func.count(NumeroProtocolo.id)).join(SequenciaProtocolo).where(
        SequenciaProtocolo.tipo_id.in_(ids), NumeroProtocolo.origem_sgi_id.is_(None), NumeroProtocolo.reservado_em.is_not(None)))
    if local:
        sys.exit(f"ERRO: {local} número(s) já foram reservados AQUI nesses tipos; --substituir os apagaria. Nada foi feito.")
    removidos = sessao.execute(TipoProtocolo.__table__.delete().where(TipoProtocolo.id.in_(ids))).rowcount
    sessao.execute(Anexo.__table__.delete().where(Anexo.id.in_([id_(r["Id"]) for r in pacote.tabela("stored_attachments")])))
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
        ids = [id_(r["Id"]) for r in pacote.tabela("protocol_document_types")]
        existentes = sessao.scalar(select(func.count()).select_from(TipoProtocolo).where(TipoProtocolo.id.in_(ids)))
        if existentes and args.substituir:
            print(f"Carga anterior removida ({limpar_carga(pacote, sessao)} tipo(s)).")
        elif existentes:
            sys.exit(f"ERRO: {existentes} tipo(s) deste pacote já estão no banco. Use --substituir para recarregar.")
        contagem = migrar(pacote, sessao)
        sessao.expire_all()
        problemas = conferir(pacote, sessao)
        print("Carga:", contagem)
        for aviso in avisos:
            print("  aviso:", aviso)
        if problemas:
            print("CONFERÊNCIA COM DIVERGÊNCIAS:")
            for p in problemas:
                print("  -", p)
        else:
            print("Conferência: tipos, números, reservas, utilizados e anexos batem com o SGI.")
        if not args.gravar or problemas:
            sessao.rollback()
            if args.gravar:
                sys.exit("Nada foi gravado por causa das divergências.")
            print("Ensaio: nada foi gravado.")
            return
        copiados, falhas = copiar_arquivos(pacote)
        if falhas:
            sessao.rollback()
            sys.exit("Arquivos com problema, nada foi gravado:\n" + "\n".join(falhas))
        sessao.commit()
        print(f"Gravado. {copiados} arquivo(s) de documento em {servico_anexos.diretorio_anexos()}.")


if __name__ == "__main__":
    main()
