# Importação do SGI (`/api/contratos/migracao-sgi`)

Tag no OpenAPI: **Contratos: importação do SGI**. Serviço: `backend/app/services/contratos/servico_migracao_sgi.py`.

Traz o Módulo de Contratos do SGI SPI para este servidor pela tela, com o botão **Importar do SGI** da
carteira (`/contratos`), visível só para o SuperRoot. Por baixo, roda os mesmos scripts da migração pelo
terminal ([../migracao-sgi.md](../migracao-sgi.md)).

## Regras

- **Autorização:** papel SuperRoot nas duas rotas; os demais recebem `403 acesso_negado`.
- **Senhas:** o SuperRoot informa duas senhas a cada execução. Elas são conferidas por SSH antes de começar e
  **nunca são gravadas** (nem no estado, nem no registro, nem na auditoria):
  - `senha_origem`: usuário `MIGRACAO_SGI_USUARIO` em `MIGRACAO_SGI_HOST` (padrão `administrador@10.23.1.220`).
    Também precisa ser aceita pelo `sudo` de lá, porque a extração lê o banco como `postgres`;
  - `senha_destino`: usuário `MIGRACAO_LOCAL_USUARIO` em `MIGRACAO_LOCAL_HOST` (padrão `administrador@127.0.0.1`,
    este servidor). Serve de confirmação de quem opera o servidor.
- **Execução em segundo plano** (leva alguns minutos), uma por vez:
  1. `extraindo`: extração somente leitura do SGI (nada é alterado lá);
  2. `carregando`: carga com conferência e **substituição**. Todos os contratos, empresas, anexos e a
     auditoria migrada deste servidor são apagados e substituídos pelos do SGI. Se a conferência divergir,
     nada é gravado.
  3. O pacote extraído (dados pessoais e documentos) é apagado do disco ao final, com sucesso ou erro.
- **Estado** em `MIGRACAO_DIRETORIO/estado.json` (padrão `dados/migracao-sgi/`, permissão 700), para valer
  entre os workers da API. Se o serviço for reiniciado no meio, a execução aparece como `erro` (interrompida).
- **Auditoria:** `contrato.migracao_sgi.iniciar`, `contrato.migracao_sgi.concluir` (com as quantidades) e
  `contrato.migracao_sgi.falhar` (com o erro), com `alvo_tipo = migracao`.
- **Segurança de rede:** as senhas trafegam no corpo da requisição. Com o site em HTTP, elas passam sem
  criptografia pela rede; use HTTPS no Nginx para operar este recurso.

## `GET /api/contratos/migracao-sgi`

Resposta `200` (`EstadoMigracaoSgi`):

| Campo | Descrição |
|---|---|
| `situacao` | `ociosa`, `executando`, `concluida` ou `erro` |
| `etapa` | `iniciando`, `extraindo`, `carregando` ou `concluida` |
| `mensagem` | Texto da etapa ou do erro |
| `origem`, `destino` | `usuario@servidor` configurados |
| `iniciada_em`, `concluida_em`, `iniciada_por` | Quando e por quem |
| `resultado` | Quantidades carregadas (`empresas`, `contratos`, `competencias`, `anexos`, …) |
| `avisos` | Avisos da carga (ex.: valor global calculado diferente do gravado pelo SGI) |
| `log` | Últimas 40 linhas do registro da execução |

## `POST /api/contratos/migracao-sgi`

Corpo (`InicioMigracaoSgi`):

```json
{ "senha_origem": "…", "senha_destino": "…" }
```

Resposta **`202`** com o `EstadoMigracaoSgi` (`situacao = executando`). Erros:

| HTTP | `codigo` | Quando |
|---|---|---|
| `400` | `senha_invalida` | Senha incorreta em um dos servidores ou recusada pelo `sudo` da origem (o `detalhe` diz qual) |
| `409` | `conflito` | Já existe uma importação em andamento |
| `502` | `servidor_inacessivel` | Não foi possível conectar por SSH |

## Consumo no Angular

- Botão **Importar do SGI** no cabeçalho da carteira (`/contratos`), só para o SuperRoot.
- Janela com as duas senhas (origem e destino, com usuário e servidor à vista) e confirmação com contagem
  regressiva, porque a carga substitui os dados do módulo.
- Enquanto `situacao = executando`, a tela consulta o `GET` a cada 3 segundos e mostra a etapa e o registro. Ao
  concluir, recarrega a carteira e mostra as quantidades importadas.
