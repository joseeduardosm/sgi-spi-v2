# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a migração do módulo de tarefas do 10.23.1.220 (scripts/migrar-tarefas-sgi.py) com um pacote mínimo.
"""Pacote sintético no formato do `extrair-tarefas-sgi.py`: uma equipe, um marcador, duas tarefas e a linha do tempo."""

import csv
import importlib.util
import json
from pathlib import Path

from sqlalchemy import select

from app.core.banco import FabricaSessao
from app.models.tarefas import EventoTarefa, Tarefa
from tests.conftest import criar_usuario

RAIZ = Path(__file__).resolve().parents[2]
especificacao = importlib.util.spec_from_file_location("migrar_tarefas", RAIZ / "scripts" / "migrar-tarefas-sgi.py")
migrar_tarefas = importlib.util.module_from_spec(especificacao)
especificacao.loader.exec_module(migrar_tarefas)

EQUIPE, MARCADOR = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
T1, T2 = "33333333-3333-3333-3333-333333333333", "44444444-4444-4444-4444-444444444444"
CRIADO = "2026-08-10 12:00:00+00"


def _csv(pasta: Path, n: int, nome: str, linhas: list[dict]) -> None:
    colunas = list(linhas[0]) if linhas else ["Id"]
    with open(pasta / "dados" / f"{n:02d}_{nome}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, colunas)
        w.writeheader()
        w.writerows(linhas)


def _evento(i: int, tarefa: str, tipo: str, payload: dict, descricao: str = "", quando: str = CRIADO) -> dict:
    return {"Id": f"5555555{i}-5555-5555-5555-555555555555", "TaskId": tarefa, "Type": tipo, "AuthorUserId": "7", "AuthorName": "Ana Antiga",
            "Title": "", "Description": descricao, "PayloadJson": json.dumps(payload), "CreatedAt": quando, "UpdatedAt": quando,
            "RemovalReason": "", "RemovedAt": "", "RemovedByUserId": ""}


def _pacote(pasta: Path) -> Path:
    (pasta / "dados").mkdir(parents=True)
    (pasta / "anexos").mkdir()
    with open(pasta / "usuarios.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Id", "Username", "ExternalId", "Origin", "FullName", "Email", "Department", "JobTitle", "IsActive", "IsSuperuser"])
        w.writerow(["7", "ana", "", "Ldap", "Ana Antiga", "ana@sp.gov.br", "", "", "True", "False"])
        w.writerow(["8", "saiu", "", "Ldap", "Pessoa que Saiu", "saiu@sp.gov.br", "", "", "False", "False"])
    base = {"CreatedAt": CRIADO, "UpdatedAt": CRIADO}
    _csv(pasta, 1, "task_teams", [{"Id": EQUIPE, "Name": "CCC/DGA", "OwnerUserId": "7", "ParentTeamId": "", "Active": "t", **base, "ManagerUserId": "7"}])
    _csv(pasta, 2, "task_team_leaders", [])
    _csv(pasta, 3, "task_team_members", [{"Id": "66666666-6666-6666-6666-666666666666", "TeamId": EQUIPE, "UserId": "8", **base}])
    _csv(pasta, 4, "task_markers", [{"Id": MARCADOR, "Name": "Contrato\t008/2026 – nome bem longo " + "x" * 60, "Color": "#9ad51a", **base}])
    tarefa = {"CreatorUserId": "7", "Description": "", "Priority": "High", "CompletedAt": "", "Version": "4", "SortIndex": "0",
              "InProgressSince": "", "OperationalSeconds": "0", "ParentTaskId": "", "PlannedOccurrence": "", "RecurrenceId": "",
              "ApprovalUserId": "", "ApprovalRequesterUserId": "", **base}
    _csv(pasta, 5, "work_tasks", [
        {"Id": T1, "Title": "Revisar edital", "Deadline": "2026-09-20 20:00:00+00", "Status": "InProgress", "TeamId": EQUIPE, "Number": "12", **tarefa},
        {"Id": T2, "Title": "Tarefa pessoal", "Deadline": "2026-08-20 20:00:00+00", "Status": "Completed", "TeamId": "", "Number": "11",
         **{**tarefa, "CompletedAt": "2026-08-19 10:00:00+00"}},
    ])
    _csv(pasta, 6, "work_task_participants", [{"Id": f"7777777{i}-7777-7777-7777-777777777777", "TaskId": t, "UserId": u, **base}
                                             for i, (t, u) in enumerate(((T1, "8"), (T2, "7")))])
    _csv(pasta, 7, "work_task_markers", [{"Id": "88888888-8888-8888-8888-888888888888", "TaskId": T1, "MarkerId": MARCADOR, **base}])
    _csv(pasta, 8, "work_task_events", [
        _evento(1, T1, "Created", {"deadline": "2026-09-01T20:00:00+00:00", "responsibleUserId": 7}),
        _evento(2, T1, "DeadlineChanged", {"previous": "2026-09-01T20:00:00+00:00", "current": "2026-09-20T20:00:00+00:00",
                                           "justification": "Aguardando parecer"}, quando="2026-08-11 12:00:00+00"),
        _evento(3, T1, "StatusChanged", {"previous": 0, "current": 1}, quando="2026-08-12 12:00:00+00"),
        _evento(4, T1, "Transferred", {"fromUserId": 7, "toUserId": 8, "justification": "Férias", "previousDeadline": "2026-09-20T20:00:00+00:00",
                                       "newDeadline": "2026-09-20T20:00:00+00:00"}, quando="2026-08-13 12:00:00+00"),
        _evento(5, T1, "Edited", {"Title": "Revisar edital", "Priority": 2, "markerIds": [MARCADOR]}, quando="2026-08-14 12:00:00+00"),
        _evento(6, T1, "CommentAdded", {"hasText": True}, "Segue a minuta.", quando="2026-08-15 12:00:00+00"),
        _evento(7, T2, "Created", {"deadline": "2026-08-20T20:00:00+00:00", "responsibleUserId": 7}),
        _evento(8, T2, "StatusChanged", {"currentStatus": "Completed", "previousStatus": "AwaitingApproval"}, quando="2026-08-19 10:00:00+00"),
    ])
    for n, nome in ((9, "work_task_event_attachments"), (10, "task_checklist_items"), (11, "task_transfers"), (12, "stored_attachments")):
        _csv(pasta, n, nome, [])
    return pasta


def test_migracao_de_tarefas_do_sgi(tmp_path):
    criar_usuario("ana", nome_completo="Ana Atual")
    pacote = migrar_tarefas.Pacote(_pacote(tmp_path / "pacote"))
    with FabricaSessao() as sessao:
        # Tarefa criada aqui com o número de uma tarefa do SGI ganha o próximo livre
        from datetime import datetime, timezone
        agora = datetime.now(timezone.utc)
        sessao.add(Tarefa(numero=12, titulo="Criada aqui", prazo=agora, prazo_original=agora))
        sessao.commit()
        contagem = migrar_tarefas.migrar(pacote, sessao)
        sessao.flush()
        assert migrar_tarefas.conferir(pacote, sessao) == []
        assert contagem["tarefas"] == 2 and contagem["eventos"] == 8
        assert sessao.scalar(select(Tarefa.numero).where(Tarefa.titulo == "Criada aqui")) == 13
        t1 = sessao.scalar(select(Tarefa).where(Tarefa.numero == 12))
        assert (t1.status, t1.prioridade, t1.equipe.nome) == ("em_andamento", "alta", "CCC/DGA")
        assert t1.prazo_original.day == 1 and t1.prazo.day == 20
        assert [m.nome for m in t1.marcadores][0].startswith("Contrato 008/2026") and len(t1.marcadores[0].nome) <= 120
        saiu = t1.responsavel_id
        eventos = {e.tipo: e for e in sessao.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id == t1.id))}
        assert eventos["prazo"].texto == "Aguardando parecer" and eventos["prazo"].dados["de"].startswith("2026-09-01")
        assert eventos["status"].dados == {"de": "a_fazer", "para": "em_andamento"}
        assert eventos["transferida"].dados == {"de": "Ana Antiga", "para": "Pessoa que Saiu"} and eventos["transferida"].autor_nome == "Ana Antiga"
        assert eventos["editada"].dados["campos"]["prioridade"] == {"para": "alta"}
        t2 = sessao.scalar(select(Tarefa).where(Tarefa.numero == 11))
        assert t2.status == "concluida" and t2.equipe_id is None
        antigo = sessao.scalar(select(EventoTarefa).where(EventoTarefa.tarefa_id == t2.id, EventoTarefa.tipo == "status"))
        assert antigo.dados == {"de": "em_validacao", "para": "concluida"}
        # Quem não existia aqui foi criado inativo e sem senha
        from app.models.usuario import Usuario
        pessoa = sessao.get(Usuario, saiu)
        assert (pessoa.login, pessoa.ativo, pessoa.hash_senha) == ("saiu", False, None)
        sessao.rollback()
