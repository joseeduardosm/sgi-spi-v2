# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras de conversão dos ativos do GLPI em bens do Patrimônio (funções puras, sem acesso ao GLPI nem ao banco).
"""Conversão dos ativos do GLPI em bens do Patrimônio.

Só três informações vêm do GLPI, e nada vai para o campo de observações:
- Patrimônio (`otherserial`) vira a chapa; vazio ou "N/C" (e parecidos) significa que o bem **não tem patrimônio** e fica sem chapa.
  Chapa repetida no GLPI vale só para o primeiro ativo.
- Número de série (`serial`) vai para o campo próprio.
- Descrição: o tipo do equipamento (Notebook, Switch, Desktop, Monitor...) seguido da marca e do modelo.
- Inservível no GLPI (local "INSERVÍVEL..." ou estado DESCARTE): entra como ativo, com conservação 1.
Todos os bens entram na localização "NECESSÁRIO ATUALIZAR" (sem andar), para a equipe ajustar depois por movimentação.
"""

import re
from typing import Any

# Tipos de ativo do GLPI: tabela -> descrição quando o GLPI não informa um tipo aproveitável
TIPOS_GLPI = {
    "computers": "Computador",
    "monitors": "Monitor",
    "printers": "Impressora",
    "phones": "Telefone IP",
    "peripherals": "Periférico",
    "networkequipments": "Equipamento de rede",
}
# Tipos do GLPI que servem como descrição (o resto é sujeira, como fabricante cadastrado no lugar do tipo); a chave está em minúsculas
TIPOS_APROVEITADOS = {
    "notebook": "Notebook", "desktop": "Desktop", "qemu": "Máquina virtual", "televisão": "Televisão", "voip": "Telefone IP", "keyboard": "Teclado",
    "webcam": "Webcam", "headset": "Headset", "módulo transceptor sfp+": "Módulo transceptor SFP+", "switch": "Switch", "acess point": "Access point",
}
# Valores que o GLPI usa para "não informado"
VALORES_VAZIOS = {"", "n/c", "nc", "n/a", "na", "-", "--", "s/n", "sn", "sem", "sem patrimonio", "sem patrimônio", "não consta", "nao consta"}
CONSERVACAO_PADRAO = 4
CONSERVACAO_INSERVIVEL = 1
SALA_ATUALIZAR = "NECESSÁRIO ATUALIZAR"
CODIGO_SALA_ATUALIZAR = "ATUALIZAR"


def limpar(valor: Any) -> str | None:
    """Texto sem espaços nas pontas; vazio e marcadores de "não informado" viram `None`."""
    if valor is None:
        return None
    texto = re.sub(r"\s+", " ", str(valor)).strip()
    return None if texto.lower() in VALORES_VAZIOS else texto


def eh_inservivel(registro: dict[str, Any]) -> bool:
    """Local "INSERVÍVEL..." ou estado DESCARTE no GLPI: o bem entra como ativo, mas com conservação 1 (péssimo)."""
    local = (registro.get("local") or "").strip().lower()
    estado = (registro.get("estado") or "").strip().lower()
    return local.startswith("inserv") or estado == "descarte"


def descricao_do_bem(registro: dict[str, Any]) -> str:
    """Tipo do equipamento (Notebook, Switch, Desktop, Monitor...) + marca + modelo (sem repetir a marca no começo do modelo)."""
    tipo = limpar(registro.get("tipo_nome"))
    base = TIPOS_APROVEITADOS.get(tipo.lower()) if tipo else None
    partes = [base or TIPOS_GLPI[registro["tipo"]]]
    marca, modelo = limpar(registro.get("fabricante")), limpar(registro.get("modelo"))
    if marca:
        partes.append(marca)
    if modelo and not (marca and modelo.lower().startswith(marca.lower())):
        partes.append(modelo)
    elif modelo:
        partes[-1] = modelo
    return " ".join(partes)[:300]


def montar_bem(registro: dict[str, Any], chapas_usadas: set[str]) -> dict[str, Any]:
    """Converte um ativo do GLPI nos campos do bem (chapa, número de série e descrição). `chapas_usadas` (chaves em minúsculas) é atualizado."""
    patrimonio = limpar(registro.get("patrimonio"))
    # Chapa longa demais ou repetida fica sem chapa (o bem continua identificado pelo número de série)
    if patrimonio and (len(patrimonio) > 60 or patrimonio.lower() in chapas_usadas):
        patrimonio = None
    if patrimonio:
        chapas_usadas.add(patrimonio.lower())
    return {
        "id_cliente": f"glpi:{registro['tipo']}:{registro['id']}",
        "chapa": patrimonio,
        "chapa_chave": patrimonio.lower() if patrimonio else None,
        "numero_serie": (limpar(registro.get("serie")) or "")[:80] or None,
        "descricao": descricao_do_bem(registro),
        "conservacao": CONSERVACAO_INSERVIVEL if eh_inservivel(registro) else CONSERVACAO_PADRAO,
        "situacao": "ativo",
        "origem": "proprio",
    }
