# Assinatura de e-mail (`/api/assinatura-email`)

Tag no OpenAPI: **Assinatura de e-mail**. Implementação:
- rotas: `backend/app/api/routes/assinatura_email.py`; schemas: `backend/app/schemas/assinatura_email.py`;
- geração: `backend/app/services/assinatura_email.py` (Pillow e a fonte Bitstream Vera, que vem com o reportlab); brasão em `backend/app/recursos/assinatura/sp_brasao.png`.

Trazido do app `assinatura_e_mail` do servidor de aplicações da SPI (10.23.1.243), com melhorias: PNG em alta resolução, versão em HTML, texto longo quebrado ou abreviado com aviso, celular e andar/lado opcionais e dados institucionais na configuração.

## Finalidade

Cada usuário gera a **própria** assinatura institucional: uma imagem PNG e um HTML para colar na assinatura do Outlook ou do webmail. Os dados do perfil só **pré-preenchem** o formulário; o que for ajustado na tela vale para a imagem e **nunca é gravado no perfil** (alterações do perfil passam pela validação da CGP).

## Endpoints

Autenticação: `Authorization: Bearer <token>` (perfil em dia; ver [autenticacao.md](autenticacao.md)). Qualquer usuário; sem ACL.

| Método e caminho | Resposta |
|---|---|
| `GET /api/assinatura-email/dados` | `LeituraDadosAssinatura`: dados **em vigor** do perfil (o que está pendente de validação da CGP não entra) `faltando` (nome, cargo, e-mail) e `telefone_prefixo` (prefixo do telefone; o ramal vem depois dele) |
| `POST /api/assinatura-email/previa` | `PreviaAssinatura`: `png_base64`, `html`, `avisos[]` |
| `POST /api/assinatura-email/png` | `200 image/png`, anexo `assinatura-email.png` |
| `POST /api/assinatura-email/html` | `200 text/html`, anexo `assinatura-email.html` |

**`DadosAssinatura`** (corpo dos três `POST`): `nome_completo` (até 220), `cargo` (180), `departamento` (180), `email` (formato válido), `ramal` (só dígitos e hífen, até 20), `celular` (dígitos, espaço, parênteses, `+` e hífen), `andar` (`Subsolo` ou `1` a `13`), `lado` (`A` ou `B`), `incluir_celular` e `incluir_andar_lado` (padrão `false`).

**Imagem:** PNG de **1692×471** (3× o tamanho de e-mail de 564×157; use-o a 564 px de largura). Esquerda: brasão e "GOVERNO DO ESTADO DE SÃO PAULO"; direita: nome, cargo, secretaria, departamento, e-mail, telefone (`prefixo + ramal`) e endereço, com os dois filetes inferiores do modelo da SPI. Celular e "5º andar · Lado B" saem alinhados ao telefone, só quando marcados e presentes.

**Texto longo:** nome e e-mail diminuem a fonte até o mínimo e depois são abreviados com "…"; cargo e departamento quebram em até duas linhas antes de abreviar. Cada abreviação gera um aviso (ex.: "Cargo muito longo: abreviado na imagem."). Campo marcado e ausente (celular, andar/lado) ou sem ramal também gera aviso.

**HTML:** tabela com estilos inline (Outlook e webmails), texto selecionável, `mailto:` e `tel:` clicáveis, brasão pequeno embutido (`data:`). Todo texto digitado é escapado.

### Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `400` | `invalido` | Nome, cargo ou e-mail vazio ("Informe nome, cargo para gerar a assinatura.") |
| `401` | `nao_autenticado` | Sem token ou token inválido |
| `403` | `revisao_perfil_obrigatoria` | Perfil pendente |
| `422` | `validacao` | E-mail, ramal ou celular em formato inválido; campo maior que o limite |

`png` e `html` são auditados como `assinatura.gerar` (formato; sem o conteúdo da assinatura).

## Configuração (opcional)

Os textos fixos e o prefixo do telefone vêm de variáveis de ambiente (padrões da SPI): `ASSINATURA_SECRETARIA` ("Secretaria de Parcerias em Investimentos – SPI"), `ASSINATURA_ENDERECO` ("Rua Iaiá, 126 - Itaim Bibi"), `ASSINATURA_CIDADE` ("São Paulo/SP – CEP 04542-906") e `ASSINATURA_TELEFONE_PREFIXO` ("(11) 3702-").

## Consumo no Angular

- **Menu do usuário** (canto superior direito): item "Assinatura de e-mail" abaixo de "Folha de ponto" (oculto com o perfil pendente). Rota `/assinatura-email`.
- Formulário pré-preenchido por `/dados`, com as caixas "Incluir celular" e "Incluir andar e lado"; **prévia ao vivo** (PNG e HTML) por `/previa`, com os avisos; botões **Baixar PNG**, **Copiar assinatura** (HTML na área de transferência) e **Baixar HTML**; aba "Como instalar" (Outlook e webmail).
