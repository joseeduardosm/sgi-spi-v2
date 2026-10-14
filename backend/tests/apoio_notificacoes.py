# Criado por José Eduardo Santana Martins
# Este arquivo serve para ajudar os testes a ligar canais de notificação (todo usuário novo começa com e-mail, navegador e desktop desmarcados).
"""Apoio dos testes de Notificações."""

from app.core.banco import FabricaSessao
from app.models.notificacao_preferencias import ConfigNotificacaoUsuario, PreferenciaNotificacao
from app.services.notificacoes.catalogo import EVENTOS


def ligar_canais(usuarios_ids, canais=("email",), eventos=None) -> None:
    """Liga os canais para os usuários, em todos os eventos (ou só nos informados), como se cada um tivesse marcado na tela de Preferências."""
    with FabricaSessao() as sessao:
        for usuario_id in usuarios_ids:
            for chave, evento in EVENTOS.items():
                if eventos is not None and chave not in eventos:
                    continue
                for canal in canais:
                    if canal in evento.canais_disponiveis:
                        sessao.add(PreferenciaNotificacao(usuario_id=usuario_id, evento=chave, canal=canal))
        sessao.commit()


def configurar(usuario_id, **campos) -> None:
    """Grava a configuração do usuário (frequência do e-mail, não perturbe)."""
    with FabricaSessao() as sessao:
        linha = sessao.get(ConfigNotificacaoUsuario, usuario_id) or ConfigNotificacaoUsuario(usuario_id=usuario_id)
        for campo, valor in campos.items():
            setattr(linha, campo, valor)
        sessao.add(linha)
        sessao.commit()


import pytest  # noqa: E402


@pytest.fixture
def todos_com_email(monkeypatch):
    """Simula que todo mundo ligou o e-mail em todos os eventos (os testes de fluxo dos módulos conferem os e-mails dos avisos)."""
    from app.services.notificacoes import preferencias

    original = preferencias.canais_por_destinatario

    def com_email(*args, **kwargs):
        resultado = original(*args, **kwargs)
        for canais in resultado.values():
            canais.email = True
        return resultado

    monkeypatch.setattr(preferencias, "canais_por_destinatario", com_email)
