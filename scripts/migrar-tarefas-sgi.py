#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para migrar o módulo de tarefas do SGI SPI (10.23.1.220) para o Módulo Tarefas do SGI SPI.
"""Migra o módulo de tarefas do SGI SPI (10.23.1.220) para o Módulo Tarefas.

Lê o pacote gerado por `scripts/extrair-tarefas-sgi.py` e carrega equipes, marcadores, tarefas, participantes,
linha do tempo (com o nome do autor preservado), remoções lógicas e anexos dos comentários.

- usuários (`*UserId`) são convertidos pelo `usuarios.csv`, casando login ou id externo (AD); quem não existe aqui
  é criado inativo, sem senha;
- o número público (`Number`) é preservado; uma tarefa criada aqui com o mesmo número recebe o próximo livre;
- situação: Pending → a_fazer, InProgress → em_andamento, Completed → concluida (AwaitingApproval, que o SGI
  desligou, → em_validacao nos eventos antigos);
- o prazo original é o "anterior" da primeira mudança de prazo (ou o prazo da criação);
- nenhum aviso ou e-mail é disparado.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-tarefas-sgi.py <pacote>                 # ensaio: carrega, confere e desfaz
    .venv/bin/python ../scripts/migrar-tarefas-sgi.py <pacote> --gravar        # grava de verdade
    ... --gravar --substituir   # apaga antes o que veio de uma carga anterior (mesmos ids) e recarrega
"""

import argparse
import csv
import glob
import hashlib
import json
import shutil
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
csv.field_size_limit(sys.maxsize)

from sqlalchemy import func, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.anexo import Anexo  # noqa: E402
from app.models.tarefas import (  # noqa: E402
    AnexoEventoTarefa, EquipeTarefas, EventoTarefa, ItemChecklistTarefa, LiderEquipeTarefas, MarcadorTarefa, MembroEquipeTarefas,
    ParticipanteTarefa, Tarefa, VinculoMarcadorTarefa,
)
from app.models.usuario import OrigemUsuario, Usuario  # noqa: E402
from app.services import servico_anexos  # noqa: E402

# --- De-para de valores ------------------------------------------------------------------------

STATUS = {"Pending": "a_fazer", "InProgress": "em_andamento", "Completed": "concluida", "AwaitingApproval": "em_validacao",
          "0": "a_fazer", "1": "em_andamento", "2": "concluida", "3": "em_validacao"}
PRIORIDADES = {"Low": "baixa", "Normal": "normal", "High": "alta", "Critical": "critica",
               "0": "baixa", "1": "normal", "2": "alta", "3": "critica"}
CATEGORIA_ANEXO = "tarefa-comentario"
avisos: list[str] = []


# --- Leitura do pacote -------------------------------------------------------------------------

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


def inteiro(v: str | None) -> int | None:
    return int(v) if nulo(v) else None


def booleano(v: str | None) -> bool:
    return (v or "").lower() in ("t", "true", "1")


def instante(v: str | None) -> datetime | None:
    if not nulo(v):
        return None
    v = v.replace(" ", "T", 1)
    if v[-3] in "+-" and v[-6] != ":" and ":" not in v[-3:]:
        v += ":00"
    return datetime.fromisoformat(v)


def iso(v) -> str | None:
    """Data do payload (texto ISO) normalizada; None se vazia."""
    d = instante(str(v)) if v not in (None, "") else None
    return d.isoformat() if d else None


def status_(v) -> str | None:
    return STATUS.get(str(v)) if v is not None else None


def ids_por_tarefa(linhas: list[dict], campo: str) -> dict[str, list[str]]:
    resultado = defaultdict(list)
    for r in linhas:
        resultado[r["TaskId"]].append(r[campo])
    return resultado


# --- Carga -------------------------------------------------------------------------------------

def migrar(pacote: Pacote, sessao) -> dict:
    t = pacote.tabela
    contador = Counter()

    # Usuários: Id do SGI → id local
    locais = list(sessao.scalars(select(Usuario)))
    por_login = {u.login.lower(): u for u in locais}
    por_externo = {u.id_externo.lower(): u for u in locais if u.id_externo}
    with open(pacote.pasta / "usuarios.csv", encoding="utf-8", newline="") as f:
        sgi_usuarios = {r["Id"]: r for r in csv.DictReader(f)}
    mapa: dict[str, int | None] = {}
    criados: list[str] = []

    def usuario(v: str | None) -> int | None:
        if not nulo(str(v) if v is not None else None):
            return None
        v = str(v)
        if v in mapa:
            return mapa[v]
        origem = sgi_usuarios.get(v)
        if origem is None:
            avisos.append(f"usuário {v} do SGI não está no usuarios.csv: referência ficou vazia")
            mapa[v] = None
            return None
        local = por_login.get(texto(origem["Username"]).lower()) or por_externo.get(texto(origem["ExternalId"]).lower())
        if local is None and "ldap" not in texto(origem["Origin"]).lower() and booleano(origem["IsSuperuser"]):
            # Conta administrativa local do SGI (ex.: `admin`) = conta administrativa local daqui (`root`)
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
            criados.append(local.login)
        mapa[v] = local.id
        return local.id

    def nome(v) -> str:
        """Nome para a linha do tempo: o do SGI (retrato da época) ou, na falta, o daqui."""
        origem = sgi_usuarios.get(str(v)) if v is not None else None
        if origem and nulo(origem["FullName"]):
            return origem["FullName"]
        local = sessao.get(Usuario, usuario(v)) if v is not None and usuario(v) else None
        return (local.nome_completo or local.login) if local else "—"

    # Equipes (dono, líderes, membros); as desativadas no SGI continuam desativadas
    for r in t("task_teams"):
        sessao.add(EquipeTarefas(id=id_(r["Id"]), nome=r["Name"][:150], dono_id=usuario(r["OwnerUserId"]), ativa=booleano(r["Active"]),
                                 criado_em=instante(r["CreatedAt"])))
        contador["equipes"] += 1
    sessao.flush()
    for r in t("task_teams"):
        if nulo(r["ParentTeamId"]):
            sessao.get(EquipeTarefas, id_(r["Id"])).equipe_pai_id = id_(r["ParentTeamId"])
    lideres = defaultdict(set)
    for r in t("task_team_leaders"):
        if (u := usuario(r["UserId"])) is not None:
            lideres[r["TeamId"]].add(u)
    for equipe_id, ids in lideres.items():
        for u in sorted(ids):
            sessao.add(LiderEquipeTarefas(equipe_id=id_(equipe_id), usuario_id=u))
    for r in t("task_team_members"):
        u = usuario(r["UserId"])
        if u is not None and u not in lideres[r["TeamId"]]:
            sessao.add(MembroEquipeTarefas(equipe_id=id_(r["TeamId"]), usuario_id=u))

    # Marcadores (no SGI eram globais)
    marcadores: dict[str, MarcadorTarefa] = {}
    for r in t("task_markers"):
        cor = r["Color"] if len(texto(r["Color"])) == 7 else "#5364ce"
        m = MarcadorTarefa(id=id_(r["Id"]), equipe_id=None, nome=" ".join(r["Name"].split())[:120], cor=cor.lower())
        sessao.add(m)
        marcadores[r["Id"]] = m
        contador["marcadores"] += 1

    # Anexos (metadados; o arquivo é copiado no fim, só quando grava)
    for r in t("stored_attachments"):
        sessao.add(Anexo(id=id_(r["Id"]), nome_original=r["OriginalName"][:255], chave_armazenamento=r["StorageKey"],
                         tipo_conteudo=texto(r["ContentType"]) or "application/octet-stream", sha256=r["Sha256"].lower(), tamanho=int(r["Size"]),
                         categoria=CATEGORIA_ANEXO, enviado_por_id=usuario(r["UploadedByUserId"]),
                         excluido_em=instante(r["DeletedAt"]), criado_em=instante(r["CreatedAt"])))
        contador["anexos"] += 1
    sessao.flush()

    # Tarefas
    participantes = ids_por_tarefa(t("work_task_participants"), "UserId")
    vinculos = ids_por_tarefa(t("work_task_markers"), "MarkerId")
    eventos_por_tarefa = defaultdict(list)
    for r in t("work_task_events"):
        r["_payload"] = json.loads(r["PayloadJson"]) if nulo(r["PayloadJson"]) else {}
        eventos_por_tarefa[r["TaskId"]].append(r)
    anexos_por_evento = defaultdict(list)
    for r in t("work_task_event_attachments"):
        anexos_por_evento[r["EventId"]].append(r["AttachmentId"])

    # Número já usado aqui por uma tarefa criada no SGI SPI: ela ganha o próximo livre
    numeros_sgi = {int(r["Number"]) for r in t("work_tasks")}
    proximo = max(numeros_sgi | set(sessao.scalars(select(Tarefa.numero))) | {0}) + 1
    for local in sessao.scalars(select(Tarefa).where(Tarefa.numero.in_(numeros_sgi))):
        avisos.append(f"tarefa #{local.numero} criada aqui (\"{local.titulo}\") passou a ser #{proximo}: o número pertence a uma tarefa do SGI")
        local.numero = proximo
        proximo += 1
    sessao.flush()

    for r in t("work_tasks"):
        eventos = sorted(eventos_por_tarefa[r["Id"]], key=lambda e: e["CreatedAt"])
        responsaveis = participantes.get(r["Id"], [])
        if len(responsaveis) != 1:
            avisos.append(f"tarefa #{r['Number']}: {len(responsaveis)} participantes no SGI (esperado 1)")
        prazo = instante(r["Deadline"])
        prazo_original = None
        for e in eventos:
            p = e["_payload"]
            if e["Type"] == "DeadlineChanged" and p.get("previous"):
                prazo_original = instante(p["previous"])
                break
            if e["Type"] == "Transferred" and p.get("previousDeadline") and p.get("newDeadline") and p["previousDeadline"] != p["newDeadline"]:
                prazo_original = instante(p["previousDeadline"])
                break
        if prazo_original is None:
            criada = next((e for e in eventos if e["Type"] == "Created"), None)
            prazo_original = instante(criada["_payload"].get("deadline")) if criada and criada["_payload"].get("deadline") else prazo
        iniciada = next((instante(e["CreatedAt"]) for e in eventos if status_(e["_payload"].get("current", e["_payload"].get("currentStatus"))) == "em_andamento"), None)
        status = STATUS[r["Status"]]
        tarefa = Tarefa(
            id=id_(r["Id"]), numero=int(r["Number"]), titulo=r["Title"][:200], descricao=texto(r["Description"]), equipe_id=id_(r["TeamId"]),
            criado_por_id=usuario(r["CreatorUserId"]), responsavel_id=usuario(responsaveis[0]) if responsaveis else None,
            prazo=prazo, prazo_original=prazo_original, prioridade=PRIORIDADES[r["Priority"]], status=status, ordem=inteiro(r["SortIndex"]) or 0,
            iniciada_em=iniciada or (instante(r["InProgressSince"]) if status != "a_fazer" else None),
            em_andamento_desde=instante(r["InProgressSince"]) if status == "em_andamento" else None,
            segundos_em_andamento=inteiro(r["OperationalSeconds"]) or 0, concluida_em=instante(r["CompletedAt"]) if status == "concluida" else None,
            versao=inteiro(r["Version"]) or 1, criado_em=instante(r["CreatedAt"]), atualizado_em=instante(r["UpdatedAt"]),
        )
        tarefa.participantes = [ParticipanteTarefa(usuario_id=u) for u in dict.fromkeys(usuario(x) for x in responsaveis) if u is not None]
        tarefa.marcadores = [marcadores[m] for m in dict.fromkeys(vinculos.get(r["Id"], [])) if m in marcadores]
        sessao.add(tarefa)
        contador["tarefas"] += 1
        contador[f"situacao:{status}"] += 1
        sessao.flush()
        # A edição do SGI grava os valores novos; o "de" é o da edição anterior (na primeira, fica desconhecido)
        anterior: dict = {}
        for e in eventos:
            contador["eventos"] += 1
            tipo, titulo, corpo, dados = _evento(e, anterior, nome, marcadores)
            contador[f"evento:{tipo}"] += 1
            ev = EventoTarefa(
                id=id_(e["Id"]), tarefa_id=tarefa.id, tipo=tipo, autor_id=usuario(e["AuthorUserId"]), autor_nome=texto(e["AuthorName"]) or nome(e["AuthorUserId"]),
                titulo=titulo[:300], texto=corpo, dados=dados, criado_em=instante(e["CreatedAt"]),
                removido_em=instante(e["RemovedAt"]), removido_por_nome=nome(e["RemovedByUserId"]) if nulo(e["RemovedByUserId"]) else None,
                motivo_remocao=nulo(e["RemovalReason"]),
            )
            ev.anexos = [AnexoEventoTarefa(anexo_id=id_(a)) for a in anexos_por_evento.get(e["Id"], [])]
            contador["anexos_vinculados"] += len(ev.anexos)
            contador["eventos_removidos"] += ev.removido_em is not None
            sessao.add(ev)
    for r in t("task_checklist_items"):
        sessao.add(ItemChecklistTarefa(id=id_(r["Id"]), tarefa_id=id_(r["TaskId"]), texto=r["Text"][:300], posicao=inteiro(r["Position"]) or 0,
                                       concluido_em=instante(r["CompletedAt"])))
        contador["checklist"] += 1
    sessao.flush()
    if criados:
        avisos.append("usuários criados inativos (não existiam aqui): " + ", ".join(sorted(criados)))
    return dict(contador)


def _evento(e: dict, anterior: dict, nome, marcadores: dict) -> tuple[str, str, str, dict]:
    """Tipo, título, texto e dados do evento daqui a partir do evento do SGI."""
    p, tipo_sgi = e["_payload"], e["Type"]
    titulo = texto(e["Title"])
    descricao = texto(e["Description"])
    if tipo_sgi == "Created":
        return "criada", titulo or "Tarefa criada", descricao, {"prazo": iso(p.get("deadline")), "responsavel": nome(p.get("responsibleUserId"))}
    if tipo_sgi == "DeadlineChanged":
        return "prazo", titulo or "Prazo alterado", texto(p.get("justification")) or descricao, {"de": iso(p.get("previous")), "para": iso(p.get("current"))}
    if tipo_sgi in ("StatusChanged", "Reopened"):
        de = status_(p.get("previous", p.get("previousStatus")))
        para = status_(p.get("current", p.get("currentStatus")))
        corpo = texto(p.get("justification")) or descricao
        return ("reaberta" if tipo_sgi == "Reopened" else "status"), titulo or "Situação alterada", corpo, {"de": de, "para": para}
    if tipo_sgi == "Transferred":
        de, para = nome(p.get("fromUserId")), nome(p.get("toUserId"))
        dados = {"de": de, "para": para}
        if p.get("previousDeadline") != p.get("newDeadline") and p.get("newDeadline"):
            dados |= {"prazo_de": iso(p.get("previousDeadline")), "prazo_para": iso(p.get("newDeadline"))}
        return "transferida", f"Transferida de {de} para {para}", texto(p.get("justification")) or descricao, dados
    if tipo_sgi == "Edited":
        campos: dict = {}
        novo = {"titulo": p.get("Title"), "prioridade": PRIORIDADES.get(str(p.get("Priority"))) if p.get("Priority") is not None else None,
                "marcadores": sorted(marcadores[m].nome for m in p.get("markerIds") or [] if m in marcadores) if "markerIds" in p else None}
        for campo, valor in novo.items():
            if valor is None:
                continue
            if campo not in anterior:
                campos[campo] = {"para": valor}
            elif anterior[campo] != valor:
                campos[campo] = {"de": anterior[campo], "para": valor}
            anterior[campo] = valor
        atuais, antigos = set(p.get("currentResponsibleIds") or []), set(p.get("previousResponsibleIds") or [])
        if atuais != antigos:
            campos["participantes"] = {"entraram": sorted(nome(i) for i in atuais - antigos), "sairam": sorted(nome(i) for i in antigos - atuais)}
        return "editada", titulo or "Tarefa editada", texto(p.get("responsibleChangeJustification")) or descricao, {"campos": campos}
    if tipo_sgi == "CommentAdded":
        return "comentario", titulo or ("Comentário" if descricao else "Anexo"), descricao, {}
    if tipo_sgi == "ContentRemoved":
        return "removido", titulo or "Item da linha do tempo removido", descricao, {}
    avisos.append(f"evento {e['Id']} de tipo desconhecido {tipo_sgi}: gravado como comentário")
    return "comentario", titulo or tipo_sgi, descricao, {}


# --- Conferência -------------------------------------------------------------------------------

def conferir(pacote: Pacote, sessao) -> list[str]:
    """Compara as contagens daqui com o pacote (divergência impede gravar)."""
    problemas = []
    t = pacote.tabela
    ids = [id_(r["Id"]) for r in t("work_tasks")]
    pares = (
        ("work_tasks", select(func.count()).select_from(Tarefa).where(Tarefa.id.in_(ids))),
        ("work_task_events", select(func.count()).select_from(EventoTarefa).where(EventoTarefa.tarefa_id.in_(ids))),
        ("work_task_participants", select(func.count()).select_from(ParticipanteTarefa).where(ParticipanteTarefa.tarefa_id.in_(ids))),
        ("work_task_markers", select(func.count()).select_from(VinculoMarcadorTarefa).where(VinculoMarcadorTarefa.tarefa_id.in_(ids))),
        ("work_task_event_attachments", select(func.count()).select_from(AnexoEventoTarefa).join(EventoTarefa).where(EventoTarefa.tarefa_id.in_(ids))),
        ("task_teams", select(func.count()).select_from(EquipeTarefas).where(EquipeTarefas.id.in_([id_(r["Id"]) for r in t("task_teams")]))),
        ("task_markers", select(func.count()).select_from(MarcadorTarefa).where(MarcadorTarefa.id.in_([id_(r["Id"]) for r in t("task_markers")]))),
    )
    for nome_tabela, consulta in pares:
        aqui, la = sessao.scalar(consulta), len(t(nome_tabela))
        if aqui != la:
            problemas.append(f"{nome_tabela}: {aqui} aqui × {la} no SGI")
    # Situação e número de cada tarefa
    for r in t("work_tasks"):
        tarefa = sessao.get(Tarefa, id_(r["Id"]))
        if tarefa.status != STATUS[r["Status"]] or tarefa.numero != int(r["Number"]):
            problemas.append(f"tarefa #{r['Number']}: situação ou número divergente")
    return problemas


def relatorio(pacote: Pacote, sessao) -> None:
    """Resumo por situação e por pessoa (responsável), para conferir com o SGI por amostragem."""
    ids = [id_(r["Id"]) for r in pacote.tabela("work_tasks")]
    por_pessoa = Counter()
    for tarefa in sessao.scalars(select(Tarefa).where(Tarefa.id.in_(ids))):
        u = sessao.get(Usuario, tarefa.responsavel_id) if tarefa.responsavel_id else None
        por_pessoa[((u.nome_completo or u.login) if u else "—", tarefa.status)] += 1
    pessoas = sorted({p for p, _ in por_pessoa})
    print("Por responsável (a fazer / em andamento / concluída):")
    for p in pessoas:
        print(f"  {p}: {por_pessoa[(p, 'a_fazer')]} / {por_pessoa[(p, 'em_andamento')]} / {por_pessoa[(p, 'concluida')]}")


# --- Arquivos ----------------------------------------------------------------------------------

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
    """Apaga o que veio de uma carga anterior deste pacote (mesmos ids). As tarefas criadas aqui ficam."""
    t = pacote.tabela
    ids = [id_(r["Id"]) for r in t("work_tasks")]
    removidas = sessao.execute(Tarefa.__table__.delete().where(Tarefa.id.in_(ids))).rowcount
    sessao.execute(MarcadorTarefa.__table__.delete().where(MarcadorTarefa.id.in_([id_(r["Id"]) for r in t("task_markers")])))
    sessao.execute(EquipeTarefas.__table__.delete().where(EquipeTarefas.id.in_([id_(r["Id"]) for r in t("task_teams")])))
    sessao.execute(Anexo.__table__.delete().where(Anexo.id.in_([id_(r["Id"]) for r in t("stored_attachments")])))
    sessao.flush()
    return removidas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pacote", type=Path)
    parser.add_argument("--gravar", action="store_true", help="grava; sem esta opção é só um ensaio (tudo é desfeito)")
    parser.add_argument("--substituir", action="store_true", help="apaga antes o que veio de uma carga anterior deste pacote")
    args = parser.parse_args()
    pacote = Pacote(args.pacote)

    with FabricaSessao() as sessao:
        ids = [id_(r["Id"]) for r in pacote.tabela("work_tasks")]
        existentes = sessao.scalar(select(func.count()).select_from(Tarefa).where(Tarefa.id.in_(ids)))
        if existentes and args.substituir:
            print(f"Carga anterior removida ({limpar_carga(pacote, sessao)} tarefa(s)).")
        elif existentes:
            sys.exit(f"ERRO: {existentes} tarefa(s) deste pacote já estão no banco. Use --substituir para recarregar.")
        contagem = migrar(pacote, sessao)
        sessao.expire_all()
        problemas = conferir(pacote, sessao)
        print("Carga:", json.dumps(contagem, ensure_ascii=False, sort_keys=True))
        for aviso in avisos:
            print("  aviso:", aviso)
        relatorio(pacote, sessao)
        if problemas:
            print("CONFERÊNCIA COM DIVERGÊNCIAS:")
            for p in problemas:
                print("  -", p)
        else:
            print("Conferência: tarefas, eventos, participantes, marcadores, anexos e equipes batem com o SGI.")
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
        print(f"Gravado. {copiados} arquivo(s) de anexo em {servico_anexos.diretorio_anexos()}.")


if __name__ == "__main__":
    main()
