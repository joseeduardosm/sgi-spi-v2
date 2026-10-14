#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para importar os ativos do GLPI (somente leitura lá) para o módulo Patrimônio: chapa, número de série e descrição.
"""Importa os ativos do GLPI para o Patrimônio.

No GLPI só há SELECT (via SSH + mysql). Traz só patrimônio (chapa), número de série e descrição (tipo + marca + modelo); todos os bens entram na
localização "NECESSÁRIO ATUALIZAR", sem observações. Grava em `patrimonio_bens` com histórico "cadastrou" (origem "importação GLPI").
É idempotente: cada bem leva `id_cliente` = `glpi:<tipo>:<id>`, então rodar de novo não duplica.

Uso (a partir da raiz do projeto):
  GLPI_SENHA=... backend/.venv/bin/python scripts/importar-glpi.py             # simulação: só mostra os números
  GLPI_SENHA=... backend/.venv/bin/python scripts/importar-glpi.py --aplicar   # grava no banco
Variáveis: GLPI_HOST (padrão 10.23.1.242), GLPI_USUARIO (padrão root), GLPI_BANCO (padrão helpdesk). Sem GLPI_SENHA, a senha é pedida.
"""
import getpass
import json
import os
import sys
import uuid
from collections import Counter
from pathlib import Path

import paramiko

# Permite importar o pacote `app` do backend ao rodar o script da raiz do projeto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.patrimonio import Bem, EventoPatrimonio, Localizacao  # noqa: E402
from app.services.patrimonio.importacao_glpi import CODIGO_SALA_ATUALIZAR, SALA_ATUALIZAR, TIPOS_GLPI, montar_bem  # noqa: E402

HOST = os.environ.get("GLPI_HOST", "10.23.1.242")
USUARIO = os.environ.get("GLPI_USUARIO", "root")
BANCO = os.environ.get("GLPI_BANCO", "helpdesk")
APLICAR = "--aplicar" in sys.argv
ORIGEM = "importação GLPI"


def ler_glpi() -> list[dict]:
    """Todos os ativos não excluídos do GLPI, um dicionário por ativo (consulta só de leitura)."""
    senha = os.environ.get("GLPI_SENHA") or getpass.getpass(f"Senha de {USUARIO}@{HOST}: ")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USUARIO, password=senha, timeout=15, look_for_keys=False, allow_agent=False)
    registros: list[dict] = []
    for tabela in TIPOS_GLPI:
        # Tipo e modelo seguem o padrão glpi_<tabela sem o s final>types / ...models
        base = tabela[:-1]
        consulta = (
            "select json_object('tipo','%s','id',x.id,'nome',x.name,'serie',x.serial,'patrimonio',x.otherserial,'contato',x.contact,'contato_num',x.contact_num,"
            "'comentario',x.comment,'usuario',u.name,'usuario_nome',concat_ws(' ',u.firstname,u.realname),'local',l.completename,'estado',s.name,"
            "'tipo_nome',t.name,'modelo',m.name,'fabricante',f.name) from glpi_%s x "
            "left join glpi_users u on u.id=x.users_id left join glpi_locations l on l.id=x.locations_id left join glpi_states s on s.id=x.states_id "
            "left join glpi_%stypes t on t.id=x.%stypes_id left join glpi_%smodels m on m.id=x.%smodels_id left join glpi_manufacturers f on f.id=x.manufacturers_id "
            "where x.is_deleted=0 and x.is_template=0 order by x.id" % (tabela, tabela, base, base, base, base)
        )
        # --raw: o JSON já escapa quebras de linha, então cada ativo ocupa exatamente uma linha
        _, saida, erro = ssh.exec_command(f"mysql {BANCO} --raw -N -B -e \"{consulta}\"")
        texto = saida.read().decode()
        if saida.channel.recv_exit_status():
            raise RuntimeError(f"{tabela}: {erro.read().decode()}")
        registros += [json.loads(linha) for linha in texto.splitlines() if linha.strip()]
    ssh.close()
    return registros


def sala_necessario_atualizar(sessao) -> Localizacao:
    """Localização "NECESSÁRIO ATUALIZAR" (sem andar nem lado, direto no prédio) para o que veio do GLPI sem sala e sem andar."""
    nome, codigo = SALA_ATUALIZAR, CODIGO_SALA_ATUALIZAR
    sala = sessao.scalar(select(Localizacao).where(Localizacao.codigo == codigo))
    if sala is not None:
        return sala
    predio = sessao.scalar(select(Localizacao).where(Localizacao.tipo == "predio"))
    sala = Localizacao(id=uuid.uuid4(), pai_id=predio.id, tipo="sala", nome=nome, codigo=codigo, ativo=True)
    sessao.add(sala)
    sessao.flush()
    return sala


def main() -> None:
    registros = ler_glpi()
    print(f"GLPI: {len(registros)} ativos lidos ({dict(Counter(r['tipo'] for r in registros))})")
    resumo: Counter = Counter()
    with FabricaSessao() as sessao:
        ja_importados = set(sessao.scalars(select(Bem.id_cliente).where(Bem.id_cliente.like("glpi:%"))))
        # Chapas que já existem no Patrimônio contam como usadas (o ativo do GLPI entra sem chapa)
        chapas_usadas = {c for c in sessao.scalars(select(Bem.chapa_chave).where(Bem.chapa_chave.is_not(None)))}
        sala = sala_necessario_atualizar(sessao) if APLICAR else None
        for registro in registros:
            bem = montar_bem(registro, chapas_usadas)
            if bem["id_cliente"] in ja_importados:
                resumo["já importado"] += 1
                continue
            resumo["importar"] += 1
            resumo["sem chapa"] += 0 if bem["chapa"] else 1
            resumo["sem chapa e sem série"] += 0 if (bem["chapa"] or bem["numero_serie"]) else 1
            if not APLICAR:
                continue
            novo = Bem(id=uuid.uuid4(), localizacao_id=sala.id, **bem)
            sessao.add(novo)
            sessao.flush()
            sessao.add(EventoPatrimonio(
                id=uuid.uuid4(), bem_id=novo.id, tipo="cadastrou", autor_nome="Sistema", origem=ORIGEM, texto=f"Importado do GLPI para {SALA_ATUALIZAR}",
                dados={"sala_id": str(sala.id), "sala": sala.codigo, "glpi": bem["id_cliente"]}))
        if APLICAR:
            sessao.commit()
    print(("GRAVADO" if APLICAR else "SIMULAÇÃO (nada foi gravado; use --aplicar)") + f": {dict(resumo)}")


if __name__ == "__main__":
    main()
