# Criado por José Eduardo Santana Martins
# Este arquivo serve para povoar o laboratório do manual dos Chamados com um dia comum de atendimento (pessoas, setores, salas e chamados fictícios).
"""Povoamento do laboratório do manual (nada disto vai para a produção; o banco é um SQLite descartável).

Pessoas (senha `senha-lab-1`): maria (CGP, abre chamados), ana (Comunicação, abre), joao (TI, atende), pedro (CGI, atende),
carla (administra os Chamados). O root (`senha-teste`) é o SuperRoot.
"""

import uuid
from datetime import UTC, datetime, timedelta

from cliente import FabricaSessao, MembroSetor, Setor, Usuario, agora_utc, chamar, gerar_hash_senha, login
from app.models.chamados import Chamado
from app.models.patrimonio import Localizacao

Z = UTC


def sp(dia: int, mes: int, h: int, m: int = 0) -> datetime:
    """Data e hora de São Paulo (UTC-3) em UTC."""
    return datetime(2026, mes, dia, h + 3, m, tzinfo=Z)


with FabricaSessao() as s:
    sgc = Setor(nome="Subsecretaria de Gestão Corporativa", sigla="SGC")
    s.add(sgc); s.flush()
    dga = Setor(nome="Diretoria de Gestão Administrativa", sigla="DGA", setor_pai_id=sgc.id)
    ti = Setor(nome="Tecnologia da Informação", sigla="TI", setor_pai_id=sgc.id)
    cgp = Setor(nome="Coordenadoria de Gestão de Pessoas", sigla="CGP", setor_pai_id=sgc.id)
    com = Setor(nome="Assessoria de Comunicação", sigla="ASCOM")
    s.add_all([dga, ti, cgp, com]); s.flush()
    cgi = Setor(nome="Centro de Gestão de Infraestrutura", sigla="CGI", setor_pai_id=dga.id)
    s.add(cgi); s.flush()
    ids = {"sgc": sgc.id, "dga": dga.id, "ti": ti.id, "cgp": cgp.id, "com": com.id, "cgi": cgi.id}
    pessoas = (("maria", "Maria Aparecida Souza", cgp), ("ana", "Ana Paula Ribeiro", com), ("joao", "João Carlos Lima", ti),
               ("pedro", "Pedro Henrique Alves", cgi), ("carla", "Carla Mendes Rocha", dga))
    for login_, nome, setor in pessoas:
        u = Usuario(login=login_, hash_senha=gerar_hash_senha("senha-lab-1"), nome_completo=nome, email=f"{login_}@exemplo.gov.br", ramal="4321",
                    cargo="Analista", departamento=setor.nome, andar="5", predio="A", perfil_revisado_em=agora_utc(), boas_vindas_em=agora_utc(),
                    boas_vindas_email_em=agora_utc())
        s.add(u); s.flush(); s.add(MembroSetor(setor_id=setor.id, usuario_id=u.id)); ids[login_] = u.id
    # Salas do Patrimônio (prédio > andar > sala), para o campo "Onde é o problema?"
    predio = Localizacao(tipo="predio", nome="Prédio sede"); s.add(predio); s.flush()
    salas = {}
    for andar, codigos in ((3, ("03A10", "03B04")), (5, ("05A03", "05A04", "05B12"))):
        a = Localizacao(tipo="andar", nome=f"{andar}º andar", pai_id=predio.id, andar=andar); s.add(a); s.flush()
        for codigo in codigos:
            sala = Localizacao(tipo="sala", nome=f"Sala {codigo}", codigo=codigo, pai_id=a.id, andar=andar, lado=codigo[2]); s.add(sala); s.flush()
            salas[codigo] = str(sala.id)
    s.commit()

root = login("root", "senha-teste")
rec = chamar("POST", "/acl/recursos", root, {"nome": "Chamados", "slug": "chamados"})["id"]
chamar("POST", "/acl/regras", root, {"recurso_id": rec, "nivel": "LEITURA", "usuarios_ids": [], "setores_ids": [ids["cgp"], ids["com"], ids["sgc"]]})
chamar("POST", "/acl/regras", root, {"recurso_id": rec, "nivel": "MODIFICACAO", "usuarios_ids": [ids["joao"], ids["pedro"]], "setores_ids": []})
chamar("POST", "/acl/regras", root, {"recurso_id": rec, "nivel": "CONTROLE_TOTAL", "usuarios_ids": [ids["carla"]], "setores_ids": []})
rede = chamar("POST", "/acl/recursos", root, {"nome": "Rede", "slug": "rede"})["id"]
chamar("POST", "/acl/regras", root, {"recurso_id": rede, "nivel": "MODIFICACAO", "usuarios_ids": [ids["joao"]], "setores_ids": []})

# Parâmetros: expediente, prazos, categorias, campos, status, respostas prontas, motivos, recorrente e TV
faixas = [{"dia_semana": d, "inicio": "08:00", "fim": "18:00"} for d in range(5)]
exp = chamar("POST", "/chamados/parametros/expedientes", root, {"nome": "Expediente padrão (seg a sex, 8h às 18h)", "faixas": faixas})["id"]
tto = chamar("POST", "/chamados/parametros/slas", root, {"nome": "Atendimento em 30 min", "tipo": "tto", "tempo": 30, "unidade": "minuto", "expediente_id": exp})["id"]
ttr = chamar("POST", "/chamados/parametros/slas", root, {"nome": "Solução em 8 h", "tipo": "ttr", "tempo": 8, "unidade": "hora", "expediente_id": exp})["id"]
ttr_predial = chamar("POST", "/chamados/parametros/slas", root, {"nome": "Solução em 3 dias", "tipo": "ttr", "tempo": 3, "unidade": "dia", "expediente_id": exp})["id"]
cat = {}
def categoria(nome, pai=None, **extra):
    cat[nome] = chamar("POST", "/chamados/parametros/categorias", root, {"nome": nome, "pai_id": cat.get(pai), **extra})["id"]
categoria("Informática", setor_id=ids["ti"], sla_tto_id=tto, sla_ttr_id=ttr)
for n in ("Impressoras", "Rede e Internet", "Acesso e senhas", "Computador e notebook", "Sistemas (SEI, e-mail)"):
    categoria(n, "Informática")
categoria("Reset de senha", "Acesso e senhas", prioridade_padrao="alta")
categoria("Telefonia", setor_id=ids["ti"], sla_tto_id=tto, sla_ttr_id=ttr)
categoria("Prédio e manutenção", setor_id=ids["cgi"], sla_tto_id=tto, sla_ttr_id=ttr_predial)
for n in ("Ar-condicionado", "Elétrica e iluminação", "Mobiliário"):
    categoria(n, "Prédio e manutenção")
categoria("Crachá e acesso ao prédio", setor_id=ids["dga"], sla_ttr_id=ttr_predial)
ramal = chamar("POST", f"/chamados/parametros/categorias/{cat['Telefonia']}/campos", root, {"rotulo": "Número do ramal", "tipo": "numero", "obrigatorio": True, "ajuda": "O ramal que está com problema."})["id"]
chamar("PUT", "/chamados/parametros/status/pendente", root, {"nome": "Aguardando", "cor": "alerta"})
chamar("POST", "/chamados/parametros/substatus", root, {"status_base": "em_atendimento", "nome": "Aguardando peça", "cor": "atencao"})
for t, x in (("Reiniciar e testar", "Bom dia! Reinicie o computador e teste de novo, por favor. Se continuar, responda aqui que eu vou até a sua sala."),
             ("Toner trocado", "O toner foi trocado e a impressora imprimiu a página de teste. Pode usar normalmente.")):
    chamar("POST", "/chamados/parametros/respostas-prontas", root, {"titulo": t, "texto": f"<p>{x}</p>"})
for m in ("Aguardando peça", "Aguardando o solicitante", "Aguardando fornecedor"):
    chamar("POST", "/chamados/parametros/motivos-pendencia", root, {"nome": m})
chamar("POST", "/chamados/parametros/recorrentes", root, {"nome": "Conferir os backups", "categoria_id": cat["Sistemas (SEI, e-mail)"], "titulo": "Conferir os backups da noite",
                                                          "descricao": "<p>Ver se todas as rotinas de backup terminaram sem erro.</p>", "periodicidade_quantidade": 1,
                                                          "periodicidade_unidade": "dia", "antecedencia_min": 0, "so_dias_uteis": True,
                                                          "proxima_em": (datetime.now(Z) + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0).isoformat()})

# O dia: chamados em vários pontos do atendimento
maria, ana, joao, pedro = login("maria"), login("ana"), login("joao"), login("pedro")
def abrir(quem, titulo, texto, categoria_, **extra):
    return chamar("POST", "/chamados", quem, multipart={"titulo": titulo, "descricao": f"<p>{texto}</p>", "categoria_id": cat[categoria_], **extra})["numero"]
def assumir(quem, n):
    chamar("POST", f"/chamados/{n}/assumir", quem, {"versao": chamar("GET", f"/chamados/{n}", quem)["versao"]})
n_impressora = abrir(maria, "Impressora do 3º andar não imprime", "A impressora do lado B parou depois da troca de toner. Aparece \"erro de papel\".", "Impressoras",
                     impedindo_trabalho=True, localizacao_id=salas["03B04"])
n_wifi = abrir(ana, "Notebook não conecta no Wi-Fi", "Desde ontem o notebook não conecta na rede sem fio. No celular funciona.", "Rede e Internet", localizacao_id=salas["05A03"])
n_senha = abrir(maria, "Senha do SEI bloqueada", "Errei a senha três vezes e o SEI bloqueou.", "Reset de senha")
n_ar = abrir(ana, "Ar-condicionado da sala 05B12 pingando", "Está pingando água em cima da mesa do canto.", "Ar-condicionado", localizacao_id=salas["05B12"])
n_ramal = abrir(maria, "Ramal sem linha", "O telefone dá sinal de ocupado o tempo todo.", "Telefonia", campos={ramal: "4321"})
n_monitor = abrir(ana, "Monitor piscando", "O monitor da direita pisca a cada poucos minutos.", "Computador e notebook", localizacao_id=salas["05A04"])
n_mesa = abrir(maria, "Cadeira quebrada", "O encosto da cadeira soltou.", "Mobiliário", localizacao_id=salas["03A10"])

assumir(joao, n_wifi)
chamar("POST", f"/chamados/{n_wifi}/acompanhamentos", joao, multipart={"texto": "<p>O ponto de acesso do 5º andar reiniciou de madrugada; vou checar a configuração.</p>", "privado": True})
chamar("POST", f"/chamados/{n_wifi}/acompanhamentos", joao, multipart={"texto": "<p>Olá, Ana! Passo na sua sala às 14h para ver o notebook.</p>"})
chamar("POST", f"/chamados/{n_wifi}/acompanhamentos", ana, multipart={"texto": "<p>Combinado, obrigada!</p>"})
assumir(joao, n_monitor)
chamar("POST", f"/chamados/{n_monitor}/pendente", joao, {"motivo": "Aguardando peça"})
assumir(pedro, n_ar)
chamar("POST", f"/chamados/{n_ar}/aprovacoes", pedro, {"alvo_setor_id": ids["dga"], "pedido": "Troca do dreno pela empresa de manutenção (custo de R$ 480,00). Pode autorizar?"})
assumir(joao, n_senha)
chamar("POST", f"/chamados/{n_senha}/solucao", joao, multipart={"texto": "<p>Senha desbloqueada. A senha provisória foi enviada para o seu e-mail.</p>"})
chamar("POST", f"/chamados/{n_senha}/satisfacao", maria, {"nota": 5, "comentario": "Resolveu em poucos minutos."})
assumir(joao, n_ramal)
chamar("POST", f"/chamados/{n_ramal}/solucao", joao, multipart={"texto": "<p>O cabo do telefone estava solto na tomada. Reconectado e testado.</p>"})

# Prazos em pontos diferentes (para as cores da fila e do painel): aberto na sexta e no fim de semana
ajustes = {n_impressora: (sp(30, 10, 9, 0), sp(2, 11, 9, 0)), n_wifi: (sp(30, 10, 10, 30), sp(2, 11, 12, 30)), n_monitor: (sp(30, 10, 14, 0), sp(3, 11, 14, 0))}
with FabricaSessao() as s:
    for c in s.query(Chamado):
        if c.numero in ajustes:
            c.aberto_em, c.prazo_ttr = ajustes[c.numero]
            c.criado_em = c.aberto_em
            c.prazo_tto = c.aberto_em + timedelta(minutes=30)
            if c.tomado_em is not None or c.numero == n_impressora:
                c.tomado_em = c.aberto_em + timedelta(minutes=10)
    s.commit()

# Rede: um rack com switch e patch panel
m = chamar("POST", "/rede/modelos", root, {"nome": "Switch 24 portas + 4 SFP", "linhas": 2, "colunas": 12,
                                            "portas_extras": [{"numero": n, "rotulo": f"SFP {n - 24}", "tipo": "fibra"} for n in range(25, 29)]})
pp = chamar("POST", "/rede/modelos", root, {"nome": "Patch panel 24", "linhas": 1, "colunas": 24, "numeracao": "linha"})
rack = chamar("POST", "/rede/racks", root, {"nome": "Rack do 5º andar", "cor": "cinza", "altura_u": 16, "localizacao_id": salas["05A03"]})
chamar("POST", "/rede/racks", root, {"nome": "Rack do 3º andar", "cor": "preto", "altura_u": 12, "localizacao_id": salas["03A10"]})
sw = chamar("POST", "/rede/equipamentos", root, {"nome": "SW-05A", "modelo_face_id": m["id"], "ip_gerencia": "10.0.5.2", "funcao": "acesso", "rack_id": rack["id"], "posicao_u": 8})
pa = chamar("POST", "/rede/equipamentos", root, {"nome": "PP-05A", "tipo": "patch_panel", "modelo_face_id": pp["id"], "rack_id": rack["id"], "posicao_u": 10})
v10 = chamar("POST", "/rede/vlans", root, {"numero": 10, "nome": "Dados"}); v20 = chamar("POST", "/rede/vlans", root, {"numero": 20, "nome": "Voz"})
for i, p in enumerate(sw["portas"][:16]):
    chamar("PUT", f"/rede/portas/{p['id']}", root, {"descricao": f"Sala 05A{i + 1:02d}", "modo": "access", "vlan_nativa_id": v10["id"], "status": "down" if i in (3, 9, 13) else "up",
                                                    "velocidade_mbps": 1000, "duplex": "full"})
chamar("PUT", f"/rede/portas/{sw['portas'][24]['id']}", root, {"descricao": "Uplink para o núcleo", "modo": "trunk", "vlan_nativa_id": v10["id"], "vlans_tag": [v20["id"]],
                                                              "status": "up", "velocidade_mbps": 10000})
chamar("POST", f"/rede/portas/{pa['portas'][2]['id']}/conexao", root, {"porta_id": sw["portas"][2]["id"], "forcar": True})
chamar("POST", "/rede/pontos", root, {"codigo": "05A-03", "porta_id": pa["portas"][2]["id"], "localizacao_id": salas["05A03"]})
# Impressora do Patrimônio ligada na porta 5 do switch (a ligação aparece na porta e no cadastro do bem)
from app.models.patrimonio import Bem
with FabricaSessao() as s:
    impressora = Bem(chapa="012345", descricao="Impressora multifuncional", localizacao_id=uuid.UUID(salas["05A03"]), conservacao=1)
    s.add(impressora); s.commit(); impressora_id = str(impressora.id)
chamar("POST", f"/rede/portas/{sw['portas'][4]['id']}/conexao", root, {"bem_id": impressora_id})
abrir(ana, "Ponto de rede sem sinal", "O ponto da parede ao lado da janela não tem sinal.", "Rede e Internet", rede_porta_id=sw["portas"][3]["id"], localizacao_id=salas["05A04"])
print("bem", impressora_id)
print("ok", {"impressora": n_impressora, "wifi": n_wifi, "senha": n_senha, "ar": n_ar, "ramal": n_ramal, "monitor": n_monitor, "mesa": n_mesa}, "switch", sw["id"])
