# Prints do manual: acesso (ACL), modelos e checklists, primeiro acesso, Meu cadastro (bio e ficha dos legados), validação do RH e bio no cartão.
import subprocess, sys; sys.path.insert(0, ".")
from cap import *


def ir(pg, rota, espera=800):
    pg.goto(BASE + rota); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(espera)


def novo_contexto(nav):
    return nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")


with sync_playwright() as p:
    nav, ctx = abrir(p)

    # Acesso ao módulo (Controle de acesso, recurso RH)
    root = entrar(novo_contexto(nav), "root", "senha-teste")
    ir(root, "/admin/acl", 1000)
    root.get_by_role("tab", name="Recursos").click(); root.wait_for_timeout(900)
    foto(root, "h02-acesso-rh", [(root.locator("tbody tr").nth(1).locator("td").first, 1, "esq"), (root.locator("tbody tr").nth(1).locator("td").nth(3), 2, "dir")],
         legendas=["O recurso RH no Controle de acesso: quem é o RH deixou de ser \"quem está num setor\" e passou a ser definido aqui, por regra direta, por setor ou por perfil", "O que cada nível libera: Consultar a estrutura (leitura), Gerir setores e cargos (modificação) e Ser o RH do sistema (controle total: valida cadastros, fichas, admissões, modelos e parâmetros)"])

    pg = entrar(ctx, "rita")
    # Modelos e checklists
    ir(pg, "/rh/modelos", 1000)
    foto(pg, "m01-modelos-textos", [(pg.locator(".abas"), 1, "esq"), (pg.locator(".cartao-dados").first, 2, "esq"), (pg.get_by_role("button", name="Editar").first, 3, "cima")],
         legendas=["Duas abas: os textos e os checklists de documentos", "Quatro textos editáveis: resolução de nomeação, e-mail \"Sua nomeação foi publicada\", termo de posse e boas-vindas. Cada um nasce com um texto padrão", "Abre o editor do texto"])
    pg.get_by_role("button", name="Editar").nth(1).click(); pg.wait_for_timeout(2500)
    foto(pg, "m02-editor-modelo", [("#ass-email_nomeacao_publicada", 1, "esq"), (pg.locator(".editor-rico").first, 2, "esq"), (pg.locator("details.nota-explicativa summary"), 3, "esq"), (pg.get_by_role("button", name="Restaurar o texto padrão"), 4, "cima"), (pg.get_by_role("button", name="Salvar", exact=True), 5, "cima")],
         legendas=["Assunto do e-mail (só nos modelos de e-mail)", "Texto no editor, com negrito, listas, tabelas e cores", "Lista dos placeholders permitidos (clique para abrir)", "Volta ao texto padrão do sistema", "Salva: vale para as próximas admissões"], rolar="#mod-email_nomeacao_publicada")
    pg.get_by_text("Placeholders permitidos").click(); pg.wait_for_timeout(400)
    foto(pg, "m02b-placeholders", [(pg.locator("details.nota-explicativa ul"), 1, "esq")],
         legendas=["Os placeholders são trocados pelos dados da pessoa na hora de gerar o PDF ou o e-mail: #nome, #cpf, #rg, #cargo, #setor, #datainicio, #dataposse, #numeroresolucao, #anoresolucao, #datapublicacao, #hoje e outros. Qualquer outro # é recusado ao salvar"], rolar="details.nota-explicativa")
    pg.get_by_role("tab", name="Checklists de documentos").click(); pg.wait_for_timeout(800)
    foto(pg, "m03-checklists", [(pg.get_by_role("button", name="Novo checklist"), 1, "esq"), (pg.locator("th:has-text('Vale para')"), 2, "cima"), (pg.locator("tbody tr").first.get_by_role("button", name="Editar"), 3, "cima")],
         legendas=["Cria um checklist de documentos", "A quais classificações de cargo o checklist vale (ex.: 1.15–1.18 ou 2.04–2.17)", "Edita o checklist"])
    pg.locator("tbody tr").first.get_by_role("button", name="Editar").click(); pg.wait_for_timeout(700)
    foto(pg, "m04-checklist-classificacoes", [("#ck-nome", 1, "esq"), (pg.locator(".bloco-classificacao").nth(1), 2, "esq"), (pg.get_by_role("button", name="Todos").nth(1), 3, "cima"), (pg.get_by_label("Também vale para cargos sem classificação (Outros)"), 4, "esq"), (pg.locator(".item-checklist").first, 5, "esq")],
         legendas=["Nome do checklist", "Grupo 1 (direção e chefia) e Grupo 2 (assessoria): clique nos níveis a que ele vale. Cada chip é uma classificação, como 1.15 ou 2.10", "Marca ou desmarca todos os níveis do grupo", "Também vale para cargos sem classificação (tipo Outros)", "Documentos exigidos: obrigatórios ou opcionais; a admissão copia os do cargo da pessoa"])
    pg.keyboard.press("Escape")

    # Primeiro acesso de quem acabou de ganhar a conta (Mariana)
    mar = nav.new_context(viewport={"width": 1366, "height": 860}, locale="pt-BR", timezone_id="America/Sao_Paulo")
    pgm = mar.new_page(); pgm.goto(BASE + "/login"); pgm.wait_for_load_state("networkidle")
    pgm.fill("input[name=login], #login, input[autocomplete=username]", "mariana.ribeiro"); pgm.fill("input[type=password]", "senha-lab-1"); pgm.keyboard.press("Enter")
    pgm.wait_for_selector("#titulo-boas-vindas", timeout=20000); pgm.wait_for_timeout(800)
    foto(pgm, "u01-boas-vindas", [("#titulo-boas-vindas", 1, "esq"), (pgm.locator(".corpo-janela-mensagem"), 2, "esq"), (pgm.get_by_role("button", name="Completar meu cadastro"), 3, "cima")],
         legendas=["O aviso aparece só no primeiro acesso de quem acabou de ganhar a conta (quem já usava o sistema nunca o vê). O mesmo texto também vai por e-mail", "Texto do modelo \"Boas-vindas\" (RH › Modelos), com o nome, o cargo e o setor da pessoa", "Leva ao cadastro (Meu perfil) para a pessoa conferir os dados"])
    pgm.get_by_role("button", name="Completar meu cadastro").click(force=True); pgm.wait_for_timeout(1500)
    subprocess.run(["/home/administrador/projeto/backend/.venv/bin/python", "lab_perfil.py", "mariana.ribeiro"], env={**os.environ, "PYTHONPATH": "/home/administrador/projeto/backend:."}, capture_output=True)
    ir(pgm, "/rh/meu-cadastro", 1200)
    pgm.wait_for_selector("#bio-texto", timeout=15000)
    pgm.fill("#bio-texto", "Servidora de carreira há 12 anos, formada em Administração Pública. Já trabalhei com planejamento e parcerias, e gosto de trilhas e de fotografia.")
    pgm.wait_for_selector(".opcoes-parametros label.opcao input:not([disabled])", timeout=8000); pgm.locator(".opcoes-parametros label.opcao input").first.evaluate("e => e.click()"); pgm.wait_for_timeout(300)
    foto(pgm, "u02-meu-cadastro-bio", [("#bio-texto", 1, "esq"), (pgm.locator(".opcoes-parametros label.opcao").first, 2, "esq"), (pgm.get_by_role("button", name="Salvar bio"), 3, "cima"), (pgm.locator(".aviso-bloco").first, 4, "esq")],
         legendas=["Bio opcional: idade, formação, experiências, o que quiser contar", "Só se esta caixa estiver marcada a bio aparece para os colegas, na busca de usuários e no cartão de contato. Sem marcar, só a própria pessoa a vê", "Salva a bio", "Quem entrou pela admissão tem a ficha cadastrada pelo RH: ela aparece abaixo só para consulta"])
    pgm.get_by_role("button", name="Salvar bio").click(force=True); pgm.wait_for_timeout(1200); pgm.keyboard.press("Escape"); pgm.keyboard.press("Enter"); pgm.wait_for_timeout(500)

    # Quem já estava no sistema (Pedro): preenche a ficha e o RH valida
    ped = novo_contexto(nav); pgp = entrar(ped, "pedro")
    ir(pgp, "/rh/meu-cadastro", 1200)
    pgp.fill("#f-cpf", "390.533.447-05"); pgp.fill("#f-celular", "(11) 97777-6666"); pgp.fill("#f-nome_mae", "Maria Lima")
    foto(pgp, "u03-ficha-do-legado", [(pgp.locator(".aviso-bloco").first, 1, "esq")],
         legendas=["Para quem já tinha conta antes do pré-cadastro: a pessoa mesma preenche a ficha, e o RH confere e valida. Só a pessoa e o RH veem estes dados"], rolar=".aviso-bloco")
    foto(pgp, "u03b-ficha-do-legado-campos", [("#f-cpf", 1, "esq"), (pgp.get_by_role("button", name="Enviar para validação"), 2, "cima")],
         legendas=["Mesmos campos da ficha (identificação, documentos, contato, endereço, formação e experiências). CPF e PIS são conferidos", "Envia a ficha para o RH validar. Cada novo envio pede nova validação"], rolar="#sec-documentos")
    pgp.get_by_role("button", name="Enviar para validação").click(force=True); pgp.wait_for_timeout(1500); pgp.keyboard.press("Enter"); pgp.wait_for_timeout(400)
    ir(pg, "/rh/pre-cadastros", 800)
    pg.get_by_role("button", name="Aguardando validação").click(force=True); pg.wait_for_timeout(900)
    foto(pg, "u04-aguardando-validacao", [(pg.get_by_role("button", name="Aguardando validação"), 1, "cima"), (pg.locator(".tabela-gestao tbody tr").first, 2, "esq")],
         legendas=["As fichas que as próprias pessoas enviaram e o RH ainda não validou", "Abra a ficha para conferir os dados"])
    pg.locator(".tabela-gestao tbody tr").first.get_by_role("link").click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1200)
    foto(pg, "u05-validar-ficha", [(pg.locator(".aviso-bloco").first, 1, "esq"), (pg.get_by_role("button", name="Validar ficha"), 2, "cima")],
         legendas=["Aviso: a própria pessoa enviou esta ficha e falta o RH validar. O RH pode corrigir algum dado antes", "Valida a ficha e registra no histórico funcional da pessoa"], rolar=".aviso-bloco")

    # Bio e foto no cartão de contato
    ir(pg, "/rh/organograma", 1500)
    pg.locator(".caixa-org .titulo-org", has_text="Subsecretaria de Gestão Corporativa").first.click(); pg.wait_for_timeout(700)
    pg.locator(".posicoes-org .pessoa-org", has_text="Mariana").first.click(); pg.wait_for_timeout(1000)
    foto(pg, "u06-cartao-com-bio", [(pg.locator(".detalhe-contato .avatar-diretorio").first, 1, "esq"), (pg.locator(".bio-detalhe"), 2, "dir")],
         legendas=["A foto enviada na admissão já é a foto da pessoa na intranet (Diretório)", "A bio aparece no cartão de contato só porque a pessoa liberou"])
    nav.close()
