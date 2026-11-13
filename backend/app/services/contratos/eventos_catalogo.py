"""
===============================================================================
ARQUIVO: eventos_catalogo.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Traduzir cada ação gravada na auditoria de um contrato (ex.:
"contrato.reajuste.concluir") para um nome em linguagem de usuário e uma
categoria da aba "Eventos" do contrato.

RESUMO TÉCNICO:
- `ROTULOS`: ação → rótulo (as mais comuns, escritas à mão).
- `categoria(acao)`: regra por prefixo (execução, documentos, equipe e
  cadastro, sem efeito; o resto altera o contrato).
- `rotulo(acao)`: o rótulo do dicionário ou, na falta, um rótulo montado a
  partir das partes da ação (ex.: "Reajuste · evidencia").
- `CATEGORIAS`: as categorias na ordem dos chips da tela.

FINALIDADE DE NEGÓCIO:
Quem administra contratos (Controle total) vê tudo o que aconteceu num
contrato, separado em categorias e com nomes que um usuário entende.

CONTEXTO NO SISTEMA:
Usado por servico_eventos.py (rota GET /contratos/{id}/eventos).

===============================================================================
"""

# Categorias da aba Eventos, na ordem dos chips (a primeira é a escolhida ao abrir)
CATEGORIAS = {
    "altera_contrato": "Alteram o contrato",
    "execucao": "Execução",
    "documentos": "Documentos",
    "equipe_cadastro": "Equipe e cadastro",
    "sem_efeito": "Sem efeito",
}

# Nomes das ações mais comuns (as demais recebem um nome montado em `rotulo`)
ROTULOS = {
    "contrato.criar": "Contrato cadastrado",
    "contrato.alterar": "Contrato alterado",
    "contrato.excluir": "Contrato excluído",
    "contrato.importar_xlsx": "Contrato importado de planilha",
    "contrato.itens.alterar": "Itens alterados",
    "contrato.item.corrigir_descricao": "Descrição de item corrigida",
    "contrato.itens.correcao.propor": "Correção de itens proposta",
    "contrato.itens.correcao.confirmar": "Correção de itens aplicada",
    "contrato.itens.correcao.recusar": "Correção de itens recusada",
    "contrato.itens.correcao.cancelar": "Correção de itens cancelada",
    "contrato.prorrogacao.salvar": "Prorrogação: rascunho salvo",
    "contrato.prorrogacao.ciencia": "Prorrogação: ciência registrada",
    "contrato.prorrogacao.descartar": "Prorrogação: rascunho descartado",
    "contrato.prorrogacao.registrar": "Prorrogação registrada",
    "contrato.prorrogacao.desfazer": "Prorrogação tornada sem efeito",
    "contrato.vigencia_retroativa.registrar": "Vigência retroativa registrada",
    "contrato.vigencia_retroativa.desfazer": "Vigência retroativa tornada sem efeito",
    "contrato.reajuste.abrir": "Reajuste aberto",
    "contrato.reajuste.memoria": "Reajuste: memória salva",
    "contrato.reajuste.memoria.gerar": "Reajuste: memória gerada",
    "contrato.reajuste.evidencia": "Reajuste: evidência do índice anexada",
    "contrato.reajuste.concluir": "Reajuste concluído",
    "contrato.reajuste.cancelar": "Reajuste cancelado",
    "contrato.reajuste.sem_efeito": "Reajuste tornado sem efeito",
    "contrato.reajuste.modo_retroativo": "Reajuste: cálculo manual ou automático escolhido",
    "contrato.reajuste.diferenca_manual.gravar": "Reajuste: diferença manual informada",
    "contrato.reajuste.diferenca_manual.remover": "Reajuste: diferença manual removida",
    "contrato.repactuacao.abrir": "Repactuação aberta",
    "contrato.repactuacao.linhas": "Repactuação: itens salvos",
    "contrato.repactuacao.memoria": "Repactuação: memória gerada",
    "contrato.repactuacao.mes_quebrado": "Repactuação: cálculo do mês quebrado escolhido",
    "contrato.repactuacao.modo_retroativo": "Repactuação: cálculo manual ou automático escolhido",
    "contrato.repactuacao.diferenca_manual.gravar": "Repactuação: diferença manual informada",
    "contrato.repactuacao.diferenca_manual.remover": "Repactuação: diferença manual removida",
    "contrato.repactuacao.consolidado": "Repactuação: consolidado gerado",
    "contrato.repactuacao.finalizar": "Repactuação concluída",
    "contrato.repactuacao.cancelar": "Repactuação cancelada",
    "contrato.repactuacao.sem_efeito": "Repactuação tornada sem efeito",
    "contrato.repactuacao.excluir_correcao": "Repactuação excluída (correção de dados)",
    "contrato.aditamento.abrir": "Aditamento aberto",
    "contrato.aditamento.concluir": "Aditamento concluído",
    "contrato.aditamento.cancelar": "Aditamento cancelado",
    "contrato.aditamento.sem_efeito": "Aditamento tornado sem efeito",
    "contrato.supressao.abrir": "Supressão aberta",
    "contrato.supressao.concluir": "Supressão concluída",
    "contrato.supressao.cancelar": "Supressão cancelada",
    "contrato.supressao.sem_efeito": "Supressão tornada sem efeito",
    "contrato.equipe.alterar": "Equipe alterada",
    "contrato.equipe.ajustar": "Equipe ajustada",
    "contrato.documento.enviar": "Documento importante enviado",
    "contrato.documento.limpar": "Documento importante retirado",
    "contrato.nota_empenho.criar": "Nota de empenho cadastrada",
    "contrato.nota_empenho.alterar": "Nota de empenho alterada",
    "contrato.nota_empenho.cancelar": "Nota de empenho cancelada",
    "contrato.nota_empenho.excluir": "Nota de empenho excluída",
    "contrato.previsao.salvar": "Previsão orçamentária salva",
    "contrato.execucao.gerar": "Competências geradas",
    "contrato.execucao.medicao.salvar": "Medição salva",
    "contrato.execucao.medicao.ciencia": "Ciência na medição",
    "contrato.execucao.medicao.concluir": "Medição concluída",
    "contrato.execucao.avaliacao.concluir": "Avaliação concluída",
    "contrato.execucao.avaliacao.ciencia_ateste": "Ciência no ateste",
    "contrato.execucao.nota_fiscal.concluir": "Nota fiscal concluída",
    "contrato.execucao.retencao": "Retenção de tributos conferida",
    "contrato.execucao.retencao.recusar": "Retenção de tributos recusada",
    "contrato.execucao.cadin": "CADIN registrado",
    "contrato.execucao.checklist.concluir": "Checklist da competência concluído",
    "contrato.execucao.consolidado": "Consolidado da competência gerado",
    "contrato.execucao.ordem_bancaria": "Ordem bancária registrada",
    "contrato.execucao.ordem_bancaria.sigeo": "Ordem bancária importada do SIGEO",
    "contrato.execucao.reabrir": "Competência reaberta",
    "contrato.execucao.zerar": "Medição zerada",
    "contrato.execucao.adicional.incluir": "Medição adicional incluída",
    "contrato.execucao.adicional.excluir": "Medição adicional excluída",
    "contrato.execucao.credito.aplicar": "Crédito aplicado na medição",
    "contrato.execucao.credito.retirar": "Crédito retirado da medição",
    "contrato.diario.registrar": "Ocorrência no diário de bordo",
    "portaria.solicitar": "Portaria de designação solicitada",
    "portaria.criar": "Portaria de designação criada",
    "portaria.publicar": "Portaria de designação publicada",
    "portaria.cancelar": "Portaria de designação cancelada",
}

# Nomes das partes, para montar o rótulo das ações sem nome no dicionário
PARTES = {
    "contrato": "", "execucao": "Execução", "checklist": "Checklist", "formulario": "Formulário de avaliação", "diario": "Diário de bordo",
    "reajuste": "Reajuste", "repactuacao": "Repactuação", "prorrogacao": "Prorrogação", "aditamento": "Aditamento", "supressao": "Supressão",
    "portaria": "Portaria", "nota_empenho": "Nota de empenho", "previsao": "Previsão orçamentária", "equipe": "Equipe", "rascunho": "Rascunho",
    "processo_financeiro": "Processo financeiro", "migracao_sgi": "Migração do SGI antigo", "sgi": "SGI antigo",
}


def categoria(acao: str) -> str:
    """Categoria da aba Eventos para a ação (chave de `CATEGORIAS`)."""
    if acao.endswith(".sem_efeito") or acao in ("contrato.prorrogacao.desfazer", "contrato.vigencia_retroativa.desfazer"):
        return "sem_efeito"
    if acao.startswith(("contrato.execucao.", "sgi.contract.execution.")):
        return "execucao"
    if acao.startswith(("contrato.documento.", "contrato.checklist.", "contrato.formulario.", "contrato.diario.", "sgi.contract.document.")):
        return "documentos"
    if acao.startswith(("contrato.equipe.", "contrato.empresa.", "contrato.preposto.", "contrato.nota_empenho.", "contrato.previsao.",
                        "contrato.processo_financeiro.", "contrato.rascunho.")):
        return "equipe_cadastro"
    return "altera_contrato"


def rotulo(acao: str) -> str:
    """Nome da ação em linguagem de usuário."""
    if acao in ROTULOS:
        return ROTULOS[acao]
    partes = [p for p in acao.split(".") if p not in ("contrato", "contract")]
    nomes = [PARTES.get(p, p.replace("_", " ")) for p in partes]
    texto = " · ".join(n for n in nomes if n)
    return (texto[:1].upper() + texto[1:]) if texto else acao


# Ações de conclusão que podem ser tornadas sem efeito: ação → segmento da URL do tipo
CONCLUSOES = {
    "contrato.reajuste.concluir": "reajustes",
    "contrato.repactuacao.finalizar": "repactuacoes",
    "contrato.aditamento.concluir": "alteracoes",
    "contrato.supressao.concluir": "alteracoes",
    "contrato.prorrogacao.registrar": "prorrogacoes",
    "contrato.vigencia_retroativa.registrar": "vigencias-retroativas",
}
