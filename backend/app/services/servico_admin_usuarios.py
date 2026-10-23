# Criado por José Eduardo Santana Martins
# Este arquivo serve para administrar usuários e o próprio perfil.
"""Administração de usuários e manutenção do próprio perfil.

Regras de proteção: a conta administrativa principal (definida no .env) não pode ser
desativada, excluída nem perder o SuperRoot, e ninguém pode desativar ou excluir a própria conta.
"""

from sqlalchemy import Select, String, and_, case, func, literal, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.configuracao import obter_configuracao
from app.core.seguranca import gerar_hash_senha
from app.models.diretorio_ldap import DiretorioLdap
from app.models.rh import DadosFuncionais
from app.models.rh_cargos import Cargo, Ocupacao, TipoCargo
from app.models.rh_pre_cadastro import PreCadastro
from app.models.setor import MembroSetor, Setor
from app.models.usuario import OrigemUsuario, Usuario
from app.schemas.usuarios import AlteracaoUsuario, CriacaoUsuario, DadosPerfil, DetalheUsuario, OpcaoUsuario, PerfilLeitura
from app.services import servico_perfil
from app.services.servico_perfil import validar_localizacao
from app.services.servico_auditoria import auditar
from app.services.servico_usuarios import buscar_por_login

# Campos do perfil institucional copiados entre o schema e o modelo
CAMPOS_PERFIL = ("nome_completo", "email", "ramal", "celular", "linkedin", "cargo", "departamento", "andar", "predio", "data_nascimento", "gestor_id")
# Campos pesquisados pela busca livre da listagem de usuários
CAMPOS_BUSCA = ("login", "nome_completo", "email", "ramal", "celular", "cargo", "departamento", "predio")


class UsuarioNaoEncontrado(Exception):
    """O usuário pedido não existe (vira 404)."""
    pass


class ErroRegraUsuario(Exception):
    """Violação de regra de negócio (mensagem pronta para o usuário)."""

    def __init__(self, mensagem: str, conflito: bool = False) -> None:
        super().__init__(mensagem)
        self.conflito = conflito


def eh_admin_principal(usuario: Usuario) -> bool:
    """Indica se é a conta administrativa principal (login definido em `LOGIN_ADMIN`)."""
    return usuario.login.lower() == obter_configuracao().login_admin.lower()


def _aplicar_busca(consulta: Select, busca: str | None, *, dados_rh: bool = False, dados_ficha: bool = False, completa: bool = True) -> Select:
    """Acrescenta à consulta o filtro de busca livre.

    O texto se divide em palavras e **todas** precisam aparecer (cada uma em qualquer campo): "assessor silva" acha quem é Assessor e se chama Silva. Procura nos
    campos do perfil (`CAMPOS_BUSCA`), no cargo ocupado (denominação, tipo, nível), no setor e na hierarquia (setor, setor pai e avô: a **chefia imediata e mediata**,
    pelo líder de cada um, além do superior do cadastro) e, só com `dados_rh` (quem tem acesso ao módulo RH), nos dados funcionais (RS/PV e RG/CIN).

    `completa=False` (seletores de pessoa, como o das notificações) procura só na própria pessoa: perfil, cargo e setor. Sem isso, digitar o nome de um chefe traria os liderados
    dele e o próprio chefe sumiria do limite de resultados.
    """
    if not (busca and busca.strip()):
        return consulta
    for palavra in busca.strip().lower().split():
        termo = f"%{palavra}%"
        condicoes = [func.lower(func.coalesce(getattr(Usuario, c), "")).like(termo) for c in CAMPOS_BUSCA]
        # Cargo vigente: denominação, tipo e classificação ("FCESP 2.16"), e o setor do cargo
        setor, pai, avo = aliased(Setor), aliased(Setor), aliased(Setor)
        cargo_setor = (
            select(Ocupacao.usuario_id).join(Cargo, Cargo.id == Ocupacao.cargo_id).join(TipoCargo, TipoCargo.id == Cargo.tipo_id).join(setor, setor.id == Cargo.setor_id)
            .where(Ocupacao.fim.is_(None))
        )
        classificacao = func.lower(TipoCargo.codigo + " " + func.coalesce(func.cast(Cargo.grupo, String), "") + "." + func.coalesce(func.cast(Cargo.nivel, String), ""))
        condicoes.append(Usuario.id.in_(cargo_setor.where(or_(
            func.lower(Cargo.denominacao).like(termo), classificacao.like(termo), func.lower(setor.nome).like(termo), func.lower(func.coalesce(setor.sigla, "")).like(termo)))))
        if not completa:
            consulta = consulta.where(or_(*condicoes))
            continue
        # Chefia: líder do setor do cargo (nível 0), do setor pai (1) e do avô (2), menos a própria pessoa
        for profundidade in range(3):
            setores = [aliased(Setor) for _ in range(profundidade + 1)]
            chefe = aliased(Usuario)
            consulta_chefia = select(Ocupacao.usuario_id).join(Cargo, Cargo.id == Ocupacao.cargo_id).join(setores[0], setores[0].id == Cargo.setor_id)
            for acima, abaixo in zip(setores, setores[1:]):
                consulta_chefia = consulta_chefia.join(abaixo, abaixo.id == acima.setor_pai_id)
            consulta_chefia = consulta_chefia.join(chefe, chefe.id == setores[-1].lider_id).where(
                Ocupacao.fim.is_(None), chefe.id != Ocupacao.usuario_id,
                or_(func.lower(func.coalesce(chefe.nome_completo, "")).like(termo), func.lower(chefe.login).like(termo)))
            condicoes.append(Usuario.id.in_(consulta_chefia))
        superior = aliased(Usuario)
        condicoes.append(Usuario.gestor_id.in_(select(superior.id).where(or_(func.lower(func.coalesce(superior.nome_completo, "")).like(termo), func.lower(superior.login).like(termo)))))
        # Bio: só entra na busca quando a pessoa liberou
        condicoes.append(and_(Usuario.bio_visivel.is_(True), func.lower(func.coalesce(Usuario.bio_texto, "")).like(termo)))
        if dados_rh:
            condicoes.append(Usuario.id.in_(select(DadosFuncionais.usuario_id).where(or_(
                func.lower(func.coalesce(DadosFuncionais.rs_pv, "")).like(termo), func.lower(func.coalesce(DadosFuncionais.rg_cin, "")).like(termo)))))
        if dados_ficha:
            # Ficha de pré-cadastro (dados pessoais sensíveis): só para o RH com controle total
            colunas = (PreCadastro.nome_social, PreCadastro.nome_mae, PreCadastro.nome_pai, PreCadastro.cpf, PreCadastro.rg_numero, PreCadastro.cin, PreCadastro.pis_pasep,
                       PreCadastro.email_pessoal, PreCadastro.celular, PreCadastro.cidade, PreCadastro.bairro, PreCadastro.vinculo_tipo, PreCadastro.orgao_origem,
                       PreCadastro.cargo_origem, PreCadastro.rs_pv)
            condicoes.append(Usuario.id.in_(select(PreCadastro.usuario_id).where(PreCadastro.usuario_id.is_not(None), or_(*[func.lower(func.coalesce(c, "")).like(termo) for c in colunas]))))
        consulta = consulta.where(or_(*condicoes))
    return consulta


def _proprio_primeiro(busca: str | None):
    """Ordem da lista com busca: quem tem **o nome ou o login** pesquisado (todas as palavras) vem antes de quem só casou por cargo, setor ou chefia."""
    palavras = (busca or "").strip().lower().split()
    if not palavras:
        return literal(0)
    proprio = and_(*[or_(func.lower(func.coalesce(Usuario.nome_completo, "")).like(f"%{p}%"), func.lower(Usuario.login).like(f"%{p}%")) for p in palavras])
    return case((proprio, 0), else_=1)


def listar_usuarios(
    sessao: Session, busca: str | None, situacao: str, origem: str | None, pagina: int, tamanho_pagina: int, *, dados_rh: bool = False, dados_ficha: bool = False
) -> tuple[list[DetalheUsuario], int]:
    """Lista paginada de usuários e o total (para a paginação da tela). `dados_rh` inclui os dados funcionais na busca (só para o RH)."""
    consulta = _aplicar_busca(select(Usuario), busca, dados_rh=dados_rh, dados_ficha=dados_ficha)
    if situacao == "ativos":
        consulta = consulta.where(Usuario.ativo.is_(True))
    elif situacao == "inativos":
        consulta = consulta.where(Usuario.ativo.is_(False))
    if origem:
        consulta = consulta.where(Usuario.origem == origem)
    # Conta o total antes da paginação, usando a consulta filtrada como subconsulta
    total = sessao.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    usuarios = list(
        sessao.scalars(
            # Ordena pelo nome (ou pelo login, quando o nome está vazio) e recorta a página pedida
            consulta.order_by(_proprio_primeiro(busca), func.lower(func.coalesce(func.nullif(Usuario.nome_completo, ""), Usuario.login)))
            .offset((pagina - 1) * tamanho_pagina)
            .limit(tamanho_pagina)
        )
    )
    return para_detalhes(sessao, usuarios), total


def opcoes(sessao: Session, busca: str | None, limite: int = 20, incluir_inativos: bool = False) -> list[OpcaoUsuario]:
    """Busca curta para campos de seleção (sem paginação, com limite)."""
    consulta = _aplicar_busca(select(Usuario), busca, completa=False)
    if not incluir_inativos:
        consulta = consulta.where(Usuario.ativo.is_(True))
    usuarios = sessao.scalars(consulta.order_by(func.lower(Usuario.nome_completo), Usuario.login).limit(limite))
    return [para_opcao(u) for u in usuarios]


def para_opcao(u: Usuario) -> OpcaoUsuario:
    """Converte o usuário na forma reduzida usada nos seletores."""
    return OpcaoUsuario(id=u.id, login=u.login, nome_completo=u.nome_completo or u.login, cargo=u.cargo, ativo=u.ativo)


def obter_usuario(sessao: Session, usuario_id: int) -> Usuario:
    """Usuário pelo id, ou `UsuarioNaoEncontrado`."""
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioNaoEncontrado()
    return usuario


def para_detalhes(sessao: Session, usuarios: list[Usuario]) -> list[DetalheUsuario]:
    """Monta o detalhe de vários usuários de uma vez, com poucas consultas.

    Em vez de consultar gestor, diretório e setores usuário por usuário (N consultas), busca
    tudo de uma vez para a lista inteira e monta dicionários de apoio.
    """
    if not usuarios:
        return []
    ids = [u.id for u in usuarios]
    # Nomes dos gestores: {id: nome}
    ids_gestores = {u.gestor_id for u in usuarios if u.gestor_id}
    gestores = (
        {g.id: g.nome_completo or g.login for g in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids_gestores)))}
        if ids_gestores
        else {}
    )
    # Nomes dos diretórios LDAP: {id: nome}
    ids_diretorios = {u.diretorio_id for u in usuarios if u.diretorio_id}
    diretorios = (
        {d.id: d.nome for d in sessao.scalars(select(DiretorioLdap).where(DiretorioLdap.id.in_(ids_diretorios)))}
        if ids_diretorios
        else {}
    )
    # Setores de cada usuário: {usuario_id: [nomes]}
    setores: dict[int, list[str]] = {}
    for usuario_id, nome in sessao.execute(
        select(MembroSetor.usuario_id, Setor.nome)
        .join(Setor, Setor.id == MembroSetor.setor_id)
        .where(MembroSetor.usuario_id.in_(ids))
        .order_by(Setor.nome)
    ):
        setores.setdefault(usuario_id, []).append(nome)
    return [
        DetalheUsuario(
            id=u.id,
            login=u.login,
            ativo=u.ativo,
            superusuario=u.superusuario,
            conta_integracao=u.conta_integracao,
            origem=u.origem,
            possui_senha_local=bool(u.hash_senha),
            diretorio_nome=diretorios.get(u.diretorio_id) if u.diretorio_id else None,
            id_externo=u.id_externo,
            perfil=PerfilLeitura(
                **{c: getattr(u, c) for c in CAMPOS_PERFIL},
                gestor_nome=gestores.get(u.gestor_id) if u.gestor_id else None,
                perfil_revisado_em=u.perfil_revisado_em,
            ),
            perfil_completo=not servico_perfil.campos_pendentes(u),
            revisao_obrigatoria=servico_perfil.revisao_vencida(u),
            setores=setores.get(u.id, []),
            ultimo_acesso_em=u.ultimo_acesso_em,
            criado_em=u.criado_em,
            atualizado_em=u.atualizado_em,
        )
        for u in usuarios
    ]


def para_detalhe(sessao: Session, usuario: Usuario) -> DetalheUsuario:
    """Detalhe de um único usuário (reaproveita a versão em lote)."""
    return para_detalhes(sessao, [usuario])[0]


def _aplicar_perfil(sessao: Session, usuario: Usuario, perfil: DadosPerfil) -> None:
    """Valida a localização e o gestor e copia os campos do perfil para o usuário."""
    erro_local = validar_localizacao(perfil.andar, perfil.predio, usuario.andar or "", usuario.predio or "")
    if erro_local:
        raise ErroRegraUsuario(erro_local)
    if perfil.gestor_id is not None:
        if perfil.gestor_id == usuario.id:
            raise ErroRegraUsuario("O usuário não pode ser gestor de si mesmo.")
        if sessao.get(Usuario, perfil.gestor_id) is None:
            raise ErroRegraUsuario("Gestor imediato inválido.")
        # Sem ciclos na hierarquia (A superior de B e B superior de A)
        from app.services.rh.servico_cadastro import ErroCadastro, validar_superior

        try:
            validar_superior(sessao, usuario.id, perfil.gestor_id, False)
        except ErroCadastro as erro:
            raise ErroRegraUsuario(str(erro)) from erro
    # O Departamento define o setor do usuário (participação usada pela ACL); o import é local por causa do ciclo entre os módulos
    from app.services import servico_setores

    servico_setores.sincronizar_departamento(sessao, usuario.id, usuario.departamento, perfil.departamento)
    for campo in CAMPOS_PERFIL:
        setattr(usuario, campo, getattr(perfil, campo))


def criar_conta_local(sessao: Session, dados: CriacaoUsuario, autor: str) -> Usuario:
    """Cria uma conta local com senha em hash bcrypt."""
    if buscar_por_login(sessao, dados.login) is not None:
        raise ErroRegraUsuario("Este login já está cadastrado.", conflito=True)
    usuario = Usuario(
        login=dados.login.strip(),
        hash_senha=gerar_hash_senha(dados.senha),
        origem=OrigemUsuario.LOCAL,
        ativo=dados.ativo,
        superusuario=dados.superusuario,
        conta_integracao=dados.conta_integracao,
    )
    sessao.add(usuario)
    # flush para obter o id antes de validar o gestor (que não pode ser o próprio usuário)
    sessao.flush()
    _aplicar_perfil(sessao, usuario, dados.perfil)
    auditar(sessao, autor, "usuario.criar", usuario.login, f"id={usuario.id} superusuario={usuario.superusuario}")
    sessao.commit()
    return usuario


def alterar_usuario(sessao: Session, usuario_id: int, dados: AlteracaoUsuario, autor: Usuario) -> Usuario:
    """Altera situação, papel, perfil e (opcionalmente) a senha do usuário."""
    usuario = obter_usuario(sessao, usuario_id)
    # Regras de proteção contra perder o acesso administrativo
    if eh_admin_principal(usuario) and (not dados.ativo or not dados.superusuario):
        raise ErroRegraUsuario("A conta administrativa principal não pode ser desativada nem perder o papel SuperRoot.")
    # Só perde o papel quem o tem: quem não é SuperRoot (ex.: CGP) pode editar o próprio cadastro normalmente
    if usuario.id == autor.id and (not dados.ativo or (usuario.superusuario and not dados.superusuario)):
        raise ErroRegraUsuario("Você não pode desativar a própria conta nem remover o próprio papel SuperRoot.")
    # Lista do que mudou, para a linha de auditoria
    alteracoes = []
    if usuario.ativo != dados.ativo:
        alteracoes.append(f"ativo={dados.ativo}")
    if usuario.superusuario != dados.superusuario:
        alteracoes.append(f"superusuario={dados.superusuario}")
    if dados.conta_integracao is not None and dados.conta_integracao != usuario.conta_integracao:
        if not autor.superusuario:
            raise ErroRegraUsuario("Só o SuperRoot define uma conta como de integração.")
        alteracoes.append(f"conta_integracao={dados.conta_integracao}")
        usuario.conta_integracao = dados.conta_integracao
    usuario.ativo = dados.ativo
    usuario.superusuario = dados.superusuario
    _aplicar_perfil(sessao, usuario, dados.perfil)
    if dados.senha:
        if eh_admin_principal(usuario):
            raise ErroRegraUsuario("A senha da conta administrativa principal é definida no .env (HASH_SENHA_ADMIN).")
        usuario.hash_senha = gerar_hash_senha(dados.senha)
        if usuario.origem == OrigemUsuario.LDAP:
            usuario.origem = OrigemUsuario.LOCAL_LDAP  # conta corporativa ganha senha local de contingência
        alteracoes.append("senha")
    auditar(sessao, autor.login, "usuario.alterar", usuario.login, ", ".join(alteracoes) or None)
    sessao.commit()
    return usuario


def excluir_usuario(sessao: Session, usuario_id: int, autor: Usuario) -> None:
    """Exclui o usuário, respeitando as regras de proteção."""
    usuario = obter_usuario(sessao, usuario_id)
    if eh_admin_principal(usuario):
        raise ErroRegraUsuario("A conta administrativa principal não pode ser excluída.")
    if usuario.id == autor.id:
        raise ErroRegraUsuario("Você não pode excluir a própria conta.")
    auditar(sessao, autor.login, "usuario.excluir", usuario.login, f"id={usuario.id} origem={usuario.origem}")
    sessao.delete(usuario)
    sessao.commit()


def revisar_proprio_perfil(sessao: Session, usuario: Usuario, perfil: DadosPerfil) -> Usuario:
    """Confirma o próprio perfil no mês. Usuário comum: alterações ficam pendentes de validação da CGP (Módulo RH)."""
    from app.services.rh.servico_cadastro import ErroCadastro, revisar_perfil

    try:
        return revisar_perfil(sessao, usuario, perfil)
    except ErroCadastro as erro:
        raise ErroRegraUsuario(str(erro)) from erro
