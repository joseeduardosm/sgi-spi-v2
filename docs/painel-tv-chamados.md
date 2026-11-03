# Painel dos Chamados numa TV

O painel mostra, ao vivo, os chamados em que **o setor de quem está logado é o setor responsável**. Para deixar numa TV da sala da
equipe, basta um computador (ou mini-PC) ligado à TV, **logado no SGI com a conta de alguém do setor**.

## 1. Abrir o painel

1. Entre no SGI com a conta de alguém da equipe.
2. Vá em **Chamados › Painel** e clique em **Tela cheia**.

Quem administra ajusta a exibição em **Chamados › Parâmetros › Painel**: quantas linhas por página (ou automático, quantas couberem),
tamanho do texto (grande para ler de longe), tempo de cada página, voz, cor na linha inteira e quais colunas aparecem.
As cores do prazo (amarelo 50%, laranja 75%, vermelho 90%) ficam na aba **Geral**.

## 2. Chrome em modo quiosque (para a TV ligar sozinha no painel)

```
google-chrome --kiosk --autoplay-policy=no-user-gesture-required --noerrdialogs --disable-session-crashed-bubble \
  --disable-infobars --lang=pt-BR "https://<endereço do SGI>/chamados/painel"
```

- `--kiosk`: tela cheia, sem barra de endereço.
- `--autoplay-policy=no-user-gesture-required`: deixa a voz falar sem ninguém clicar na tela.
  A voz anuncia chamado novo, assumido, resolvido, reaberto e transferido para o painel (ver `docs/endpoints/chamados.md`).
- `--noerrdialogs --disable-session-crashed-bubble`: depois de uma queda de energia, o Chrome volta sem a janela "Restaurar páginas?".
- Na primeira vez, entre com a conta pelo próprio quiosque. A sessão se renova enquanto o painel estiver aberto.
- No Windows: o mesmo comando com `"C:\Program Files\Google\Chrome\Application\chrome.exe"` num atalho na pasta `shell:startup`.
  No Linux: um arquivo `.desktop` em `~/.config/autostart/` com a linha `Exec=` acima.

## 3. Conferências

- **Voz em português:** no console do Chrome (F12), `speechSynthesis.getVoices().filter(v => v.lang.startsWith('pt'))` não pode vir vazio.
  Se vier, instale a voz pt-BR do sistema.
- **Economia de energia:** desligue o descanso de tela e a suspensão do computador e da TV.
- **Selo "Ao vivo" / "Reconectando…":** "Reconectando…" por mais de um minuto quer dizer rede ou SGI fora; o painel volta sozinho e,
  enquanto isso, mostra a última situação conhecida.
- **A conta usada saiu do setor ou foi desativada:** o painel fica vazio ou pede login. Entre com outra conta do setor.
