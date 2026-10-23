# Simula o que o laboratório não tem: o GLPI (formulário "CGP - Nomeações"), o servidor de e-mail e o AD (conferência de login). Nada sai da máquina.
from app.services.cliente_smtp import ResultadoSmtp
from app.services.glpi.cliente_formulario import PerguntaFormulario


def _radio(i, titulo, sim, nao):
    return PerguntaFormulario(id=i, nome=f"answers_{i}[]", rotulo=titulo, tipo="radio", opcoes=[(sim, "Sim"), (nao, "Não")])


PERGUNTAS = [
    PerguntaFormulario(id=44, nome="answers_44", rotulo="Nome", tipo="text", obrigatoria=True), PerguntaFormulario(id=47, nome="answers_47", rotulo="Cargo", tipo="text", obrigatoria=True),
    PerguntaFormulario(id=48, nome="answers_48", rotulo="Registo do Servidor (RS)", tipo="number"), PerguntaFormulario(id=49, nome="answers_49", rotulo="Lotação", tipo="text", obrigatoria=True),
    PerguntaFormulario(id=50, nome="answers_50", rotulo="Data de início", tipo="text"), PerguntaFormulario(id=51, nome="answers_51", rotulo="Usuário espelho", tipo="text"),
    PerguntaFormulario(id=52, nome="answers_52", rotulo="RG", tipo="text", obrigatoria=True), PerguntaFormulario(id=53, nome="answers_53", rotulo="CPF", tipo="number", obrigatoria=True),
    _radio(42, "Criar usuário de rede", "r1", "r2"), _radio(72, "Criar e-mail corporativo", "e1", "e2"), _radio(73, "Criar acesso ao SEI", "s1", "s2"),
    _radio(74, "Criar acesso ao Compras SP", "c1", "c2"), _radio(75, "Provisionar equipamento de trabalho", "q1", "q2"), _radio(76, "Preparo da estação", "t1", "t2"),
    _radio(77, "Solicitar crachá", "k1", "k2"), _radio(79, "Provisionar telefone", "f1", "f2"), _radio(83, "Provisionar mobiliário", "m1", "m2"),
    _radio(104, "Alguma observação adicional?", "o1", "o2"), PerguntaFormulario(id=109, nome="answers_109", rotulo="Observações adicionais", tipo="textarea"),
    PerguntaFormulario(id=85, rotulo="Foto", tipo="file", uploader="_uploader_answers_85"),
]
SERVICOS = [("SOLICITAÇÃO DE EQUIPAMENTOS", 75), ("USUÁRIO DE REDE", 42), ("E-MAIL CORPORATIVO", 72), ("TELEFONIA", 79), ("SEI", 73), ("COMPRAS SP", 74), ("MOBILIÁRIO", 83), ("ESTAÇÃO", 76), ("CRACHÁ", 77)]
CONTADOR = {"n": 2000}
EMAILS: list = []


class FormularioFalso:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def perguntas(self, formulario_id):
        return PERGUNTAS, "csrf"

    def subir_arquivo(self, pergunta, nome, conteudo, tipo_mime):
        return {"name": "tmp_" + nome, "prefix": "pfx"}

    def enviar(self, formulario_id, respostas, arquivos=None):
        nome = respostas[44]
        links = []
        for titulo, pergunta in SERVICOS:
            if respostas.get(pergunta, "").endswith("1"):  # chaves "Sim" do laboratório terminam em 1
                CONTADOR["n"] += 1
                links.append(f'<a href="/front/ticket.form.php?id={CONTADOR["n"]}">CGP | NOMEAÇÃO | {titulo} | {nome}</a>')
        return {"links_to_created_items": links}


def aplicar() -> None:
    from app.services import servico_ldap, servico_smtp
    from app.services.rh import servico_admissao

    servico_admissao._cliente_formulario = lambda sessao: (FormularioFalso(), 8)
    servico_smtp.enviar_email = lambda sessao, mensagem: EMAILS.append(mensagem) or ResultadoSmtp(True, 1, "ok")
    servico_ldap.situacao_do_login = lambda sessao, login: ("encontrado", "Já existe no AD (conta de outra pessoa).") if login in ("ana.souza", "rita.moura") else ("livre", "Login livre no AD.")
