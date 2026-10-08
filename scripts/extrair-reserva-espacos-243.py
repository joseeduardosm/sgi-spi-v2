#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para extrair do 10.23.1.243, somente leitura, os dados da reserva de espaços (objetos, reservas, eventos e fiscais).
"""Extrai da reserva de espaços do 10.23.1.243 (SOMENTE LEITURA) o pacote para `migrar-reserva-espacos-243.py`.

As tabelas `reservas_recursos_*` e os usuários envolvidos saem por `\\copy` numa transação read only; os fiscais são os
membros do grupo configurado em `reservas_recursos_configuracaoreservaespacos`.

Uso: SGI243_SENHA=... backend/.venv/bin/python scripts/extrair-reserva-espacos-243.py <pasta-destino>
"""
import csv, getpass, io, os, sys
import paramiko

DESTINO = sys.argv[1]
HOST = os.environ.get("SGI243_HOST", "10.23.1.243")
USUARIO = os.environ.get("SGI243_USUARIO", "root")
SENHA = os.environ.get("SGI243_SENHA") or getpass.getpass(f"Senha de {USUARIO}@{HOST}: ")
os.makedirs(DESTINO, exist_ok=True)
os.chmod(DESTINO, 0o700)

c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USUARIO, password=SENHA, timeout=15, allow_agent=False, look_for_keys=False)


def sql(script: str) -> str:
    i, o, e = c.exec_command("cd /tmp && sudo -u postgres psql -d spi_db -X -q -v ON_ERROR_STOP=1 -At -f -")
    i.write(script); i.channel.shutdown_write()
    saida = o.read().decode()
    if o.channel.recv_exit_status():
        raise RuntimeError(e.read().decode())
    return saida


MARCA = "@@TABELA@@"
TABELAS = {
    "objetos": "select * from reservas_recursos_objetoreservavel order by id",
    "reservas": "select * from reservas_recursos_reservarecurso order by id",
    "eventos": "select * from reservas_recursos_reservarecursoevento order by id",
    "usuarios": "select id, username, first_name, last_name, email, is_active from auth_user where id in "
                "(select criado_por_id from reservas_recursos_reservarecurso union select fiscal_responsavel_id from reservas_recursos_reservarecurso "
                "union select usuario_id from reservas_recursos_reservarecursoevento union select user_id from auth_user_groups "
                "where group_id = (select grupo_fiscais_id from reservas_recursos_configuracaoreservaespacos limit 1)) order by id",
    "fiscais": "select u.username from auth_user_groups ug join auth_user u on u.id = ug.user_id "
               "where ug.group_id = (select grupo_fiscais_id from reservas_recursos_configuracaoreservaespacos limit 1) order by u.username",
}
script = ["begin transaction isolation level repeatable read read only;"]
for nome, consulta in TABELAS.items():
    script += [f"\\echo {MARCA}{nome}", f"\\copy ({consulta}) to stdout with (format csv, header true, encoding 'UTF8')"]
script.append("commit;")
for parte in sql("\n".join(script) + "\n").split(MARCA)[1:]:
    nome, conteudo = parte.split("\n", 1)
    open(f"{DESTINO}/{nome}.csv", "w", encoding="utf-8", newline="").write(conteudo)
    print(nome, len(list(csv.DictReader(io.StringIO(conteudo, newline="")))))
os.system(f"chmod -R go-rwx {DESTINO}")
print("pacote em", DESTINO)
