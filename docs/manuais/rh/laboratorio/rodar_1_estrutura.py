# Prints do manual: acesso ao módulo, setores, cargos, organograma, visão das vagas, histórico e busca.
import sys; sys.path.insert(0, ".")
from cap import *
import api


def ir(pg, rota, espera=800):
    pg.goto(BASE + rota); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(espera)


def id_de(login, tok):
    return next(u["id"] for u in api.chamar("GET", f"/usuarios/opcoes?busca={login}", tok) if u["login"] == login)


with sync_playwright() as p:
    nav, ctx = abrir(p)
    pg = entrar(ctx, "rita")

    # 1. Atalhos do módulo
    ir(pg, "/rh/ferias")
    foto(pg, "h01-atalhos", [("nav[aria-label='Atalhos do Módulo RH']", 1, "cima")],
         legendas=["Os atalhos do módulo RH. Setores, Cargos, Pré-cadastro, Admissões e Modelos aparecem para quem tem acesso ao RH; Organograma e Meu cadastro, para todos."])

    # 2. Setores
    ir(pg, "/rh/setores")
    foto(pg, "s01-setores-lista", [(pg.locator(".barra-ferramentas button.acao-primaria"), 1, "esq"), (pg.locator("th:has-text('Tipo')").first, 2, "cima"),
                                   (pg.locator(".tabela-gestao tbody tr").first.locator("td").first.locator("small").first, 3, "dir"), (pg.locator(".tabela-gestao tbody tr").first.get_by_role("button", name="Editar"), 4, "baixo")],
         legendas=["Cria um setor novo", "Origem do setor: institucional (estrutura da SPI) ou grupo sistêmico (só para dar acesso)", "Sigla e tipo da unidade, para rotular o organograma", "Edita o setor: nome, setor pai, líder, sigla, tipo e membros"])
    pg.get_by_role("button", name="Novo setor").click(); pg.wait_for_timeout(600)
    foto(pg, "s02-setor-formulario", [("#setor-nome", 1, "esq"), ("#setor-pai", 2, "esq"), ("#setor-tipo", 3, "dir"), ("#setor-sigla", 4, "esq")],
         legendas=["Nome do setor (único)", "Setor pai: define onde ele fica na hierarquia (sem ciclos)", "Tipo da unidade: secretaria, subsecretaria, diretoria, coordenadoria, serviço, assessoria, colegiado, vinculada ou outro", "Sigla (ex.: SGC), usada no organograma"])
    pg.keyboard.press("Escape")

    # 3. Cargos
    ir(pg, "/rh/cargos")
    foto(pg, "c01-cargos-lista", [(pg.locator(".abas"), 1, "esq"), (pg.locator("select[aria-label='Setor']"), 2, "cima"), (pg.locator(".chips-filtro").first, 3, "esq"),
                                  (pg.locator(".tabela-gestao tbody tr").nth(1).locator("td").nth(2), 4, "dir"), (pg.locator(".barra-ferramentas button.acao-primaria"), 5, "esq")],
         legendas=["Duas abas: Cargos e vagas, e A reconciliar (quem ainda tem o cargo escrito à mão)", "Filtros por setor, tipo e busca por cargo, setor ou pessoa", "Todos, só Vagos ou só Ocupados", "Quem ocupa o cargo (o nome abre o histórico funcional) ou o selo Vago", "Cria cargos novos, até em lote"])
    pg.get_by_role("button", name="Novo cargo").click(); pg.wait_for_timeout(500)
    foto(pg, "c02-novo-cargo", [("#cargo-setor", 1, "esq"), ("#cargo-tipo", 2, "esq"), ("#cargo-grupo", 3, "dir"), ("#cargo-nivel", 4, "esq"), ("#cargo-quantidade", 5, "dir"), ("#cargo-denominacao", 6, "esq")],
         legendas=["Setor onde a vaga fica", "Tipo: CCESP (cargo em comissão), FCESP (função de confiança) ou Outros", "Grupo 1 (direção e chefia) ou 2 (assessoria)", "Nível de 1 a 18: grupo e nível formam a classificação (ex.: 2.16)", "Quantas vagas iguais criar de uma vez", "Denominação, como Assessor Especial IV"])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.get_by_role("button", name="Vagos").click(); pg.wait_for_timeout(700)
    pg.get_by_role("button", name="Alocar").first.click(); pg.wait_for_timeout(500)
    pg.locator("#ocupar-inicio").fill("2026-11-03"); pg.locator("#ocupar-ato").fill("Resolução SPI 12/2026")
    foto(pg, "c03-alocar", [("#ocupar-pessoa", 1, "esq"), ("#ocupar-inicio", 2, "esq"), ("#ocupar-ato", 3, "dir")],
         legendas=["Pessoa que assume a vaga. Se já ocupa outro cargo, aquele é encerrado como troca e ela passa a fazer parte do setor do novo cargo", "Data da posse", "Ato: resolução ou portaria da nomeação"])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.get_by_role("button", name="Ocupados").click(); pg.wait_for_timeout(700)
    pg.get_by_role("button", name="Vagar").first.click(); pg.wait_for_timeout(500)
    pg.select_option("#vagar-motivo", "exoneracao"); pg.locator("#vagar-fim").fill("2026-11-30"); pg.locator("#vagar-ato").fill("Resolução SPI 15/2026")
    foto(pg, "c04-vagar", [("#vagar-motivo", 1, "esq"), ("#vagar-fim", 2, "esq"), ("#vagar-ato", 3, "dir"), (pg.locator(".modal-portal footer button[type=submit]"), 4, "cima")],
         legendas=["Motivo da saída: troca, exoneração, dispensa ou outro", "Data de saída", "Ato da exoneração (publicado)", "Com Exoneração o botão fica vermelho: a vaga volta a ficar livre e o histórico da pessoa registra a exoneração"])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.get_by_role("tab", name="A reconciliar").click(); pg.wait_for_timeout(700)
    foto(pg, "c05-a-reconciliar", [(pg.locator(".tabela-gestao tbody tr").first.locator("td").nth(1), 1, "esq"), (pg.locator(".tabela-gestao tbody tr").first.locator("td").nth(3), 2, "esq"), (pg.locator(".tabela-gestao tbody tr").first.get_by_role("button"), 3, "cima")],
         legendas=["Cargo como estava escrito no cadastro antigo", "O que o sistema vai criar ao interpretar o texto (tipo, grupo, nível e denominação)", "Cria o cargo no setor da pessoa e já a aloca nele"])

    # 4. Organograma
    ir(pg, "/rh/organograma", 1500)
    pg.get_by_role("button", name="Árvore").click(); pg.wait_for_timeout(1200)
    foto(pg, "o01-arvore", [(pg.locator(".organograma-barra .chips-filtro").first, 1, "dir"), (pg.locator(".organograma-zoom"), 2, "baixo"), (pg.locator(".caixa-org").nth(2), 3, "dir"), (pg.locator(".recolher-org").first, 4, "dir")],
         legendas=["Vagas, Recolher e Expandir: mostra ou esconde as vagas e as unidades subordinadas", "Zoom: − e + (ou o scroll do mouse); a porcentagem volta a 100% e Ajustar mostra tudo; arraste para mover", "Cada cartão é uma unidade: tipo, nome, líder e quantos cargos estão ocupados; clique para ver as pessoas", "Recolhe ou expande as unidades abaixo desta"])
    pg.get_by_role("button", name="Vertical").click(); pg.wait_for_timeout(1000)
    foto(pg, "o02-vertical", [(pg.locator(".organograma-barra .chips-filtro").nth(1), 1, "dir"), (pg.locator(".caixa-org").nth(1), 2, "dir")],
         legendas=["Árvore ou Vertical: a vertical é a melhor no celular e fica como padrão", "As unidades subordinadas ficam recuadas sob a linha-guia"])
    pg.locator(".caixa-org .titulo-org", has_text="Coordenadoria de Gestão de Pessoas").first.click(); pg.wait_for_timeout(700)
    foto(pg, "o03-unidade", [(pg.locator(".rotulo-lider").first, 1, "dir"), (pg.locator(".lider-lista"), 2, "dir"), (pg.locator(".posicoes-org").nth(1), 3, "dir")],
         legendas=["O líder da unidade (campo líder do setor)", "Foto, nome e cargo; clique para abrir o cartão de contato", "Cargos da unidade: quem ocupa (com foto) e, para o RH e a liderança, as vagas"])
    pg.locator(".lider-lista .pessoa-org").first.click(); pg.wait_for_timeout(900)
    foto(pg, "o04-cartao", [(pg.locator(".detalhe-contato .identidade-detalhe").first, 1, "dir")], legendas=["O cartão de contato da pessoa (o mesmo do Diretório): foto, cargo, setor, ramal, chefia e equipe"])
    pg.keyboard.press("Escape"); pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    ir(pg, "/rh/organograma", 1200)
    foto(pg, "o05-vagas-rh", [(pg.locator(".caixa-org small").nth(2), 1, "dir")], legendas=["Para o RH, a contagem inclui as vagas (ex.: 2/4 ocupadas: 2 vagas livres)"])

    # Visão de quem não é do RH
    ctx2 = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")  # outra sessão: pessoa comum
    pg2 = entrar(ctx2, "pedro")
    ir(pg2, "/rh/organograma", 1500)
    foto(pg2, "o06-vagas-comum", [(pg2.locator(".caixa-org small").nth(2), 1, "dir"), (pg2.locator("nav[aria-label='Atalhos do Módulo RH']"), 2, "baixo")],
         legendas=["Para quem não é do RH nem lidera o setor, as vagas não aparecem: as contagens trazem só os cargos ocupados", "Os atalhos de gestão (Setores, Cargos, Pré-cadastro...) também não aparecem"])

    # 5. Histórico funcional (a pessoa vista pelo RH)
    tok = api.login("rita")
    ir(pg, f"/rh/historico/{id_de('lucas', tok)}", 1000)
    foto(pg, "hf01-historico", [(pg.get_by_role("button", name="Exportar PDF"), 1, "esq"), (pg.locator(".chips-filtro"), 2, "esq"), (pg.locator("h3:has-text('Cargos e setores') + .tabela-gestao-envoltorio"), 3, "esq"),
                                (pg.locator("h3:has-text('Linha do tempo') + .tabela-gestao-envoltorio"), 4, "esq")],
         legendas=["Exporta o histórico em PDF, com os mesmos filtros da tela", "Filtros por tipo de fato (cadastro, cargo, setor, férias, licença-prêmio, exoneração...) e por período", "Cargos e setores por onde a pessoa passou, com início, fim e o ato", "Linha do tempo: cada fato mostra quando aconteceu e quem o registrou (nome e data e hora)"])

    # 6. Busca na lista de usuários (administração): acha a pessoa e quem ela chefia
    ctx3 = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pg3 = entrar(ctx3, "root", "senha-teste")
    ir(pg3, "/usuarios", 1000)
    campo = pg3.locator("input[placeholder^='Pesquisar por nome']").first
    campo.fill("Sofia"); pg3.wait_for_timeout(1500)
    foto(pg3, "hf02-busca-usuarios", [(campo, 1, "esq"), (pg3.locator("table tbody tr").first, 2, "esq"), (pg3.locator("table tbody tr").nth(1), 3, "esq")],
         legendas=["A busca procura em várias informações: nome, login, cargo, setor, chefia imediata e mediata, e a bio liberada", "Quem tem o nome pesquisado vem primeiro", "Depois vêm as pessoas que casaram pela chefia (aqui, quem tem a Sofia como líder do setor)"])
    nav.close()
