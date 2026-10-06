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

**Modelo:** a imagem é desenhada a partir de um PowerPoint, `backend/app/recursos/assinatura/modelo-assinatura.pptx` (o `GOV_ASSINATURA-DE-EMAIL_2023.pptx`, padrão do Governo de SP). **Para mudar o visual, troque esse arquivo** (mesmo nome, 1º slide); a próxima assinatura gerada já sai nova, sem reiniciar nem alterar código.

**Imagem:** PNG no **pixel original do fundo do modelo** (hoje **1765×492**, sem reamostrar: é a nitidez do arquivo do Governo; um PPTX com fundo de maior resolução gera uma imagem maior). Use-a a **564 px** de largura nos clientes de e-mail. O fundo traz a marca "SÃO PAULO – Governo do Estado", o divisor, as redes sociais e os filetes; o texto vem por cima, em cinco campos do modelo, reconhecidos pelo texto de exemplo (`Nome Sobrenome`, `Cargo`, `Órgão ou Secretaria`, `email@sp.gov.br | 11 0000-0000` e `Av. Morumbi, 4.500 - São Paulo - SP`) ou por fichas `{{nome}}`, `{{cargo}}`, `{{departamento}}`, `{{secretaria}}`, `{{email}}`, `{{telefone}}`, `{{celular}}`, `{{endereco}}`, `{{cidade}}` e `{{andar_lado}}`. Fonte: a do modelo (Verdana) se houver `Verdana.ttf` e `Verdana-Bold.ttf` em `recursos/assinatura/fontes/`; senão, a Bitstream Vera, de proporções parecidas.

**Conteúdo:** nome; cargo (negrito); departamento e Secretaria (configuração); e-mail e telefone (`prefixo + ramal`); endereço e cidade (configuração). Celular e "5º andar · Lado B", quando marcados e presentes, saem numa linha a mais.

**Espaço e texto longo:** o texto não pode passar de 75% da altura do modelo (embaixo ficam as redes sociais). Se não couber, o sistema aproxima as linhas e, em seguida, junta o endereço e a cidade numa linha e, por fim, tira as linhas opcionais (com aviso). Texto de uma linha que não cabe na largura encolhe até 80% do tamanho do modelo e depois é abreviado com "…". Cada abreviação gera um aviso (ex.: "Cargo muito longo: abreviado na imagem."). Campo marcado e ausente (celular, andar/lado) ou sem ramal também gera aviso.

**HTML:** a mesma imagem (embutida como `data:`, exibida a 564 px) em uma tabela, com o texto alternativo completo (nome, cargo, órgão, e-mail, telefone, endereço e extras); como o fundo do Governo é uma figura única, o texto não é selecionável nem tem `mailto:`/`tel:`. Todo texto digitado é escapado.

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
