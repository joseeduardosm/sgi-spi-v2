# Criado por José Eduardo Santana Martins
# Este arquivo serve para autenticar usuários pelo LDAP e, como contingência, pela conta local.
"""Autenticação: diretório LDAP ativo primeiro; conta local como contingência.

Assim, as pessoas entram com a senha da rede, e a conta local (ex.: `root`) continua
funcionando quando o AD está fora do ar.
"""

import logging

from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.core.seguranca import criar_token_acesso, verificar_senha
from app.models.usuario import Usuario
from app.schemas.autenticacao import RespostaToken, UsuarioSessao
from app.services import cliente_ldap, servico_ldap, servico_perfil, servico_usuarios
from app.services.cliente_ldap import ErroLdapIndisponivel, ParametrosDiretorio

registro_log = logging.getLogger(__name__)

# Hash fixo usado quando o usuário não existe, para que o tempo de resposta
# não revele quais logins são válidos.
_HASH_FICTICIO = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO5xX0b3XcLrE7j0mdQh6sQ0h0e9w5mSa"


class ServicoAutenticacao:
    """Autentica login e senha e emite o token de acesso."""
    def __init__(self, sessao: Session) -> None:
        self.sessao = sessao

    def autenticar(self, login: str, senha: str) -> Usuario | None:
        """Tenta o LDAP e, se não der certo, a conta local. Devolve o usuário ou None."""
        usuario = self._autenticar_ldap(login, senha)
        if usuario is not None:
            return usuario
        return self._autenticar_local(login, senha)

    def _autenticar_ldap(self, login: str, senha: str) -> Usuario | None:
        """Confere a senha no AD; em caso de sucesso, cria ou atualiza a conta de representação no portal."""
        diretorio = servico_ldap.obter_diretorio_ativo(self.sessao)
        if diretorio is None:
            return None
        try:
            identidade = cliente_ldap.autenticar(ParametrosDiretorio.do_modelo(diretorio), login, senha)
        # AD fora do ar não impede o login: a tentativa segue para a conta local
        except ErroLdapIndisponivel as erro:
            registro_log.warning("LDAP indisponível no login (%s); tentando conta local.", erro)
            return None
        if identidade is None:
            return None
        # Só entra quem continuar ativo depois de aplicados os dados do AD
        usuario = servico_usuarios.registrar_login_ldap(self.sessao, diretorio, identidade)
        return usuario if usuario is not None and usuario.ativo else None

    def _autenticar_local(self, login: str, senha: str) -> Usuario | None:
        """Confere a senha contra o hash bcrypt gravado no banco."""
        usuario = servico_usuarios.buscar_por_login(self.sessao, login)
        if usuario is None or not usuario.hash_senha:
            # Mesmo sem usuário, faz uma verificação falsa para gastar o mesmo tempo (evita descobrir logins válidos)
            verificar_senha(senha, _HASH_FICTICIO)
            return None
        if not usuario.ativo or not verificar_senha(senha, usuario.hash_senha):
            return None
        # Registra o último acesso (exibido na administração de usuários)
        usuario.ultimo_acesso_em = agora_utc()
        self.sessao.commit()
        return usuario

    def emitir_token(self, usuario: Usuario) -> RespostaToken:
        """Gera o JWT com o id do usuário e devolve a resposta completa do login."""
        token, expira_em = criar_token_acesso(str(usuario.id), {"login": usuario.login, "papeis": usuario.papeis})
        return RespostaToken(
            token_acesso=token,
            tipo_token="bearer",
            expira_em_segundos=obter_configuracao().minutos_expiracao_token * 60,
            expira_em=expira_em,
            usuario=para_usuario_sessao(usuario),
        )


def para_usuario_sessao(usuario: Usuario) -> UsuarioSessao:
    """Converte o usuário do banco no formato de sessão usado pelo frontend."""
    return UsuarioSessao(
        id=usuario.id,
        login=usuario.login,
        nome_completo=usuario.nome_completo or usuario.login,
        papeis=usuario.papeis,
        origem=usuario.origem,
        perfil_restrito=servico_perfil.perfil_restrito(usuario),
        campos_pendentes=servico_perfil.campos_pendentes(usuario),
        revisao_obrigatoria=servico_perfil.revisao_vencida(usuario),
    )
