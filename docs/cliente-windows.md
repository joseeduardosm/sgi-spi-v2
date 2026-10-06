# SGI SPI Alertas (cliente para Windows)

Aplicativo de bandeja que mostra as mensagens do SGI (mensageria) como **alertas no canto inferior direito da tela**, perto do relógio.
Código em `client/`; o instalador pronto é `client/SgiSpiAlertas-<versão>.msi`. Não há endpoint novo: o aplicativo usa a API existente.

## Como funciona
- **Instalação:** MSI por máquina (precisa de administrador) em `C:\Program Files\SGI SPI Alertas`. Não exige .NET no PC (o programa leva o próprio). Windows 10 e 11, 64 bits. Atalho "SGI SPI Alertas" no menu Iniciar.
- **Início:** executa sozinho no logon de **cada usuário** do Windows (chave `Run` em `HKLM`). Em cada sessão abre no **centro da tela** a janela de login, com o login do Windows já preenchido; só falta a senha.
- **Credenciais do Windows:** o Windows não entrega a senha de quem está logado, e usar o logon integrado (Kerberos/NTLM) exigiria configurar o servidor para isso. Por isso, hoje, o usuário digita a senha a cada sessão. A senha nunca é gravada: só o token fica em memória, e ele é renovado pelo próprio uso (`X-Token-Renovado`).
- **Conexão:** `https://portal.spi.sp.gov.br`. Se o DNS falhar, conecta pelo IP `10.23.0.254`, mas o HTTPS continua sendo negociado com o nome do portal (o certificado é conferido normalmente).
- **Consulta:** a cada 60 s chama `GET /api/mensagens?estado=pendentes`; quando há mensagem nova, chama também `GET /api/mensagens/resumo` (para saber quais avisos abrem em janela). Uma mensagem vira alerta uma única vez por usuário/computador (`%LOCALAPPDATA%\SgiSpiAlertas\vistos-<login>.json`).
- **Alertas:** cartão com categoria, assunto e remetente, som do Windows, sem tirar o foco. Some em 15 s; os de prioridade **alta/crítica** e os que o sistema manda abrir em janela **ficam até alguém fechar**. Clicar abre a mensagem no navegador (a ciência continua sendo dada no portal). Na primeira vez no computador, a caixa pendente vira um aviso só ("Você tem N mensagens pendentes"). Mais de 3 novas de uma vez: 3 alertas e um resumo.
- **Bandeja:** menu com situação, mensagens pendentes, "Abrir o SGI", "Trocar usuário…" e "Sair". Se a sessão expirar, o login reabre.

## Configuração opcional
Os padrões estão no programa. Para trocar servidor, IP alternativo ou intervalos, a TI cria `appsettings.json` ao lado do `.exe`:
```json
{ "Servidor": "portal.spi.sp.gov.br", "IpAlternativo": "10.23.0.254", "IntervaloSegundos": 60, "SegundosAlerta": 15 }
```
O MSI não inclui esse arquivo, então atualizações não o sobrescrevem.

## Como gerar o instalador
`client/construir.sh` publica o aplicativo (C#/.NET 8, `win-x64`, um único .exe) e monta o MSI com `wixl`. Neste servidor: .NET 8 SDK da Microsoft em `~/.dotnet` e os pacotes `wixl` e `msitools`. A versão vem de `<Version>` em `client/SgiAlertas/SgiAlertas.csproj`.

## Implantação e limites
- Para centenas de PCs, distribua por GPO/SCCM/Intune: `msiexec /i SgiSpiAlertas-1.0.0.msi /qn`. Atualizar = instalar o MSI de versão maior por cima; remover = `msiexec /x` ou "Aplicativos" do Windows.
- O MSI **não é assinado digitalmente**: o SmartScreen pode avisar na instalação manual. A distribuição por GPO/SCCM não é afetada. Se quiserem assinar, é preciso um certificado de assinatura de código da TI.
- O certificado HTTPS do portal precisa ser confiável no Windows do usuário (certificado interno da rede já instalado nos PCs do domínio).
- Carga na API: 1 consulta por usuário a cada 60 s.
- O MSI foi gerado em Linux e a estrutura foi conferida (tabelas do MSI), mas **não foi testado em um Windows**: faça a primeira instalação em um PC de teste.
