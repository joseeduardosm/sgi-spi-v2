# Endpoints de cargos, organograma e histórico funcional (`/api/rh`)

Tag no OpenAPI: **RH – Cargos e histórico**. Implementação: `backend/app/api/routes/rh_cargos.py`, `backend/app/services/rh/servico_cargos.py` e `servico_historico.py`.

## Quem é o RH (ACL `rh`)

O RH deixou de depender do nome de um setor no código: é definido em **Controle de acesso > recurso `rh`** (regra direta, por setor ou por perfil).

| Nível | O que libera |
|---|---|
| **Leitura** | Consultar a estrutura do RH (cargos, organograma, pessoas a reconciliar) e os dados funcionais (RS/PV, RG/CIN) na busca de usuários |
| **Modificação** | Gerir setores e cargos: criar vagas, alocar e vagar pessoas, criar e alterar setores |
| **Controle total** | Ser o RH do sistema: validar cadastros, parâmetros, ver o histórico de qualquer pessoa |

- SuperRoot sempre tem acesso pleno.
- Enquanto o recurso `rh` não tiver regras nem perfis, vale o setor `setor_cgp` (configuração) como RH, para o sistema nunca ficar sem RH. A migração `d5a1c7e3b9f2` já cria a regra de Controle total para esse setor e dá Modificação a quem tinha Controle total em `setores`.
- Diferente dos demais módulos, `rh` **nunca** fica "aberto a todos" por não ter regras.

## Cargos (vagas)

`Cargo` é uma **posição** de um setor: tipo (CCESP, FCESP ou OUTRO), grupo (1 ou 2), nível (1 a 18) e denominação. Rótulo: "FCESP 2.16 – Assessor Especial IV". A `Ocupacao` guarda o histórico de quem ocupou; sem fim = vigente (uma vigente por cargo e uma por pessoa). Quem ocupa o cargo passa a ser membro do setor dele, e `cargo`/`departamento` do usuário viram espelho (rótulo do cargo e nome do setor); o perfil não os altera mais.

O ocupante vigente traz `foto_url` (mesma foto do Diretório; nulo sem foto), usada no organograma.

**Quem vê as vagas:** `GET /api/rh/organograma` é aberto a qualquer usuário autenticado, mas as **vagas** só aparecem para o RH (leitura ou mais) e para a liderança: o líder de um setor vê as vagas dele e as dos setores abaixo (e, em cadeia, os líderes acima fazem o mesmo). Liderados, colegas e líderes de outros setores não veem vagas, nem nas contagens. A tela de Cargos (`GET /api/rh/cargos`) segue só para o RH.

O organograma mostra **só pessoas do LDAP** (contas `ldap` e `local_ldap`): cargos ocupados por conta local (TV, serviço, teste) ficam fora da lista e das contagens, e conta local não aparece como líder.

`GET /api/rh/organograma` traz, em cada unidade, `lider` (`usuario_id`, `nome`, `cargo`, `foto_url`; nulo se o setor não tem líder) além de `lider_nome`.

## Rotas

| Método | Rota | Acesso (ACL `rh`) | Descrição |
|---|---|---|---|
| `GET` | `/api/rh/tipos-cargo` | Leitura | Tipos de cargo |
| `POST` | `/api/rh/tipos-cargo` | Modificação | Cadastra tipo (201) |
| `PUT` | `/api/rh/tipos-cargo/{tipo_id}` | Modificação | Altera tipo |
| `GET` | `/api/rh/cargos` | Leitura | Lista cargos; filtros `setor_id`, `tipo_id`, `situacao` (`vago`/`ocupado`), `busca`, `incluir_inativos` |
| `POST` | `/api/rh/cargos` | Modificação | Cria `quantidade` vagas iguais (201). 422 se CCESP/FCESP sem grupo e nível |
| `PUT` | `/api/rh/cargos/{cargo_id}` | Modificação | Altera o cargo |
| `DELETE` | `/api/rh/cargos/{cargo_id}` | Modificação | Exclui a vaga, **mesmo que já tenha tido ocupantes**: o histórico de ocupações dela e as admissões canceladas saem junto (ficam na auditoria `rh.cargo.excluir`; os eventos do histórico das pessoas continuam). `409` se o cargo está ocupado agora (vague antes) ou tem admissão em andamento/concluída (cancele-a ou desative o cargo). 204 em sucesso |
| `POST` | `/api/rh/cargos/{cargo_id}/ocupacao` | Modificação | Aloca a pessoa (`usuario_id`, `inicio`, `ato`). Se ela ocupa outro cargo, aquele termina como troca. 409 se o cargo está ocupado |
| `POST` | `/api/rh/cargos/{cargo_id}/vacancia` | Modificação | Encerra a ocupação (`fim`, `motivo`: `troca`, `exoneracao`, `dispensa`, `outro`; `ato`). Exoneração tem tipo próprio no histórico |
| `GET` | `/api/rh/cargos-a-reconciliar` | Leitura | Pessoas com cargo em texto livre ainda sem vínculo, com a sugestão interpretada |
| `POST` | `/api/rh/cargos-a-reconciliar/{usuario_id}` | Modificação | Cria o cargo sugerido no setor (`setor_id`) ou usa `cargo_id`, e aloca a pessoa |
| `GET` | `/api/rh/organograma` | Autenticado (vagas: RH ou liderança) | Árvore de setores com posições e ocupantes (`incluir_vagas`) |
| `GET` | `/api/rh/usuarios/{usuario_id}/historico` | Controle total ou a própria pessoa | Histórico funcional (`tipos`, `de`, `ate`). Fatos sigilosos só para o RH |
| `GET` | `/api/rh/usuarios/{usuario_id}/historico.pdf` | Controle total ou a própria pessoa | Mesmo conteúdo em PDF, com autor e data (dd/mm/aaaa hh:mm) |

Erros no formato `{"detalhe", "codigo"}`: 403 `acesso_negado` sem o nível exigido; 404 cargo/pessoa inexistente; 409 conflito de ocupação.

## Histórico funcional (`rh_historico`)

Livro-razão somente de inserção. Cada fato guarda tipo, título, detalhe, data do fato, quem registrou e a origem (`origem_tipo`, `origem_id`), o que torna a carga retroativa idempotente. Tipos: `cadastro`, `documento`, `cargo`, `setor`, `periodo_ferias`, `ferias`, `licenca_premio`, `exoneracao`, `admissao`, `outro`.

Registram sozinhos: alteração cadastral validada, criação de período aquisitivo, férias e licença-prêmio gozadas, posse, troca e vacância de cargo.

Carga retroativa: `backend/scripts_manutencao/carga-historico-rh.py` (simula por padrão; `--aplicar` grava). Migração dos cargos antigos: `migrar-cargos-legados.py` (mesmo padrão).

## Busca de usuários

**Seletores de pessoa** (`GET /api/usuarios/opcoes`, usado nos campos "pesquisar pessoa", como o das notificações do sistema) procuram **só na própria pessoa** (perfil, cargo e setor): digitar o nome de um chefe traz o chefe, não os liderados dele. Na **lista de usuários** (`GET /api/usuarios?busca=`) a busca é ampla, como descrito abaixo, e quem tem o nome ou o login pesquisado vem **primeiro**.

`GET /api/usuarios?busca=` procura por **todas as palavras** em nome, login, e-mail, cargo, setor, chefia imediata e mediata (líder do setor, do pai e do avô) e superior do cadastro. Dados funcionais (RS/PV, RG/CIN) entram na busca só para quem tem Leitura no RH.

## Setor de apoio administrativo

`GET`/`PUT /api/rh/parametros` passam a trazer `setor_reserva_protocolo_id` (setor da CGI, que dá andamento nos números "Reservado CGI"; vazio = pelo nome da configuração `setor_reserva_protocolo`) e `tipo_resolucao_protocolo_id` (tipo do Protocolo da resolução de admissão; vazio = resolução sem número; veja rh-admissao.md) e `setor_apoio_administrativo_id` (Serviço de Apoio Administrativo, que vê os tipos do Protocolo restritos a um setor; vazio = pelo nome da configuração `setor_apoio_administrativo`; migração `d7e3f9a5b1c4`).

---

# Pré-cadastro (`/api/rh/pre-cadastros`)

Tag no OpenAPI: **Módulo RH: pré-cadastro**. Implementação: `api/routes/rh_pre_cadastro.py` e `services/rh/servico_pre_cadastro.py`. Todas as rotas exigem **Controle total** no RH (dados pessoais sensíveis).

A ficha reúne o que um pré-cadastro de emprego pede: identificação, documentos (CPF, RG/CIN, PIS/PASEP, título, CTPS, CNH), contato, endereço, vínculo (tipo, órgão e cargo de origem, RS/PV, início previsto, cargo pretendido), formações e experiências (1 a N). CPF e PIS/PASEP têm os dígitos verificadores conferidos e são gravados só com dígitos; CEP tem 8 dígitos; UF, 2 letras.

**Login proposto:** único entre usuários do SGI, fichas não canceladas e o AD. Vai como proposta para a TI no chamado do GLPI. Quando a conta aparece (sincronização do AD ou primeiro login), a ficha é **vinculada automaticamente** (`status = vinculado`), o que o usuário ainda não tem é copiado (data de nascimento, celular, RS/PV, RG/CIN) e o histórico funcional registra o fato.

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/rh/pre-cadastros/login-disponivel?login=&ficha_id=` | Confere o login no SGI e no AD (só leitura). `verificado_no_ad = false` quando o AD não está configurado ou não respondeu. `motivo`: `livre`, `formato`, `usuario`, `ficha`, `ad`, `ad_indisponivel` |
| `GET` | `/api/rh/pre-cadastros?busca=&status=` | Lista (sem dados sensíveis). A busca procura por todas as palavras em nome, login, CPF, documentos, RS/PV e cargo de origem |
| `POST` | `/api/rh/pre-cadastros` | Cria (201). 400 em CPF/PIS/CEP/UF inválidos ou `aguardando_conta` sem login; 409 se o login estiver ocupado |
| `GET` | `/api/rh/pre-cadastros/{id}` | Consulta a ficha completa |
| `PUT` | `/api/rh/pre-cadastros/{id}` | Substitui dados, formações e experiências. 409 se já vinculada ou cancelada |
| `DELETE` | `/api/rh/pre-cadastros/{id}` | Cancela e libera o login (204). 409 se já vinculada |

### Ficha por planilha (formulário XLSX de uma pessoa)

O RH baixa um **formulário** em XLSX, envia à pessoa, que preenche e devolve; o RH importa o arquivo. **Um arquivo = a ficha de uma pessoa.** Fluxo: modelo → prévia → importação. Exige **Controle total** no RH.

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/rh/pre-cadastros/importacao/modelo` | Formulário em branco |
| `POST` | `/api/rh/pre-cadastros/importacao/previa` | `multipart/form-data` com `arquivo`. Confere sem gravar e devolve os erros (uma linha no resultado) |
| `POST` | `/api/rh/pre-cadastros/importacao` | Mesma planilha: confere de novo e, **sem erro**, cria a ficha como **rascunho** (201, com `ficha_id`). Com erro, `400` e nada é gravado. Auditado como `rh.pre_cadastro.importar` |

**O formulário:** uma aba só ("Ficha"), no formato de formulário: instruções no topo, seções (identificação, documentos, contato, endereço, vínculo com o serviço público, formação, experiências anteriores), **rótulos bloqueados** e **só as células de resposta liberadas** (a planilha vai protegida, sem senha). Onde há opções fixas (sexo, estado civil, UF, tipo de vínculo, nível de formação, Sim/Não) a célula tem lista. Se a pessoa digitar fora do padrão (CPF, PIS ou CEP com a quantidade errada de números, e-mail sem "@", data inválida ou futura, ano fora de 1950–2100, texto longo demais), o Excel bloqueia e explica como preencher; ao selecionar a célula, uma dica mostra o que escrever. Formação e experiências têm 5 linhas cada.

**Leitura:** cada célula de resposta tem um nome definido (`f_cpf`, `fo1_curso`, `ex2_empresa`...), e o arquivo é lido por eles, não pela posição. Uma planilha que não seja o formulário dá `400`.

**O que a pessoa não preenche:** setor e cargo pretendidos, login proposto, início previsto e a situação da ficha. Esses ficam com o RH, na ficha criada como rascunho.

Regras conferidas na prévia (as mesmas da tela): nome e CPF obrigatórios, CPF e PIS/PASEP com dígitos verificadores, CEP com 8 dígitos, UF com 2 letras, datas dd/mm/aaaa, fim da experiência não anterior ao início e CPF ainda não cadastrado em outra ficha ativa.

O CPF também é único fora da planilha: criar ou alterar uma ficha com CPF já presente em outra ficha ativa dá `409`.

Status: `rascunho`, `aguardando_conta` (pronta, esperando a conta no AD), `vinculado`, `cancelado`.

**Ficha dos legados:** quem já tinha conta preenche a própria ficha (`PUT /api/rh/minha-ficha`) e o RH valida (`POST /api/rh/pre-cadastros/{id}/validar`; `?pendentes_de_validacao=true` na lista). O RH pode corrigir a ficha antes de validar. Ver [rh-admissao.md](rh-admissao.md).

**Busca de usuários:** com Controle total no RH, `GET /api/usuarios?busca=` também procura nos dados da ficha vinculada (nome da mãe e do pai, CPF, RG/CIN, PIS, e-mail pessoal, cidade, órgão e cargo de origem...).


## Posse sem data (vínculos automáticos)

`ocupante.inicio` (cargos) e `inicio` das ocupações do histórico podem ser **nulos**: os vínculos automáticos do cadastro anterior (`POST /cargos-a-reconciliar/{usuario_id}`, ato "Vínculo do cadastro anterior") ficam **sem data de posse**, em vez de uma data inventada (migração `f9a5b1c7d3e6` também limpou a data dos 100 vínculos já criados). Sem data, alocar a pessoa em outro cargo (`POST /cargos/{id}/ocupacao`) funciona com qualquer data de posse e encerra o vínculo como troca. A tela mostra a posse em branco.
