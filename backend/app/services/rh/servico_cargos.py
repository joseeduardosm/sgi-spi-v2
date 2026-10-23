# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerir os cargos (vagas por setor), quem os ocupa, a exoneração, o que falta reconciliar e o organograma.
"""Cargos do RH.

- Cada `Cargo` é **uma posição** de um setor. A pessoa que o ocupa passa a fazer parte do setor **pelo cargo** (`MembroSetor`) e os campos legados
  `Usuario.cargo` e `Usuario.departamento` viram espelho (rótulo do cargo e nome do setor), mantidos por aqui.
- `ocupar` encerra a ocupação anterior da pessoa (troca) e `vagar` encerra a vigente (troca, exoneração, dispensa...). Tudo vai para o histórico (`rh_historico`)
  com quem fez e quando.
- `reconciliar` lista quem tem cargo em texto livre sem cargo cadastrado; `vincular_legado` cria o cargo a partir do texto e aloca a pessoa.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import hoje_sao_paulo, agora_utc
from app.models.rh_cargos import MOTIVOS_FIM, Cargo, Ocupacao, TipoCargo
from app.models.setor import MembroSetor, Setor
from app.models.usuario import OrigemUsuario, Usuario
from app.schemas.rh_cargos import (
    GravacaoCargo, GravacaoTipoCargo, LeituraCargo, LeituraTipoCargo, LiderSetor, NoOrganograma, OcupanteCargo, PendenciaCargo,
)
from app.services import servico_diretorio
from app.services.rh import cargo_legado, servico_historico
from app.services.servico_auditoria import auditar

TIPOS_PADRAO = (("CCESP", "Cargo em comissão (CCESP)", 1), ("FCESP", "Função de confiança (FCESP)", 2), ("OUTRO", "Outros", 9))
TIPOS_UNIDADE = ("secretaria", "subsecretaria", "diretoria", "coordenadoria", "servico", "assessoria", "colegiado", "vinculada", "outro")


class ErroRegraCargo(Exception):
    """Regra de cargos violada: 409 quando `conflito`, senão 400."""

    def __init__(self, mensagem: str, conflito: bool = False) -> None:
        super().__init__(mensagem)
        self.conflito = conflito


class CargoNaoEncontrado(Exception):
    """Cargo (ou tipo, setor, pessoa) inexistente (vira 404)."""

    def __init__(self, o_que: str = "Cargo") -> None:
        super().__init__(o_que)
        self.o_que = o_que


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "Sistema"


# --- Tipos ---------------------------------------------------------------------------------------

def garantir_tipos(sessao: Session) -> None:
    """Semeia CCESP, FCESP e OUTRO quando a tabela está vazia (a migração já faz; aqui vale para bancos novos e testes)."""
    if sessao.scalar(select(func.count()).select_from(TipoCargo)):
        return
    for codigo, nome, ordem in TIPOS_PADRAO:
        sessao.add(TipoCargo(codigo=codigo, nome=nome, ordem=ordem, ativo=True))
    sessao.commit()  # as consultas do RH são GET: sem gravar aqui, a semente se perderia


def _tipo(sessao: Session, tipo_id: int) -> TipoCargo:
    tipo = sessao.get(TipoCargo, tipo_id)
    if tipo is None:
        raise CargoNaoEncontrado("Tipo de cargo")
    return tipo


def tipo_por_codigo(sessao: Session, codigo: str) -> TipoCargo:
    garantir_tipos(sessao)
    tipo = sessao.scalar(select(TipoCargo).where(func.upper(TipoCargo.codigo) == codigo.upper()))
    if tipo is None:
        tipo = TipoCargo(codigo=codigo.upper(), nome=codigo.upper(), ordem=50, ativo=True)
        sessao.add(tipo)
        sessao.flush()
    return tipo


def listar_tipos(sessao: Session) -> list[LeituraTipoCargo]:
    garantir_tipos(sessao)
    return [LeituraTipoCargo(id=t.id, codigo=t.codigo, nome=t.nome, ordem=t.ordem, ativo=t.ativo)
            for t in sessao.scalars(select(TipoCargo).order_by(TipoCargo.ordem, TipoCargo.codigo))]


def gravar_tipo(sessao: Session, dados: GravacaoTipoCargo, autor: Usuario, tipo_id: int | None = None) -> list[LeituraTipoCargo]:
    garantir_tipos(sessao)
    codigo = dados.codigo.strip().upper()
    duplicado = sessao.scalar(select(TipoCargo.id).where(func.upper(TipoCargo.codigo) == codigo))
    if duplicado is not None and duplicado != tipo_id:
        raise ErroRegraCargo("Já existe um tipo de cargo com este código.", conflito=True)
    tipo = _tipo(sessao, tipo_id) if tipo_id else TipoCargo()
    tipo.codigo, tipo.nome, tipo.ordem, tipo.ativo = codigo, dados.nome.strip(), dados.ordem, dados.ativo
    sessao.add(tipo)
    auditar(sessao, autor.login, "rh.tipo_cargo.gravar", codigo, autor_id=autor.id)
    sessao.commit()
    return listar_tipos(sessao)


# --- Cargos --------------------------------------------------------------------------------------

def _setor(sessao: Session, setor_id: int) -> Setor:
    setor = sessao.get(Setor, setor_id)
    if setor is None:
        raise CargoNaoEncontrado("Setor")
    return setor


def obter(sessao: Session, cargo_id: int) -> Cargo:
    cargo = sessao.get(Cargo, cargo_id)
    if cargo is None:
        raise CargoNaoEncontrado("Cargo")
    return cargo


def _validar_classificacao(tipo: TipoCargo, grupo: int | None, nivel: int | None) -> None:
    if (grupo is None) != (nivel is None):
        raise ErroRegraCargo("Informe o grupo (1 ou 2) e o nível (1 a 18) juntos, ou deixe os dois vazios.")
    if tipo.codigo in ("CCESP", "FCESP") and nivel is None:
        raise ErroRegraCargo(f"Cargo {tipo.codigo} precisa de grupo e nível (ex.: {tipo.codigo} 2.16).")


def leitura(sessao: Session, cargo: Cargo, setores: dict[int, str] | None = None, usuarios: dict[int, Usuario] | None = None) -> LeituraCargo:
    vigente = cargo.vigente
    ocupante = None
    if vigente is not None:
        u = (usuarios or {}).get(vigente.usuario_id) or sessao.get(Usuario, vigente.usuario_id)
        ocupante = OcupanteCargo(usuario_id=u.id, nome=u.nome_completo or u.login, login=u.login, inicio=vigente.inicio, ato=vigente.ato, tem_foto=bool(u.foto_anexo_id), foto_url=servico_diretorio.foto_url(u))
    nome_setor = (setores or {}).get(cargo.setor_id) or _setor(sessao, cargo.setor_id).nome
    return LeituraCargo(
        id=cargo.id, setor_id=cargo.setor_id, setor_nome=nome_setor, tipo_id=cargo.tipo_id, tipo_codigo=cargo.tipo.codigo, grupo=cargo.grupo, nivel=cargo.nivel,
        denominacao=cargo.denominacao, classificacao=cargo.classificacao, rotulo=cargo.rotulo, ativo=cargo.ativo, ocupante=ocupante)


def listar(
    sessao: Session, *, setor_id: int | None = None, tipo_id: int | None = None, situacao: str | None = None, busca: str | None = None, incluir_inativos: bool = False,
) -> list[LeituraCargo]:
    """Cargos com o ocupante vigente. `situacao` = `vago` ou `ocupado`; `busca` procura na denominação, no setor e no nome do ocupante."""
    garantir_tipos(sessao)
    consulta = select(Cargo)
    if not incluir_inativos:
        consulta = consulta.where(Cargo.ativo.is_(True))
    if setor_id is not None:
        consulta = consulta.where(Cargo.setor_id == setor_id)
    if tipo_id is not None:
        consulta = consulta.where(Cargo.tipo_id == tipo_id)
    cargos = list(sessao.scalars(consulta))
    setores = {s.id: s.nome for s in sessao.scalars(select(Setor))}
    ids_usuarios = {o.usuario_id for c in cargos for o in c.ocupacoes if o.fim is None}
    usuarios = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids_usuarios)))} if ids_usuarios else {}
    itens = [leitura(sessao, c, setores, usuarios) for c in cargos]
    if situacao == "vago":
        itens = [i for i in itens if i.ocupante is None]
    elif situacao == "ocupado":
        itens = [i for i in itens if i.ocupante is not None]
    if busca and busca.strip():
        termo = busca.strip().lower()
        itens = [i for i in itens if termo in " ".join([i.denominacao, i.rotulo, i.setor_nome, i.ocupante.nome if i.ocupante else "", i.ocupante.login if i.ocupante else ""]).lower()]
    return sorted(itens, key=lambda i: (i.setor_nome.lower(), i.tipo_codigo, -(i.grupo or 0), -(i.nivel or 0), i.denominacao.lower(), i.id))


def criar(sessao: Session, dados: GravacaoCargo, autor: Usuario) -> list[LeituraCargo]:
    """Cria `quantidade` vagas iguais no setor."""
    setor, tipo = _setor(sessao, dados.setor_id), _tipo(sessao, dados.tipo_id)
    _validar_classificacao(tipo, dados.grupo, dados.nivel)
    criados = []
    for _ in range(dados.quantidade):
        cargo = Cargo(setor_id=setor.id, tipo_id=tipo.id, grupo=dados.grupo, nivel=dados.nivel, denominacao=dados.denominacao.strip(), ativo=dados.ativo)
        sessao.add(cargo)
        criados.append(cargo)
    sessao.flush()
    auditar(sessao, autor.login, "rh.cargo.criar", f"{dados.denominacao.strip()} ({setor.nome})", autor_id=autor.id, dados={"quantidade": dados.quantidade})
    sessao.commit()
    return [leitura(sessao, c) for c in criados]


def alterar(sessao: Session, cargo_id: int, dados: GravacaoCargo, autor: Usuario) -> LeituraCargo:
    cargo = obter(sessao, cargo_id)
    setor, tipo = _setor(sessao, dados.setor_id), _tipo(sessao, dados.tipo_id)
    _validar_classificacao(tipo, dados.grupo, dados.nivel)
    vigente = cargo.vigente
    if vigente is not None and setor.id != cargo.setor_id:
        raise ErroRegraCargo("O cargo está ocupado: vague-o antes de mudá-lo de setor.", conflito=True)
    if not dados.ativo and vigente is not None:
        raise ErroRegraCargo("O cargo está ocupado: vague-o antes de desativá-lo.", conflito=True)
    cargo.setor_id, cargo.tipo_id, cargo.grupo, cargo.nivel, cargo.denominacao, cargo.ativo = setor.id, tipo.id, dados.grupo, dados.nivel, dados.denominacao.strip(), dados.ativo
    sessao.flush()
    sessao.refresh(cargo)
    if vigente is not None:
        _espelhar(sessao, sessao.get(Usuario, vigente.usuario_id), cargo)  # o rótulo mudou: o perfil da pessoa acompanha
    auditar(sessao, autor.login, "rh.cargo.alterar", cargo.rotulo, autor_id=autor.id, dados={"cargo_id": cargo.id})
    sessao.commit()
    return leitura(sessao, cargo)


def excluir(sessao: Session, cargo_id: int, autor: Usuario) -> None:
    """Só exclui vaga que nunca foi ocupada (senão, desative: o histórico precisa do cargo)."""
    cargo = obter(sessao, cargo_id)
    if cargo.ocupacoes:
        raise ErroRegraCargo("Este cargo já teve ocupante: desative-o em vez de excluir (o histórico mantém o cargo).", conflito=True)
    auditar(sessao, autor.login, "rh.cargo.excluir", cargo.rotulo, autor_id=autor.id)
    sessao.delete(cargo)
    sessao.commit()


# --- Ocupação ------------------------------------------------------------------------------------

def _espelhar(sessao: Session, usuario: Usuario | None, cargo: Cargo) -> None:
    """Campos legados do perfil acompanham o cargo (rótulo e nome do setor) e a pessoa entra no setor do cargo."""
    if usuario is None:
        return
    setor = _setor(sessao, cargo.setor_id)
    usuario.cargo, usuario.departamento = cargo.rotulo[:150], setor.nome[:150]
    if sessao.get(MembroSetor, (setor.id, usuario.id)) is None:
        sessao.add(MembroSetor(setor_id=setor.id, usuario_id=usuario.id))
    sessao.flush()


def ocupar(sessao: Session, cargo_id: int, usuario_id: int, autor: Usuario | None, *, inicio: date | None = None, ato: str = "") -> Ocupacao:
    """A pessoa assume o cargo (sem commit). Se já ocupa outro, aquela ocupação é encerrada como troca; o setor antigo deixa de contá-la como membro."""
    cargo = obter(sessao, cargo_id)
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise CargoNaoEncontrado("Pessoa")
    if not cargo.ativo:
        raise ErroRegraCargo("Este cargo está desativado.", conflito=True)
    inicio = inicio or hoje_sao_paulo()
    atual = cargo.vigente
    if atual is not None:
        if atual.usuario_id == usuario_id:
            raise ErroRegraCargo("Esta pessoa já ocupa este cargo.", conflito=True)
        raise ErroRegraCargo("O cargo já está ocupado: vague-o antes (troca, exoneração ou dispensa).", conflito=True)
    anterior = sessao.scalar(select(Ocupacao).where(Ocupacao.usuario_id == usuario_id, Ocupacao.fim.is_(None)))
    setor = _setor(sessao, cargo.setor_id)
    setor_anterior: Setor | None = None
    if anterior is not None:
        if anterior.inicio > inicio:
            raise ErroRegraCargo("A posse é anterior ao início da ocupação atual da pessoa.")
        setor_anterior = _setor(sessao, anterior.cargo.setor_id)
        _encerrar(sessao, anterior, inicio, "troca", "", autor, registrar_historico=False)
        if setor_anterior.id != setor.id:
            sessao.execute(MembroSetor.__table__.delete().where(MembroSetor.setor_id == setor_anterior.id, MembroSetor.usuario_id == usuario_id))
    ocupacao = Ocupacao(cargo_id=cargo.id, usuario_id=usuario_id, inicio=inicio, ato=(ato or "").strip(), registrado_por_id=autor.id if autor else None,
                        registrado_por_nome=_nome(autor), registrado_em=agora_utc())
    sessao.add(ocupacao)
    sessao.flush()
    sessao.refresh(cargo)
    _espelhar(sessao, usuario, cargo)
    detalhe = f"Ato: {ocupacao.ato}" if ocupacao.ato else ""
    if anterior is not None:
        detalhe = (f"Deixou {anterior.cargo.rotulo} ({setor_anterior.nome}). " + detalhe).strip()
    servico_historico.registrar(sessao, usuario_id, "cargo", f"Assumiu {cargo.rotulo} no setor {setor.nome}", detalhe, autor, quando=agora_utc(), dados={"ocupacao_id": ocupacao.id, "cargo_id": cargo.id})
    if setor_anterior is not None and setor_anterior.id != setor.id:
        servico_historico.registrar(sessao, usuario_id, "setor", f"Mudou do setor {setor_anterior.nome} para {setor.nome}", "", autor)
    elif anterior is None:
        servico_historico.registrar(sessao, usuario_id, "setor", f"Passou a integrar o setor {setor.nome}", "", autor)
    return ocupacao


def _encerrar(sessao: Session, ocupacao: Ocupacao, fim: date, motivo: str, ato: str, autor: Usuario | None, *, registrar_historico: bool = True) -> None:
    if motivo not in MOTIVOS_FIM:
        raise ErroRegraCargo("Motivo inválido.")
    if fim < ocupacao.inicio:
        raise ErroRegraCargo("A data de saída é anterior à posse.")
    ocupacao.fim, ocupacao.motivo_fim, ocupacao.ato_fim = fim, motivo, (ato or "").strip()
    if registrar_historico:
        rotulo = {"exoneracao": "Exonerado(a) de", "dispensa": "Dispensado(a) de", "troca": "Deixou", "outro": "Deixou"}[motivo]
        tipo = "exoneracao" if motivo == "exoneracao" else "cargo"
        detalhe = f"Ato: {ocupacao.ato_fim}" if ocupacao.ato_fim else ""
        servico_historico.registrar(sessao, ocupacao.usuario_id, tipo, f"{rotulo} {ocupacao.cargo.rotulo} em {fim:%d/%m/%Y}", detalhe, autor, quando=agora_utc(),
                                    dados={"ocupacao_id": ocupacao.id, "motivo": motivo})


def vagar(sessao: Session, cargo_id: int, autor: Usuario, *, fim: date | None = None, motivo: str = "outro", ato: str = "") -> Ocupacao:
    """Encerra a ocupação vigente do cargo (troca, exoneração, dispensa ou outro) e tira a pessoa do setor do cargo (sem commit)."""
    cargo = obter(sessao, cargo_id)
    vigente = cargo.vigente
    if vigente is None:
        raise ErroRegraCargo("Este cargo já está vago.", conflito=True)
    _encerrar(sessao, vigente, fim or hoje_sao_paulo(), motivo, ato, autor)
    sessao.execute(MembroSetor.__table__.delete().where(MembroSetor.setor_id == cargo.setor_id, MembroSetor.usuario_id == vigente.usuario_id))
    sessao.flush()
    return vigente


# --- Reconciliação dos cadastros antigos ---------------------------------------------------------

def _setor_do_departamento(sessao: Session, texto: str | None) -> Setor | None:
    nome = (texto or "").strip().lower()
    if not nome:
        return None
    return sessao.scalar(select(Setor).where(func.lower(func.trim(Setor.nome)) == nome, Setor.sistemico.is_(False)))


def reconciliar(sessao: Session) -> list[PendenciaCargo]:
    """Pessoas ativas com cargo em texto livre e sem ocupação vigente: o que a migração dos legados não casou (ou ainda não rodou)."""
    com_ocupacao = select(Ocupacao.usuario_id).where(Ocupacao.fim.is_(None))
    pendencias = []
    for u in sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True), func.trim(Usuario.cargo) != "", Usuario.id.not_in(com_ocupacao)).order_by(func.lower(Usuario.nome_completo))):
        interpretado = cargo_legado.interpretar(u.cargo)
        setor = _setor_do_departamento(sessao, u.departamento)
        sugestao = None
        if interpretado is not None:
            sugestao = interpretado.denominacao if not interpretado.interpretado else f"{interpretado.tipo} {interpretado.grupo}.{interpretado.nivel:02d} – {interpretado.denominacao}"
        pendencias.append(PendenciaCargo(
            usuario_id=u.id, nome=u.nome_completo or u.login, login=u.login, cargo_texto=u.cargo, departamento_texto=u.departamento or "",
            interpretado=bool(interpretado and interpretado.interpretado), sugestao=sugestao, setor_id=setor.id if setor else None))
    return pendencias


def cargo_do_texto(sessao: Session, texto: str, setor: Setor, *, autor: Usuario | None = None) -> Cargo:
    """Cargo vago do setor que combina com o texto; se não houver, cria um a partir do texto interpretado."""
    interpretado = cargo_legado.interpretar(texto)
    if interpretado is None:
        raise ErroRegraCargo("A pessoa não tem cargo informado.")
    tipo = tipo_por_codigo(sessao, interpretado.tipo)
    existentes = sessao.scalars(select(Cargo).where(
        Cargo.setor_id == setor.id, Cargo.tipo_id == tipo.id, Cargo.grupo.is_(interpretado.grupo) if interpretado.grupo is None else Cargo.grupo == interpretado.grupo,
        Cargo.nivel.is_(interpretado.nivel) if interpretado.nivel is None else Cargo.nivel == interpretado.nivel,
        func.lower(Cargo.denominacao) == interpretado.denominacao.lower(), Cargo.ativo.is_(True)))
    vago = next((c for c in existentes if c.vigente is None), None)
    if vago is not None:
        return vago
    cargo = Cargo(setor_id=setor.id, tipo_id=tipo.id, grupo=interpretado.grupo, nivel=interpretado.nivel, denominacao=interpretado.denominacao, ativo=True)
    sessao.add(cargo)
    sessao.flush()
    sessao.refresh(cargo)
    return cargo


def vincular_legado(sessao: Session, usuario_id: int, autor: Usuario | None, *, setor_id: int | None = None, cargo_id: int | None = None) -> Ocupacao:
    """Aloca a pessoa num cargo: o informado (vago) ou um criado a partir do texto que ela já tinha, no setor informado ou no do departamento (sem commit)."""
    usuario = sessao.get(Usuario, usuario_id)
    if usuario is None:
        raise CargoNaoEncontrado("Pessoa")
    if cargo_id is not None:
        cargo = obter(sessao, cargo_id)
    else:
        setor = _setor(sessao, setor_id) if setor_id is not None else _setor_do_departamento(sessao, usuario.departamento)
        if setor is None:
            raise ErroRegraCargo("Informe o setor do cargo: o departamento da pessoa não corresponde a um setor cadastrado.")
        cargo = cargo_do_texto(sessao, usuario.cargo, setor, autor=autor)
    # A posse legada começa na criação do cadastro (a data real da nomeação o RH ajusta depois, se quiser)
    inicio = usuario.criado_em.date() if getattr(usuario, "criado_em", None) else hoje_sao_paulo()
    return ocupar(sessao, cargo.id, usuario_id, autor, inicio=min(inicio, hoje_sao_paulo()), ato="Vínculo do cadastro anterior")


# --- Organograma ---------------------------------------------------------------------------------

def setores_com_vagas_visiveis(setores: list[Setor], usuario_id: int) -> set[int]:
    """Setores cujas vagas a pessoa pode ver: os que ela lidera e todos os abaixo deles (a liderança vê a cadeia para baixo; colegas, liderados e líderes de outros setores não)."""
    filhos: dict[int, list[int]] = {}
    for s in setores:
        if s.setor_pai_id is not None:
            filhos.setdefault(s.setor_pai_id, []).append(s.id)
    visiveis: set[int] = set()
    fila = [s.id for s in setores if s.lider_id == usuario_id]
    while fila:
        atual = fila.pop()
        if atual not in visiveis:
            visiveis.add(atual)
            fila.extend(filhos.get(atual, []))
    return visiveis


def organograma(sessao: Session, *, incluir_vagas: bool = True, ver_todas_as_vagas: bool = True, usuario_id: int | None = None) -> list[NoOrganograma]:
    """Árvore de unidades (setores institucionais ativos) com as posições de cada uma. Raízes: setores sem pai.

    Com `ver_todas_as_vagas=False` (quem não é do RH), as vagas só aparecem nas unidades que `usuario_id` lidera e nas abaixo delas; nas demais a vaga some
    da lista e das contagens, para não vazar o planejamento do quadro."""
    garantir_tipos(sessao)
    setores = list(sessao.scalars(select(Setor).where(Setor.ativo.is_(True), Setor.sistemico.is_(False))))
    ids = {s.id for s in setores}
    # Só pessoas do LDAP entram no organograma: contas locais (TV, serviço, teste) não são gente da estrutura
    locais = set(sessao.scalars(select(Usuario.id).where(Usuario.origem == OrigemUsuario.LOCAL)))
    cargos = [c for c in listar(sessao) if c.ocupante is None or c.ocupante.usuario_id not in locais]
    if not ver_todas_as_vagas:
        com_vagas = setores_com_vagas_visiveis(setores, usuario_id or 0)
        cargos = [c for c in cargos if c.ocupante is not None or c.setor_id in com_vagas]
    por_setor: dict[int, list[LeituraCargo]] = {}
    for c in cargos:
        por_setor.setdefault(c.setor_id, []).append(c)
    lideres = {u.id: LiderSetor(usuario_id=u.id, nome=u.nome_completo or u.login, cargo=u.cargo or "", foto_url=servico_diretorio.foto_url(u)) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_([s.lider_id for s in setores if s.lider_id]), Usuario.id.not_in(locais) if locais else True))} if any(s.lider_id for s in setores) else {}
    filhos: dict[int | None, list[Setor]] = {}
    for s in setores:
        filhos.setdefault(s.setor_pai_id if s.setor_pai_id in ids else None, []).append(s)

    def montar(setor: Setor) -> NoOrganograma:
        posicoes = por_setor.get(setor.id, [])
        visiveis = posicoes if incluir_vagas else [p for p in posicoes if p.ocupante is not None]
        return NoOrganograma(
            setor_id=setor.id, nome=setor.nome, sigla=setor.sigla, tipo_unidade=setor.tipo_unidade, lider_nome=lideres[setor.lider_id].nome if setor.lider_id in lideres else None, lider=lideres.get(setor.lider_id),
            total_posicoes=len(posicoes), total_vagas=sum(1 for p in posicoes if p.ocupante is None), posicoes=visiveis,
            filhos=[montar(f) for f in sorted(filhos.get(setor.id, []), key=lambda x: x.nome.lower())])

    return [montar(r) for r in sorted(filhos.get(None, []), key=lambda x: x.nome.lower())]
