# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas de cargos, ocupações, exoneração, reconciliação, organograma e histórico funcional do RH.
"""Cargos e vida funcional (`/api/rh/...`).

- `tipos-cargo`: CCESP, FCESP e OUTRO (editáveis).
- `cargos`: vagas por setor (criar em lote, alterar, excluir), `ocupacao` (assumir), `vacancia` (troca, exoneração, dispensa) e `reconciliar` (cargos em texto livre).
- `organograma`: árvore de unidades com as posições e os ocupantes.
- `usuarios/{id}/historico` (+ `.pdf`): histórico funcional (cadastro, documentos, cargos, setores, férias, licença-prêmio, exoneração) com quem registrou e quando.

Níveis do módulo (ACL `rh`): LEITURA consulta; MODIFICACAO gere setores e cargos; CONTROLE_TOTAL é o RH. O histórico de uma pessoa também é visível a ela mesma (sem os itens sigilosos).
"""

from contextlib import contextmanager
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_rh, obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.schemas.rh_cargos import (
    GravacaoCargo, GravacaoTipoCargo, HistoricoUsuario, LeituraCargo, LeituraTipoCargo, NoOrganograma, OcuparCargo, PendenciaCargo, VagarCargo, VincularCargoLegado,
)
from app.services.rh import papeis, servico_cargos, servico_historico
from app.services.rh.servico_cargos import CargoNaoEncontrado, ErroRegraCargo

roteador = APIRouter(prefix="/rh", tags=["Módulo RH: cargos e histórico"], responses=RESPOSTAS_AUTENTICADAS)

ler = exigir_rh(NivelAcl.LEITURA)
gerir = exigir_rh(NivelAcl.MODIFICACAO)
NAO_ENCONTRADO = resposta_nao_encontrado("Cargo, setor ou pessoa")


@contextmanager
def _traduzir(sessao: Session):
    """Erros de cargos no formato padrão da API (desfaz a transação em caso de erro)."""
    try:
        yield
    except CargoNaoEncontrado as erro:
        sessao.rollback()
        raise nao_encontrado(erro.o_que) from erro
    except ErroRegraCargo as erro:
        sessao.rollback()
        raise erro_regra(str(erro), erro.conflito) from erro


# --- Tipos de cargo ------------------------------------------------------------------------------

@roteador.get("/tipos-cargo", response_model=list[LeituraTipoCargo], summary="Tipos de cargo", description="CCESP, FCESP, OUTRO e os que o RH cadastrar. Exige acesso de leitura ao RH.")
def tipos_de_cargo(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(ler)):
    return servico_cargos.listar_tipos(sessao)


@roteador.post("/tipos-cargo", response_model=list[LeituraTipoCargo], status_code=status.HTTP_201_CREATED, summary="Cadastrar tipo de cargo",
               description="Exige **Gerir setores e cargos** (MODIFICACAO no RH). O código é único (`409`).", responses={**CONFLITO, **INVALIDO})
def criar_tipo(dados: GravacaoTipoCargo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerir)):
    with _traduzir(sessao):
        return servico_cargos.gravar_tipo(sessao, dados, autor)


@roteador.put("/tipos-cargo/{tipo_id}", response_model=list[LeituraTipoCargo], summary="Alterar tipo de cargo", description="Exige **Gerir setores e cargos**.",
              responses={**CONFLITO, **resposta_nao_encontrado("Tipo de cargo")})
def alterar_tipo(tipo_id: int, dados: GravacaoTipoCargo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerir)):
    with _traduzir(sessao):
        return servico_cargos.gravar_tipo(sessao, dados, autor, tipo_id)


# --- Cargos --------------------------------------------------------------------------------------

@roteador.get("/cargos", response_model=list[LeituraCargo], summary="Listar cargos (vagas)",
              description="Uma linha por posição, com o ocupante vigente. Filtros: `setor_id`, `tipo_id`, `situacao` (`vago` ou `ocupado`), `busca` (denominação, setor ou ocupante) e `incluir_inativos`. Exige acesso de leitura ao RH.")
def listar_cargos(setor_id: int | None = None, tipo_id: int | None = None, situacao: str | None = Query(None, pattern="^(vago|ocupado)$"), busca: str | None = Query(None, max_length=100),
                  incluir_inativos: bool = False, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(ler)):
    return servico_cargos.listar(sessao, setor_id=setor_id, tipo_id=tipo_id, situacao=situacao, busca=busca, incluir_inativos=incluir_inativos)


@roteador.post("/cargos", response_model=list[LeituraCargo], status_code=status.HTTP_201_CREATED, summary="Criar vagas de um cargo",
               description="Cria `quantidade` vagas iguais no setor (ex.: 3 vagas de Assessor II). CCESP e FCESP exigem grupo (1 ou 2) e nível (1 a 18). Exige **Gerir setores e cargos**.",
               responses={**INVALIDO, **NAO_ENCONTRADO})
def criar_cargos(dados: GravacaoCargo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerir)):
    with _traduzir(sessao):
        return servico_cargos.criar(sessao, dados, autor)


@roteador.put("/cargos/{cargo_id}", response_model=LeituraCargo, summary="Alterar um cargo",
              description="Não muda de setor nem desativa um cargo ocupado (`409`). Se o rótulo mudar, o perfil de quem o ocupa acompanha. Exige **Gerir setores e cargos**.",
              responses={**CONFLITO, **INVALIDO, **NAO_ENCONTRADO})
def alterar_cargo(cargo_id: int, dados: GravacaoCargo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerir)):
    with _traduzir(sessao):
        return servico_cargos.alterar(sessao, cargo_id, dados, autor)


@roteador.delete("/cargos/{cargo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir uma vaga",
                 description="Só vagas que nunca tiveram ocupante (`409`); as demais se desativam. Exige **Gerir setores e cargos**.", responses={**CONFLITO, **NAO_ENCONTRADO})
def excluir_cargo(cargo_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerir)) -> Response:
    with _traduzir(sessao):
        servico_cargos.excluir(sessao, cargo_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador.post("/cargos/{cargo_id}/ocupacao", response_model=LeituraCargo, status_code=status.HTTP_201_CREATED, summary="Alocar uma pessoa no cargo",
               description="A pessoa assume o cargo (data e ato opcionais). Se já ocupava outro, aquela ocupação é encerrada como troca. Ela passa a fazer parte do setor do cargo, o perfil "
               "(cargo e departamento) acompanha e o fato vai para o histórico. `409` se o cargo já está ocupado. Exige **Gerir setores e cargos**.", responses={**CONFLITO, **INVALIDO, **NAO_ENCONTRADO})
def ocupar_cargo(cargo_id: int, dados: OcuparCargo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerir)):
    with _traduzir(sessao):
        servico_cargos.ocupar(sessao, cargo_id, dados.usuario_id, autor, inicio=dados.inicio, ato=dados.ato)
        sessao.commit()
        return servico_cargos.leitura(sessao, servico_cargos.obter(sessao, cargo_id))


@roteador.post("/cargos/{cargo_id}/vacancia", response_model=LeituraCargo, summary="Vagar o cargo (troca, exoneração, dispensa)",
               description="Encerra a ocupação vigente com data, motivo (`troca`, `exoneracao`, `dispensa` ou `outro`) e ato. A pessoa sai do setor do cargo e o fato (a exoneração é um tipo próprio) vai para o histórico. "
               "`409` se o cargo já está vago. Exige **Gerir setores e cargos**.", responses={**CONFLITO, **INVALIDO, **NAO_ENCONTRADO})
def vagar_cargo(cargo_id: int, dados: VagarCargo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerir)):
    with _traduzir(sessao):
        servico_cargos.vagar(sessao, cargo_id, autor, fim=dados.fim, motivo=dados.motivo, ato=dados.ato)
        sessao.commit()
        return servico_cargos.leitura(sessao, servico_cargos.obter(sessao, cargo_id))


@roteador.get("/cargos-a-reconciliar", response_model=list[PendenciaCargo], summary="Pessoas com cargo ainda sem vínculo",
              description="Usuários ativos com cargo em texto livre e sem ocupação vigente: o que a migração dos cadastros antigos não casou. Cada linha traz a sugestão de cargo interpretada do texto. Exige acesso de leitura ao RH.")
def a_reconciliar(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(ler)):
    return servico_cargos.reconciliar(sessao)


@roteador.post("/cargos-a-reconciliar/{usuario_id}", response_model=LeituraCargo, summary="Vincular uma pessoa a um cargo",
               description="Cria o cargo a partir do texto que a pessoa já tinha (no setor informado ou no do departamento) ou usa um cargo vago informado, e a aloca. Exige **Gerir setores e cargos**.",
               responses={**CONFLITO, **INVALIDO, **NAO_ENCONTRADO})
def vincular(usuario_id: int, dados: VincularCargoLegado, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(gerir)):
    with _traduzir(sessao):
        ocupacao = servico_cargos.vincular_legado(sessao, usuario_id, autor, setor_id=dados.setor_id, cargo_id=dados.cargo_id)
        sessao.commit()
        return servico_cargos.leitura(sessao, servico_cargos.obter(sessao, ocupacao.cargo_id))


# --- Organograma ---------------------------------------------------------------------------------

@roteador.get("/organograma", response_model=list[NoOrganograma], summary="Organograma",
              description="Árvore de unidades (setores institucionais ativos) com as posições de cada uma e os ocupantes (só pessoas do LDAP). Aberto a qualquer usuário autenticado. "
                          "**Vagas:** o RH (leitura ou mais) vê todas; os demais só veem as vagas das unidades que lideram e das abaixo delas (a liderança do setor e, em cadeia, as lideranças acima). "
                          "Colegas, liderados e líderes de outros setores não veem vagas. `incluir_vagas=false` esconde todas.")
def organograma(incluir_vagas: bool = True, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_atual)):
    return servico_cargos.organograma(sessao, incluir_vagas=incluir_vagas, ver_todas_as_vagas=papeis.tem_nivel_rh(sessao, usuario, NivelAcl.LEITURA), usuario_id=usuario.id)


# --- Histórico funcional -------------------------------------------------------------------------

def _historico(sessao: Session, solicitante: Usuario, usuario_id: int, tipos: list[str] | None, de: date | None, ate: date | None) -> tuple[Usuario, HistoricoUsuario]:
    pessoa = sessao.get(Usuario, usuario_id)
    if pessoa is None:
        raise nao_encontrado("Pessoa")
    eh_rh = papeis.tem_nivel_rh(sessao, solicitante, NivelAcl.LEITURA)
    if not eh_rh and solicitante.id != pessoa.id:
        raise ErroApi(status.HTTP_403_FORBIDDEN, "Somente o RH ou a própria pessoa consulta o histórico funcional.", "sem_permissao")
    return pessoa, servico_historico.consultar(sessao, pessoa, ver_sigilosos=eh_rh, tipos=tipos, de=de, ate=ate)


@roteador.get("/usuarios/{usuario_id}/historico", response_model=HistoricoUsuario, summary="Histórico funcional da pessoa",
              description="Cargos e setores por onde passou e a linha do tempo (cadastro, documentos, período de férias, férias e licença-prêmio gozadas, exoneração), do mais recente ao mais antigo, "
              "cada item com **quem registrou e quando**. Filtros: `tipos`, `de` e `ate` (datas). Visível ao RH (tudo) e à própria pessoa (sem os itens sigilosos); `403` para os demais.",
              responses=resposta_nao_encontrado("Pessoa"))
def historico(usuario_id: int, tipos: list[str] | None = Query(None), de: date | None = None, ate: date | None = None, sessao: Session = Depends(obter_sessao),
              usuario: Usuario = Depends(obter_usuario_atual)):
    return _historico(sessao, usuario, usuario_id, tipos, de, ate)[1]


@roteador.get("/usuarios/{usuario_id}/historico.pdf", summary="Histórico funcional em PDF",
              description="Mesmo conteúdo da tela (identificação, cargos e setores, linha do tempo com autor e dd/mm/aaaa hh:mm), nos mesmos filtros e com a mesma regra de acesso.",
              responses={status.HTTP_200_OK: {"content": {"application/pdf": {}}}, **resposta_nao_encontrado("Pessoa")})
def historico_pdf(usuario_id: int, tipos: list[str] | None = Query(None), de: date | None = None, ate: date | None = None, sessao: Session = Depends(obter_sessao),
                  usuario: Usuario = Depends(obter_usuario_atual)) -> Response:
    pessoa, dados = _historico(sessao, usuario, usuario_id, tipos, de, ate)
    conteudo = servico_historico.gerar_pdf(dados, usuario.nome_completo or usuario.login)
    return Response(content=conteudo, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="historico-{pessoa.login}.pdf"'})
