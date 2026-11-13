# Criado por José Eduardo Santana Martins
# Este arquivo serve para tirar os prints do manual da RDM: gerar e preencher, enviar, analisar (aprovar ou reprovar), reenviar e acompanhar.
import sys; sys.path.insert(0, ".")
from cap import *


def ir(pg, rota, seletor, espera=900):
    pg.goto(BASE + rota); pg.wait_for_selector(seletor, timeout=20000); pg.wait_for_timeout(espera)


def nova(nav, login):
    ctx = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    return ctx, entrar(ctx, login)


with sync_playwright() as p:
    nav, ctx = abrir(p)
    pg = entrar(ctx, "ana")
    # 1. A tarefa em andamento oferece "Gerar RDM"
    ir(pg, "/tarefas/1", ".acoes-pipeline")
    gerar = pg.locator(".acoes-pipeline a", has_text="Gerar RDM")
    foto(pg, "r01-gerar", [(pg.locator(".acoes-pipeline button", has_text="Entregar"), 1, "esq"), (gerar, 2, "esq")],
         legendas=["Entregar para validação: o caminho de sempre, só com um comentário", "Gerar RDM: quando a entrega é uma mudança no ambiente, abre o formulário da Requisição de Mudança"])
    # 2. O formulário: identificação
    ir(pg, "/tarefas/2/rdm", "#rdm-titulo")
    foto(pg, "r02-identificacao", [(".situacao-rdm .selo-status", 1, "dir"), ("#rdm-titulo", 2, "esq"), ("#rdm-tipo", 3, "esq"), ("#rdm-solicitante", 4, "esq")],
         legendas=["Situação da RDM: Rascunho enquanto não for enviada", "Assunto: vira o título da RDM (\"RDM SGI 00001/2026 - Assunto\")",
                   "Tipo: programada, pré-aprovada (rotineira) ou emergencial", "Requisitante, área e data já vêm preenchidos com os seus dados"])
    # 3. Objetivo, categorização
    foto(pg, "r03-objetivo", [("#rdm-objetivo", 1, "esq"), ("#rdm-justificativa", 2, "esq"), ("#rdm-risco", 3, "cima"), ("#rdm-impacto", 4, "cima")],
         rolar="#rdm-objetivo", legendas=["Objetivo: o que a mudança vai fazer", "Justificativa: por que ela é necessária",
                                         "Risco da mudança (alto, médio ou baixo)", "Impacto nos serviços (alto, médio ou baixo)"])
    # 4. Janela e plano de execução
    foto(pg, "r04-janela-plano", [("#rdm-ini-data", 1, "esq"), ("#rdm-fim-data", 2, "esq"), (pg.locator(".linha-rdm").first, 3, "esq"),
                                  (pg.locator("button", has_text="Adicionar atividade").first, 4, "dir")],
         rolar="#rdm-ini-data", legendas=["Início da janela de implantação (data e hora)", "Fim da janela", "Cada atividade do plano: o que será feito, quem faz e em que etapa",
                                         "Adicionar atividade: uma linha por passo, na ordem"])
    # 5. Rollback
    foto(pg, "r05-rollback", [(pg.locator("section.secao-tarefa", has_text="Plano de remediação").locator(".linha-rdm").first, 1, "esq"), ("#rdm-rb-just", 2, "esq")],
         rolar="#rdm-rb-just", legendas=["Plano de retorno (rollback): como voltar ao estado anterior se algo der errado, quanto tempo leva e quem faz",
                                         "Justificativa do rollback"])
    # 6. Complementares e envio
    foto(pg, "r06-complementares", [("#rdm-categoria", 1, "esq"), ("#rdm-riscos", 2, "esq")],
         rolar="#rdm-categoria", legendas=["Informações complementares: vão num anexo do PDF da RDM", "Riscos identificados (e, logo abaixo, as medidas preventivas, a validação e os critérios de sucesso)"])
    foto(pg, "r06b-prerequisitos", [(".lista-checks", 1, "esq")], rolar=".lista-checks",
         legendas=["Marque os pré-requisitos já atendidos (backup, configurações registradas, equipes comunicadas…)"])
    pg.locator("footer.acoes-formulario").last.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    foto(pg, "r07-enviar", [(pg.locator("button", has_text="Salvar rascunho"), 1, "cima"), (pg.locator("button", has_text="Enviar para aprovação"), 2, "cima")],
         legendas=["Salvar rascunho: guarda sem enviar (dá para continuar depois)", "Enviar para aprovação: a RDM ganha o número do Protocolo e a tarefa vai para Em validação"])
    ctx.close()

    # 7. A liderança: a tarefa com RDM pendente
    ctx, pg = nova(nav, "lia")
    ir(pg, "/tarefas/3", ".acoes-pipeline")
    foto(pg, "r08-analisar", [(pg.locator(".acoes-pipeline a", has_text="Analisar RDM"), 1, "esq"), (".selo-rdm", 2, "esq")],
         legendas=["Analisar RDM: abre o formulário para ler e decidir (no lugar de Validar e Devolver)", "O selo amarelo: RDM aguardando aprovação, com o número e o assunto"])
    ir(pg, "/tarefas/3/rdm", "#titulo-decisao-rdm")
    pg.locator("#titulo-decisao-rdm").scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    foto(pg, "r09-decisao", [("#rdm-motivo", 1, "esq"), (pg.locator("button", has_text="Reprovar RDM"), 2, "cima"), (pg.locator("button", has_text="Aprovar RDM"), 3, "cima")],
         legendas=["Motivo: obrigatório para reprovar", "Reprovar: a tarefa volta para Em andamento com o motivo; não gera PDF",
                   "Aprovar: gera o PDF, anexa à tarefa, envia o e-mail e a tarefa volta para Em andamento para executar a mudança"])
    # 8. A lista de RDMs
    ir(pg, "/tarefas/rdms", "tbody tr")
    foto(pg, "r12-lista", [(".chips-filtro", 1, "dir"), (pg.locator("tbody tr").first.locator("td").nth(3).locator(".selo-status"), 2, "dir"), (pg.locator("th").first, 3, "esq")],
         legendas=["Filtre pela situação", "Cada cor é uma situação: amarela aguardando, laranja aprovada, vermelha reprovada, verde concluída", "Clique no título da coluna para ordenar"])
    ctx.close()

    # 9. Aprovada (quem executa) e reprovada
    ctx, pg = nova(nav, "ana")
    ir(pg, "/tarefas/4/rdm", ".situacao-rdm")
    foto(pg, "r10-aprovada", [(".situacao-rdm .selo-status", 1, "baixo"), (pg.locator(".situacao-rdm button", has_text="Baixar PDF"), 2, "baixo")],
         legendas=["Aprovada (laranja): quem aprovou e quando", "Baixar PDF: o formulário da RDM no modelo da Prodesp (também anexado à tarefa e enviado por e-mail)"])
    ir(pg, "/tarefas/5/rdm", ".aviso-bloco")
    pg.locator("footer.acoes-formulario").last.scroll_into_view_if_needed(); pg.wait_for_timeout(200)
    pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); pg.wait_for_timeout(200)
    foto(pg, "r11-reprovada", [(".situacao-rdm .selo-status", 1, "esq"), (".aviso-bloco.erro", 2, "esq")],
         legendas=["Reprovada (vermelha)", "O motivo de quem reprovou: corrija o que foi pedido e envie de novo (o número continua o mesmo)"])
    ctx.close(); nav.close()
