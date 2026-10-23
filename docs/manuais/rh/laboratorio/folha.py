# Folha de contato: junta vários prints numa imagem só (2 colunas) para conferir o layout de relance.
import sys
from PIL import Image
nomes = sys.argv[2:]
imgs = [Image.open(f"../imagens/{n}.png").convert("RGB") for n in nomes]
L = 760
imgs = [i.resize((L, int(i.height * L / i.width))) for i in imgs]
cols = 2; linhas = (len(imgs) + 1) // 2
altura = [max(i.height for i in imgs[r * 2:r * 2 + 2]) for r in range(linhas)]
folha = Image.new("RGB", (L * cols + 10, sum(altura) + 10 * linhas), "white")
y = 0
for r in range(linhas):
    for c, i in enumerate(imgs[r * 2:r * 2 + 2]):
        folha.paste(i, (c * (L + 10), y))
    y += altura[r] + 10
folha.save(sys.argv[1])
