#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para extrair do SGI SPI (10.23.1.220), somente leitura, o pacote de Contratações (ETP e TR) para a migração.
"""Extrai do SGI SPI (10.23.1.220), SOMENTE LEITURA, o pacote de Contratações (ETP e TR) para a migração.

Mesmo formato de `extrair-protocolo-sgi.py`: o SQL roda numa única transação read only (\\copy ... to stdout) e o mapa de usuários sai sem
senhas. Não copia auditoria, mensagens nem código-fonte (decisão do projeto). Nada é gravado no servidor de origem.

Uso: SGI_SENHA=... backend/.venv/bin/python scripts/extrair-contratacoes-sgi.py <pasta-destino>
A senha do usuário SSH também é usada no sudo (para ler o banco como postgres).
O pacote contém conteúdo de documentos e dados pessoais: a pasta é criada com permissão 700.
"""
import csv, getpass, io, os, sys
import paramiko

DESTINO = sys.argv[1]
HOST = os.environ.get("SGI_HOST", "10.23.1.220")
USUARIO = os.environ.get("SGI_USUARIO", "administrador")
SENHA = os.environ.get("SGI_SENHA") or getpass.getpass(f"Senha de {USUARIO}@{HOST}: ")
os.makedirs(f"{DESTINO}/dados", exist_ok=True)
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


ORDEM = {
    "procurement_documents": '"CreatedAt", "Id"',
    "procurement_sections": '"DocumentId", "Order"',
    "procurement_items": '"SectionId", "ParentId" nulls first, "Order"',
    "procurement_tr_table_items": '"ItemId", "Order"',
    "procurement_item_reviews": '"ItemId", "CreatedAt"',
    "procurement_imported_comments": '"ItemId", "CreatedAt"',
}
TABELAS = list(ORDEM)

# Um único snapshot: cada tabela sai delimitada por um marcador na mesma transação
MARCA = "@@TABELA@@"
script = ["begin transaction isolation level repeatable read read only;"]
for t in TABELAS:
    script.append(f"\\echo {MARCA}{t}")
    script.append(f"\\copy (select * from sgi.{t} order by {ORDEM[t]}) to stdout with (format csv, header true, encoding 'UTF8')")
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
    f.write("# Extração somente leitura de Contratações (10.23.1.220)\n\n[linhas]\n")
    for t, n in linhas.items():
        f.write(f"{t}={n}\n")
os.system(f"chmod -R go-rwx {DESTINO}")
print("pacote em", DESTINO)
