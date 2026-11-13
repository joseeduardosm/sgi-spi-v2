# Criado por José Eduardo Santana Martins
# Este arquivo serve para povoar o laboratório do manual da RDM: a equipe de Infraestrutura e tarefas com RDM em cada situação (dados fictícios).
"""Povoamento do laboratório do manual da RDM (nada disto vai para a produção; o banco é um SQLite descartável).

Pessoas (senha `senha-lab-1`): lia (lidera a equipe Infraestrutura, aprova as RDMs), ana (executa as tarefas), beto (membro).
Tarefas: #1 sem RDM, #2 RDM em rascunho, #3 pendente, #4 aprovada, #5 reprovada, #6 concluída e implantada.
"""

from datetime import UTC, date, datetime, timedelta

from cliente import FabricaSessao, Usuario, agora_utc, chamar, gerar_hash_senha, login

with FabricaSessao() as s:
    for login_, nome, cargo, setor in (("lia", "Lia Moreira Santos", "Coordenadora", "Coordenadoria de Gestão e Infraestrutura"),
                                       ("ana", "Ana Paula Ribeiro", "Analista de Infraestrutura", "Coordenadoria de Gestão e Infraestrutura"),
                                       ("beto", "Roberto Dias", "Técnico de Redes", "Coordenadoria de Gestão e Infraestrutura")):
        s.add(Usuario(login=login_, hash_senha=gerar_hash_senha("senha-lab-1"), nome_completo=nome, email=f"{login_}@exemplo.gov.br", ramal="4321",
                      cargo=cargo, departamento=setor, andar="5", predio="A", perfil_revisado_em=agora_utc(), boas_vindas_em=agora_utc(), boas_vindas_email_em=agora_utc()))
    s.commit()
    ids = {u.login: u.id for u in s.query(Usuario).all()}

lia, ana = login("lia"), login("ana")
equipe = chamar("POST", "/tarefas/equipes", lia, {"nome": "Infraestrutura", "lideres_ids": [ids["lia"]], "membros_ids": [ids["ana"], ids["beto"]]})
prazo = (datetime.now(UTC) + timedelta(days=12)).isoformat()


def tarefa(titulo: str) -> int:
    t = chamar("POST", "/tarefas", lia, {"titulo": titulo, "descricao": "<p>Tarefa da equipe de Infraestrutura.</p>", "prazo": prazo, "equipe_id": equipe["id"],
                                         "responsaveis_ids": [ids["ana"]], "prioridade": "alta"})
    chamar("POST", f"/tarefas/{t['numero']}/mover", ana, {"acao": "iniciar"})
    return t["numero"]


hoje = date.today()
janela = (hoje + timedelta(days=9)).isoformat()


def formulario(titulo: str, **extra) -> dict:
    """Uma RDM bem preenchida (o exemplo da planilha da Prodesp: drivers VirtIO na VM do AD)."""
    corpo = {
        "titulo": titulo,
        "identificacao": {"tipo": "PROGRAMADA", "solicitante": "Ana Paula Ribeiro", "area": "CGI / Servidores", "data_solicitacao": hoje.isoformat()},
        "objetivo": "Instalar os drivers da placa de rede e o guest-agent do Proxmox na VM Windows 105 (controlador de domínio), deixando a placa no padrão VirtIO.",
        "justificativa": "A VM está com a placa de rede fora do padrão do Proxmox (VirtIO), o que causa lentidão e impede o desligamento controlado pelo host.",
        "categorizacao": {"acao": "INSTALAÇÃO", "finalidade": "CORREÇÃO", "prioridade": "MÉDIA", "risco": "BAIXO", "impacto": "MÉDIO"},
        "abrangencia": {"departamentos": "Todos os setores (autenticação na rede)", "usuarios_internos": "350", "usuarios_externos": "0",
                        "ics": "VM 105 - AD01 (controlador de domínio e DNS)", "indisponibilidade": "SIM", "tempo_indisponibilidade": "1 hora"},
        "cronograma": [
            {"etapa": "HOMOLOGAÇÃO", "inicio": "", "duracao": "", "termino": ""},
            {"etapa": "EXECUÇÃO", "inicio": "07:00", "duracao": "2 horas", "termino": "09:00"},
            {"etapa": "VALIDAÇÃO", "inicio": "09:00", "duracao": "1 hora", "termino": "10:00"}],
        "janela": {"inicio_data": janela, "inicio_hora": "07:00", "fim_data": janela, "fim_hora": "10:00", "tempo": "03 horas"},
        "plano_execucao": [
            {"atividade": "Anexar a ISO virtio-win v173 ao drive de DVD da VM 105 no Proxmox", "executor": "CGI", "etapa": "EXECUÇÃO"},
            {"atividade": "Registrar a configuração de rede atual (IP, máscara, DNS)", "executor": "CGI", "etapa": "EXECUÇÃO"},
            {"atividade": "Executar o assistente virtio-win e instalar o guest-agent", "executor": "CGI", "etapa": "EXECUÇÃO"},
            {"atividade": "Desligar a VM, trocar o tipo da placa para VirtIO e religar", "executor": "CGI", "etapa": "EXECUÇÃO"},
            {"atividade": "Testar login no domínio, resolução de nomes e compartilhamentos", "executor": "CGI", "etapa": "VALIDAÇÃO"}],
        "comunicacao": [
            {"quem": "Todos os servidores", "momento": "Antecipado (2 dias antes)", "meio": "E-mail", "responsavel": "CGI"},
            {"quem": "Equipe de Infraestrutura", "momento": "Início e fim da atividade", "meio": "Chamados", "responsavel": "CGI"}],
        "rollback": [{"atividade": "Voltar o tipo da placa para e1000 e reaplicar a configuração registrada", "tempo": "00:30", "executor": "CGI"}],
        "rollback_justificativa": "Garantir a autenticação na rede caso o driver novo não funcione.",
        "conhecimento": [{"tipo_documento": d, "acao": "ALTERAÇÃO" if d == "PROCEDIMENTO" else "NÃO SE APLICA", "responsavel": "CGI" if d == "PROCEDIMENTO" else ""}
                         for d in ("INVENTÁRIO", "PROCEDIMENTO", "BASE DE CONHECIMENTO", "PLANO DE ESCALONAMENTO", "REGISTRO DE ERRO CONHECIDO")],
        "conhecimento_observacoes": "Atualizar o procedimento de criação de VMs Windows no Proxmox.",
        "complementares": {"categoria": "Servidores", "descricao_tecnica": "Proxmox VE 8, VM 105 (Windows Server 2022), driver virtio-win 0.1.173.",
                           "responsavel_execucao": "Ana Paula Ribeiro", "equipes_envolvidas": "Servidores e Redes", "impacto_previsto": "Médio",
                           "riscos": "A VM ficar sem rede depois da troca do tipo da placa.", "medidas_preventivas": "Snapshot da VM antes de começar.",
                           "procedimentos_validacao": "Login no domínio de duas estações e consulta de DNS.", "criterios_sucesso": "Rede e domínio funcionando sem erro por 1 hora.",
                           "pre_requisitos": ["Backup realizado e validado, quando aplicável", "Configurações atuais registradas", "Plano de rollback definido", "Janela de mudança acordada"],
                           "responsavel_analise_tecnica": "Roberto Dias", "observacoes_adicionais": ""},
    }
    corpo.update(extra)
    return corpo


n1 = tarefa("Atualizar o firmware do switch core")
n2 = tarefa("Instalar drivers VirtIO na VM 105 (AD)")
chamar("PUT", f"/tarefas/{n2}/rdm", ana, formulario("Instalar drivers VirtIO na VM 105 (AD)"))
n3 = tarefa("Parada para manutenção elétrica do gerador")
chamar("POST", f"/tarefas/{n3}/rdm/enviar", ana, formulario("Desligamento controlado da infraestrutura para teste do gerador",
       identificacao={"tipo": "PROGRAMADA", "solicitante": "Ana Paula Ribeiro", "area": "CGI", "data_solicitacao": hoje.isoformat()}))
n4 = tarefa("Trocar o firewall de borda")
chamar("POST", f"/tarefas/{n4}/rdm/enviar", ana, formulario("Substituição do firewall de borda"))
chamar("POST", f"/tarefas/{n4}/rdm/aprovar", lia)
n5 = tarefa("Migrar o DNS interno")
chamar("POST", f"/tarefas/{n5}/rdm/enviar", ana, formulario("Migração do DNS interno para o novo servidor", comunicacao=[]))
chamar("POST", f"/tarefas/{n5}/rdm/reprovar", lia, {"motivo": "Falta o plano de comunicação: os setores precisam ser avisados antes da janela."})
n6 = tarefa("Ampliar o armazenamento do servidor de arquivos")
chamar("POST", f"/tarefas/{n6}/rdm/enviar", ana, formulario("Ampliação do volume do servidor de arquivos"))
chamar("POST", f"/tarefas/{n6}/rdm/aprovar", lia)
chamar("POST", f"/tarefas/{n6}/mover", ana, {"acao": "entregar", "texto": "Ampliação feita e validada."})
chamar("POST", f"/tarefas/{n6}/mover", lia, {"acao": "validar"})
print("tarefas", n1, n2, n3, n4, n5, n6)
