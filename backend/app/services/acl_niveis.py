# Criado por José Eduardo Santana Martins
# Este arquivo serve para dizer, em cada módulo (recurso da ACL), o que cada nível de acesso libera.
"""Textos dos níveis de acesso por recurso da ACL.

Os valores gravados continuam sendo `LEITURA`, `MODIFICACAO` e `CONTROLE_TOTAL` (hierárquicos: o maior inclui o menor).
Aqui cada recurso diz, em linguagem de quem configura a regra, **o que cada nível libera naquele módulo**:
`rotulo` é o nome curto (selo e seletor) e `descricao`, a frase completa.

**Todo recurso novo da ACL precisa de uma entrada aqui**, escrita a partir do que as rotas do módulo realmente exigem
(o teste `test_acl_niveis.py` falha se faltar). Nível que o módulo não diferencia diz isso no texto.
"""

from typing import TypedDict


class TextoNivel(TypedDict):
    rotulo: str
    descricao: str


def _n(rotulo: str, descricao: str) -> TextoNivel:
    return {"rotulo": rotulo, "descricao": descricao}


GENERICOS: dict[str, TextoNivel] = {
    "LEITURA": _n("Leitura", "Consulta o módulo."),
    "MODIFICACAO": _n("Modificação", "Consulta e altera dados do módulo."),
    "CONTROLE_TOTAL": _n("Controle total", "Faz tudo no módulo, inclusive administrar."),
}

NIVEIS_POR_RECURSO: dict[str, dict[str, TextoNivel]] = {
    "protocolo": {
        "LEITURA": _n("Consultar números", "Vê a grade de números, o histórico, o painel e baixa os documentos que não são sigilosos."),
        "MODIFICACAO": _n("Reservar números de documentos", "Reserva o próximo número de ofício, portaria ou resolução, anexa o documento, marca sigilo, vincula a contrato e libera a própria reserva."),
        "CONTROLE_TOTAL": _n("Administrar o Protocolo", "Tudo isso e também cria tipos de documento e faixas de numeração, lança números já usados e anula números."),
    },
    "contratos": {
        "LEITURA": _n("Consultar contratos", "Vê contratos, empresas, execução, calendário de vencimentos e relatórios do módulo."),
        "MODIFICACAO": _n("Editar contratos e conduzir a execução", "Cria contratos e empresas, importa planilhas e, sendo da equipe do contrato (ou o criador), edita o contrato, conduz as etapas da competência e solicita a portaria de designação. Exclui os contratos que ele mesmo criou."),
        "CONTROLE_TOTAL": _n("Administrar contratos e empresas", "Tudo isso, em qualquer contrato (mesmo sem ser da equipe nem o criador), e também exclui contratos e empresas e cadastra as autoridades signatárias e as máscaras das portarias."),
    },
    "importacao-contratos": {
        "LEITURA": _n("Sem acesso útil", "Este módulo não tem consulta: use Modificação para importar."),
        "MODIFICACAO": _n("Importar contratos (XLSX)", "Envia a planilha de contratos e confirma a importação."),
        "CONTROLE_TOTAL": _n("Importar contratos (XLSX)", "Igual a Modificação: o módulo não diferencia."),
    },
    "importacao-modelos": {
        "LEITURA": _n("Sem acesso útil", "Este módulo não tem consulta: use Modificação para importar."),
        "MODIFICACAO": _n("Importar checklists e formulários", "Envia a planilha de modelos de checklist e formulário e confirma a importação."),
        "CONTROLE_TOTAL": _n("Importar checklists e formulários", "Igual a Modificação: o módulo não diferencia."),
    },
    "relatorios": {
        "LEITURA": _n("Sem efeito hoje", "Os relatórios gerenciais da carteira são restritos ao SuperRoot; este nível ainda não libera nada."),
        "MODIFICACAO": _n("Sem efeito hoje", "Igual a Leitura: o módulo não diferencia."),
        "CONTROLE_TOTAL": _n("Sem efeito hoje", "Igual a Leitura: o módulo não diferencia."),
    },
    "contratacoes": {
        "LEITURA": _n("Acompanhar seus documentos", "Vê os documentos de contratação em que participa (criador, editor ou revisor)."),
        "MODIFICACAO": _n("Criar documentos de contratação", "Tudo isso e também cria novos documentos de contratação."),
        "CONTROLE_TOTAL": _n("Administrar todos os documentos", "Tudo isso e também vê e administra todos os documentos, de qualquer pessoa."),
    },
    "painel-executivo": {
        "LEITURA": _n("Ver o Painel Executivo", "Abre os slides e baixa os PDFs do painel."),
        "MODIFICACAO": _n("Ver o Painel Executivo", "Igual a Leitura: o módulo não diferencia."),
        "CONTROLE_TOTAL": _n("Ver o Painel Executivo", "Igual a Leitura: o módulo não diferencia."),
    },
    "melhorias": {
        "LEITURA": _n("Sugerir melhorias", "Qualquer nível permite enviar e acompanhar as próprias sugestões."),
        "MODIFICACAO": _n("Sugerir melhorias", "Igual a Leitura: o módulo não diferencia."),
        "CONTROLE_TOTAL": _n("Fazer a triagem das sugestões", "Tudo isso e também faz a triagem (muda a situação, responde) e recebe o aviso de sugestão nova."),
    },
    "noticias": {
        "LEITURA": _n("Ler notícias", "Lê as notícias publicadas."),
        "MODIFICACAO": _n("Redigir notícias", "Tudo isso e também escreve e edita notícias e as envia para aprovação."),
        "CONTROLE_TOTAL": _n("Aprovar e publicar notícias", "Tudo isso e também aprova e publica; recebe o pedido de aprovação."),
    },
    "mensageria-setores": {
        "LEITURA": _n("Sem efeito", "O envio para setores só existe no Controle total."),
        "MODIFICACAO": _n("Sem efeito", "O envio para setores só existe no Controle total."),
        "CONTROLE_TOTAL": _n("Enviar mensagens a setores", "Envia mensagens para setores inteiros."),
    },
    "usuarios": {
        "LEITURA": _n("Consultar usuários", "Vê a lista e os dados dos usuários."),
        "MODIFICACAO": _n("Consultar usuários", "Igual a Leitura: criar e alterar usuários exige Controle total."),
        "CONTROLE_TOTAL": _n("Gerenciar usuários", "Tudo isso e também cria, altera, ativa e desativa usuários (menos os papéis e senhas reservados ao SuperRoot)."),
    },
    "setores": {
        "LEITURA": _n("Consultar setores", "Vê a estrutura de setores e seus integrantes."),
        "MODIFICACAO": _n("Consultar setores", "Igual a Leitura: alterar a estrutura exige Controle total."),
        "CONTROLE_TOTAL": _n("Gerenciar setores", "Tudo isso e também cria, move, renomeia e exclui setores e define seus integrantes."),
    },
    "abrir-chamado": {
        "LEITURA": _n("Abrir chamados no GLPI", "Abre chamados de suporte pelo SGI e vê os que abriu."),
        "MODIFICACAO": _n("Abrir chamados no GLPI", "Igual a Leitura: o módulo não diferencia."),
        "CONTROLE_TOTAL": _n("Abrir chamados no GLPI", "Igual a Leitura: o módulo não diferencia."),
    },
    "atalhos": {
        "LEITURA": _n("Sem efeito", "Os atalhos fixos aparecem para todos; este nível não libera nada."),
        "MODIFICACAO": _n("Gerenciar atalhos fixos", "Cria, altera e exclui categorias e atalhos da barra lateral."),
        "CONTROLE_TOTAL": _n("Gerenciar atalhos fixos", "Igual a Modificação: o módulo não diferencia."),
    },
    "documentacao-api": {
        "LEITURA": _n("Ver a documentação da API", "Abre a documentação técnica (Swagger e ReDoc) e baixa a especificação."),
        "MODIFICACAO": _n("Ver a documentação da API", "Igual a Leitura: o módulo não diferencia."),
        "CONTROLE_TOTAL": _n("Ver a documentação da API", "Igual a Leitura: o módulo não diferencia."),
    },
    "manuais": {
        "LEITURA": _n("Ler os manuais", "Navega, busca e lê os manuais do BookStack dentro do SGI."),
        "MODIFICACAO": _n("Ler os manuais", "Igual a Leitura: o módulo não diferencia."),
        "CONTROLE_TOTAL": _n("Ler os manuais", "Igual a Leitura: o módulo não diferencia."),
    },
    "sla": {
        "LEITURA": _n("Ver as políticas de SLA", "Vê as metas de prazo (dias úteis) de tarefas e melhorias."),
        "MODIFICACAO": _n("Alterar as políticas de SLA", "Tudo isso e também altera as metas de resposta e resolução."),
        "CONTROLE_TOTAL": _n("Alterar as políticas de SLA", "Igual a Modificação: o módulo não diferencia."),
    },
    "reserva-espacos": {
        "LEITURA": _n("Usar a reserva de espaços", "Vê a agenda, solicita e altera as próprias reservas; os fiscais analisam as solicitações."),
        "MODIFICACAO": _n("Usar a reserva de espaços", "Igual a Leitura: o módulo não diferencia."),
        "CONTROLE_TOTAL": _n("Usar a reserva de espaços", "Igual a Leitura: o módulo não diferencia."),
    },
}


def textos_do_recurso(slug: str) -> dict[str, TextoNivel]:
    """Textos dos três níveis do recurso (os genéricos para um slug sem entrada, o que o teste impede)."""
    return {nivel: NIVEIS_POR_RECURSO.get(slug, {}).get(nivel, GENERICOS[nivel]) for nivel in GENERICOS}
