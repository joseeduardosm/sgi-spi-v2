# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor as rotas da admissão do RH: modelos editáveis, checklists de documentos e a trilha (chamado, documentos, resolução, Protocolo, publicação, e-mail, posse).
"""Admissão (`/api/rh/admissoes`, `/api/rh/modelos`, `/api/rh/checklists`). Dados pessoais sensíveis: só o RH (ACL `rh`, controle total)."""

import uuid
from contextlib import contextmanager
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_rh, obter_usuario_atual
from app.api.respostas import CONFLITO, INVALIDO, RESPOSTAS_AUTENTICADAS, erro_regra, nao_encontrado, resposta_nao_encontrado
from app.core.banco import obter_sessao
from app.core.erros import ErroApi
from app.models.acl import NivelAcl
from app.models.usuario import Usuario
from app.schemas.rh_admissao import (
    SOLICITACOES, EntradaChamado, EntradaDataPublicacao, EntradaMotivo, EntradaPosse, EntradaProtocolo, EntradaTexto, GravacaoChecklist, GravacaoModelo, IniciarAdmissao, LeituraAdmissao,
    LeituraChecklist, LeituraModelo, ResumoAdmissao, TextoParaCopiar, TipoProtocoloResolucao,
)
from app.services import servico_anexos
from app.services.rh import rh_mascara, servico_admissao, servico_checklists, servico_modelos
from app.services.rh.servico_admissao import AdmissaoNaoEncontrada, ErroAdmissao
from app.services.rh.servico_checklists import ChecklistNaoEncontrado, ErroChecklist
from app.services.rh.servico_modelos import ErroModelo

roteador = APIRouter(prefix="/rh", tags=["Módulo RH: admissão"], responses=RESPOSTAS_AUTENTICADAS)

rh = exigir_rh(NivelAcl.CONTROLE_TOTAL)
NAO_ENCONTRADO = resposta_nao_encontrado("Admissão")
PDF = {status.HTTP_200_OK: {"content": {"application/pdf": {}}}}


@contextmanager
def _traduzir(sessao: Session):
    """Erros da admissão no formato padrão da API (desfaz a transação em caso de erro)."""
    try:
        yield
    except (AdmissaoNaoEncontrada, ChecklistNaoEncontrado) as erro:
        sessao.rollback()
        raise nao_encontrado("Checklist" if isinstance(erro, ChecklistNaoEncontrado) else "Admissão") from erro
    except ErroAdmissao as erro:
        sessao.rollback()
        if erro.proibido:
            raise ErroApi(status.HTTP_403_FORBIDDEN, str(erro), "sem_permissao") from erro
        raise erro_regra(str(erro), erro.conflito) from erro
    except (ErroModelo, ErroChecklist) as erro:
        sessao.rollback()
        raise erro_regra(str(erro), False) from erro


def _pdf(conteudo: bytes, nome: str) -> Response:
    return Response(content=conteudo, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{nome}"'})


# --- Modelos -----------------------------------------------------------------------------------------------

@roteador.get("/modelos", response_model=list[LeituraModelo], summary="Modelos do RH",
              description="Resolução de nomeação, e-mail \"Sua nomeação foi publicada\", termo de posse e boas-vindas. Cada um nasce com um texto padrão que o RH edita. Exige **Controle total** no RH.")
def listar_modelos(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    return servico_modelos.listar(sessao)


@roteador.get("/modelos/placeholders", response_model=dict[str, str], summary="Placeholders permitidos nos modelos",
              description="Lista fechada: `#nome`, `#cargo`, `#numeroresolucao`... Qualquer outro `#` barra o salvamento.")
def placeholders(_: Usuario = Depends(rh)):
    return rh_mascara.PLACEHOLDERS


@roteador.put("/modelos/{tipo}", response_model=LeituraModelo, summary="Salvar modelo", responses={**INVALIDO, **resposta_nao_encontrado("Modelo")},
              description="Grava o assunto e o HTML do modelo. 400 se houver placeholder fora da lista.")
def salvar_modelo(tipo: str, dados: GravacaoModelo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_modelos.salvar(sessao, tipo, dados.assunto, dados.html, autor)


@roteador.post("/modelos/{tipo}/restaurar", response_model=LeituraModelo, summary="Restaurar o texto padrão do modelo", responses=INVALIDO)
def restaurar_modelo(tipo: str, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_modelos.restaurar(sessao, tipo, autor)


# --- Checklists --------------------------------------------------------------------------------------------

@roteador.get("/checklists", response_model=list[LeituraChecklist], summary="Checklists de documentos da admissão",
              description="Cada checklist vale para os tipos de cargo (CCESP, FCESP, OUTRO) ligados a ele. Ao iniciar uma admissão, os documentos do tipo do cargo são copiados para ela.")
def listar_checklists(sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    return servico_checklists.listar(sessao)


@roteador.post("/checklists", response_model=LeituraChecklist, status_code=status.HTTP_201_CREATED, summary="Criar checklist", responses=INVALIDO)
def criar_checklist(dados: GravacaoChecklist, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_checklists.criar(sessao, dados, autor)


@roteador.put("/checklists/{checklist_id}", response_model=LeituraChecklist, summary="Alterar checklist", responses={**INVALIDO, **resposta_nao_encontrado("Checklist")})
def alterar_checklist(checklist_id: int, dados: GravacaoChecklist, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_checklists.alterar(sessao, checklist_id, dados, autor)


@roteador.delete("/checklists/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Excluir checklist", responses=resposta_nao_encontrado("Checklist"),
                 description="Admissões já iniciadas guardam a própria cópia dos documentos e não são afetadas.")
def excluir_checklist(checklist_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)) -> Response:
    with _traduzir(sessao):
        servico_checklists.excluir(sessao, checklist_id, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Admissões ----------------------------------------------------------------------------------------------

@roteador.get("/admissoes/solicitacoes", response_model=dict[str, str], summary="Serviços que o chamado no GLPI pode pedir",
              description="Chave → rótulo (rede, e-mail, SEI, Compras SP, equipamento, estação, crachá, telefone, mobiliário), como no formulário \"CGP – Nomeações\" do GLPI.")
def solicitacoes(_: Usuario = Depends(rh)):
    return SOLICITACOES


@roteador.get("/admissoes/tipos-protocolo", response_model=list[TipoProtocoloResolucao], summary="Tipos de Resolução do Protocolo",
              description="Tipos do Protocolo cujo nome começa com \"Resolu\", e se já têm faixa de numeração para o ano. Com um tipo definido nos Parâmetros do RH, só ele é devolvido, a não ser com `todos=true` (tela de Parâmetros).")
def tipos_protocolo(todos: bool = False, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    return servico_admissao.tipos_de_resolucao(sessao, todos)


@roteador.get("/admissoes", response_model=list[ResumoAdmissao], summary="Listar admissões",
              description="Mais recentes primeiro. `status`: andamento, concluida ou cancelada; `busca` procura por todas as palavras em nome, login, cargo e unidade.")
def listar_admissoes(status_admissao: str | None = Query(None, alias="status", pattern="^(andamento|concluida|cancelada)$"), busca: str | None = Query(None, max_length=100),
                     sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    return servico_admissao.listar(sessao, status_admissao, busca)


@roteador.post("/admissoes", response_model=LeituraAdmissao, status_code=status.HTTP_201_CREATED, summary="Iniciar a admissão de uma ficha",
               description="Exige ficha em rascunho ou aguardando a conta, com login proposto e cargo pretendido (vaga livre). Copia os documentos do checklist do tipo do cargo.",
               responses={**INVALIDO, **CONFLITO, **resposta_nao_encontrado("Ficha")})
def iniciar(dados: IniciarAdmissao, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.iniciar(sessao, dados.ficha_id, autor)


@roteador.get("/admissoes/{admissao_id}", response_model=LeituraAdmissao, summary="Consultar a admissão (trilha completa)", responses=NAO_ENCONTRADO)
def consultar(admissao_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.obter(sessao, admissao_id)


@roteador.post("/admissoes/{admissao_id}/cancelar", response_model=LeituraAdmissao, summary="Cancelar a admissão",
               description="Número do Protocolo ainda sem documento volta para a fila. Admissão concluída não se cancela.", responses={**CONFLITO, **NAO_ENCONTRADO})
def cancelar(admissao_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.cancelar(sessao, admissao_id, autor)


@roteador.post("/admissoes/{admissao_id}/chamado", response_model=LeituraAdmissao, summary="Enviar o formulário de nomeação ao GLPI",
               description="Preenche e envia o formulário \"CGP - Nomeações\" do GLPI com os dados da ficha e os serviços marcados; o próprio formulário abre os chamados e dispara os e-mails dos seus destinos (nenhum chamado à parte é criado). "
                           "O login proposto vai junto nas observações. Entra no GLPI pela tela web com a conta de serviço da integração. 502 se o GLPI estiver fora do ar ou recusar; 503 sem integração ativa ou sem login web.",
               responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def abrir_chamado(admissao_id: int, dados: EntradaChamado, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.abrir_chamado(sessao, admissao_id, dados.solicitacoes, dados.observacoes, autor, dados.usuario_espelho)


@roteador.put("/admissoes/{admissao_id}/foto", response_model=LeituraAdmissao, summary="Foto da pessoa (opcional)",
              description="`multipart/form-data` com `arquivo` (PNG ou JPG, até 5 MB). A foto vai no formulário de nomeação do GLPI (se ainda não foi enviado) e, assim que a conta da pessoa existir "
                          "(ligação com a ficha ou conclusão da admissão), vira a **foto do Diretório (intranet)**. Trocar a foto depois do envio atualiza a intranet, mas não reenvia ao GLPI.",
              responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def definir_foto(admissao_id: int, arquivo: UploadFile = File(..., description="PNG ou JPG"), sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.definir_foto(sessao, admissao_id, arquivo.file, autor)


@roteador.delete("/admissoes/{admissao_id}/foto", response_model=LeituraAdmissao, summary="Remover a foto da admissão", responses={**CONFLITO, **NAO_ENCONTRADO})
def remover_foto(admissao_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.remover_foto(sessao, admissao_id, autor)


@roteador.get("/admissoes/{admissao_id}/foto", response_class=FileResponse, summary="Ver a foto da admissão", responses=NAO_ENCONTRADO)
def ver_foto(admissao_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    with _traduzir(sessao):
        anexo = servico_admissao.anexo_foto(sessao, admissao_id)
    return servico_anexos.resposta_download(anexo)


@roteador.post("/admissoes/{admissao_id}/documentos/concluir", response_model=LeituraAdmissao, summary="Concluir a etapa de documentos",
               description="Exige o envio registrado de todos os documentos obrigatórios.", responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def concluir_documentos(admissao_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.concluir_documentos(sessao, admissao_id, autor)


@roteador.post("/admissoes/{admissao_id}/documentos/{documento_id}", response_model=LeituraAdmissao, summary="Registrar o envio de um documento ao Portal de Indicações",
               description="`multipart/form-data` com `enviado_em` (data), `observacao` e, opcionalmente, o `comprovante` (PDF, imagem ou Office). O Portal de Indicações é externo: aqui só se registra o envio.",
               responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def registrar_documento(admissao_id: int, documento_id: int, enviado_em: date = Form(...), observacao: str = Form(""), comprovante: UploadFile | None = File(None),
                        sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        arquivo = (comprovante.file, comprovante.filename or "comprovante") if comprovante is not None and comprovante.filename else None
        return servico_admissao.registrar_documento(sessao, admissao_id, documento_id, enviado_em, observacao, arquivo, autor)


@roteador.delete("/admissoes/{admissao_id}/documentos/{documento_id}", response_model=LeituraAdmissao, summary="Desfazer o registro de envio de um documento",
                 responses={**CONFLITO, **NAO_ENCONTRADO})
def desfazer_documento(admissao_id: int, documento_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.desfazer_documento(sessao, admissao_id, documento_id, autor)


@roteador.get("/admissoes/{admissao_id}/documentos/{documento_id}/comprovante", response_class=FileResponse, summary="Baixar o comprovante de envio",
              responses=NAO_ENCONTRADO)
def baixar_comprovante(admissao_id: int, documento_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    with _traduzir(sessao):
        anexo = servico_admissao.comprovante(sessao, admissao_id, documento_id)
    return servico_anexos.resposta_download(anexo)


@roteador.post("/admissoes/{admissao_id}/resolucao", response_model=LeituraAdmissao, summary="Gerar o texto da resolução",
               description="Copia o modelo \"Resolução de nomeação\" para a admissão (ou, com `html` no corpo de `PUT`, grava o texto editado). O texto guarda os placeholders: número, datas e nomes entram na hora do PDF.",
               responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def gerar_resolucao(admissao_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.gerar_resolucao(sessao, admissao_id, autor)


@roteador.put("/admissoes/{admissao_id}/resolucao", response_model=LeituraAdmissao, summary="Editar o texto da resolução",
              description="Substitui o texto (placeholders validados). Não se altera depois da publicação.", responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def editar_resolucao(admissao_id: int, dados: EntradaTexto, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.gerar_resolucao(sessao, admissao_id, autor, dados.html)


@roteador.get("/admissoes/{admissao_id}/resolucao.pdf", summary="PDF da resolução",
              description="Com a marca d'água MINUTA até a publicação ser registrada; depois, sem marca.", responses={**PDF, **INVALIDO, **NAO_ENCONTRADO})
def resolucao_pdf(admissao_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)) -> Response:
    with _traduzir(sessao):
        conteudo, nome = servico_admissao.resolucao_pdf(sessao, admissao_id, autor)
    return _pdf(conteudo, nome)


@roteador.get("/admissoes/{admissao_id}/resolucao/copia", response_model=TextoParaCopiar, summary="Texto da resolução para colar no SEI",
              description="O texto da resolução com os placeholders já trocados (número, nomes, datas): `html` com a formatação e `texto` simples. A tela copia os dois para a área de transferência.",
              responses={**INVALIDO, **NAO_ENCONTRADO})
def resolucao_para_copiar(admissao_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    with _traduzir(sessao):
        html, texto = servico_admissao.resolucao_para_copiar(sessao, admissao_id)
    return TextoParaCopiar(html=html, texto=texto)


@roteador.post("/admissoes/{admissao_id}/protocolo", response_model=LeituraAdmissao, summary="Reservar o número da resolução no Protocolo",
               description="Reserva o próximo número livre do tipo de Resolução definido nos Parâmetros do RH (`tipo_protocolo_id` só vale se os Parâmetros não definirem um), na faixa do ano atual. `409` se a admissão é de resolução sem número.", responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def reservar_numero(admissao_id: int, dados: EntradaProtocolo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.reservar_numero(sessao, admissao_id, dados.tipo_protocolo_id, autor)


@roteador.post("/admissoes/{admissao_id}/protocolo/liberar", response_model=LeituraAdmissao, summary="Liberar o número da resolução no Protocolo",
               description="Devolve o número ao Protocolo (livre de novo), **mesmo com o PDF da publicação já subido**: o PDF é excluído logicamente, a publicação deixa de estar registrada e a trilha volta à etapa do número. "
                           "Quem reservou o número, o Serviço de Apoio Administrativo (parâmetro do RH) e o SuperRoot (`403 sem_permissao` nos demais). `motivo` obrigatório; `409` sem número reservado ou depois da posse. O e-mail de nomeação já enviado não é desfeito.",
               responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO, status.HTTP_403_FORBIDDEN: {"description": "Não reservou o número nem é do Serviço de Apoio Administrativo."}})
def liberar_numero(admissao_id: int, dados: EntradaMotivo, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(obter_usuario_atual)):
    with _traduzir(sessao):
        return servico_admissao.liberar_numero(sessao, admissao_id, dados.motivo, autor)


@roteador.post("/admissoes/{admissao_id}/publicacao", response_model=LeituraAdmissao, summary="Registrar a publicação no D.O.E.",
               description="`multipart/form-data` com o `arquivo` (PDF da publicação) e `publicado_em`. O PDF fica anexado ao número do Protocolo. Se o Protocolo anexar o PDF direto, a publicação também fica registrada (data de hoje; ajuste em `PUT .../publicacao`).",
               responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def registrar_publicacao(admissao_id: int, publicado_em: date = Form(...), arquivo: UploadFile = File(...), sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.registrar_publicacao(sessao, admissao_id, arquivo.file, arquivo.filename or "publicacao.pdf", publicado_em, autor)


@roteador.put("/admissoes/{admissao_id}/publicacao", response_model=LeituraAdmissao, summary="Ajustar a data da publicação", responses={**INVALIDO, **NAO_ENCONTRADO})
def ajustar_publicacao(admissao_id: int, dados: EntradaDataPublicacao, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.ajustar_data_publicacao(sessao, admissao_id, dados.publicado_em, autor)


@roteador.get("/admissoes/{admissao_id}/publicacao.pdf", response_class=FileResponse, summary="Baixar o PDF da publicação", responses=NAO_ENCONTRADO)
def baixar_publicacao(admissao_id: int, sessao: Session = Depends(obter_sessao), _: Usuario = Depends(rh)):
    with _traduzir(sessao):
        anexo = servico_admissao.anexo_publicacao(sessao, admissao_id)
    return servico_anexos.resposta_download(anexo)


@roteador.post("/admissoes/{admissao_id}/email", response_model=LeituraAdmissao, summary="Reenviar o e-mail de nomeação",
               description="O e-mail \"Sua nomeação foi publicada\" **sai sozinho** quando a publicação é registrada (pelo RH ou pelo Protocolo), para o e-mail pessoal da ficha, com o PDF da publicação. "
                           "Esta rota só reenvia quando o envio automático falhou (o motivo fica em `email_erro`). 409 se já foi enviado.", responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def reenviar_email(admissao_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.reenviar_email(sessao, admissao_id, autor)


@roteador.post("/admissoes/{admissao_id}/posse", response_model=LeituraAdmissao, summary="Registrar a posse",
               description="Grava a data da posse (não anterior à publicação) e prepara o texto do termo a partir do modelo.", responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def registrar_posse(admissao_id: int, dados: EntradaPosse, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.registrar_posse(sessao, admissao_id, dados.posse_em, autor)


@roteador.put("/admissoes/{admissao_id}/termo", response_model=LeituraAdmissao, summary="Editar o texto do termo de posse", responses={**INVALIDO, **NAO_ENCONTRADO})
def editar_termo(admissao_id: int, dados: EntradaTexto, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.salvar_termo(sessao, admissao_id, dados.html, autor)


@roteador.get("/admissoes/{admissao_id}/termo.pdf", summary="PDF do termo de posse", responses={**PDF, **INVALIDO, **NAO_ENCONTRADO})
def termo_pdf(admissao_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)) -> Response:
    with _traduzir(sessao):
        conteudo, nome = servico_admissao.termo_pdf(sessao, admissao_id, autor)
    return _pdf(conteudo, nome)


@roteador.post("/admissoes/{admissao_id}/concluir", response_model=LeituraAdmissao, summary="Concluir a admissão (entrada no SGI)",
               description="Exige a posse registrada e a conta da pessoa já vinculada à ficha (a TI cria o login no AD). A pessoa assume o cargo na data da posse e o histórico funcional registra o fato.",
               responses={**INVALIDO, **CONFLITO, **NAO_ENCONTRADO})
def concluir(admissao_id: int, sessao: Session = Depends(obter_sessao), autor: Usuario = Depends(rh)):
    with _traduzir(sessao):
        return servico_admissao.concluir(sessao, admissao_id, autor)
