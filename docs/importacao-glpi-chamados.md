# Importação do histórico do GLPI e roteiro da virada

Como trazer os chamados do GLPI (versão 10 ou 11) para o módulo Chamados e como desligar o GLPI depois.
O script **nunca fala com o GLPI em produção**: ele lê um arquivo de dump e, para os anexos, uma cópia da pasta `files/`.

## 1. O que a equipe do GLPI entrega

1. **Dump do banco, com dados**, gerado pela própria equipe do GLPI:
   `mysqldump --single-transaction --default-character-set=utf8mb4 helpdesk > glpi.sql`
2. **Cópia da pasta `files/`** do GLPI (sem `_cache`, `_log`, `_sessions` e `_tmp`), para os anexos. Sem ela, os chamados vêm sem anexos
   e o relatório diz quantos ficaram de fora.

Os dois arquivos ficam num lugar só de leitura para o servidor do SGI. Depois da carga, apague as cópias: elas têm dados pessoais.

## 2. Preparar o de-para (revisão humana)

Na pasta `backend` do servidor do SGI:

```
.venv/bin/python ../scripts/migrar-chamados-glpi.py preparar glpi.sql de-para/
```

Saem três planilhas (separador `;`, abrem no Excel ou LibreOffice). Revise **a última coluna** de cada uma:

| Arquivo | Última coluna | O que pôr |
|---|---|---|
| `usuarios.csv` | `login_sgi` | Login da pessoa no SGI. Já vem preenchido quando o login ou o e-mail batem. Vazio = a pessoa não tem conta: o chamado fica com o e-mail dela como "solicitante externo" e as mensagens dela ficam sem autor. |
| `grupos.csv` | `setor_sgi` | Nome do setor do SGI que corresponde ao grupo do GLPI. Vazio = o chamado cai no setor padrão. |
| `etiquetas.csv` | `acao` | `responsavel:<login>` (a etiqueta era o nome do técnico: vira o responsável), `setor:<nome do setor>`, `nota` (fica registrada na linha do tempo, só para a equipe) ou `ignorar`. |

## 3. Ensaio e carga

```
.venv/bin/python ../scripts/migrar-chamados-glpi.py carregar glpi.sql de-para/ --setor-padrao "Suporte TI" --arquivos files/
```

Sem `--gravar` é **ensaio**: carrega tudo numa transação, mostra o relatório e desfaz. O relatório (também gravado em
`de-para/relatorio-carregar.txt`) tem, para cada item, quantos havia no dump, quantos entraram e quantos já existiam, e a lista de avisos
(pessoa sem par, anexo que não está na pasta, categoria repetida, número já usado). Corrija o de-para e repita até o relatório ficar bom.

Para valer, acrescente `--gravar`. Pode rodar de novo quantas vezes precisar: o que já veio é pulado.

### O que entra e como

- **Chamado** mantém o número do GLPI; o próximo aberto no SGI continua depois do maior. Fica **somente leitura** (ninguém responde nem
  muda) e com os prazos e as datas do GLPI (o SLA não é recalculado). Status: novo → Novo; em atendimento e planejado → Em atendimento;
  pendente → Pendente; em aprovação → Em aprovação; solucionado e fechado → Solucionado. Excluído no GLPI → excluído aqui.
- **Categorias**: viram **categorias ITIL** (a classificação técnica), nunca assuntos. Nome repetido no mesmo nível ganha "(GLPI id)". Todos os
  importados ficam no assunto "Importados do GLPI" (inativo); o grupo da categoria no GLPI ainda serve de setor quando o chamado não tem grupo.
  O chamado ainda **aberto** no GLPI entra como chamado normal do SGI (só o resolvido fica somente leitura).
  Também há a **migração pelo botão** (Parâmetros > Migração do GLPI), que lê o banco do GLPI só para leitura: ver `docs/endpoints/chamados.md`.
- **Pessoas**: requerente → solicitante; o primeiro atribuído → responsável; os outros atribuídos e os observadores → em cópia
  (menos quem já é solicitante ou responsável). Grupo atribuído → setor responsável; grupo requerente → setor solicitante.
- **Linha do tempo**: acompanhamentos (o privado continua privado), soluções (só a última aceita fica vigente), tarefas, aprovações
  (no GLPI 11, o alvo pode ser um grupo) e anexos (do chamado, do acompanhamento e da solução).
- **Satisfação**: a nota (na escala de 5) e o comentário; pesquisa sem resposta entra como pedida e não respondida.
- **Não entram nesta versão**: formulários, base de conhecimento, ativos e o histórico de alterações (`glpi_logs`).

## 4. Roteiro da virada

1. **Antes** (dias): Parâmetros dos Chamados completos (categorias e setores da DGA e da TI, SLAs, expedientes, painel de TV pareado);
   ensaio da importação com um dump recente; equipe treinada.
2. **Na véspera**: pedir à equipe que resolva no GLPI o que der. O que continuar aberto será importado como somente leitura e precisa ser
   aberto de novo no SGI por quem atende (o relatório lista os números).
3. **No dia**:
   1. GLPI em **somente leitura** (perfil de solicitante sem "criar chamado"; a equipe do GLPI faz isso);
   2. dump final + cópia de `files/` → ensaio → `--gravar`;
   3. na ACL, criar as regras do recurso `chamados` (Leitura para todos, Modificação para quem atende, Controle total para a
      administração): isso **abre o módulo** para todos e o botão "Abrir Chamado" passa a levar para ele;
   4. Parâmetros > RH: escolher a categoria de cada serviço e trocar o destino para "Chamados do SGI" (a Nomeação para de ir ao GLPI).
4. **Depois** (período combinado): o GLPI fica só para consulta. Ao desligá-lo, sai do SGI a ponte antiga (`/api/chamados-glpi`,
   o modal de abertura no GLPI e a configuração em Integração GLPI), em uma alteração própria.
