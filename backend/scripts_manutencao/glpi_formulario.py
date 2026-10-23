# Criado por José Eduardo Santana Martins
# Este arquivo serve para descobrir, só por leitura, como o formulário de nomeações do GLPI ("CGP - Nomeações", id 8) é montado: perguntas, tipos e opções de resposta.
"""Diagnóstico SOMENTE LEITURA do formulário de nomeações do GLPI.

Entra no GLPI pela tela web com a conta de serviço (usuário e senha web cifrados em Administração > Integração GLPI; nada é impresso), abre `/Form/Render/<id>` e
lista as perguntas (`answers_<id>`), o tipo de cada campo, se é obrigatório e as opções de resposta. Depois sai do GLPI.

Não envia o formulário, não cria chamado e não grava nada no SGI nem no GLPI (só o login, um GET e o logout).

Uso: cd backend && .venv/bin/python scripts_manutencao/glpi_formulario.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.banco import FabricaSessao  # noqa: E402
from app.services import servico_integracao_glpi as integracao  # noqa: E402
from app.services.rh.servico_admissao import conferir_perguntas  # noqa: E402
from app.services.glpi.cliente_formulario import ClienteFormularioGlpi  # noqa: E402
from app.services.glpi.cliente_glpi import ErroGlpi  # noqa: E402


def main() -> None:
    with FabricaSessao() as sessao:
        config = integracao.obter(sessao)
        url, formulario = config.url_base, config.formulario_nomeacao_id
        try:
            usuario, senha = integracao.credencial_web(config)
        except ErroGlpi as erro:
            print("Sem credencial web:", erro.mensagem)
            return
    print(f"GLPI: {url} | formulário {formulario} | conta de serviço: {usuario}")
    try:
        with ClienteFormularioGlpi(url, usuario, senha) as glpi:
            print("login: ok")
            perguntas, csrf = glpi.perguntas(formulario)
            bruto = glpi.html_do_formulario(formulario) if "--trecho" in sys.argv else ""
    except ErroGlpi as erro:
        print("Falhou:", erro.mensagem)
        return
    print(f"token CSRF na página: {bool(csrf)} | perguntas: {len(perguntas)}")
    for p in perguntas:
        opcoes = f" opções: {p.opcoes}" if p.opcoes else ""
        print(f"  answers_{p.id} \"{p.rotulo}\": {p.tipo or '?'} | obrigatória: {p.obrigatoria}{opcoes}")


    if "--testar-upload" in sys.argv:
        # Sobe uma imagem de 1 pixel à área TEMPORÁRIA do GLPI (não envia o formulário, não cria chamado) só para ver o formato da resposta
        import base64

        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        pergunta = next((p for p in perguntas if p.uploader), None)
        print("\npergunta de arquivo:", (pergunta.id, pergunta.rotulo, pergunta.uploader) if pergunta else "não achada")
        if pergunta:
            try:
                with ClienteFormularioGlpi(url, usuario, senha) as glpi2:
                    glpi2.perguntas(formulario)
                    enviado = glpi2.subir_arquivo(pergunta, "teste-upload.png", png, "image/png")
                print("upload temporário ok; chaves devolvidas:", sorted(enviado.keys()))
            except ErroGlpi as erro:
                print("upload falhou:", erro.mensagem)
    problemas = conferir_perguntas(perguntas)
    print("\nConferência do que o SGI preenche contra o formulário real:", "tudo certo" if not problemas else "; ".join(problemas))
    if bruto:
        import re

        procurados = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--procurar=")]
        for alvo in procurados or ("answers_42", "answers_44", "answers_50"):
            achado = bruto.find(alvo + "[")  if bruto.find(alvo + "[") >= 0 else bruto.find(alvo)
            trecho = bruto[max(0, achado - 900): achado + 900] if achado >= 0 else "(não achou)"
            print(f"\n--- trecho em torno de {alvo} ---\n" + re.sub(r"\s+", " ", re.sub(r'(csrf[^"]*"[^"]*")', "…", trecho)))


if __name__ == "__main__":
    main()
