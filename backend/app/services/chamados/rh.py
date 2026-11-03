# Criado por José Eduardo Santana Martins
# Este arquivo serve para abrir, dentro do módulo Chamados, os chamados que o RH pede na Nomeação (rede, e-mail, SEI, crachá...).
"""Chamados do RH.

**Chave de transição (`rh_destino`, Parâmetros > RH):**
- `glpi` (padrão): o RH > Admissão continua enviando o formulário "CGP - Nomeações" ao GLPI, como hoje;
- `na_data`: GLPI até a data "a partir de" (Parâmetros > Geral) e, dali em diante, o SGI, sozinho: o RH vira no mesmo dia que os chamados;
- `chamados`: depois da virada, o SGI abre **um chamado por serviço pedido** no próprio módulo. Cada serviço tem nos Parâmetros a **fila**
  (setor que atende), a **prioridade** e os **prazos** (SLAs); o chamado nasce no assunto fixo do fluxo ("Nomeação (RH)" / "Exoneração (RH)"),
  que só agrupa nos relatórios e não aparece para quem abre chamado.

**Exoneração** (só no destino `chamados`): o inverso da Nomeação. Cada serviço tem o seu par ("Criar usuário de rede" → "Desativar usuário de
rede"); a tela sugere marcados os que foram pedidos na nomeação da pessoa. O chamado guarda a ocupação encerrada (`rh_ocupacao_id`).

Cada chamado guarda a admissão (`admissao_id`) e o serviço (`servico_rh`); a tela da admissão mostra o andamento de cada um, ao vivo.

**Dados pessoais (LGPD, minimização):** a descrição, que o solicitante e quem está em cópia leem, leva só o necessário para o
serviço (nome, cargo, lotação, início, login proposto). CPF, RG, RS e e-mail pessoal vão numa **nota privada**, que só quem atende vê.
"""

from dataclasses import dataclass
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chamados import AcompanhamentoChamado, CategoriaChamados, Chamado, ServicoRhChamados
from app.models.usuario import Usuario
from app.services.chamados import configuracao, parametros
from app.services.chamados.acesso import Papeis
from app.services.chamados.parametros import ErroParametro
from app.services.chamados.servico import DadosAbertura, abrir

# O que se grava em `rh_destino`; o que vale numa dada hora (`destino()`) é sempre `glpi` ou `chamados`
DESTINOS = ("glpi", "chamados", "na_data")
parametros.PADROES["rh_destino"] = "glpi"
FLUXO_NOMEACAO = "nomeacao"
FLUXO_EXONERACAO = "exoneracao"
# Exoneração: o inverso de cada serviço da Nomeação (mesmas chaves). "Se pediu acesso, pede para cancelar o acesso."
SERVICOS_EXONERACAO = {
    "rede": "Desativar usuário de rede", "email": "Desativar e-mail corporativo", "sei": "Cancelar acesso ao SEI", "compras_sp": "Cancelar acesso ao Compras SP",
    "equipamento": "Recolher equipamento de trabalho", "estacao": "Liberar a estação de trabalho", "cracha": "Recolher crachá",
    "telefone": "Desativar telefone", "mobiliario": "Liberar mobiliário",
}


def destino_configurado(sessao: Session) -> str:
    """O que está gravado nos Parâmetros > RH: `glpi`, `chamados` ou `na_data`."""
    valor = parametros.obter(sessao, "rh_destino")
    return valor if valor in DESTINOS else "glpi"


def destino(sessao: Session) -> str:
    """Para onde vão os chamados do RH agora: `glpi` ou `chamados`.

    Com `na_data`, segue a data "a partir de": antes dela (ou sem data marcada) continua no GLPI; no dia, passa ao SGI sem ninguém mexer.
    """
    valor = destino_configurado(sessao)
    if valor == "na_data":
        return "chamados" if configuracao.atendimento_aberto(sessao) else "glpi"
    return valor


def servicos(sessao: Session, fluxo: str = FLUXO_NOMEACAO) -> dict[str, ServicoRhChamados]:
    return {s.servico: s for s in sessao.scalars(select(ServicoRhChamados).where(ServicoRhChamados.fluxo == fluxo))}


@dataclass
class ConfigServico:
    """Fila (setor que atende), prioridade e prazos de um serviço do RH."""
    setor_id: int | None
    prioridade: str = "normal"
    sla_tto_id: object = None
    sla_ttr_id: object = None


def gravar(sessao: Session, novo_destino: str, config_por_fluxo: dict[str, dict[str, ConfigServico]], conhecidos_por_fluxo: dict[str, dict[str, str]]) -> None:
    """Grava a chave de transição e, por fluxo, a fila, a prioridade e os prazos de cada serviço (sem fila = serviço sem destino). Sem commit.

    Para ligar o destino `chamados`, todo serviço da Nomeação e da Exoneração precisa de fila (setor ativo): assim o RH nunca envia um
    pedido que não tem para onde ir.
    """
    from app.models.chamados import PRIORIDADES, SlaChamados
    from app.models.setor import Setor

    if novo_destino not in DESTINOS:
        raise ErroParametro("Destino inválido (glpi, chamados ou na_data).")
    if novo_destino == "na_data" and configuracao.inicio_atendimento(sessao) is None:
        raise ErroParametro("Para o RH virar junto, marque antes a data \"Atendimento no SGI a partir de\" em Parâmetros > Geral.")
    faltam: list[str] = []
    for fluxo, conhecidos in conhecidos_por_fluxo.items():
        configs = config_por_fluxo.get(fluxo, {})
        desconhecidos = set(configs) - set(conhecidos)
        if desconhecidos:
            raise ErroParametro("Serviço desconhecido: " + ", ".join(sorted(desconhecidos)) + ".")
        atuais = servicos(sessao, fluxo)
        for chave, rotulo in conhecidos.items():
            cfg = configs.get(chave)
            if cfg is None or cfg.setor_id is None:
                if chave in atuais:
                    sessao.delete(atuais[chave])
                faltam.append(rotulo)
                continue
            setor = sessao.get(Setor, cfg.setor_id)
            if setor is None or not setor.ativo:
                raise ErroParametro(f"Escolha um setor ativo como fila de \"{rotulo}\".")
            if cfg.prioridade not in PRIORIDADES:
                raise ErroParametro(f"Prioridade inválida em \"{rotulo}\".")
            for sla_id, tipo in ((cfg.sla_tto_id, "tto"), (cfg.sla_ttr_id, "ttr")):
                sla = sessao.get(SlaChamados, sla_id) if sla_id else None
                if sla_id and (sla is None or sla.tipo != tipo or not sla.ativo):
                    raise ErroParametro(f"Prazo inválido em \"{rotulo}\" (escolha um SLA ativo de {'atendimento' if tipo == 'tto' else 'solução'}).")
            linha = atuais.get(chave) or ServicoRhChamados(fluxo=fluxo, servico=chave)
            linha.setor_id, linha.prioridade, linha.sla_tto_id, linha.sla_ttr_id = setor.id, cfg.prioridade, cfg.sla_tto_id, cfg.sla_ttr_id
            if chave not in atuais:
                sessao.add(linha)
    # `na_data` também exige fila em tudo: no dia da virada não há ninguém olhando para corrigir
    if novo_destino in ("chamados", "na_data") and faltam:
        raise ErroParametro("Para o RH abrir os chamados aqui, todo serviço precisa de fila. Faltam: " + ", ".join(faltam) + ".",
                            409, "servico_sem_fila")
    parametros.gravar(sessao, "rh_destino", novo_destino)
    sessao.flush()


@dataclass
class DadosNomeacao:
    """O que a admissão manda para os chamados (montado pelo RH a partir da ficha)."""
    nome: str
    cargo: str
    lotacao: str
    inicio: str
    login_proposto: str
    usuario_espelho: str
    observacoes: str
    # Só na nota privada
    cpf: str
    rg: str
    rs: str
    email_pessoal: str


ASSUNTOS_FIXOS = {FLUXO_NOMEACAO: "Nomeação (RH)", FLUXO_EXONERACAO: "Exoneração (RH)"}


def assunto_fixo(sessao: Session, fluxo: str) -> CategoriaChamados:
    """O "lugar" dos chamados do RH de cada fluxo (criado na primeira vez). Fora de uso para quem abre chamado: só agrupa nos relatórios e
    filtros; a fila, a prioridade e os prazos vêm do serviço."""
    from sqlalchemy import func

    nome = ASSUNTOS_FIXOS[fluxo]
    c = sessao.scalar(select(CategoriaChamados).where(CategoriaChamados.pai_id.is_(None), func.lower(CategoriaChamados.nome) == nome.lower()))
    if c is None:
        c = CategoriaChamados(nome=nome, caminho=nome, nivel=1, ativa=False, visivel_solicitante=False, perguntar_impedindo=False)
        sessao.add(c)
        sessao.flush()
    return c


def _abrir_servicos(sessao: Session, fluxo: str, pedidos: dict[str, str], autor: Usuario, titulo_de, descricao: str) -> list[tuple[str, Chamado]]:
    """Um chamado por serviço, no assunto fixo do fluxo, com a fila, a prioridade e os prazos do serviço."""
    from app.services.chamados.servico import RegrasFixas

    mapa = servicos(sessao, fluxo)
    sem = [rotulo for chave, rotulo in pedidos.items() if chave not in mapa or mapa[chave].setor_id is None]
    if sem:
        raise ErroParametro("Serviço sem fila nos Parâmetros dos Chamados: " + ", ".join(sem) + ". Avise a administração dos Chamados.",
                            409, "servico_sem_fila")
    assunto = assunto_fixo(sessao, fluxo)
    criados = []
    for chave, rotulo in pedidos.items():
        s = mapa[chave]
        chamado = abrir(sessao, autor, Papeis(True, True, True), DadosAbertura(
            titulo=titulo_de(rotulo)[:250], categoria_id=assunto.id, tipo="requisicao", descricao=descricao,
            fixas=RegrasFixas(setor_id=s.setor_id, prioridade=s.prioridade, sla_tto_id=s.sla_tto_id, sla_ttr_id=s.sla_ttr_id),
        ))
        criados.append((chave, chamado))
    return criados


def _linhas(itens: list[tuple[str, str]]) -> str:
    return "".join(f"<li><strong>{escape(rotulo)}:</strong> {escape(valor)}</li>" for rotulo, valor in itens if valor)


def abrir_nomeacao(sessao: Session, admissao_id: int, pedidos: dict[str, str], dados: DadosNomeacao, autor: Usuario) -> list[Chamado]:
    """Um chamado por serviço pedido (`pedidos` = chave → rótulo). Sem commit: a admissão grava junto, tudo ou nada."""
    publico = _linhas([("Nome", dados.nome), ("Cargo", dados.cargo), ("Lotação", dados.lotacao), ("Início previsto", dados.inicio),
                       ("Login de rede proposto", dados.login_proposto), ("Usuário espelho", dados.usuario_espelho)])
    observacoes = f"<p>{escape(dados.observacoes.strip())}</p>" if dados.observacoes.strip() else ""
    privado = _linhas([("CPF", dados.cpf), ("RG ou CIN", dados.rg), ("RS", dados.rs), ("E-mail pessoal", dados.email_pessoal)])
    criados = []
    for chave, chamado in _abrir_servicos(sessao, FLUXO_NOMEACAO, pedidos, autor, lambda rotulo: f"{rotulo}: {dados.nome}",
                                          f"<p>Pedido do RH na nomeação.</p><ul>{publico}</ul>{observacoes}"):
        chamado.admissao_id, chamado.servico_rh = admissao_id, chave
        if privado:
            chamado.acompanhamentos.append(AcompanhamentoChamado(
                autor_id=autor.id, privado=True, texto=f"<p>Dados pessoais para o atendimento (só a equipe vê):</p><ul>{privado}</ul>"))
        criados.append(chamado)
    sessao.flush()
    return criados


@dataclass
class DadosExoneracao:
    nome: str
    login: str
    cargo: str
    lotacao: str
    saida: str
    ato: str
    observacoes: str


def abrir_exoneracao(sessao: Session, ocupacao_id: int, pedidos: dict[str, str], dados: DadosExoneracao, autor: Usuario) -> list[Chamado]:
    """Um chamado por serviço a desfazer (`pedidos` = chave → rótulo da Exoneração). Sem commit."""
    lista = _linhas([("Nome", dados.nome), ("Login de rede", dados.login), ("Cargo", dados.cargo), ("Lotação", dados.lotacao),
                     ("Data de saída", dados.saida), ("Ato", dados.ato)])
    observacoes = f"<p>{escape(dados.observacoes.strip())}</p>" if dados.observacoes.strip() else ""
    criados = []
    for chave, chamado in _abrir_servicos(sessao, FLUXO_EXONERACAO, pedidos, autor, lambda rotulo: f"{rotulo}: {dados.nome}",
                                          f"<p>Pedido do RH na exoneração.</p><ul>{lista}</ul>{observacoes}"):
        chamado.rh_ocupacao_id, chamado.servico_rh = ocupacao_id, chave
        criados.append(chamado)
    sessao.flush()
    return criados


def _links(sessao: Session, condicao) -> list[dict]:
    itens = list(sessao.scalars(select(Chamado).where(condicao, Chamado.excluido_em.is_(None)).order_by(Chamado.numero)))
    if not itens:
        return []
    apresentacao = configuracao.apresentacao(sessao)
    return [
        {"url": f"/chamados/{c.numero}", "texto": c.titulo, "chave": c.servico_rh, "numero": c.numero,
         "status_nome": apresentacao[c.status_base][0], "status_cor": apresentacao[c.status_base][1]}
        for c in itens
    ]


def chamados_da_exoneracao(sessao: Session, ocupacao_id: int) -> list[dict]:
    """Os chamados abertos por esta exoneração, com o status de agora (para a tela do RH)."""
    return _links(sessao, Chamado.rh_ocupacao_id == ocupacao_id)


def chamados_da_admissao(sessao: Session, admissao_id: int) -> list[dict]:
    """Os chamados do módulo abertos por esta admissão, com o status de agora (para a tela do RH)."""
    return _links(sessao, Chamado.admissao_id == admissao_id)
