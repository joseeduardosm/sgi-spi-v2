# Módulo Melhorias (`/api/melhorias`)

Tag no OpenAPI: **Melhorias**. Implementação:
- rotas: `backend/app/api/routes/melhorias.py`;
- regras: `backend/app/services/servico_melhorias.py`;
- modelos: `backend/app/models/melhorias.py` (migração `11d8a496ccab`).

Trazido do "Banco de melhorias" do 10.23.1.220, com retorno ao autor, triagem pela ACL, prints, conversão em tarefa e relatórios.

## Finalidade

Qualquer usuário logado sugere melhorias no sistema pelo botão flutuante **"Sugerir melhoria"**, presente em todas as telas autenticadas. A equipe responsável faz a triagem, responde ao autor e pode transformar a sugestão em tarefa.

## Quem faz o quê (recurso `melhorias` da ACL)

| Quem | Pode |
|---|---|
| Qualquer usuário logado (perfil em dia) | Enviar sugestões, acompanhar as próprias em "Minhas sugestões" e baixar os próprios prints |
| **SuperRoot** ou **CONTROLE_TOTAL** em `melhorias` | Triagem: listar, filtrar, tratar (situação, resposta, observação interna), converter em tarefa, exportar XLSX e PDF |

- O recurso `melhorias` é criado pela migração **sem regras**. Nesse estado, só o SuperRoot faz a triagem; ninguém vira triador por acaso.
- Sem triagem, as rotas de triagem respondem `403 acl_negado`.
- A sugestão de outra pessoa responde `404`, para não revelar que ela existe.

## Situações

`nova` → `em_analise` → `aceita` / `recusada` → `concluida`. A situação é livre na triagem: qualquer uma pode ser escolhida.

## Regras

- **Texto:** de 1 a 4.000 caracteres. A tela de origem (`tela`, a rota do Angular) vai junto, e o **módulo** é derivado dela:
  - `/contratos…` → `contratos`; `/rh…` → `rh`; `/tarefas…` → `tarefas`; `/noticias…` → `noticias`;
  - `/usuarios`, `/setores` e `/admin…` → `administracao`; `/` → `portal`; outras rotas → `geral`.
- **Prints:** até **3** imagens PNG, JPG ou WebP, conferidas pelo conteúdo. Formato inválido → `400` com o nome do arquivo.
- **Número público:** `#N`, sequencial. As rotas usam o número.
- **Aviso de sugestão nova:** quem faz a triagem (SuperRoot e CONTROLE_TOTAL, ativos) recebe um aviso na caixa de Mensagens, categoria pendência, com e-mail e link para `/melhorias/triagem?sugestao=N`.
- **Aviso ao autor:** quando a situação muda, ou quando a resposta muda e não fica vazia, o autor recebe um aviso na caixa de Mensagens, com e-mail e link para `/melhorias?sugestao=N`. Mudar só a observação interna não gera aviso.
- **Observação interna:** até 12.000 caracteres e **nunca** vai ao autor. Os schemas do autor (`SugestaoAutor`) não têm esse campo.
- **Histórico:** cada tratamento grava um evento (quem, quando, de → para). Tratar sem nenhuma mudança não grava nada.
- **Converter em tarefa:**
  - cria a tarefa no [Módulo Tarefas](tarefas.md) com título, prazo, prioridade, equipe e responsável;
  - a descrição da tarefa leva o número, o autor, a data, a tela e o texto da sugestão;
  - valem as regras do Tarefas (ex.: numa equipe, o responsável precisa ser da equipe → `400`);
  - a sugestão fica **Aceita** se estava Nova ou Em análise, e o autor é avisado;
  - uma segunda conversão → `409 conflito`.
- **Auditoria:** `melhorias.enviar`, `melhorias.tratar` e `melhorias.tarefa`.

## Schemas

### `GravacaoSugestao` (campo `dados` do multipart)

| Campo | Tipo | Regras |
|---|---|---|
| `texto` | string | 1 a 4.000 caracteres (espaços nas pontas são removidos) |
| `tela` | string | Até 1.000 caracteres; a rota em que o usuário estava |

### `SugestaoAutor` (resposta ao autor)

`id`, `numero`, `texto`, `tela`, `modulo`, `situacao`, `resposta_publica`, `criado_em`, `atualizado_em` e `prints[]` (`id`, `nome`, `tamanho`, `url`). A `url` baixa o print com o token.

### `SugestaoTriagem` (triagem)

Os campos de `SugestaoAutor`, mais:
- `autor_id`, `autor_nome`, `autor_login` (retrato do momento do envio);
- `observacao_interna`, `atualizado_por_nome`;
- `tarefa_numero`, a tarefa criada a partir da sugestão, se houver;
- `sla` (`SlaItem`, só na triagem; o autor não vê): resposta = primeira mudança de situação, resolução = conclusão ou recusa, em dias úteis com a política de [sla.md](sla.md); a planilha ganhou as colunas "SLA resposta" e "SLA resolução";
- `eventos[]`, com `descricao`, `situacao_anterior`, `situacao_nova`, `autor_nome` e `criado_em`.

### `PaginaSugestoesTriagem`

`itens[]`, `total`, `pagina`, `tamanho`, mais:
- `totais`: quantidade por situação, com os demais filtros aplicados (os selos da tela);
- `modulos`: os módulos que têm sugestões, para o filtro.

### `TratamentoSugestao` (`PUT`)

| Campo | Tipo | Regras |
|---|---|---|
| `situacao` | `nova` \| `em_analise` \| `aceita` \| `recusada` \| `concluida` | Obrigatório |
| `resposta_publica` | string | Até 4.000; vai ao autor |
| `observacao_interna` | string | Até 12.000; só a triagem vê |

### `ConversaoTarefa` (`POST …/tarefa`)

| Campo | Tipo | Regras |
|---|---|---|
| `titulo` | string | 1 a 200 |
| `prazo` | datetime | Obrigatório |
| `prioridade` | `baixa` \| `normal` \| `alta` \| `critica` | Padrão `normal` |
| `equipe_id` | UUID \| null | Equipe do Tarefas (vazio: tarefa pessoal) |
| `responsavel_id` | int \| null | Vazio: quem converte |

## Endpoints

Todas as rotas exigem login com o perfil em dia.

| Método e caminho | Quem | Descrição | Respostas |
|---|---|---|---|
| `GET /api/melhorias/acesso` | Logado | `{ "triagem": bool }`, para a tela mostrar a aba Triagem | `200` |
| `POST /api/melhorias/sugestoes` | Logado | `multipart/form-data`: `dados` (JSON de `GravacaoSugestao`) e até 3 `arquivos` | `201` `SugestaoAutor`, `400`, `422` |
| `GET /api/melhorias/minhas?pagina=&tamanho=` | Logado | Minhas sugestões, da mais recente para a mais antiga | `200` |
| `GET /api/melhorias/minhas/{numero}` | Autor | Uma das minhas sugestões | `200`, `404` |
| `GET /api/melhorias/sugestoes/{numero}/prints/{anexo_id}` | Autor ou triagem | Baixa o print | `200` imagem, `404` |
| `GET /api/melhorias/sugestoes` | Triagem | Lista com os filtros `busca` (texto, autor, login, tela ou `#N`), `situacao`, `modulo`, `inicio` e `fim` (dias de envio, inclusivos), mais `pagina` e `tamanho` | `200` `PaginaSugestoesTriagem`, `400` (período invertido), `403` |
| `GET /api/melhorias/sugestoes/exportar` | Triagem | XLSX com os mesmos filtros (sem paginação) | `200`, `403` |
| `GET /api/melhorias/sugestoes/relatorio` | Triagem | PDF com os mesmos filtros: resumo por situação e por módulo e uma seção por sugestão, com os prints | `200` `application/pdf`, `403` |
| `GET /api/melhorias/sugestoes/{numero}` | Triagem | Detalhe | `200` `SugestaoTriagem`, `403`, `404` |
| `PUT /api/melhorias/sugestoes/{numero}` | Triagem | Trata a sugestão (`TratamentoSugestao`) | `200`, `403`, `404`, `422` |
| `POST /api/melhorias/sugestoes/{numero}/tarefa` | Triagem | Converte em tarefa (`ConversaoTarefa`) | `200` `SugestaoTriagem`, `400`, `403`, `404`, `409` |

Exemplo de envio:

```bash
curl -X POST https://portal.spi.sp.gov.br/api/melhorias/sugestoes \
  -H "Authorization: Bearer <token>" \
  -F 'dados={"texto":"O painel de contratos poderia lembrar os filtros da última visita.","tela":"/contratos/painel"}' \
  -F 'arquivos=@print.png'
```

## Consumo no Angular

- **Botão flutuante** (`shared/componentes/botao-melhorias/botao-melhorias.component.ts`), no `LayoutAutenticadoComponent`. Não aparece com o perfil pendente.
  - **Arrastar:** o botão pode ser arrastado para qualquer ponto da tela (mouse, caneta ou toque), sem sair da janela. Um clique sem arrasto abre a janela de envio.
  - **"×":** esconde o botão **só nesta aba**.
  - **Posição e "fechado":** ficam no `sessionStorage` (chave `sgi-melhorias-botao`), que é por aba. Recarregar mantém o estado; uma **aba nova volta ao canto inferior direito**, visível.
  - **Janela de envio:** texto (contador de 4.000), a tela e o módulo de origem e até 3 prints (escolher arquivo ou **colar com Ctrl+V**). Ao enviar, o aviso "Sugestão #N enviada" traz o link para "Minhas sugestões".
- **`/melhorias` (Minhas sugestões):** item **Melhorias** em Módulos na barra lateral. Mostra cartões com a situação, o módulo, a data, o texto, os prints e a resposta da equipe. `?sugestao=N` destaca a sugestão.
- **`/melhorias/triagem`:** o atalho só aparece se `GET /acesso` devolver `triagem: true`; sem acesso, a tela mostra o aviso.
  - **Lista:** abas por situação com os totais; filtros de busca, módulo e período; "Exportar planilha" e "Relatório PDF".
  - **Janela de tratamento:** dados, prints, situação, resposta ao autor, observação interna, histórico e "Converter em tarefa" (equipe, responsável, prazo e prioridade).
  - `?sugestao=N` abre a sugestão.
- **Serviço:** `features/melhorias/melhorias-api.service.ts`. O envio usa `FormData`; os downloads usam `baixarArquivo`.
