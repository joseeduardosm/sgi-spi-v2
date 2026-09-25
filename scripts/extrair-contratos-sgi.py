#!/usr/bin/env python3
"""Extrai do SGI SPI (10.23.1.220), SOMENTE LEITURA, o pacote do Módulo de Contratos para a migração.

Mesmo formato do deploy/sql/backup-modulo-contratos.sh do SGI, sem gravar nada lá: o SQL roda numa única
transação read only (\\copy ... to stdout), os anexos vêm por SFTP e o mapa de usuários sai sem senhas.

Uso: SGI_SENHA=... backend/.venv/bin/python scripts/extrair-contratos-sgi.py <pasta-destino>
A senha do usuário SSH também é usada no sudo (para ler o banco como postgres).
O pacote contém dados pessoais e documentos contratuais: a pasta é criada com permissão 700.
"""
import csv, getpass, hashlib, io, json, os, sys
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
    status = o.channel.recv_exit_status()
    erro = e.read().decode()
    if status:
        raise RuntimeError(f"{comando[:80]}: {erro}")
    return saida


def sql(script: str) -> str:
    # O psql lê o script da entrada padrão depois da senha do sudo
    i, o, e = c.exec_command("sudo -S -p '' -u postgres psql -d sgi_spi -X -q -v ON_ERROR_STOP=1 -At -f -")
    i.write(SENHA + "\n" + script); i.channel.shutdown_write()
    saida = o.read().decode(); status = o.channel.recv_exit_status()
    if status:
        raise RuntimeError(e.read().decode())
    return saida


TABELAS = """contract_companies company_representatives stored_attachments contracts
  contract_role_assignments contract_items contract_documents contract_term_extensions
  contract_forecast_vigencies contract_forecast_item_limits contract_forecast_allocations
  contract_commitment_notes contract_execution_checklists contract_execution_checklist_items
  contract_execution_evaluation_forms contract_execution_competences
  contract_execution_measurement_items contract_execution_acknowledgements
  contract_execution_memories contract_execution_cadin_checks
  contract_execution_checklist_documents contract_execution_evaluations
  contract_commitment_note_movements contract_adjustments contract_adjustment_items
  contract_adjustment_memories contract_quantity_changes contract_quantity_change_items
  contract_quantity_change_acknowledgements contract_extension_processes
  contract_extension_acknowledgements audit_events contract_execution_commitment_note_selections""".split()

filtro = sql("""begin transaction read only;
select string_agg(format('select %I as id from %s', a.attname, c.conrelid::regclass), ' union ')
  from pg_constraint c
  join pg_attribute a on a.attrelid = c.conrelid and a.attnum = c.conkey[1]
  where c.contype = 'f' and c.confrelid = 'sgi.stored_attachments'::regclass
    and c.connamespace = 'sgi'::regnamespace and c.conrelid::regclass::text like 'sgi.contract%';
commit;""").strip()
assert filtro, "sem FKs de anexos"


def consulta(t: str) -> str:
    if t == "stored_attachments":
        return f'select * from sgi.stored_attachments where "Id" in (select id from ({filtro}) r where id is not null) order by "CreatedAt", "Id"'
    if t == "contract_execution_commitment_note_selections":
        # Criada no SGI em 24/09/2026 (várias NEs por competência); pode não existir em versões anteriores
        return f'select * from sgi.{t} order by "CreatedAt", "Id"'
    if t == "audit_events":
        return """select * from sgi.audit_events where "ResourceType" in ('Contract','ContractCompany','contract') order by "CreatedAt", "Id\""""
    return f'select * from sgi.{t} order by "CreatedAt", "Id"'


# Um único snapshot: cada tabela sai delimitada por um marcador na mesma transação
MARCA = "@@TABELA@@"
script = ["begin transaction isolation level repeatable read read only;"]
for t in TABELAS:
    script.append(f"\\echo {MARCA}{t}")
    script.append(f"\\copy ({consulta(t)}) to stdout with (format csv, header true, encoding 'UTF8')")
script.append("commit;")
saida = sql("\n".join(script) + "\n")
partes = saida.split(MARCA)[1:]
linhas = {}
for n, parte in enumerate(partes, 1):
    nome, conteudo = parte.split("\n", 1)
    assert nome == TABELAS[n - 1], nome
    with open(f"{DESTINO}/dados/{n:02d}_{nome}.csv", "w", encoding="utf-8", newline="") as f:
        f.write(conteudo)
    linhas[nome] = sum(1 for _ in csv.reader(io.StringIO(conteudo, newline=""))) - 1
print("linhas:", linhas)

meta = sql("begin transaction read only; select max(\"MigrationId\") from public.\"__EFMigrationsHistory\"; commit;").strip()

# Anexos por SFTP, conferindo o SHA-256 gravado no banco
sftp = c.open_sftp()
ausentes, divergentes, total = [], [], 0
with open(f"{DESTINO}/dados/03_stored_attachments.csv", encoding="utf-8", newline="") as f:
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
    f.write(f"# Extração somente leitura do Módulo de Contratos (10.23.1.220)\nultima_migration={meta}\n")
    f.write(f"anexos_copiados={total}\nanexos_ausentes={len(ausentes)}\nanexos_sha_divergente={len(divergentes)}\n\n[linhas]\n")
    for t, n in linhas.items():
        f.write(f"{t}={n}\n")
os.system(f"chmod -R go-rwx {DESTINO}")
print("pacote em", DESTINO)
