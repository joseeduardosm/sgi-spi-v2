# Criado por José Eduardo Santana Martins
# Este arquivo serve para excluir a ficha de pré-cadastro 1 (teste de José Martia), a pedido do solicitante.
"""Exclui de vez a ficha de pré-cadastro 1 (José Martia, login proposto jesmartins2), com as formações e experiências.

Só exclui se a ficha não tiver admissão nem conta ligada (a admissão 1 já foi desfeita). O login proposto e o CPF ficam livres. A exclusão fica na auditoria
(`rh.pre_cadastro.excluir`).

Uso: cd backend && .venv/bin/python scripts_manutencao/excluir_ficha_pre_cadastro_1.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.rh_admissao import Admissao  # noqa: E402
from app.models.rh_pre_cadastro import PreCadastro  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

FICHA_ID = 1

with FabricaSessao() as s:
    ficha = s.get(PreCadastro, FICHA_ID)
    if ficha is None:
        sys.exit("Ficha 1 não encontrada: nada foi alterado.")
    if ficha.usuario_id is not None or s.scalar(select(Admissao.id).where(Admissao.pre_cadastro_id == ficha.id)) is not None:
        sys.exit("A ficha 1 tem conta ligada ou admissão: nada foi alterado.")
    autor = s.scalar(select(Usuario).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))
    resumo = {"ficha": ficha.id, "nome": ficha.nome_completo, "status": ficha.status, "login_proposto": ficha.login_proposto, "formacoes": len(ficha.formacoes), "experiencias": len(ficha.experiencias)}
    print("Excluindo:", json.dumps(resumo, ensure_ascii=False))
    auditar(s, autor.login, "rh.pre_cadastro.excluir", ficha.nome_completo, "Ficha de teste excluída a pedido do solicitante", autor_id=autor.id, dados=resumo)
    s.delete(ficha)
    s.commit()

with FabricaSessao() as s:
    print("Depois: fichas =", [(f.id, f.nome_completo, f.status) for f in s.scalars(select(PreCadastro))])
