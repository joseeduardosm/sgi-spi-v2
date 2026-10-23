# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras da ficha de pré-cadastro do RH: gravação com validação, login proposto único (SGI + AD) e vínculo automático com a conta.
"""Pré-cadastro (Fase 2 do RH).

- A ficha guarda dados pessoais, documentos, contato, endereço, vínculo, formações e experiências.
- O **login proposto** precisa ser único: não pode existir como usuário, em outra ficha nem no AD. Ele vai para a TI no chamado de criação da conta.
- Quando a conta aparece (sincronização do AD ou primeiro login), `vincular_conta` liga a ficha ao usuário, copia o que o usuário ainda não tem
  (data de nascimento, celular, RS/PV, RG/CIN) e registra o fato no histórico funcional.
"""

import re
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.rh import DadosFuncionais
from app.models.rh_cargos import Cargo
from app.models.rh_pre_cadastro import FichaExperiencia, FichaFormacao, PreCadastro
from app.models.usuario import Usuario
from app.schemas.rh_pre_cadastro import GravacaoFicha, GravacaoMinhaFicha, LeituraFicha, LoginDisponivel, ResumoFicha
from app.services import servico_ldap
from app.services.rh import servico_historico
from app.services.servico_auditoria import auditar

FORMATO_LOGIN = re.compile(r"^[a-z][a-z0-9._-]{2,29}$")


class FichaNaoEncontrada(Exception):
    """Ficha inexistente (vira 404)."""


class ErroFicha(Exception):
    """Regra da ficha violada; `conflito` indica 409 (duplicidade) em vez de 400."""

    def __init__(self, mensagem: str, conflito: bool = False):
        super().__init__(mensagem)
        self.conflito = conflito


# --- Validações de documentos ---------------------------------------------------------------------

def so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def cpf_valido(cpf: str) -> bool:
    """Confere os dois dígitos verificadores (rejeita sequências iguais)."""
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        if int(cpf[tamanho]) != (soma * 10 % 11) % 10:
            return False
    return True


def pis_valido(pis: str) -> bool:
    """PIS/PASEP: 11 dígitos, dígito verificador com pesos 3,2,9,8,7,6,5,4,3,2."""
    if len(pis) != 11 or len(set(pis)) == 1:
        return False
    soma = sum(int(d) * p for d, p in zip(pis[:10], (3, 2, 9, 8, 7, 6, 5, 4, 3, 2)))
    resto = 11 - soma % 11
    return int(pis[10]) == (0 if resto >= 10 else resto)


def normalizar_login(login: str | None) -> str | None:
    texto = (login or "").strip().lower()
    return texto or None


# --- Login proposto ----------------------------------------------------------------------------------

def login_disponivel(sessao: Session, login: str, ignorar_ficha_id: int | None = None) -> LoginDisponivel:
    """Confere o login no SGI (usuários e outras fichas) e no AD (só leitura). Existir em qualquer um deles o torna indisponível."""
    texto = normalizar_login(login) or ""
    if not FORMATO_LOGIN.match(texto):
        return LoginDisponivel(login=texto, disponivel=False, verificado_no_ad=False, motivo="formato",
                               detalhe="Use de 3 a 30 caracteres: letras minúsculas, números, ponto, hífen ou sublinhado, começando por letra.")
    if sessao.scalar(select(Usuario.id).where(func.lower(Usuario.login) == texto)) is not None:
        return LoginDisponivel(login=texto, disponivel=False, verificado_no_ad=False, motivo="usuario", detalhe="Já existe um usuário com esse login no SGI.")
    consulta = select(PreCadastro.nome_completo).where(func.lower(PreCadastro.login_proposto) == texto, PreCadastro.status != "cancelado")
    if ignorar_ficha_id is not None:
        consulta = consulta.where(PreCadastro.id != ignorar_ficha_id)
    outro = sessao.scalar(consulta)
    if outro is not None:
        return LoginDisponivel(login=texto, disponivel=False, verificado_no_ad=False, motivo="ficha", detalhe=f"Já é o login proposto na ficha de {outro}.")
    situacao, mensagem = servico_ldap.situacao_do_login(sessao, texto)
    if situacao == "encontrado":
        return LoginDisponivel(login=texto, disponivel=False, verificado_no_ad=True, motivo="ad", detalhe=mensagem)
    if situacao == "livre":
        return LoginDisponivel(login=texto, disponivel=True, verificado_no_ad=True, motivo="livre", detalhe=mensagem)
    # Sem AD configurado ou fora do ar: livre no SGI, mas o RH precisa saber que o AD não foi conferido
    return LoginDisponivel(login=texto, disponivel=True, verificado_no_ad=False, motivo="ad_indisponivel", detalhe=mensagem)


# --- Gravação -----------------------------------------------------------------------------------------

def _normalizar(dados: dict) -> dict:
    """Limpa e valida os campos; devolve o dicionário pronto para gravar."""
    for campo in ("naturalidade_uf", "rg_uf", "ctps_uf", "uf"):
        dados[campo] = (dados.get(campo) or "").strip().upper()
    for campo in ("cpf", "pis_pasep", "cep"):
        dados[campo] = so_digitos(dados.get(campo, ""))
    if dados["cpf"] and not cpf_valido(dados["cpf"]):
        raise ErroFicha("CPF inválido.")
    if dados["pis_pasep"] and not pis_valido(dados["pis_pasep"]):
        raise ErroFicha("PIS/PASEP inválido.")
    if dados["cep"] and len(dados["cep"]) != 8:
        raise ErroFicha("CEP deve ter 8 dígitos.")
    for campo in ("naturalidade_uf", "rg_uf", "ctps_uf", "uf"):
        if dados[campo] and len(dados[campo]) != 2:
            raise ErroFicha("UF deve ter 2 letras.")
    if dados.get("data_nascimento") and dados["data_nascimento"] >= date.today():
        raise ErroFicha("A data de nascimento deve ser anterior a hoje.")
    return dados


def _aplicar(sessao: Session, ficha: PreCadastro, dados: GravacaoFicha | GravacaoMinhaFicha, *, legado: bool = False) -> None:
    """`legado`: ficha da própria pessoa (sem login proposto nem status: continua `vinculado`)."""
    valores = dados.model_dump(exclude={"formacoes", "experiencias", "login_proposto", "status", "cargo_id", "rs_pv"} if legado else {"formacoes", "experiencias", "login_proposto", "status"})
    valores = _normalizar(valores)
    if valores.get("cpf"):
        dona = sessao.scalar(select(PreCadastro.nome_completo).where(PreCadastro.cpf == valores["cpf"], PreCadastro.status != "cancelado", PreCadastro.id != (ficha.id or 0)))
        if dona is not None:
            raise ErroFicha(f"Este CPF já está na ficha de {dona}.", conflito=True)
    if valores.get("cargo_id") is not None and sessao.get(Cargo, valores["cargo_id"]) is None:
        raise ErroFicha("Cargo pretendido não encontrado.")
    for campo, valor in valores.items():
        setattr(ficha, campo, valor)
    if legado:
        ficha.formacoes = [FichaFormacao(**f.model_dump()) for f in dados.formacoes]
        ficha.experiencias = [FichaExperiencia(**e.model_dump()) for e in dados.experiencias]
        return
    login = normalizar_login(dados.login_proposto)
    if login:
        situacao = login_disponivel(sessao, login, ficha.id)
        if not situacao.disponivel:
            raise ErroFicha(f"Login proposto indisponível: {situacao.detalhe}", conflito=situacao.motivo != "formato")
    if dados.status == "aguardando_conta" and not login:
        raise ErroFicha("Informe o login proposto para deixar a ficha aguardando a criação da conta.")
    ficha.login_proposto = login
    ficha.status = dados.status
    ficha.formacoes = [FichaFormacao(**f.model_dump()) for f in dados.formacoes]
    ficha.experiencias = [FichaExperiencia(**e.model_dump()) for e in dados.experiencias]


def _por_id(sessao: Session, ficha_id: int) -> PreCadastro:
    ficha = sessao.get(PreCadastro, ficha_id)
    if ficha is None:
        raise FichaNaoEncontrada()
    return ficha


def leitura(sessao: Session, ficha: PreCadastro) -> LeituraFicha:
    cargo = sessao.get(Cargo, ficha.cargo_id) if ficha.cargo_id else None
    usuario = sessao.get(Usuario, ficha.usuario_id) if ficha.usuario_id else None
    base = LeituraFicha.model_validate(ficha, from_attributes=True)
    base.cargo_rotulo = cargo.rotulo if cargo else None
    base.usuario_nome = (usuario.nome_completo or usuario.login) if usuario else None
    return base


def criar(sessao: Session, dados: GravacaoFicha, autor: Usuario, *, commit: bool = True) -> LeituraFicha:
    """Cria a ficha. `commit=False` deixa a transação aberta (a importação em lote grava tudo ou nada)."""
    ficha = PreCadastro(nome_completo=dados.nome_completo.strip(), criado_por_id=autor.id)
    _aplicar(sessao, ficha, dados)
    sessao.add(ficha)
    sessao.flush()
    auditar(sessao, autor.login, "rh.pre_cadastro.criar", ficha.nome_completo, autor_id=autor.id, dados={"ficha_id": ficha.id})
    if commit:
        sessao.commit()
    return leitura(sessao, ficha)


def alterar(sessao: Session, ficha_id: int, dados: GravacaoFicha, autor: Usuario) -> LeituraFicha:
    ficha = _por_id(sessao, ficha_id)
    legado = ficha.status == "vinculado" and not ficha.login_proposto
    if ficha.status == "cancelado" or (ficha.status == "vinculado" and not legado):
        raise ErroFicha("Ficha vinculada a uma conta ou cancelada não pode mais ser alterada aqui.", conflito=True)
    # O RH pode corrigir a ficha que a própria pessoa preencheu (legados); ela segue vinculada e a validação continua pendente
    _aplicar(sessao, ficha, dados, legado=legado)
    auditar(sessao, autor.login, "rh.pre_cadastro.alterar", ficha.nome_completo, autor_id=autor.id, dados={"ficha_id": ficha.id})
    sessao.commit()
    return leitura(sessao, ficha)


def obter(sessao: Session, ficha_id: int) -> LeituraFicha:
    return leitura(sessao, _por_id(sessao, ficha_id))


def cancelar(sessao: Session, ficha_id: int, autor: Usuario) -> None:
    """Cancela a ficha (libera o login proposto). Ficha já vinculada a uma conta não se cancela."""
    ficha = _por_id(sessao, ficha_id)
    if ficha.status == "vinculado":
        raise ErroFicha("A ficha já está vinculada a uma conta.", conflito=True)
    ficha.status = "cancelado"
    auditar(sessao, autor.login, "rh.pre_cadastro.cancelar", ficha.nome_completo, autor_id=autor.id, dados={"ficha_id": ficha.id})
    sessao.commit()


def listar(sessao: Session, busca: str | None = None, status: str | None = None, pendentes_de_validacao: bool = False) -> list[ResumoFicha]:
    """Fichas mais recentes primeiro; a busca procura por todas as palavras em nome, login, CPF, RS/PV, documentos e cargo de origem."""
    consulta = select(PreCadastro).order_by(PreCadastro.atualizado_em.desc())
    if status:
        consulta = consulta.where(PreCadastro.status == status)
    if pendentes_de_validacao:
        consulta = consulta.where(PreCadastro.enviada_em.is_not(None), PreCadastro.validado_em.is_(None), PreCadastro.status == "vinculado")
    for palavra in (busca or "").lower().split():
        termo = f"%{palavra}%"
        colunas = (PreCadastro.nome_completo, PreCadastro.nome_social, PreCadastro.login_proposto, PreCadastro.cpf, PreCadastro.rg_numero, PreCadastro.cin,
                   PreCadastro.rs_pv, PreCadastro.pis_pasep, PreCadastro.email_pessoal, PreCadastro.orgao_origem, PreCadastro.cargo_origem, PreCadastro.vinculo_tipo)
        consulta = consulta.where(or_(*[func.lower(func.coalesce(c, "")).like(termo) for c in colunas]))
    rotulos = {c.id: c.rotulo for c in sessao.scalars(select(Cargo))}
    return [
        ResumoFicha(id=f.id, nome_completo=f.nome_completo, status=f.status, login_proposto=f.login_proposto, usuario_id=f.usuario_id,
                    cargo_rotulo=rotulos.get(f.cargo_id) if f.cargo_id else None, inicio_previsto=f.inicio_previsto, enviada_em=f.enviada_em, validado_em=f.validado_em, atualizado_em=f.atualizado_em)
        for f in sessao.scalars(consulta)
    ]


# --- Vínculo com a conta -----------------------------------------------------------------------------

def vincular_conta(sessao: Session, usuario: Usuario) -> PreCadastro | None:
    """Liga a ficha cujo login proposto é o do usuário recém-criado (sem commit). Copia o que o usuário ainda não tem e registra no histórico."""
    if usuario.id is None:
        sessao.flush()
    ficha = sessao.scalar(select(PreCadastro).where(func.lower(PreCadastro.login_proposto) == usuario.login.lower(), PreCadastro.status.in_(("rascunho", "aguardando_conta"))))
    if ficha is None:
        return None
    ficha.usuario_id = usuario.id
    ficha.status = "vinculado"
    ficha.vinculado_em = agora_utc()
    if not usuario.data_nascimento and ficha.data_nascimento:
        usuario.data_nascimento = ficha.data_nascimento
    if not usuario.celular and ficha.celular:
        usuario.celular = ficha.celular
    funcionais = sessao.get(DadosFuncionais, usuario.id)
    if funcionais is None and (ficha.rs_pv or ficha.rg_numero or ficha.cin):
        funcionais = DadosFuncionais(usuario_id=usuario.id)
        sessao.add(funcionais)
    if funcionais is not None:
        funcionais.rs_pv = funcionais.rs_pv or ficha.rs_pv or None
        funcionais.rg_cin = funcionais.rg_cin or ficha.cin or ficha.rg_numero or None
    # Foto da admissão (a mesma enviada ao GLPI): a intranet já mostra a pessoa desde o primeiro acesso
    from app.services.rh import servico_admissao

    servico_admissao.aplicar_foto_pela_ficha(sessao, ficha.id, usuario)
    servico_historico.registrar(
        sessao, usuario.id, "cadastro", "Conta criada e vinculada à ficha de pré-cadastro", f"Login {usuario.login}.", None,
        origem=("pre_cadastro", ficha.id), autor_nome="Sistema", dados={"ficha_id": ficha.id},
    )
    return ficha


# --- Ficha dos legados (a própria pessoa preenche; o RH valida) ----------------------------------------------------

def _ficha_do_usuario(sessao: Session, usuario: Usuario) -> PreCadastro | None:
    return sessao.scalar(select(PreCadastro).where(PreCadastro.usuario_id == usuario.id, PreCadastro.status == "vinculado"))


def minha_ficha(sessao: Session, usuario: Usuario) -> LeituraFicha | None:
    ficha = _ficha_do_usuario(sessao, usuario)
    return leitura(sessao, ficha) if ficha else None


def salvar_minha_ficha(sessao: Session, usuario: Usuario, dados: GravacaoMinhaFicha) -> LeituraFicha:
    """A pessoa grava a própria ficha. Cada envio zera a validação: o RH confere de novo. Quem já tem ficha de admissão altera a mesma."""
    ficha = _ficha_do_usuario(sessao, usuario)
    if ficha is None:
        ficha = PreCadastro(nome_completo=dados.nome_completo.strip(), usuario_id=usuario.id, status="vinculado", vinculado_em=agora_utc(), criado_por_id=usuario.id)
        sessao.add(ficha)
    ficha.nome_completo = dados.nome_completo.strip()
    _aplicar(sessao, ficha, dados, legado=True)
    ficha.enviada_em, ficha.validado_em, ficha.validado_por_id = agora_utc(), None, None
    sessao.flush()
    servico_historico.registrar(sessao, usuario.id, "cadastro", "Ficha cadastral enviada para validação do RH", "", usuario, dados={"ficha_id": ficha.id})
    auditar(sessao, usuario.login, "rh.minha_ficha.salvar", ficha.nome_completo, autor_id=usuario.id, dados={"ficha_id": ficha.id})
    sessao.commit()
    return leitura(sessao, ficha)


def validar(sessao: Session, ficha_id: int, autor: Usuario) -> LeituraFicha:
    """O RH confere a ficha enviada pela pessoa e a valida (registra no histórico dela)."""
    ficha = _por_id(sessao, ficha_id)
    if ficha.enviada_em is None:
        raise ErroFicha("A pessoa ainda não enviou a ficha para validação.", conflito=True)
    if ficha.usuario_id is None:
        raise ErroFicha("A ficha ainda não está ligada a uma conta.", conflito=True)
    ficha.validado_em, ficha.validado_por_id = agora_utc(), autor.id
    servico_historico.registrar(sessao, ficha.usuario_id, "cadastro", "Ficha cadastral validada pelo RH", "", autor, dados={"ficha_id": ficha.id}, sigiloso=True)
    auditar(sessao, autor.login, "rh.pre_cadastro.validar", ficha.nome_completo, autor_id=autor.id, dados={"ficha_id": ficha.id})
    sessao.commit()
    return leitura(sessao, ficha)
