#!/usr/bin/env python3
"""Migra o Protocolo do SGI SPI (10.23.1.220) para o Módulo Protocolo.
===============================================================================
ARQUIVO: migrar-protocolo-sgi.py
AUTOR: José Eduardo Santana Martins

(A 1ª linha acima precisa continuar sendo a frase-resumo: o argparse usa a
primeira linha desta docstring como descrição do --help.)

FINALIDADE:
Migrar o Protocolo do SGI SPI antigo (10.23.1.220) para o Módulo Protocolo
deste sistema: tipos de documento, números (reservas, finalidade,
responsável, datas) e os documentos anexados.

RESUMO TÉCNICO:
Lê o pacote gerado por `scripts/extrair-protocolo-sgi.py` (CSVs em dados/,
arquivos em anexos/ e usuarios.csv) e grava pelo SQLAlchemy:
- cada tipo vira uma sequência do exercício (ano da primeira reserva; sem
  reservas, o ano do pacote) com a mesma faixa de números;
- usuários (ReservedByUserId) são convertidos pelo usuarios.csv, casando
  login ou id externo (AD); quem não existe aqui é criado inativo, sem senha;
- a linha do tempo nasce dos dados: "reservou" (data da reserva) e "anexou"
  (data do uso);
- cada registro guarda `origem_sgi_id`: a carga pode ser repetida com
  --substituir (para um corte final) sem duplicar;
- o recurso ACL `protocolo` é criado com UMA regra (MODIFICACAO para quem já
  reservou números no SGI); recurso ACL sem nenhuma regra fica aberto a
  todos, por isso nunca é criado vazio. CONTROLE_TOTAL fica com o SuperRoot
  (a administração concede mais na tela de ACL);
- nenhum aviso ou e-mail é disparado.
Depois da carga, `conferir` compara as contagens com o pacote; só grava
(commit) com --gravar e sem divergências, copiando os arquivos conferidos
pelo SHA-256.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-protocolo-sgi.py <pacote>           # ensaio
    .venv/bin/python ../scripts/migrar-protocolo-sgi.py <pacote> --gravar  # grava
    ... --gravar --substituir   # apaga antes a carga anterior (mesmos ids)

FINALIDADE DE NEGÓCIO:
Preserva o histórico de numeração de documentos da SPI (quem reservou cada
número, para quê e qual documento foi anexado) na troca do sistema antigo
pelo novo, sem perder números nem repetir numeração já usada.

CONTEXTO NO SISTEMA:
Usa os modelos de app.models.protocolo (TipoProtocolo, SequenciaProtocolo,
NumeroProtocolo, EventoProtocolo), Anexo + servico_anexos (arquivos em
disco), Usuario e a ACL (RecursoAcl, RegraAcl). Roda uma vez, fora da API,
a partir da pasta backend.

===============================================================================
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

# Coloca a pasta backend/ no caminho de importação para usar os modelos do sistema;
# os CSVs do SGI têm campos muito grandes, por isso o limite do leitor CSV é ampliado.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
csv.field_size_limit(sys.maxsize)

from sqlalchemy import func, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.acl import NivelAcl, RecursoAcl, RegraAcl  # noqa: E402
from app.models.anexo import Anexo  # noqa: E402
from app.models.protocolo import EventoProtocolo, NumeroProtocolo, SequenciaProtocolo, TipoProtocolo  # noqa: E402
from app.models.usuario import OrigemUsuario, Usuario  # noqa: E402
from app.services import servico_anexos  # noqa: E402

# Categoria gravada em cada Anexo migrado; avisos acumula mensagens mostradas no fim da carga.
CATEGORIA_ANEXO = "protocolo-documento"
avisos: list[str] = []


class Pacote:
    """Pacote extraído do SGI: uma pasta com dados/*.csv, anexos/ e usuarios.csv."""
    def __init__(self, pasta: Path):
        self.pasta = pasta

    def tabela(self, nome: str) -> list[dict[str, str]]:
        """Lê a tabela `nome` do pacote (arquivo dados/*_<nome>.csv) como lista de dicionários; vazia se não existir."""
        arquivos = glob.glob(str(self.pasta / "dados" / f"*_{nome}.csv"))
        if not arquivos:
            return []
        with open(arquivos[0], encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))


# Pequenos conversores dos valores textuais dos CSVs (célula vazia = nulo).
def texto(v: str | None) -> str:
    """Devolve o texto ou string vazia quando a célula é nula."""
    return v or ""


def nulo(v: str | None) -> str | None:
    """Devolve None para célula vazia; caso contrário, o próprio texto."""
    return v if v not in (None, "") else None


def id_(v: str | None) -> uuid.UUID | None:
    """Converte o texto em UUID (ou None se vazio); os ids do SGI são mantidos aqui."""
    return uuid.UUID(v) if nulo(v) else None


def booleano(v: str | None) -> bool:
    """Interpreta os booleanos do PostgreSQL exportado ('t', 'true', '1')."""
    return (v or "").lower() in ("t", "true", "1")


def instante(v: str | None) -> datetime | None:
    """Converte a data/hora exportada do PostgreSQL ('2024-01-02 10:00:00-03') em datetime com fuso."""
    if not nulo(v):
        return None
    v = v.replace(" ", "T", 1)
    # Fuso no formato curto (ex.: '-03') vira '-03:00', que o fromisoformat aceita.
    if v[-3] in "+-" and v[-6] != ":" and ":" not in v[-3:]:
        v += ":00"
    return datetime.fromisoformat(v)


def migrar(pacote: Pacote, sessao) -> dict:
    """Carrega anexos, tipos, sequências, números, eventos e a regra de ACL na sessão.

    Usa só flush (nada é confirmado aqui); quem decide entre commit e rollback é o
    main. Devolve as contagens do que foi carregado.
    """
    # Contador de tudo que foi carregado, impresso no fim como resumo da carga.
    contador = Counter()
    tipos, numeros, anexos = pacote.tabela("protocol_document_types"), pacote.tabela("protocol_numbers"), pacote.tabela("stored_attachments")

    # Usuários: Id do SGI → id local (mesmo critério da migração de tarefas)
    locais = list(sessao.scalars(select(Usuario)))
    por_login = {u.login.lower(): u for u in locais}
    por_externo = {u.id_externo.lower(): u for u in locais if u.id_externo}
    with open(pacote.pasta / "usuarios.csv", encoding="utf-8", newline="") as f:
        sgi_usuarios = {r["Id"]: r for r in csv.DictReader(f)}
    mapa: dict[str, int | None] = {}

    # Converte o Id de usuário do SGI no id local, criando o usuário (inativo) se preciso.
    # O resultado fica em `mapa` para não repetir a busca. Um SuperRoot local do SGI
    # sem correspondência é ligado ao SuperRoot local daqui.
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
            # flush envia o INSERT ao banco (sem confirmar a transação) para o usuário ganhar id.
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

    # Agrupa os números por tipo de documento para montar a sequência de cada tipo.
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
        # Os números entram em ordem crescente; cada um ganha os eventos da linha do tempo.
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
    # Só cria a regra se o recurso ainda não tem nenhuma (não sobrescreve regras feitas na tela).
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
    """Compara o que está no banco com o pacote e devolve a lista de divergências (vazia = tudo bate)."""
    problemas = []
    tipos, numeros, anexos = pacote.tabela("protocol_document_types"), pacote.tabela("protocol_numbers"), pacote.tabela("stored_attachments")
    ids_tipos = [id_(t["Id"]) for t in tipos]
    # Cada conferência compara uma contagem do banco com a contagem do pacote.
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
    """Copia os arquivos de anexos/ para o armazenamento do sistema; devolve (copiados, problemas)."""
    destino = servico_anexos.diretorio_anexos()
    copiados, problemas = 0, []
    # Copia cada arquivo do pacote para a pasta de anexos, só se o SHA-256 bater com o registrado.
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
    # Proteção: se alguém já reservou número AQUI (sem origem_sgi_id) nesses tipos,
    # apagar os tipos levaria esses números junto; por isso a operação é recusada.
    local = sessao.scalar(select(func.count(NumeroProtocolo.id)).join(SequenciaProtocolo).where(
        SequenciaProtocolo.tipo_id.in_(ids), NumeroProtocolo.origem_sgi_id.is_(None), NumeroProtocolo.reservado_em.is_not(None)))
    if local:
        sys.exit(f"ERRO: {local} número(s) já foram reservados AQUI nesses tipos; --substituir os apagaria. Nada foi feito.")
    removidos = sessao.execute(TipoProtocolo.__table__.delete().where(TipoProtocolo.id.in_(ids))).rowcount
    sessao.execute(Anexo.__table__.delete().where(Anexo.id.in_([id_(r["Id"]) for r in pacote.tabela("stored_attachments")])))
    sessao.flush()
    return removidos


def main() -> None:
    """Lê os argumentos, carrega, confere e grava (ou desfaz, no ensaio)."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pacote", type=Path)
    parser.add_argument("--gravar", action="store_true", help="grava; sem esta opção é só um ensaio (tudo é desfeito)")
    parser.add_argument("--substituir", action="store_true", help="apaga antes o que veio de uma carga anterior deste pacote")
    args = parser.parse_args()
    pacote = Pacote(args.pacote)

    with FabricaSessao() as sessao:
        # Uma carga anterior do mesmo pacote é reconhecida pelos ids dos tipos.
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
        # Ensaio (sem --gravar) ou divergência: rollback desfaz tudo o que foi enviado com flush.
        if not args.gravar or problemas:
            sessao.rollback()
            if args.gravar:
                sys.exit("Nada foi gravado por causa das divergências.")
            print("Ensaio: nada foi gravado.")
            return
        # Os arquivos só são copiados depois de a conferência passar; o commit vem por último.
        copiados, falhas = copiar_arquivos(pacote)
        if falhas:
            sessao.rollback()
            sys.exit("Arquivos com problema, nada foi gravado:\n" + "\n".join(falhas))
        sessao.commit()
        print(f"Gravado. {copiados} arquivo(s) de documento em {servico_anexos.diretorio_anexos()}.")


if __name__ == "__main__":
    main()
