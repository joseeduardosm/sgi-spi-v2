# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da portaria de designação do contrato e das autoridades signatárias.
"""Rotas das portarias contratuais.

- `/contratos/{contrato_id}/portarias`: painel, criação (nomeações), escolha da autoridade (reserva o número no Protocolo), aceite, devolução, cancelamento
  e PDF de evidência. A publicação é feita pelo Protocolo, ao anexar o PDF do D.O.E. ao número reservado.
- `/portarias/ciencias` e `/portarias/{id}/ciencia`: ciência de quem foi nomeado (qualquer usuário autenticado).
- `/portarias/autoridades`: cadastro das autoridades signatárias (escrita: SuperRoot, controle total em Contratos ou gestor/suplente de um contrato).
"""

import uuid
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.respostas import RESPOSTAS_AUTENTICADAS, resposta_nao_encontrado
from app.api.routes.contratos.comum import SEM_VINCULO, pode_ler, pode_modificar, traduzir_erros
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.api.dependencias import obter_usuario_autenticado
from app.schemas.contratos.portaria import (EscolhaAutoridade, GravacaoAutoridade, GravacaoNomeacoes, LeituraAutoridade, LeituraCienciaPendente, MotivoPortaria, PainelPortarias,
                                            UsuarioAutoridade)
from app.services import servico_anexos
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
               summary="Criar portaria (nomeações)", description="Abre a portaria com de 1 a 6 nomeações (função + usuário; o gestor é obrigatório). Quem cria: a equipe do contrato "
               "ou quem tem controle total em Contratos (perfil Administrador de Contratos). Cada nomeado precisa ter RS/PV, RG/CIN e cargo preenchidos: enquanto faltar, a nomeação "
               "fica pendente e o RH é avisado. Com os dados completos, cada um recebe o pedido de ciência. Uma portaria em andamento por contrato (409).", responses=ESCRITA)
def criar(contrato_id: uuid.UUID, dados: GravacaoNomeacoes, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.criar(sessao, contrato_id, dados.nomeacoes, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.put("/contratos/{contrato_id}/portarias/{portaria_id}/nomeacoes", response_model=PainelPortarias, tags=TAGS, summary="Alterar as nomeações",
              description="Troca as nomeações enquanto a portaria não tem autoridade (quem mudou perde a ciência). Depois disso, devolva ou cancele a portaria (409).", responses=ESCRITA)
def alterar_nomeacoes(contrato_id: uuid.UUID, portaria_id: uuid.UUID, dados: GravacaoNomeacoes, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.definir_nomeacoes(sessao, contrato_id, portaria_id, dados.nomeacoes, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.post("/contratos/{contrato_id}/portarias/{portaria_id}/autoridade", response_model=PainelPortarias, tags=TAGS, summary="Escolher a autoridade e gerar a portaria",
               description="Com todos os nomeados cientes: escolhe a autoridade competente, gera o texto (para copiar) e **reserva** o número em \"Portaria SPI SSGC\" no Protocolo, ainda pendente. "
               "409 se faltar ciência; 400 sem máscara ativa, sem faixa de numeração do ano ou sem processo SEI/objeto no contrato.", responses=ESCRITA)
def escolher_autoridade(contrato_id: uuid.UUID, portaria_id: uuid.UUID, dados: EscolhaAutoridade, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_modificar)):
    with traduzir_erros(sessao):
        servico_portaria.escolher_autoridade(sessao, contrato_id, portaria_id, dados.autoridade_id, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.post("/contratos/{contrato_id}/portarias/{portaria_id}/aceite", response_model=PainelPortarias, tags=TAGS, summary="Aceitar portaria",
               description="Aceite da autoridade signatária (ou do SuperRoot). Atualiza o texto, gera o PDF de evidência (ciências e aceite) e deixa a portaria aguardando o D.O.E.; "
               "sem processo SEI, objeto ou RS, responde 400.", responses=ESCRITA)
def aceitar(contrato_id: uuid.UUID, portaria_id: uuid.UUID, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(pode_ler)):
    with traduzir_erros(sessao):
        servico_portaria.aceitar(sessao, contrato_id, portaria_id, autor)
        return servico_portaria.painel(sessao, contrato_id, autor)


@roteador.post("/contratos/{contrato_id}/portarias/{portaria_id}/devolucao", response_model=PainelPortarias, tags=TAGS, summary="Devolver portaria",
               description="A autoridade devolve a portaria com o motivo: o número volta ao Protocolo e quem criou ajusta as nomeações ou escolhe outra autoridade.", responses=ESCRITA)
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


@roteador.get("/contratos/{contrato_id}/portarias/{portaria_id}/evidencia", tags=TAGS, summary="PDF de evidência da portaria",
              description="PDF com a ciência de cada nomeado e o aceite da autoridade, para juntar ao SEI antes da publicação. Existe depois do aceite (400 antes).",
              responses={status.HTTP_200_OK: {"content": {"application/pdf": {}}}, **NAO_ENCONTRADO})
def baixar_evidencia(contrato_id: uuid.UUID, portaria_id: uuid.UUID, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(pode_ler)) -> Response:
    with traduzir_erros():
        anexo = servico_portaria.evidencia(sessao, contrato_id, portaria_id)
        conteudo = servico_anexos.caminho(anexo).read_bytes()
    return Response(content=conteudo, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{anexo.nome_original}"'})


@roteador.get("/portarias/ciencias", response_model=list[LeituraCienciaPendente], tags=TAGS, summary="Nomeações aguardando a minha ciência",
              description="Nomeações do usuário logado em portarias aguardando ciência. Qualquer usuário autenticado (o nomeado pode não ter acesso ao módulo); a tela abre o modal ao entrar.")
def minhas_ciencias(sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)):
    return servico_portaria.ciencias_pendentes(sessao, usuario)


@roteador.post("/portarias/{portaria_id}/ciencia", response_model=list[LeituraCienciaPendente], tags=TAGS, summary="Dar ciência da nomeação",
               description="O nomeado confirma que está ciente (todas as funções dele na portaria). Com todos cientes, a portaria segue para a escolha da autoridade. Devolve as ciências ainda pendentes do usuário.",
               responses={**NAO_ENCONTRADO, **SEM_VINCULO})
def dar_ciencia(portaria_id: uuid.UUID, sessao: Session = Depends(obter_sessao), usuario: Usuario = Depends(obter_usuario_autenticado)):
    with traduzir_erros(sessao):
        servico_portaria.registrar_ciencia(sessao, portaria_id, usuario)
        return servico_portaria.ciencias_pendentes(sessao, usuario)


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
