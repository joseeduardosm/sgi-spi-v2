#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para conferir, somente leitura, o que ainda difere entre o SGI SPI antigo (10.23.1.220) e o SGI SPI novo antes do desligamento.
"""Conferência final entre o SGI SPI antigo (10.23.1.220) e o novo, SOMENTE LEITURA nos dois lados.

Para cada tabela migrada compara o conjunto de ids: quantos existem em cada lado, quais só existem no antigo (ainda a migrar, ou
criados lá depois da carga) e quais só existem no novo (criados aqui). Usuários são comparados pelo login. Nada é gravado em lugar nenhum.
Fora do escopo por decisão do projeto: mensagens, auditoria, código-fonte, mapeamentos e referências.

Uso (na pasta backend): SGI_SENHA=... .venv/bin/python ../scripts/conferir-sgi.py
A senha do usuário SSH também é usada no sudo (para ler o banco como postgres).
"""
import getpass
import json
import os
import sys
from pathlib import Path

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.contratacoes import ComentarioImportado, DocumentoContratacao, ItemContratacao, LinhaTabelaTr, RevisaoItem, SecaoContratacao  # noqa: E402
from app.models.contratos import Contrato, DocumentoContrato, EmpresaContratada, ItemContrato  # noqa: E402
from app.models.protocolo import NumeroProtocolo, TipoProtocolo  # noqa: E402
from app.models.tarefas import EquipeTarefas, EventoTarefa, Tarefa  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402

HOST = os.environ.get("SGI_HOST", "10.23.1.220")
USUARIO = os.environ.get("SGI_USUARIO", "administrador")
SENHA = os.environ.get("SGI_SENHA") or getpass.getpass(f"Senha de {USUARIO}@{HOST}: ")

# (tabela do SGI antigo, modelo novo, coluna que guarda o id de origem). Contratos entraram por outro caminho (os ids não são os do SGI):
# são comparados pelo número NNN/AAAA. Itens, empresas e documentos de contrato só entram na contagem.
PARES = [
    ("contracts", Contrato, "numero"),
    ("task_teams", EquipeTarefas, "id"), ("work_tasks", Tarefa, "id"), ("work_task_events", EventoTarefa, "id"),
    ("protocol_document_types", TipoProtocolo, "origem_sgi_id"), ("protocol_numbers", NumeroProtocolo, "origem_sgi_id"),
    ("procurement_documents", DocumentoContratacao, "origem_sgi_id"), ("procurement_sections", SecaoContratacao, "origem_sgi_id"),
    ("procurement_items", ItemContratacao, "origem_sgi_id"), ("procurement_tr_table_items", LinhaTabelaTr, "origem_sgi_id"),
    ("procurement_item_reviews", RevisaoItem, "origem_sgi_id"), ("procurement_imported_comments", ComentarioImportado, "origem_sgi_id"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USUARIO, password=SENHA, timeout=15)


def sql(script: str) -> str:
    i, o, e = c.exec_command("sudo -S -p '' -u postgres psql -d sgi_spi -X -q -v ON_ERROR_STOP=1 -At -f -")
    i.write(SENHA + "\n" + script)
    i.channel.shutdown_write()
    saida = o.read().decode()
    if o.channel.recv_exit_status():
        raise RuntimeError(e.read().decode())
    return saida


MARCA = "@@"
script = ["begin transaction isolation level repeatable read read only;"]
for tabela, _, _ in PARES:
    chave = "lpad(\"Sequence\"::text, 3, '0') || '/' || \"Year\"" if tabela == "contracts" else '"Id"'
    script += [f"\\echo {MARCA}{tabela}", f"select {chave} from sgi.{tabela};"]
CONTAGENS = ["contract_items", "contract_companies", "contract_documents"]
for tabela in CONTAGENS:
    script += [f"\\echo {MARCA}{tabela}", f'select "Id" from sgi.{tabela};']
script.append("commit;")
antigo: dict[str, set[str]] = {}
for parte in sql("\n".join(script) + "\n").split(MARCA)[1:]:
    nome, corpo = parte.split("\n", 1)
    antigo[nome] = {linha.strip().lower() for linha in corpo.splitlines() if linha.strip()}

i, o, e = c.exec_command("python3 -c \"import json;d=json.load(open('/var/lib/sgi-spi/portal-data.json',encoding='utf-8'));print(json.dumps([u.get('Username') for u in d.get('Users',[])]))\"")
logins_antigos = {(x or "").lower() for x in json.loads(o.read().decode())}

print(f"{'tabela do SGI antigo':34} {'antigo':>7} {'novo':>7} {'só no antigo':>13} {'só no novo':>11}")
pendencias = 0
with FabricaSessao() as sessao:
    for tabela, modelo, coluna in PARES:
        novos = {str(v).lower() for v in sessao.scalars(select(getattr(modelo, coluna))) if v is not None}
        so_antigo, so_novo = antigo[tabela] - novos, novos - antigo[tabela]
        pendencias += bool(so_antigo)
        print(f"{tabela:34} {len(antigo[tabela]):7} {len(novos):7} {len(so_antigo):13} {len(so_novo):11}")
        if so_antigo:
            limite = 40 if tabela == "contracts" else 3
            print(f"    ainda só no antigo{' (amostra)' if limite == 3 else ''}: {sorted(so_antigo)[:limite]}")
        if tabela == "contracts" and so_novo:
            print(f"    só no novo: {sorted(so_novo)[:40]}")
    for tabela, modelo in zip(CONTAGENS, (ItemContrato, EmpresaContratada, DocumentoContrato)):
        print(f"{tabela + ' (só contagem)':34} {len(antigo[tabela]):7} {sessao.scalar(select(func.count()).select_from(modelo)):7}")
    logins_novos = {u.lower() for u in sessao.scalars(select(Usuario.login))}
    faltam = sorted(logins_antigos - logins_novos)
    print(f"{'usuários (por login)':34} {len(logins_antigos):7} {len(logins_novos):7} {len(faltam):13} {len(logins_novos - logins_antigos):11}")
    if faltam:
        print(f"    logins do antigo que não existem no novo: {faltam[:15]}{' …' if len(faltam) > 15 else ''}")

print("\nSó no antigo = ainda não migrado (ou criado lá depois da carga): rode de novo o script de migração do módulo com --substituir no dia do corte.")
print("Só no novo = criado aqui depois da migração (esperado). Nada foi gravado em nenhum dos dois lados.")
sys.exit(1 if pendencias else 0)
