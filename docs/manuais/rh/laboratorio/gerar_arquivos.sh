#!/bin/sh
# Gera, com o código do sistema, os arquivos de apoio dos prints: modelo.xlsx (formulário em branco) e doe.pdf (publicação fictícia no D.O.E.).
cd "$(dirname "$0")"; R=/home/administrador/projeto/backend
PYTHONPATH=$PWD:$R $R/.venv/bin/python -c "
import lab_env
from app.services.rh import importacao_pre_cadastro as ipc
from app.services.documentos.pdf import DocumentoPdf
open('modelo.xlsx','wb').write(ipc.modelo())
d = DocumentoPdf(titulo='Diário Oficial do Estado de São Paulo', subtitulo='Executivo – Seção I (exemplo fictício)', paisagem=False, autor='Laboratório')
d.paragrafo('RESOLUÇÃO SPI Nº 1, DE 2026 (EXEMPLO FICTÍCIO)'); d.paragrafo('Designa Mariana Costa Ribeiro para o cargo de Assessor Especial IV, na Subsecretaria de Gestão Corporativa.')
open('doe.pdf','wb').write(d.gerar()); print('arquivos gerados')"
