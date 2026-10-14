# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da portaria de designação do contrato e das autoridades signatárias.
"""Rotas das portarias contratuais.

- `/contratos/{contrato_id}/portarias`: painel, solicitação (reserva o número no Protocolo), reenvio, aceite, devolução, cancelamento,
  exportação da minuta (Word/PDF com marca d'água "MINUTA") e envio do PDF publicado.
- `/portarias/autoridades`: cadastro das autoridades signatárias (escrita: SuperRoot, controle total em Contratos ou gestor/suplente de um contrato).
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.respostas import RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import ARQUIVO_RECUSADO, SEM_VINCULO, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.schemas.contratos.portaria import GravacaoAutoridade, LeituraAutoridade, MotivoPortaria, PainelPortarias, SolicitacaoPortaria, UsuarioAutoridade
from app.services.contratos import servico_portaria

TAGS = ["Contratos: portaria"]
roteador = APIRouter(responses=RESPOSTAS_AUTENTICADAS)
NAO_ENCONTRADO = resposta_nao_encontrado("Contrato ou portaria")
ESCRITA = {**NAO_ENCONTRADO, **SEM_VINCULO}


@roteador.get("/contratos/{contrato_id}/portarias", response_model=PainelPortarias, tags=TAGS, summary="Portarias do contrato",
              description="Histórico de portarias do contrato, autoridades ativas para a solicitação e o que o usuário pode fazer em cada uma.", responses=NAO_ENCONTRADO)
def painel(contrato_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(pode_ler)):
    with traduzir_erros():
        return servico_portaria.painel(sessao, contrato_id, usuario)


@roteador.post("/contratos/{contrato_id}/portarias", response_model=PainelPortarias, status_code=status.HTTP_201_CREATED, tags=TAGS,
               summary="Solicitar portaria", description="Reserva o próximo número de \"Portaria\" no Protocolo, vinculado ao contrato, congela o texto com a equipe vigente "
               "e envia para o aceite da autoridade escolhida. Uma portaria em andamento por contrato (409).", responses=ESCRITA)
def solicitar(contrato_id: uuid.UUID, dados: SolicitacaoPortaria, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.solicitar(sessao, contrato_id, dados.autoridade_id, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.post("/contratos/{contrato_id}/portarias/{portaria_id}/reenviar", response_model=PainelPortarias, tags=TAGS, summary="Reenviar portaria para aceite",
               description="Refaz o texto com a equipe e os dados atuais e volta a portaria (devolvida ou aguardando) para o aceite.", responses=ESCRITA)
def reenviar(contrato_id: uuid.UUID, portaria_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.reenviar(sessao, contrato_id, portaria_id, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.post("/contratos/{contrato_id}/portarias/{portaria_id}/aceite", response_model=PainelPortarias, tags=TAGS, summary="Aceitar portaria",
               description="Aceite da autoridade signatária (ou do SuperRoot). Atualiza o texto com a equipe e o RS atuais; sem RS, processo SEI ou objeto, responde 400.", responses=ESCRITA)
def aceitar(contrato_id: uuid.UUID, portaria_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_ler)):
    with traduzir_erros(sessao):
        servico_portaria.aceitar(sessao, contrato_id, portaria_id, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.post("/contratos/{contrato_id}/portarias/{portaria_id}/devolucao", response_model=PainelPortarias, tags=TAGS, summary="Devolver portaria",
               description="A autoridade devolve a portaria ao solicitante com o motivo.", responses=ESCRITA)
def devolver(contrato_id: uuid.UUID, portaria_id: uuid.UUID, dados: MotivoPortaria, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_ler)):
    with traduzir_erros(sessao):
        servico_portaria.devolver(sessao, contrato_id, portaria_id, dados.motivo, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.post("/contratos/{contrato_id}/portarias/{portaria_id}/cancelamento", response_model=PainelPortarias, tags=TAGS, summary="Cancelar portaria",
               description="Cancela a portaria em andamento e libera o número no Protocolo.", responses=ESCRITA)
def cancelar(contrato_id: uuid.UUID, portaria_id: uuid.UUID, dados: MotivoPortaria, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.cancelar(sessao, contrato_id, portaria_id, dados.motivo, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.get("/contratos/{contrato_id}/portarias/{portaria_id}/minuta", tags=TAGS, summary="Exportar minuta da portaria",
              description="Word (`docx`) ou PDF com a marca d'água \"MINUTA\", antes e depois do aceite, para postar no SEI e no DOE.",
              responses={status.HTTP_200_OK: {"content": {"application/pdf": {}, "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}}}, **NAO_ENCONTRADO})
def minuta(contrato_id: uuid.UUID, portaria_id: uuid.UUID, formato: Annotated[Literal["docx", "pdf"], Query()] = "docx", sessao: Session = Depends(obter_sessao),
           _: Usuario = Depends(pode_ler)) -> Response:
    with traduzir_erros():
        conteudo, nome, tipo = servico_portaria.exportar(sessao, contrato_id, portaria_id, formato)
    return Response(content=conteudo, media_type=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@roteador.post("/contratos/{contrato_id}/portarias/{portaria_id}/publicacao", response_model=PainelPortarias, tags=TAGS, summary="Anexar PDF publicado da portaria",
               description="Com a portaria aceita, recebe o PDF publicado: fica anexado ao número do Protocolo e em Documentos Importantes do contrato (tipo 16).",
               responses={**ESCRITA, **ARQUIVO_RECUSADO})
def publicar(contrato_id: uuid.UUID, portaria_id: uuid.UUID, arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao),
             autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.publicar(sessao, contrato_id, portaria_id, arquivo.file, arquivo.filename or "portaria.pdf", autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


# --- Autoridades --------------------------------------------------------------------------------

@roteador.get("/portarias/autoridades", response_model=list[LeituraAutoridade], tags=TAGS, summary="Autoridades signatárias",
              description="Todas as autoridades cadastradas (ativas e desativadas).")
def listar_autoridades(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)):
    return servico_portaria.autoridades_com_nomes(sessao)


@roteador.get("/portarias/autoridades/usuarios", response_model=list[UsuarioAutoridade], tags=TAGS, summary="Usuários para escolher como autoridade",
              description="Usuários ativos (busca por nome ou login, até 20) com cargo e departamento do cadastro, que preenchem o formulário da autoridade. SuperRoot, controle total em Contratos ou gestor (ou suplente) de um contrato.")
def usuarios_para_autoridade(busca: str = Query("", max_length=100), sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros():
        servico_portaria.exigir_gestao_autoridades(sessao, autor)
    return [UsuarioAutoridade(id=u.id, login=u.login, nome_completo=u.nome_completo or u.login, cargo=u.cargo or "", departamento=u.departamento or "")
            for u in servico_portaria.buscar_usuarios(sessao, busca)]


@roteador.post("/portarias/autoridades", response_model=list[LeituraAutoridade], status_code=status.HTTP_201_CREATED, tags=TAGS, summary="Cadastrar autoridade",
               description="SuperRoot, controle total em Contratos ou gestor (ou suplente) de um contrato. Devolve a lista atualizada.")
def criar_autoridade(dados: GravacaoAutoridade, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.exigir_gestao_autoridades(sessao, autor)
        servico_portaria.criar_autoridade(sessao, dados, autor)
        return servico_portaria.autoridades_com_nomes(sessao)


@roteador.put("/portarias/autoridades/{autoridade_id}", response_model=list[LeituraAutoridade], tags=TAGS, summary="Alterar autoridade",
              description="SuperRoot, controle total em Contratos ou gestor (ou suplente) de um contrato. Portarias já criadas mantêm o retrato da autoridade. Devolve a lista atualizada.", responses=resposta_nao_encontrado("Autoridade"))
def alterar_autoridade(autoridade_id: uuid.UUID, dados: GravacaoAutoridade, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.exigir_gestao_autoridades(sessao, autor)
        servico_portaria.alterar_autoridade(sessao, autoridade_id, dados, autor)
        return servico_portaria.autoridades_com_nomes(sessao)


@roteador.delete("/portarias/autoridades/{autoridade_id}", response_model=list[LeituraAutoridade], tags=TAGS, summary="Excluir autoridade",
                 description="SuperRoot, controle total ou gestor/suplente de contrato; autoridades que já assinaram portarias devem ser desativadas (409).", responses=resposta_nao_encontrado("Autoridade"))
def excluir_autoridade(autoridade_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.exigir_gestao_autoridades(sessao, autor)
        servico_portaria.excluir_autoridade(sessao, autoridade_id, autor)
        return servico_portaria.autoridades_com_nomes(sessao)
