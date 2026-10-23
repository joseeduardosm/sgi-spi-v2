import json, os, re, sys, uuid, html as htmlmod, urllib.request
exec(open("cabecalho_pub.py").read())
exec(open("textos_novos.py").read())
LAB = "lab"
LEG = json.load(open(f"{LAB}/legendas.json"))
LEGENDA_PADRAO = "Tela do SGI SPI"


def enviar_imagem(pagina_id, nome):
    arq = f"{LAB}/imgs/{nome}.png"
    limite = uuid.uuid4().hex
    campos = {"type": "gallery", "uploaded_to": str(pagina_id), "name": nome + ".png"}
    partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in campos.items()]
    partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="image"; filename="{nome}.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + open(arq, "rb").read() + b"\r\n")
    corpo = b"".join(partes) + f"--{limite}--\r\n".encode()
    req = urllib.request.Request(BASE + "/image-gallery", data=corpo, method="POST",
                                 headers={"Authorization": f"Token {TOKEN}", "Content-Type": f"multipart/form-data; boundary={limite}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def com_imagens(h, pagina_id):
    """Cada [[nome]] vira a imagem (com link para ampliar) e a lista numerada que explica as setas."""
    def trocar(m):
        nome = m.group(1)
        img = enviar_imagem(pagina_id, nome)
        itens = "".join(f'<li value="{i["n"]}">{htmlmod.escape(i["texto"])}</li>' for i in LEG.get(nome, []))
        exib = (img.get("thumbs") or {}).get("display") or img["url"]
        alt = htmlmod.escape(f"{LEGENDA_PADRAO} – {nome}")
        return f'<p><a href="{img["url"]}" target="_blank" rel="noopener"><img src="{exib}" alt="{alt}"></a></p>' + (f"<ol>{itens}</ol>" if itens else "")
    return re.sub(r"\[\[([\w-]+)\]\]", trocar, h)


def salvar_com_imagens(i, h, nota):
    api("PUT", f"/pages/{i}", {"html": com_imagens(h, i)})
    print("atualizada", i, nota)


def marcar(h, titulo_h2, marcadores):
    """Insere os [[marcadores]] depois do primeiro parágrafo que segue o <h2> indicado."""
    k = h.index(titulo_h2); f = h.index("</p>", k) + 4
    return h[:f] + "".join(f"\n[[{m}]]" for m in marcadores) + h[f:]


# ================================================================ Contratos: visão geral (155)
h = pagina(155)["html"]
h = inserir_antes(h, "Ninguém precisa ficar conferindo",
    '<p class="callout info">A <strong>equipe de gestão e fiscalização só muda por portaria de designação</strong>, feita na aba <strong>Equipe</strong> do contrato (veja a página <em>Equipe e portaria de designação</em>). '
    'Quem pode criar a portaria é a equipe vigente do contrato e quem tem controle total em Contratos (perfil <em>Administrador de Contratos</em>).</p>')
salvar_com_imagens(155, h, "visão geral")

# ================================================================ Contratos: cadastro (156)
h = pagina(156)["html"]
h = substituir_bloco(h, "Indique quem acompanha o contrato",
    '<p>Neste cadastro, indique quem acompanha o contrato: gestor, fiscal administrativo, fiscal técnico e os suplentes de cada um. Basta pesquisar pelo nome ou login. '
    '<strong>Depois do cadastro, a equipe não é mais editada aqui</strong>: toda troca de gestor ou fiscais passa por <strong>portaria de designação</strong>, na aba <strong>Equipe</strong> do contrato. Na tela de edição, esses campos nem aparecem. '
    'Os seis papéis têm os mesmos poderes dentro do contrato; a diferença é que só o gestor reabre uma etapa já concluída. Quando alguém é trocado pela portaria, a designação anterior fica no histórico, com as datas.</p>\n[[g02-editar-sem-equipe]]')
h = inserir_depois(h, "ficam guardados os PDFs do processo",
    '<p>Em <strong>Documentos Importantes</strong> aparece também a seção <strong>Pagamentos</strong>: a cada competência paga, um item <em>Pagamento MM/AAAA</em> reúne o <strong>documento consolidado</strong> e a <strong>OB/PD</strong> juntada na última etapa, com a data em que a OB foi juntada. '
    'A portaria publicada entra no documento <em>Extrato da Portaria de Designação</em>.</p>\n[[g01-pagamentos]]')
h = inserir_depois(h, "tem quatro blocos",
    '<p class="callout info">Contratos, checklists e formulários de avaliação também podem ser <strong>importados por planilha XLSX</strong>, pelo botão <strong>Importar XLSX</strong> da lista de contratos. A importação faz parte de <em>Editar contratos e conduzir a execução</em>: quem pode editar contratos importa; não há permissão separada.</p>\n[[c01-importar-xlsx]]')
salvar_com_imagens(156, h, "cadastro")

# ================================================================ Contratos: trilha de execução (158)
h = pagina(158)["html"]
h = substituir_bloco(h, "Depois da nota fiscal, as etapas",
    '<p>Depois da nota fiscal, a <strong>retenção de tributos</strong> e o <strong>checklist</strong> ficam abertos ao mesmo tempo: o Financeiro confere a retenção enquanto a equipe monta o checklist. '
    'A <strong>consulta ao CADIN é a última etapa</strong> antes do download e só abre quando todas as anteriores estiverem concluídas. O documento consolidado exige as cinco etapas concluídas.</p>\n[[g03-trilha-etapas]]')
m5 = re.search(r"<tr>(?:(?!</tr>).)*?5\. CADIN.*?</tr>", h, re.S); m6 = re.search(r"<tr>(?:(?!</tr>).)*?6\. Checklist.*?</tr>", h, re.S)
assert m5 and m6
linha5, linha6 = m5.group(0), m6.group(0); entre = h[m5.end():m6.start()]
h = h[:m5.start()] + linha6.replace("6. Checklist", "5. Checklist") + entre + linha5.replace("5. CADIN", "6. CADIN") + h[m6.end():]
a = h.rfind("<h2", 0, h.index("5. Consulta ao CADIN")); b = h.rfind("<h2", 0, h.index("6. Documentos mensais do checklist")); c = h.rfind("<h2", 0, h.index("7. Download: documento consolidado"))
bloco_cadin = h[a:b].replace("5. Consulta ao CADIN", "6. Consulta ao CADIN (última etapa antes do download)").rstrip() + (
    '\n<p>Com pendência, o sistema <strong>registra sozinho uma ocorrência no diário de bordo</strong> e <strong>envia o e-mail de CADIN</strong> (texto da máscara cadastrada em Contratos › Modelos) a todos os prepostos ativos da contratada, com a equipe em cópia. '
    'O resultado do envio aparece na consulta, com o botão <strong>Reenviar e-mail</strong> para tentar de novo.</p>\n')
bloco_check = h[b:c].replace("6. Documentos mensais do checklist", "5. Documentos mensais do checklist")
h = h[:a] + bloco_check + bloco_cadin + h[c:]
k = h.index("8. Ordem Bancária</h2>"); k = h.rfind("<h2", 0, k); prox = h.index("<h2", k + 5)
h = h[:prox] + ('<p>Ao anexar a OB, o sistema envia à contratada o <strong>e-mail de pagamento</strong> (texto da máscara <em>E-mail de pagamento</em>, em Contratos › Modelos) e mostra na competência se o envio deu certo, com o botão <strong>Reenviar e-mail</strong>. '
    'Quem tem no perfil de acesso a ação <strong>Lançar ordem bancária</strong> anexa a OB em qualquer contrato, mesmo sem integrar a equipe (e só isso). '
    'Depois, o documento consolidado e a OB/PD passam a constar juntos em <strong>Documentos Importantes › Pagamentos</strong>, como <em>Pagamento MM/AAAA</em>.</p>\n') + h[prox:]
salvar_com_imagens(158, h, "trilha de execução")

# ================================================================ Contratos: diário (159)
h = pagina(159)["html"]
h = substituir_bloco(h, "gera o diário do contrato, com as ocorrências",
    '<p>O botão <strong>Baixar PDF</strong> gera o diário do contrato em formato de diário: <strong>uma página por dia que teve ocorrência</strong>, com todas as ocorrências daquele dia (quem registrou e quando, o relato, a competência afetada, a glosa e o impacto na avaliação). '
    'Dias sem ocorrência não geram página, e um dia com muito texto continua nas páginas seguintes. No fim vêm o resumo das glosas por item e, se houver arquivos anexados às ocorrências, a <strong>lista de anexos</strong>: cada arquivo é juntado ao PDF logo depois, precedido de uma folha de rosto. '
    'PDFs entram como estão e imagens viram uma página; documentos do Office, TXT e CSV não cabem no PDF e ficam só com a folha de rosto, avisando para baixar o arquivo no sistema. Todas as páginas são numeradas em sequência. '
    'O diário também vai anexado, recortado pelo período, no e-mail de cada medição concluída.</p>\n[[d00-diario-baixar-pdf]]\n[[d01-diario-pagina-do-dia]]\n[[d02-diario-lista-de-anexos]]')
salvar_com_imagens(159, h, "diário")

# ================================================================ Protocolo (182)
h = pagina(182)["html"]
h = inserir_depois(h, "Só há um documento por número",
    '<h3>Número de portaria de designação de contrato</h3>'
    '<p>Quando um contrato pede portaria de designação da equipe, o sistema <strong>reserva o número de Portaria SPI SSGC em nome do contrato</strong>, já com a finalidade preenchida. Ele aparece como <em>Reservado</em> e continua assim até a publicação.</p>\n[[p01-numero-da-portaria]]'
    '<p>Quando o <strong>Diário Oficial (D.O.E.)</strong> é publicado, o Protocolo abre o número, clica em <strong>Anexar documento</strong> e envia o <strong>PDF do D.O.E.</strong>. Esse anexo é o que <strong>publica a portaria no sistema</strong>: a nova equipe passa a valer no contrato, os nomeados ganham acesso e o PDF entra em <em>Documentos Importantes</em> do contrato.</p>\n[[p02-doe-anexado]]'
    '<p class="callout warning">Só se anexa ao número de uma portaria <strong>depois do aceite da autoridade</strong>, e só em PDF. Antes disso o sistema recusa o anexo. Não libere nem anule o número de uma portaria pelo Protocolo: ela é cancelada pela aba Equipe do contrato, que devolve o número sozinha.</p>')
salvar_com_imagens(182, h, "protocolo")

# ================================================================ Patrimônio (192, 193) e Tarefas (173)
h = pagina(192)["html"]
h = inserir_antes(h, "Aprovar ou recusar (Controle total)",
    '<h3>Categoria, justificativa, compartilhamento e relatório</h3>'
    '<ul><li><strong>Selecionar e pesquisar.</strong> Há <em>Selecionar todos</em>, uma pesquisa dentro da lista (local, descrição, marca, modelo ou qualquer informação) e a escolha de uma <strong>sala inteira</strong>, com a confirmação “Você deseja relacionar os X ativos da sala Y?”.</li></ul>\n[[i02-lista-selecao]]'
    '<ul><li><strong>Categoria do inservível.</strong> Ao justificar um inservível, escolha a classificação: <em>Ocioso</em>, <em>Recuperável</em>, <em>Antieconômico</em> ou <em>Irrecuperável</em>. Ela é obrigatória e, depois da aprovação, aparece como marcador no bem (por exemplo, “Inservível · Antieconômico”).</li>'
    '<li><strong>Justificativa em texto formatado</strong>, de 10 a 2000 caracteres, valendo para todos os bens marcados.</li></ul>\n[[i03-justificativa-categoria]]'
    '<ul><li><strong>Editar ou excluir.</strong> Uma justificativa já dada pode ser editada ou excluída enquanto a lista é rascunho.</li></ul>\n[[i05-lista-justificada]]'
    '<ul><li><strong>Compartilhar a lista.</strong> O botão <em>Compartilhar</em> inclui <strong>colaboradores</strong>, que têm os mesmos poderes de quem montou a lista (menos aprovar a própria lista).</li></ul>\n[[i04-compartilhar-lista]]'
    '<ul><li><strong>Relatório.</strong> O PDF da lista tem as mesmas colunas do Excel (item, chapa/série, descrição, local, fotos, justificativa e anexo); justificativas longas continuam na página seguinte.</li></ul>\n[[i06-relatorio-pdf]]')
salvar_com_imagens(192, h, "inservíveis e extraviados")

h = pagina(193)["html"]
h = inserir_antes(h, "Aprovar (Controle total)",
    '<p class="callout info">Como nas listas de inservíveis, a baixa pode ser <strong>compartilhada</strong> com colaboradores, que têm os mesmos poderes de quem a montou (menos aprovar a própria baixa). O relatório em PDF segue a mesma estrutura do Excel.</p>')
salvar_com_imagens(193, h, "baixa")

h = pagina(173)["html"]
k = inicio_do_paragrafo(h, "A tarefa principal não vai para validação"); f = fim_do_bloco(h, k)
h = h[:k] + ("<li>Quem <strong>entra ou sai da tarefa principal</strong> entra ou sai das subtarefas ainda abertas; a subtarefa pode ter responsáveis além dos da principal, mas não pode retirar os dela.</li>"
             "<li>Quando a <strong>tarefa principal é validada ou concluída, as subtarefas que ainda estavam abertas são concluídas junto</strong>.</li>") + h[f:]
salvar_com_imagens(173, h, "subtarefas")

# ================================================================ Novas páginas
cap_contratos = 154
nova = api("POST", "/pages", {"chapter_id": cap_contratos, "name": "Equipe e portaria de designação", "html": "<p>Em elaboração.</p>", "priority": 3})
P = PORTARIA
for titulo, marc in (("1. Nomeações", ["e01-equipe-nova-portaria", "e02-nomeacoes-formulario"]), ("2. Conferência do cadastro (RH)", ["e03-situacao-dados-pendentes"]),
                     ("3. Ciência dos nomeados", ["e04-janela-de-ciencia", "e05-aviso-no-sino"]), ("4. Autoridade e texto da portaria", ["e06-escolher-autoridade", "e07-texto-da-portaria"]),
                     ("5. Aceite e PDF de evidência", ["e08-aceite-da-autoridade", "e09-pdf-de-evidencia", "e11-pdf-evidencia"]),
                     ("6. Publicação e efeito no sistema", ["p01-numero-da-portaria", "p02-doe-anexado", "e10-portaria-publicada"])):
    P = marcar(P, titulo, marc)
salvar_com_imagens(nova["id"], P, "NOVA página portaria")

cap = api("POST", "/chapters", {"book_id": 147, "name": "Controle de acesso (administração)", "priority": 9, "description": "Perfis de acesso, setores e personificação."})
pa = api("POST", "/pages", {"chapter_id": cap["id"], "name": "Perfis de acesso", "html": "<p>Em elaboração.</p>", "priority": 1})
A = marcar(ACESSO, "Perfis e ações", ["a01-perfil-modulos"])
A = marcar(A, "Quem recebe o perfil", ["a02-perfil-setores"])
salvar_com_imagens(pa["id"], A, "NOVA página perfis")
print("URLs:", f"https://instrucoes.spi.sp.gov.br/books/sgi-spi/page/{nova['slug']}", f"https://instrucoes.spi.sp.gov.br/books/sgi-spi/chapter/{cap['slug']}")
