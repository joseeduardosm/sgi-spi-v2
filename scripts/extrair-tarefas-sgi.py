#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para extrair do SGI SPI (10.23.1.220), somente leitura, o pacote do módulo de tarefas para a migração.
"""Extrai do SGI SPI (10.23.1.220), SOMENTE LEITURA, o pacote do módulo de tarefas para a migração.

Mesmo formato de `extrair-contratos-sgi.py`, sem gravar nada lá: o SQL roda numa única transação read only
(\\copy ... to stdout), os anexos das tarefas vêm por SFTP (conferidos pelo SHA-256) e o mapa de usuários sai sem senhas.

Uso: SGI_SENHA=... backend/.venv/bin/python scripts/extrair-tarefas-sgi.py <pasta-destino>
A senha do usuário SSH também é usada no sudo (para ler o banco como postgres).
O pacote contém dados pessoais e documentos: a pasta é criada com permissão 700.
"""
import csv, getpass, hashlib, io, os, sys
import paramiko

DESTINO = sys.argv[1]
HOST = os.environ.get("SGI_HOST", "10.23.1.220")
USUARIO = os.environ.get("SGI_USUARIO", "administrador")
SENHA = os.environ.get("SGI_SENHA") or getpass.getpass(f"Senha de {USUARIO}@{HOST}: ")
os.makedirs(f"{DESTINO}/dados", exist_ok=True)
os.makedirs(f"{DESTINO}/anexos", exist_ok=True)
os.chmod(DESTINO, 0o700)

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USUARIO, password=SENHA, timeout=15)


def remoto(comando: str, entrada: str | None = None) -> str:
    i, o, e = c.exec_command(comando)
    if entrada is not None:
        i.write(entrada); i.channel.shutdown_write()
    saida = o.read().decode()
    if o.channel.recv_exit_status():
        raise RuntimeError(f"{comando[:80]}: {e.read().decode()}")
    return saida


def sql(script: str) -> str:
    # O psql lê o script da entrada padrão depois da senha do sudo
    i, o, e = c.exec_command("sudo -S -p '' -u postgres psql -d sgi_spi -X -q -v ON_ERROR_STOP=1 -At -f -")
    i.write(SENHA + "\n" + script); i.channel.shutdown_write()
    saida = o.read().decode()
    if o.channel.recv_exit_status():
        raise RuntimeError(e.read().decode())
    return saida


TABELAS = """task_teams task_team_leaders task_team_members task_markers work_tasks work_task_participants
  work_task_markers work_task_events work_task_event_attachments task_checklist_items task_transfers stored_attachments""".split()


def consulta(t: str) -> str:
    if t == "stored_attachments":
        return 'select * from sgi.stored_attachments where "Id" in (select "AttachmentId" from sgi.work_task_event_attachments) order by "CreatedAt", "Id"'
    return f'select * from sgi.{t} order by "CreatedAt", "Id"'


# Um único snapshot: cada tabela sai delimitada por um marcador na mesma transação
MARCA = "@@TABELA@@"
script = ["begin transaction isolation level repeatable read read only;"]
for t in TABELAS:
    script.append(f"\\echo {MARCA}{t}")
    script.append(f"\\copy ({consulta(t)}) to stdout with (format csv, header true, encoding 'UTF8')")
script.append("commit;")
partes = sql("\n".join(script) + "\n").split(MARCA)[1:]
linhas = {}
for n, parte in enumerate(partes, 1):
    nome, conteudo = parte.split("\n", 1)
    assert nome == TABELAS[n - 1], nome
    with open(f"{DESTINO}/dados/{n:02d}_{nome}.csv", "w", encoding="utf-8", newline="") as f:
        f.write(conteudo)
    linhas[nome] = sum(1 for _ in csv.reader(io.StringIO(conteudo, newline=""))) - 1
print("linhas:", linhas)

# Anexos por SFTP, conferindo o SHA-256 gravado no banco
sftp = c.open_sftp()
ausentes, divergentes, total = [], [], 0
with open(f"{DESTINO}/dados/{TABELAS.index('stored_attachments') + 1:02d}_stored_attachments.csv", encoding="utf-8", newline="") as f:
    for linha in csv.DictReader(f):
        chave = linha["StorageKey"]
        if ".." in chave or chave.startswith("/"):
            ausentes.append(chave + " (caminho inválido)"); continue
        local = f"{DESTINO}/anexos/{chave}"
        os.makedirs(os.path.dirname(local), exist_ok=True)
        try:
            sftp.get(f"/var/lib/sgi-spi/attachments/{chave}", local)
        except FileNotFoundError:
            ausentes.append(chave); continue
        total += 1
        if hashlib.sha256(open(local, "rb").read()).hexdigest().lower() != linha["Sha256"].lower():
            divergentes.append(chave)
open(f"{DESTINO}/anexos-ausentes.txt", "w").write("\n".join(ausentes))
print(f"anexos: {total} copiados, {len(ausentes)} ausentes, {len(divergentes)} com SHA-256 divergente")

# Mapa de usuários sem senhas: o JSON é lido lá e só os campos de identificação saem
usuarios = remoto("python3 -", """
import csv, json, sys
d = json.load(open('/var/lib/sgi-spi/portal-data.json', encoding='utf-8'))
w = csv.writer(sys.stdout)
w.writerow(['Id','Username','ExternalId','Origin','FullName','Email','Department','JobTitle','IsActive','IsSuperuser'])
for u in d.get('Users', []):
    p = u.get('Profile') or {}
    w.writerow([u.get('Id'), u.get('Username'), u.get('ExternalId'), u.get('Origin'), p.get('FullName'), p.get('Email'),
                p.get('Department'), p.get('JobTitle'), u.get('IsActive'), u.get('IsSuperuser')])
""")
open(f"{DESTINO}/usuarios.csv", "w", encoding="utf-8").write(usuarios)

with open(f"{DESTINO}/MANIFESTO.txt", "w") as f:
    f.write("# Extração somente leitura do módulo de tarefas (10.23.1.220)\n")
    f.write(f"anexos_copiados={total}\nanexos_ausentes={len(ausentes)}\nanexos_sha_divergente={len(divergentes)}\n\n[linhas]\n")
    for t, n in linhas.items():
        f.write(f"{t}={n}\n")
os.system(f"chmod -R go-rwx {DESTINO}")
print("pacote em", DESTINO)
