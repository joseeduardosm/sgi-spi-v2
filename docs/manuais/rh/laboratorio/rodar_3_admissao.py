# Prints do manual: admissão ponta a ponta (início, formulário no GLPI, documentos, resolução, Protocolo, publicação, posse, conta e conclusão).
import struct, subprocess, sys, zlib; sys.path.insert(0, ".")
from cap import *


def ir(pg, rota, espera=800):
    pg.goto(BASE + rota); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(espera)


def png_foto(caminho, w=240, h=240):
    """Retrato fictício (fundo azul, cabeça e ombros claros) sem bibliotecas externas."""
    linhas = []
    for y in range(h):
        linha = bytearray(b"\x00")
        for x in range(w):
            cabeca = (x - 120) ** 2 + (y - 90) ** 2 < 46 ** 2
            ombros = (x - 120) ** 2 / 95 ** 2 + (y - 235) ** 2 / 85 ** 2 < 1
            linha += bytes((240, 240, 240) if cabeca or ombros else (70, 110, 160))
        linhas.append(bytes(linha))
    dados = b"".join(linhas)
    def bloco(tipo, corpo): return struct.pack(">I", len(corpo)) + tipo + corpo + struct.pack(">I", zlib.crc32(tipo + corpo) & 0xffffffff)
    open(caminho, "wb").write(b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + bloco(b"IDAT", zlib.compress(dados)) + bloco(b"IEND", b""))


png_foto("/tmp/foto-mariana.png")
open("/tmp/comprovante.txt", "w").write("Comprovante de envio ao Portal de Indicações (exemplo fictício)\n")
secao = lambda chave: f"section[aria-labelledby='et-{chave}']"

with sync_playwright() as p:
    nav, ctx = abrir(p)
    pg = entrar(ctx, "rita")

    # Iniciar a admissão
    ir(pg, "/rh/admissoes")
    pg.get_by_role("button", name="Nova admissão").click(); pg.wait_for_timeout(600)
    pg.select_option("#adm-ficha", index=1); pg.wait_for_timeout(300)
    foto(pg, "a02-nova-admissao", [("#adm-ficha", 1, "esq"), (pg.get_by_role("button", name="Iniciar admissão"), 2, "cima")],
         legendas=["A ficha de quem vai entrar. Só aparecem fichas com login proposto e cargo pretendido (uma vaga livre) e sem admissão iniciada", "Inicia a trilha. Os documentos do checklist do cargo são copiados para a admissão"])
    pg.get_by_role("button", name="Iniciar admissão").click(); pg.wait_for_url("**/rh/admissoes/*"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1200)
    adm_url = pg.url

    # Etapa 1: formulário no GLPI
    pg.locator(".bloco-foto input[type=file]").set_input_files("/tmp/foto-mariana.png"); pg.wait_for_timeout(1500)
    for i in range(8):
        pg.locator(f"{secao('chamado')} .opcoes-parametros label.opcao").nth(i).click()
    pg.fill("#chamado-espelho", "bruna"); pg.fill("#chamado-obs", "Equipamento portátil, por favor.")
    pg.evaluate("window.scrollTo(0, 0)"); pg.wait_for_timeout(300)
    foto(pg, "a03-trilha", [(pg.locator("app-trilha-etapas"), 1, "esq"), (pg.get_by_role("link", name="Ver ficha"), 2, "cima"), (pg.get_by_role("button", name="Cancelar admissão"), 3, "cima")],
         legendas=["A trilha de 7 etapas: formulário no GLPI, documentos, resolução, número no Protocolo, publicação, posse e entrada no SGI. Cada etapa só abre depois da anterior; a atual fica em vermelho", "Abre a ficha de pré-cadastro desta pessoa", "Cancela a admissão (o número do Protocolo ainda sem documento volta para a fila)"])
    foto(pg, "a03b-etapa1", [(pg.locator(".bloco-foto"), 1, "esq"), (pg.locator(f"{secao('chamado')} .opcoes-parametros"), 2, "esq"),
                             ("#chamado-espelho", 3, "esq"), ("#chamado-obs", 4, "esq"), (pg.get_by_role("button", name="Enviar o formulário ao GLPI"), 5, "cima")],
         legendas=["Foto da pessoa (opcional): vai no formulário do GLPI e, quando a conta existir, vira a foto dela na intranet", "Os serviços que a TI deve providenciar: rede, e-mail, SEI, Compras SP, equipamento, estação, crachá, telefone e mobiliário. Desmarcado vale Não", "Usuário espelho (opcional): quem tem o acesso que serve de modelo", "Observações para a TI. O login proposto e o e-mail pessoal da ficha já vão junto", "Envia o formulário \"CGP - Nomeações\" ao GLPI com os dados da ficha. O próprio GLPI abre os chamados e dispara os e-mails"], rolar=secao("chamado"))
    pg.get_by_role("button", name="Enviar o formulário ao GLPI").click(); pg.wait_for_timeout(2000)
    foto(pg, "a04-etapa1-enviado", [(pg.locator(".resumo-chamado"), 1, "esq"), (pg.locator(f"{secao('chamado')} table"), 2, "esq"), (pg.locator(f"{secao('chamado')} tbody tr").first.locator("td").nth(2), 3, "cima")],
         legendas=["Resumo: quando foi enviado, quantos chamados o GLPI abriu e o login proposto", "Um chamado por serviço pedido, com o número; os serviços marcados Não ficam sem chamado", "O número abre o chamado no GLPI em outra aba"], rolar=secao("chamado"))

    # Etapa 2: documentos (Portal de Indicações é externo: aqui só o registro)
    pg.get_by_role("button", name="Registrar envio").first.click(); pg.wait_for_timeout(500)
    pg.locator(f"{secao('documentos')} input[type=date]").fill("2026-10-20")
    pg.locator(f"{secao('documentos')} input[type=file]").set_input_files("/tmp/comprovante.txt"); pg.wait_for_timeout(300)
    foto(pg, "a05-documentos", [(pg.locator(f"{secao('documentos')} tbody tr").first, 1, "esq"), (pg.locator(f"{secao('documentos')} input[type=date]"), 2, "esq"), (pg.locator(f"{secao('documentos')} .escolha-comprovante"), 3, "dir"), (pg.get_by_role("button", name="Registrar", exact=True), 4, "cima")],
         legendas=["Cada documento do checklist do cargo. O envio ao Portal de Indicações (sistema do governo) é feito lá", "Data em que o documento foi enviado ao Portal", "Comprovante do envio (opcional)", "Registra o envio. Dá para desfazer até concluir a etapa"], rolar=secao("documentos"))
    pg.get_by_role("button", name="Registrar", exact=True).click(); pg.wait_for_timeout(1200)
    for _ in range(3):
        pg.get_by_role("button", name="Registrar envio").first.click(); pg.wait_for_timeout(400)
        pg.locator(f"{secao('documentos')} input[type=date]").fill("2026-10-20"); pg.get_by_role("button", name="Registrar", exact=True).click(); pg.wait_for_timeout(1000)
    foto(pg, "a06-documentos-prontos", [(pg.locator(f"{secao('documentos')} tbody tr").first.locator("td").nth(1), 1, "esq"), (pg.get_by_role("button", name="Comprovante").first, 2, "cima"), (pg.get_by_role("button", name="Concluir documentos"), 3, "cima")],
         legendas=["Documento enviado: data, quem registrou e observação", "Baixa o comprovante guardado", "Conclui a etapa. Só é possível com todos os documentos obrigatórios registrados"], rolar=secao("documentos"))
    pg.get_by_role("button", name="Concluir documentos").click(); pg.wait_for_timeout(1200)

    # Etapa 3: resolução
    pg.get_by_role("button", name="Gerar o texto da resolução").click(); pg.wait_for_timeout(2500)
    foto(pg, "a07-resolucao", [(pg.locator(f"{secao('resolucao')} .editor-rico"), 1, "esq"), (pg.locator(f"{secao('resolucao')} .dica-formulario"), 2, "esq"), (pg.get_by_role("button", name="Copiar para o SEI"), 3, "cima"), (pg.get_by_role("button", name="Baixar PDF").first, 4, "cima"), (pg.get_by_role("button", name="Salvar texto").first, 5, "cima")],
         legendas=["Texto da resolução, vindo do modelo (RH › Modelos), editável só para esta admissão", "Placeholders como #nome, #cargo e #numeroresolucao: o número, as datas e os nomes entram na hora de gerar o PDF", "Copia o texto já preenchido e formatado, para colar direto no SEI", "PDF da resolução, com a marca d'água MINUTA até a publicação", "Salva a edição do texto"], rolar=secao("resolucao"))

    # Etapa 4: número no Protocolo
    pg.select_option("#tipo-protocolo", label="Resoluções SPI"); pg.wait_for_timeout(300)
    foto(pg, "a08-protocolo", [("#tipo-protocolo", 1, "esq"), (pg.get_by_role("button", name="Reservar número"), 2, "cima")],
         legendas=["Tipo de Resolução do Protocolo (tipos cujo nome começa com Resolu). Só vale o que tem faixa de numeração no ano", "Reserva o próximo número livre. Se a admissão for cancelada antes do documento, o número volta para a fila"], rolar=secao("protocolo"))
    pg.get_by_role("button", name="Reservar número").click(); pg.wait_for_timeout(1500)

    # Etapa 5: publicação (e e-mail automático)
    pg.fill("#pub-data", "2026-10-22")
    pg.locator(f"{secao('publicacao')} input[type=file]").set_input_files("doe.pdf"); pg.wait_for_timeout(500)
    foto(pg, "a09-publicacao", [(pg.locator(f"{secao('protocolo')} p"), 1, "esq"), ("#pub-data", 2, "esq"), (pg.locator(f"{secao('publicacao')} app-campo-arquivo"), 3, "dir"), (pg.get_by_role("button", name="Registrar publicação"), 4, "cima")],
         legendas=["O número reservado no Protocolo", "Data da publicação no D.O.E.", "PDF da publicação: clique, arraste e solte ou cole (Ctrl+V). Fica anexado ao número do Protocolo (se o Protocolo anexar direto, também vale)", "Registra a publicação e envia sozinho o e-mail \"Sua nomeação foi publicada\" para a pessoa, com o PDF"], rolar=secao("protocolo"))
    pg.get_by_role("button", name="Registrar publicação").click(); pg.wait_for_timeout(2000)
    foto(pg, "a10-publicada-e-email", [(pg.locator(f"{secao('publicacao')} .aviso-email"), 1, "esq"), (pg.get_by_role("button", name="Baixar PDF").last, 2, "cima"), ("#pub-ajuste", 3, "esq")],
         legendas=["O e-mail de nomeação saiu sozinho: mostra quando e para qual e-mail pessoal. Se falhar, o aviso fica vermelho com o motivo e o botão Reenviar", "Baixa o PDF da publicação", "Corrige a data da publicação, se preciso (por exemplo, quando o Protocolo anexou o PDF direto)"], rolar=secao("publicacao"))

    # Etapa 6: posse
    pg.fill("#posse-data", "2026-11-03")
    foto(pg, "a11-posse", [("#posse-data", 1, "esq"), (pg.get_by_role("button", name="Registrar posse"), 2, "cima")], legendas=["Data da posse (não pode ser anterior à publicação)", "Registra a posse e prepara o termo de posse a partir do modelo"], rolar=secao("posse"))
    pg.get_by_role("button", name="Registrar posse").click(); pg.wait_for_timeout(2500)
    foto(pg, "a12-termo-de-posse", [(pg.locator(f"{secao('posse')} .editor-rico"), 1, "esq"), (pg.get_by_role("button", name="Baixar termo (PDF)"), 2, "cima")], legendas=["Texto do termo, editável só para esta admissão", "PDF do termo de posse"], rolar=secao("posse"))

    # Etapa 7: a conta ainda não existe
    foto(pg, "a13-aguardando-conta", [(pg.locator(f"{secao('concluida')} .aviso-bloco"), 1, "esq"), (pg.get_by_role("button", name="Concluir admissão"), 2, "cima")],
         legendas=["A conta do login proposto ainda não apareceu no AD. A TI cria o login a partir do chamado; quando ele aparecer, a ficha se liga sozinha", "Fica desabilitado até a conta existir"], rolar=secao("concluida"))
    print(subprocess.run(["/home/administrador/projeto/backend/.venv/bin/python", "lab_conta.py", "mariana.ribeiro", "Mariana Costa Ribeiro"], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "/home/administrador/projeto/backend:."}).stdout.strip().splitlines()[-1:])
    pg.reload(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    foto(pg, "a14-conta-ligada", [(pg.locator(f"{secao('concluida')} .selo-situacao"), 1, "esq"), (pg.get_by_role("button", name="Concluir admissão"), 2, "cima")],
         legendas=["A conta apareceu e foi ligada à ficha automaticamente (nascimento, celular, RS/PV, RG ou CIN e a foto já foram para o cadastro)", "Conclui: a pessoa assume o cargo na data da posse e o histórico funcional registra a admissão"], rolar=secao("concluida"))
    pg.get_by_role("button", name="Concluir admissão").click(); pg.wait_for_timeout(2000)
    pg.evaluate("window.scrollTo(0, 0)"); pg.wait_for_timeout(400)
    foto(pg, "a15-concluida", [(pg.locator("app-trilha-etapas"), 1, "esq"), (pg.locator(".selo-situacao").first, 2, "dir")], legendas=["Todas as etapas concluídas", "Admissão concluída: o cargo e o setor da pessoa já estão certos"])

    # Lista de admissões
    ir(pg, "/rh/admissoes")
    pg.get_by_role("button", name="Concluídas").click(); pg.wait_for_timeout(900)
    foto(pg, "a01-lista-admissoes", [(pg.get_by_role("button", name="Nova admissão"), 1, "esq"), (pg.locator(".chips-filtro"), 2, "esq"), (pg.locator(".tabela-gestao tbody tr").first.locator("td").nth(2), 3, "esq"), (pg.locator(".tabela-gestao tbody tr").first.get_by_role("link"), 4, "cima")],
         legendas=["Inicia a admissão de uma ficha", "Filtros: em andamento, concluídas e canceladas", "Etapa em que cada pessoa está", "Abre a trilha da admissão"])
    nav.close()
