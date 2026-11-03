# Criado por José Eduardo Santana Martins
# Este arquivo serve para tirar os prints do manual da administração dos Chamados (Parâmetros) e do plano de face da rede.
import sys; sys.path.insert(0, ".")
from cap import *


def ir(pg, rota, seletor, espera=900):
    pg.goto(BASE + rota); pg.wait_for_selector(seletor, timeout=20000); pg.wait_for_timeout(espera)


def aba(pg, nome):
    pg.get_by_role("tab", name=nome, exact=True).click(); pg.wait_for_timeout(700)


with sync_playwright() as p:
    nav, ctx = abrir(p)
    pg = entrar(ctx, "carla")
    ir(pg, "/chamados/parametros", "[role=tablist]")
    aba(pg, "Categorias")
    foto(pg, "c01-categorias", [("[role=tablist]", 1, "cima"), ("#pc-nome", 2, "esq"), (pg.locator("tbody tr").first, 3, "esq")],
         legendas=["Uma aba para cada assunto da configuração", "Cria uma categoria (ou subcategoria, escolhendo a categoria-mãe): setor responsável, prazos e prioridade",
                   "A árvore de categorias; a subcategoria herda o setor e os prazos da mãe quando ficam em branco"])
    aba(pg, "SLAs")
    foto(pg, "c02-slas", [(pg.locator("form").first, 1, "esq")], legendas=["Prazo de atendimento (até alguém assumir) ou de solução, em minutos, horas ou dias úteis do expediente"])
    aba(pg, "Expedientes")
    foto(pg, "c03-expedientes", [(pg.locator("form").first, 1, "esq")], legendas=["Os horários de trabalho que contam no prazo; feriados vêm do calendário do RH"])
    aba(pg, "Status")
    foto(pg, "c04-status", [(pg.locator("form, table").first, 1, "esq")], legendas=["Nome e cor de cada situação, e os sub-status (ex.: \"Aguardando peça\")"])
    aba(pg, "Recorrentes")
    foto(pg, "c05-recorrentes", [("#pr-nome", 1, "esq"), (pg.locator("tbody tr").first, 2, "esq")],
         legendas=["Chamado que se abre sozinho a cada período (ex.: conferir os backups todo dia útil)", "Próxima ocorrência e a última gerada"])
    aba(pg, "Respostas prontas")
    foto(pg, "c06-respostas", [("#prp-titulo", 1, "esq"), ("#prp-setor", 2, "esq")],
         legendas=["Título que aparece na lista de quem atende", "Sem setor, vale para todos; com setor, só para quem atende aquele setor"])
    aba(pg, "Motivos de pendência")
    foto(pg, "c07-motivos", [("#pmo-nome", 1, "esq")], legendas=["Motivos para escolher ao pôr um chamado em pendente"])
    aba(pg, "Painel")
    foto(pg, "c10-painel", [("#pp-linhas", 1, "esq"), ("#pp-tamanho", 2, "baixo"), (pg.locator("fieldset").first, 3, "esq"), (pg.locator("input[name=cor-linha]"), 4, "esq")],
         legendas=["Linhas por página: 0 = automático (quantas couberem na tela)", "Tamanho do texto: compacto cabe mais chamados; grande é para ler de longe",
                   "Colunas que aparecem (o título é obrigatório)", "Cor do prazo na linha inteira ou só no selo; logo abaixo, a voz que anuncia chamado novo"])
    aba(pg, "RH")
    foto(pg, "c08-rh", [("#prh-destino", 1, "esq"), (pg.locator("form select").nth(1), 2, "esq")],
         legendas=["Para onde vão os chamados do RH: GLPI (como hoje) ou os Chamados do SGI", "A categoria de cada serviço da Nomeação; mais abaixo, os da Exoneração (o inverso de cada um)"])
    pg.get_by_role("tab", name="Saúde").click(); pg.wait_for_timeout(900)
    foto(pg, "c09-saude", [(pg.locator("table").first, 1, "esq")],
         legendas=["As tarefas automáticas (prazos, recorrentes) e a fila de e-mails: se algo parar, aparece aqui e quem administra é avisado no sino"])
    ctx.close()

    ctx = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pg = entrar(ctx, "joao")
    ir(pg, "/rede", ".rack-equipamento")
    foto(pg, "n01-racks", [(pg.locator(".rack-equipamento").filter(has_text="SW-05A"), 1, "dir"), (pg.locator("app-rack-rede header").first, 2, "dir"),
                           (pg.locator(".rack-u").first, 3, "esq")],
         legendas=["Cada equipamento na posição do rack, com as portas ligadas (verde) e desligadas (vermelho). Clique para abrir a face",
                   "O rack: nome, sala do Patrimônio e quantidade de U (a faixa da esquerda tem a cor do rack)", "Numeração dos U (U1 embaixo)"])
    pg.locator(".rack-equipamento").filter(has_text="SW-05A").click(); pg.wait_for_selector(".porta-face", timeout=20000); pg.wait_for_timeout(800)
    foto(pg, "n02-face", [(pg.locator(".porta-face[data-estado=up]").first, 1, "cima"), (pg.locator(".porta-face[data-estado=down]").first, 2, "baixo"),
                          (pg.locator(".face-extras"), 3, "dir")],
         legendas=["Porta verde: ligada", "Porta vermelha: desligada (a bolinha âmbar indica chamado aberto na porta)", "Portas de uplink e fibra, fora da grade"])
    pg.locator(".porta-face").nth(4).click(); pg.wait_for_selector("#rp-config", timeout=20000); pg.wait_for_timeout(800)
    foto(pg, "n03-porta", [("#rp-modo", 1, "esq"), (pg.locator("aside .cartao-chamado").nth(1), 2, "esq"), (pg.locator("#rp-chamados"), 3, "esq"),
                           (pg.get_by_role("link", name="Abrir chamado desta porta"), 4, "esq")],
         legendas=["Configuração da porta: access ou trunk, VLAN, situação e velocidade (é o cadastro; o SGI não mexe no switch)",
                   "O que está ligado: aqui, uma impressora do Patrimônio (clique para abrir o cadastro do bem). Dá para ligar um bem, outro equipamento ou descrever",
                   "Chamados desta porta e do ponto de rede ligado nela", "Abre um chamado já ligado a esta porta"], cheia=True)
    # O cadastro do bem é do Patrimônio: o print sai com o administrador (o técnico de exemplo não tem acesso ao Patrimônio)
    from cliente import chamar, login
    bem_id = chamar("GET", "/rede/bens?busca=012345", login("root", "senha-teste"))[0]["id"]
    ctx_adm = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    adm = entrar(ctx_adm, "root", "senha-teste")
    adm.goto(BASE + f"/patrimonio/bens/{bem_id}"); adm.wait_for_selector("app-rede-do-bem .rede-do-bem-linha", timeout=20000); adm.wait_for_timeout(900)
    foto(adm, "n05-bem", [(adm.locator("app-rede-do-bem .rede-do-bem-linha"), 1, "esq")], rolar="app-rede-do-bem",
         legendas=["No cadastro do bem (Patrimônio): em qual switch e porta ele está ligado. Quem edita a rede liga ou desliga daqui mesmo"])
    # Novo rack e novo equipamento: só quem administra a rede
    adm.goto(BASE + "/rede"); adm.wait_for_selector(".rack-equipamento", timeout=20000)
    adm.get_by_role("button", name="Novo equipamento").click(); adm.wait_for_timeout(500)
    foto(adm, "n06-novo-equipamento", [("#re-modelo", 1, "esq"), ("#re-rack", 2, "esq"), ("#re-u", 3, "dir")],
         legendas=["O modelo de face: as portas são criadas por ele", "O rack, já cadastrado em \"Novo rack\"", "A posição: o U mais baixo que ele ocupa (não pode sobrepor outro equipamento)"])
    adm.get_by_role("button", name="Cancelar").click(); adm.get_by_role("button", name="Novo rack").click(); adm.wait_for_timeout(500)
    foto(adm, "n07-novo-rack", [("#rk-cor", 1, "esq"), ("#rk-altura", 2, "esq"), ("#rk-busca-sala", 3, "esq")],
         legendas=["Cor do rack, para reconhecer na sala", "Quantidade de U", "Localização: a sala do Patrimônio (busque pelo código, como 05A)"])
    ctx_adm.close()
    ir(pg, "/rede/cadastros", "#pt-codigo")
    foto(pg, "n04-pontos", [("#pt-codigo", 1, "esq"), (pg.locator("tbody tr").first.locator("td").nth(2), 2, "esq")],
         legendas=["O código escrito na tomada", "O caminho do ponto até o switch: tomada → patch panel → porta do switch"])
    ctx.close(); nav.close()
