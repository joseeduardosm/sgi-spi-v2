# Criado por José Eduardo Santana Martins
# Este arquivo serve para reenviar o e-mail "Sua nomeação foi publicada" da admissão 1, a pedido do RH (o botão "Reenviar" da tela faz o mesmo).
"""Reenvia o e-mail de nomeação da admissão 1 pelo serviço da admissão (mesmo caminho do botão "Reenviar"), em nome de quem iniciou a admissão.

Uso: cd backend && .venv/bin/python scripts_manutencao/reenviar_email_nomeacao_admissao_1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.rh_admissao import Admissao  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.rh import servico_admissao  # noqa: E402

ADMISSAO_ID = 1


def main() -> None:
    with FabricaSessao() as sessao:
        admissao = sessao.get(Admissao, ADMISSAO_ID)
        autor = sessao.get(Usuario, admissao.criado_por_id)
        try:
            resultado = servico_admissao.reenviar_email(sessao, ADMISSAO_ID, autor)
        except servico_admissao.ErroAdmissao as erro:
            print("Não enviado:", erro)
            return
        print(f"E-mail enviado para {resultado.email_destino} em {resultado.email_enviado_em:%d/%m/%Y %H:%M} (UTC).")


if __name__ == "__main__":
    main()
