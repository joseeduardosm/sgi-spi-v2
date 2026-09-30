#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para extrair do portal do 10.23.1.243, somente leitura, as notícias, os atalhos e os arquivos deles.
"""Extrai do portal de notícias do 10.23.1.243 (SOMENTE LEITURA) o pacote para `migrar-noticias-243.py`.

As tabelas `noticias_noticia` e `atalhos_atalho` saem por `\\copy` numa transação read only; imagens e anexos
vêm por SFTP de `/root/aplicacoesspi/media`.

Uso: SGI243_SENHA=... backend/.venv/bin/python scripts/extrair-noticias-243.py <pasta-destino>
"""
import csv, getpass, io, os, sys
import paramiko

DESTINO = sys.argv[1]
HOST = os.environ.get("SGI243_HOST", "10.23.1.243")
USUARIO = os.environ.get("SGI243_USUARIO", "root")
SENHA = os.environ.get("SGI243_SENHA") or getpass.getpass(f"Senha de {USUARIO}@{HOST}: ")
MIDIA = "/root/aplicacoesspi/media"
os.makedirs(f"{DESTINO}/midia", exist_ok=True)
os.chmod(DESTINO, 0o700)

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USUARIO, password=SENHA, timeout=15)


def sql(script: str) -> str:
    i, o, e = c.exec_command("cd /tmp && sudo -u postgres psql -d spi_db -X -q -v ON_ERROR_STOP=1 -At -f -")
    i.write(script); i.channel.shutdown_write()
    saida = o.read().decode()
    if o.channel.recv_exit_status():
        raise RuntimeError(e.read().decode())
    return saida


MARCA = "@@TABELA@@"
TABELAS = {"noticias_noticia": 'select * from noticias_noticia order by id', "atalhos_atalho": 'select * from atalhos_atalho order by ordem, id'}
script = ["begin transaction isolation level repeatable read read only;"]
for nome, consulta in TABELAS.items():
    script += [f"\\echo {MARCA}{nome}", f"\\copy ({consulta}) to stdout with (format csv, header true, encoding 'UTF8')"]
script.append("commit;")
arquivos = []
for parte in sql("\n".join(script) + "\n").split(MARCA)[1:]:
    nome, conteudo = parte.split("\n", 1)
    open(f"{DESTINO}/{nome}.csv", "w", encoding="utf-8", newline="").write(conteudo)
    linhas = list(csv.DictReader(io.StringIO(conteudo, newline="")))
    print(nome, len(linhas))
    for r in linhas:
        arquivos += [r.get(k) for k in ("imagem_destaque", "anexo_pdf", "imagem") if r.get(k)]

sftp = c.open_sftp()
ausentes = []
for relativo in sorted(set(arquivos)):
    if ".." in relativo or relativo.startswith("/"):
        ausentes.append(relativo); continue
    local = f"{DESTINO}/midia/{relativo}"
    os.makedirs(os.path.dirname(local), exist_ok=True)
    try:
        sftp.get(f"{MIDIA}/{relativo}", local)
    except FileNotFoundError:
        ausentes.append(relativo)
print(f"arquivos: {len(set(arquivos)) - len(ausentes)} copiados, {len(ausentes)} ausentes {ausentes if ausentes else ''}")
os.system(f"chmod -R go-rwx {DESTINO}")
print("pacote em", DESTINO)
