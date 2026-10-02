# Folha de ponto no SGI SPI

**Para quem é este manual**

- **Servidores:** como gerar a própria folha de ponto do mês.
- **CGP (Coordenadoria de Gestão de Pessoas):** como cadastrar os dados funcionais (jornada, horários e documentos) que a folha exige, e como validar as alterações de cadastro.

---

## 1. Como funciona

Cada servidor gera a **própria** folha de ponto em PDF (A4, frente e verso), imprime, assina e entrega ao superior imediato.

O sistema preenche sozinho:

- o setor, o mês e a identificação do servidor;
- os dias de sábado e domingo;
- os feriados e pontos facultativos cadastrados;
- as férias e licenças-prêmio **aprovadas ou gozadas**.

Para a folha ser gerada, duas condições precisam estar atendidas:

1. O servidor **não pode ter alteração de cadastro aguardando validação** da CGP.
2. Os **dados funcionais** do servidor precisam estar preenchidos pela CGP: jornada de trabalho, horário de trabalho, intervalo de almoço e descanso, RG/CIN nº e RS/PV nº.

Se faltar alguma delas, o sistema mostra o aviso "Folha de ponto indisponível" e **avisa a CGP automaticamente** pela caixa de mensagens e por e-mail (no máximo um aviso por motivo, por servidor e por dia).

---

## 2. Servidor: gerar a folha de ponto

1. Entre no SGI SPI e, no canto superior direito, abra o **menu do seu nome**.
2. Clique em **Folha de ponto**.
3. Escolha o **mês** (o mês atual já vem selecionado; ficam disponíveis os últimos 12 meses e os próximos 2).
4. Clique em **Gerar PDF**. O arquivo `folha-ponto-AAAA-MM-<seu login>.pdf` é baixado.
5. Imprima (frente e verso), assine e entregue ao superior imediato.

> O item "Folha de ponto" só aparece depois que você confirma o seu perfil do mês (ver "Meu perfil").

### Se aparecer "Folha de ponto indisponível"

| Mensagem | O que significa | O que fazer |
|---|---|---|
| Dados funcionais incompletos | Falta jornada, horário, intervalo, RG/CIN ou RS/PV | Nada: a CGP já foi avisada. Tente de novo depois que ela completar |
| Alterações de cadastro aguardando validação | Você alterou o perfil e a CGP ainda não validou | Aguarde a validação da CGP |

---

## 3. CGP: cadastrar os dados funcionais

Os dados funcionais são **exclusivos da CGP** e não aparecem para o servidor. Há dois caminhos: um servidor por vez (tela) ou todos de uma vez (planilha).

### 3.1. Dados que a folha de ponto usa

| Campo | O que informar | Exemplo |
|---|---|---|
| Jornada de trabalho | Horas semanais, de 1 a 80 | 40 |
| Horário de trabalho | Início e fim (os dois, ou nenhum) | 09:00 às 18:00 |
| Intervalo de almoço e descanso | Início e fim (os dois, ou nenhum); o fim deve ser depois do início | 12:00 às 13:00 |
| RG/CIN nº | Até 30 caracteres: números, letras, ponto, hífen, barra e espaço | 12.345.678-9 |
| RS/PV nº | Mesmas regras do RG/CIN | 1.234.567/8 |
| Regime de plantão | Sim ou Não (padrão: Não; não bloqueia a folha) | Não |
| Horário de estudante | Sim ou Não (padrão: Não; não bloqueia a folha) | Não |

O horário de trabalho pode ter fim menor que o início (plantão noturno), mas início e fim não podem ser iguais.

Os campos **Servidor** e **Função** da folha vêm do perfil do usuário (nome e cargo). Informação não cadastrada sai **em branco** na folha.

### 3.2. Um servidor por vez (tela)

1. Abra **Usuários** no menu lateral e clique no servidor.
2. Na página do usuário, o bloco de **RH** (à direita) traz os dados funcionais.
3. Preencha jornada, horário de trabalho, intervalo, RG/CIN e RS/PV (e plantão e horário de estudante, se for o caso).
4. Clique em **Salvar usuário**. Isso grava também os demais dados funcionais do bloco.

Se os dados ficarem incompletos ou inválidos, o sistema recusa a gravação e informa o motivo.

### 3.3. Todos de uma vez (planilha)

1. Entre em **RH › Validações** e clique em **Importar planilha de dados funcionais**.
2. Clique em **Baixar modelo**. A planilha vem com todos os servidores ativos e os valores atuais; a aba **Instruções** explica cada coluna.
3. Preencha as colunas, principalmente: **Jornada (horas/semana)**, **Horário de trabalho** (formato `9:00 às 18:00`), **Intervalo de almoço e descanso** (formato `12:00 às 13:00`), **RG/CIN nº** e **RS/PV nº**.
4. Escolha o arquivo preenchido. O sistema mostra uma **prévia** por linha, com as mudanças e os erros, **sem gravar nada**.
5. Corrija os erros na planilha, se houver, e envie de novo.
6. Clique em **Importar**.

Regras da planilha:

- **A coluna Login identifica a linha** e é obrigatória. Nome e Setor são só informativos.
- **Célula vazia mantém o valor atual:** a planilha nunca apaga dados. Reenviar o modelo sem mexer não altera ninguém.
- **A importação é tudo ou nada:** se houver qualquer erro, nada é gravado.

### 3.4. Depois de completar os dados

Ao gravar os dados completos, o aviso que a CGP recebeu ("[Nome] quer baixar a folha de ponto, mas ainda não tem os dados preenchidos") é **encerrado sozinho**. Avise o servidor, se quiser, para ele gerar a folha.

---

## 4. CGP: validar as alterações de cadastro

Quando um servidor altera o perfil, a CGP recebe a mensagem "[Nome] alterou seu cadastro e aguarda validação da CGP". **Enquanto houver alteração pendente, o servidor não consegue gerar a folha.**

1. Entre em **RH › Validações**.
2. Use a lista de pendências (ou busque o servidor). Cada alteração mostra o valor em vigor e o valor proposto.
3. Para cada alteração:
   - **Validar:** o valor proposto passa a valer.
   - **Recusar:** informe a **justificativa** (obrigatória) e a **correção**. A correção passa a valer e o servidor recebe um e-mail com a justificativa.
4. Para validar muitas de uma vez: filtre por campo (por exemplo, só "Departamento"), use **Marcar todos** e **Validar selecionadas**. Dentro de um cadastro aberto, há também **Validar todas deste usuário**.

Quando não restar alteração pendente (validada ou recusada), o aviso da CGP é encerrado e o servidor volta a poder gerar a folha.

---

## 5. Conteúdo da folha

**Frente**

- Cabeçalho com o brasão, "Governo do Estado de São Paulo", "Secretaria de Parcerias em Investimentos", o **setor** do servidor e "Registro de ponto" do mês.
- Identificação: Servidor, Função, Jornada de Trabalho, Horário de Trabalho, Intervalo de Almoço e Descanso, RG/CIN nº, RS/PV nº, Regime de Plantão e Horário de Estudante.
- Tabela com **todos os dias do mês**: Entrada, Saída, Observações e Visto do Superior Imediato. Ficam marcados em vermelho:
  1. sábado e domingo;
  2. feriado ou ponto facultativo (com a descrição em Observações);
  3. férias ou licença-prêmio aprovadas ou gozadas (com o período em Observações).
- Informações financeiras em branco, para preencher à mão.
- Assinaturas do servidor e do superior imediato, com a data.

**Verso:** o mesmo cabeçalho, a área de "Consolidação" com linhas pautadas e a assinatura do superior imediato ou do responsável.

---

## 6. Perguntas frequentes

**Os feriados não saíram na folha.**
Eles precisam estar cadastrados em **RH › Feriados e pontos facultativos** (acesso da CGP).

**As férias não aparecem.**
Só entram férias e licenças-prêmio **aprovadas ou gozadas**. Pedidos pendentes, recusados e cancelados não aparecem.

**O setor está errado na folha.**
O setor vem do Departamento do perfil do servidor. Corrija o perfil e valide a alteração em **RH › Validações**.

**Posso gerar a folha de outro servidor?**
Não. Cada pessoa gera a própria folha.

**Não vejo "Folha de ponto" no menu.**
Confirme o perfil do mês em **Meu perfil**. Enquanto o perfil estiver pendente, só essa tela funciona.
