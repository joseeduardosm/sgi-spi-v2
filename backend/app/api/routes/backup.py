# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor o backup geral do sistema (banco inteiro + anexos): gerar, listar, baixar e importar. Só SuperRoot.
"""Rotas de `/api/admin/backups` (Administração › Backup)."""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_papeis
from app.api.respostas import INVALIDO, RESPOSTAS_AUTENTICADAS, VALIDACAO
from app.core.banco import obter_sessao
from app.core.configuracao import obter_configuracao
from app.core.erros import ErroApi
from app.models.usuario import Papel, Usuario
from app.schemas.backup import AndamentoBackup, BackupGuardado, LinkDownloadBackup, ManifestoBackup, PainelBackup
from app.services import servico_backup
from app.services.servico_backup import ErroBackup

roteador = APIRouter(prefix="/admin/backups", tags=["Backup geral"], responses=RESPOSTAS_AUTENTICADAS)
super_root = exigir_papeis(Papel.SUPER_ROOT)
# O link de download vale poucos minutos: só o tempo de o navegador começar a baixar
MINUTOS_LINK_DOWNLOAD = 5


def _painel() -> PainelBackup:
    return PainelBackup(backups=[BackupGuardado(**b) for b in servico_backup.listar()], andamento=AndamentoBackup(**servico_backup.andamento()))


@roteador.get("", response_model=PainelBackup, summary="Backups guardados e andamento",
              description="Lista os backups guardados no servidor (`dados/backups`) e a situação da última operação (gerar ou importar), que roda em "
                          "segundo plano. Só SuperRoot.")
def painel(_: Usuario = Depends(super_root)) -> PainelBackup:
    return _painel()


@roteador.post("", response_model=PainelBackup, status_code=status.HTTP_202_ACCEPTED, summary="Gerar backup geral",
               description="Começa a gerar, em segundo plano, um `.zip` com o banco inteiro (`pg_dump`: configurações, ACLs, servidores SMTP e LDAP, "
                           "contratos, tudo) e todos os anexos, mais um `manifesto.json`. Acompanhe por `GET /api/admin/backups` (`andamento`). "
                           "`400` se já houver um backup ou importação em andamento. Só SuperRoot.", responses=INVALIDO)
def gerar(autor: Usuario = Depends(super_root)) -> PainelBackup:
    try:
        servico_backup.iniciar_geracao(autor)
    except ErroBackup as erro:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido") from erro
    return _painel()


@roteador.get("/arquivo/{nome}", response_class=FileResponse, summary="Baixar um backup",
              description="Download do `.zip` guardado. `404` se o nome não existir. Só SuperRoot.")
def baixar(nome: str, _: Usuario = Depends(super_root)) -> FileResponse:
    try:
        caminho = servico_backup.caminho_do_backup(nome)
    except ErroBackup as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro
    return FileResponse(caminho, media_type="application/zip", filename=caminho.name)


@roteador.post("/arquivo/{nome}/link", response_model=LinkDownloadBackup, summary="Link temporário para baixar um backup",
               description="Devolve um endereço assinado, válido por 5 minutos e só para este arquivo, que o navegador abre direto (o download "
                           "aparece na barra de downloads do navegador, sem carregar o .zip inteiro na memória da página). `404` se o nome não "
                           "existir. Só SuperRoot.")
def link_download(nome: str, autor: Usuario = Depends(super_root)) -> LinkDownloadBackup:
    try:
        caminho = servico_backup.caminho_do_backup(nome)
    except ErroBackup as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro
    config = obter_configuracao()
    expira_em = datetime.now(UTC) + timedelta(minutes=MINUTOS_LINK_DOWNLOAD)
    # Tipo próprio: esta chave não serve como token de acesso (que exige tipo "acesso") nem para outro arquivo
    chave = jwt.encode({"sub": str(autor.id), "tipo": "download_backup", "arquivo": caminho.name, "exp": expira_em},
                       config.chave_secreta_jwt.get_secret_value(), algorithm=config.algoritmo_jwt)
    return LinkDownloadBackup(url=f"/api/admin/backups/arquivo/{caminho.name}/baixar?chave={chave}", expira_em=expira_em)


@roteador.get("/arquivo/{nome}/baixar", response_class=FileResponse, summary="Baixar um backup pelo link temporário",
              description="Download direto pelo navegador, sem cabeçalho de autenticação: a `chave` é a do `POST /arquivo/{nome}/link` (vale 5 "
                          "minutos, só para este arquivo, e o usuário que a pediu precisa continuar SuperRoot e ativo). `404` com chave inválida, "
                          "vencida ou de outro arquivo.", responses=INVALIDO)
def baixar_pelo_link(nome: str, chave: str = Query(...), sessao: Session = Depends(obter_sessao)) -> FileResponse:
    config = obter_configuracao()
    try:
        conteudo = jwt.decode(chave, config.chave_secreta_jwt.get_secret_value(), algorithms=[config.algoritmo_jwt],
                              options={"require": ["sub", "exp"]})
    except jwt.InvalidTokenError:
        conteudo = {}
    usuario = sessao.get(Usuario, int(conteudo["sub"])) if conteudo.get("tipo") == "download_backup" and conteudo.get("arquivo") == nome else None
    if usuario is None or not usuario.ativo or not usuario.superusuario:
        raise ErroApi(status.HTTP_404_NOT_FOUND, "Link de download inválido ou vencido. Clique em Baixar de novo.", "nao_encontrado")
    try:
        caminho = servico_backup.caminho_do_backup(nome)
    except ErroBackup as erro:
        raise ErroApi(status.HTTP_404_NOT_FOUND, str(erro), "nao_encontrado") from erro
    return FileResponse(caminho, media_type="application/zip", filename=caminho.name)


@roteador.post("/importar", response_model=ManifestoBackup, status_code=status.HTTP_202_ACCEPTED, summary="Importar backup geral (substitui tudo)",
               description="`multipart/form-data` com `arquivo` (o `.zip` gerado por esta tela, de qualquer servidor) e `confirmacao` = `SUBSTITUIR`. "
                           "**Substitui o banco inteiro e todos os anexos.** Confere o arquivo (manifesto, banco e versão: backup de versão mais nova é "
                           "recusado) e segue em segundo plano: guarda um backup automático do estado atual, restaura o banco numa transação só (se "
                           "falhar, nada muda), troca os anexos, aplica as migrações e reinicia a API (`andamento.situacao = reiniciando`). As senhas "
                           "de LDAP e SMTP só abrem com a mesma `CHAVE_CIFRA_LDAP` do servidor de origem. `400` sem a confirmação, arquivo inválido ou "
                           "operação em andamento. Só SuperRoot.", responses={**VALIDACAO, **INVALIDO})
def importar(arquivo: UploadFile = File(...), confirmacao: str = Form(...), autor: Usuario = Depends(super_root)) -> ManifestoBackup:
    caminho = servico_backup.receber_envio(arquivo.file, arquivo.filename or "backup.zip")
    try:
        manifesto = servico_backup.iniciar_importacao(caminho, confirmacao, autor)
    except ErroBackup as erro:
        raise ErroApi(status.HTTP_400_BAD_REQUEST, str(erro), "invalido") from erro
    return ManifestoBackup(**{k: manifesto.get(k) for k in ManifestoBackup.model_fields})
