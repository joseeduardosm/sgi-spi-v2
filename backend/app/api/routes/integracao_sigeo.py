# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a configuração da integração com o SIGEO e a conferência das ordens bancárias (exclusiva do SuperRoot).
"""Integração com o SIGEO (`/api/integracao-sigeo`): credencial cifrada, teste de acesso e execução (ou ensaio) da conferência das OBs."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.models.usuario import Papel, Usuario
from app.services import servico_integracao_sigeo as servico
from app.services.contratos import servico_empenho_sigeo, servico_ob_sigeo
from app.services.servico_auditoria import auditar
from app.services.servico_integracao_sigeo import AlteracaoIntegracaoSigeo, LeituraIntegracaoSigeo, ResultadoTesteSigeo

roteador = APIRouter(prefix="/integracao-sigeo", tags=["Integração SIGEO"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)


@roteador.get("", response_model=LeituraIntegracaoSigeo, summary="Configuração da integração com o SIGEO",
              description="Endereço, análise, usuário, se há senha gravada (a senha nunca é devolvida) e o resultado da última conferência. Restrito ao SuperRoot.")
def obter(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> LeituraIntegracaoSigeo:
    """Configuração atual, sem a senha."""
    return servico.leitura(servico.obter(sessao))


@roteador.put("", response_model=LeituraIntegracaoSigeo, summary="Salvar a configuração do SIGEO", responses=VALIDACAO,
              description="Grava endereço, análise, usuário, liga/desliga e a senha (cifrada no banco). Senha vazia preserva a atual. Restrito ao SuperRoot.")
def salvar(dados: AlteracaoIntegracaoSigeo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(super_root)) -> LeituraIntegracaoSigeo:
    """Salva a configuração."""
    return servico.leitura(servico.salvar(sessao, dados, autor.login))


@roteador.post("/testar", response_model=ResultadoTesteSigeo, summary="Testar o acesso ao SIGEO",
               description="Entra no SIGEO, executa a análise e informa quantas OBs vieram. Sempre responde 200 (`sucesso` e `mensagem`). Restrito ao SuperRoot.")
def testar(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(super_root)) -> ResultadoTesteSigeo:
    """Teste de acesso."""
    return servico.testar(servico.obter(sessao))


@roteador.post("/conferir", response_model=dict, summary="Conferir agora as ordens bancárias no SIGEO",
               description="Faz o que a rotina das 08:00 faz: para cada competência esperando OB (contrato com processo financeiro), procura no SIGEO as OBs do "
               "processo cujo texto traz o mês da competência e, se a soma for igual ao líquido a pagar, conclui a etapa (comprovante em PDF, débito nas NEs e "
               "e-mail de pagamento). Com `ensaio=true` (padrão) só relata. Resposta: `verificadas`, `aguardando`, `concluidas`, `pendencias`, "
               "`sugestoes_processo` e `erros`. Restrito ao SuperRoot.")
def conferir(ensaio: bool = Query(True, description="Só relata, sem concluir nada."), sessao: Session = Depends(obter_sessao),
             autor: Usuario = Depends(super_root)) -> dict:
    """Conferência sob demanda."""
    resultado = servico_ob_sigeo.executar(sessao, ensaio=ensaio).como_dict()
    if not ensaio:
        auditar(sessao, autor.login, "integracao_sigeo.conferir", "Conferência de OBs no SIGEO", f"concluidas={len(resultado['concluidas'])} pendencias={len(resultado['pendencias'])}")
        sessao.commit()
    return resultado


@roteador.post("/empenhos", response_model=dict, summary="Cadastrar agora as NEs e cancelamentos do SIGEO",
               description="Para cada contrato com Processo Financeiro e **sem nenhuma NE cadastrada**, lê a análise de empenhos do SIGEO e cadastra as Notas de Empenho do(s) "
               "processo(s) e os cancelamentos (valor negativo ligado à NE pelo documento de origem). Nunca altera contrato que já tem NE. Com `ensaio=true` (padrão) só relata. "
               "Resposta: `contratos` (o que cadastra), `nes_cadastradas`, `cancelamentos`, `pendencias` e `sem_empenho_no_sigeo`. Restrito ao SuperRoot.")
def empenhos(ensaio: bool = Query(True, description="Só relata, sem cadastrar nada."), sessao: Session = Depends(obter_sessao),
             autor: Usuario = Depends(super_root)) -> dict:
    """Cadastro de empenhos sob demanda."""
    from app.services.servico_integracao_sigeo import baixar_empenhos
    from app.services.sigeo.cliente_obiee import ErroSigeo

    try:
        linhas = baixar_empenhos(servico.obter(sessao))
    except ErroSigeo as erro:
        return {"contratos": [], "nes_cadastradas": 0, "cancelamentos": 0, "pendencias": [], "sem_empenho_no_sigeo": [], "erros": [erro.mensagem]}
    resultado = servico_empenho_sigeo.cadastrar(sessao, linhas, autor, ensaio=ensaio).como_dict()
    if not ensaio:
        auditar(sessao, autor.login, "integracao_sigeo.empenhos", "Cadastro de empenhos no SIGEO", f"nes={resultado['nes_cadastradas']} cancelamentos={resultado['cancelamentos']}")
        sessao.commit()
    return resultado
