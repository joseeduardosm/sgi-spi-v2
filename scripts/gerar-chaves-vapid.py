#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar o par de chaves VAPID das notificações do navegador (Web Push).
"""Gera as chaves VAPID das notificações do navegador.

Uso: backend/.venv/bin/python scripts/gerar-chaves-vapid.py

Imprime as três linhas para copiar no `backend/.env`. A chave privada é segredo (não vai para o Git nem para mensagens);
trocar o par invalida as inscrições já feitas: cada pessoa precisa ativar o navegador de novo.
"""
import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


vapid = Vapid01()
vapid.generate_keys()
publica = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
privada = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
print("# Cole no backend/.env (o contato precisa ser um e-mail de quem responde pelo servidor)")
print(f"CHAVE_PUBLICA_VAPID={_b64(publica)}")
print(f"CHAVE_PRIVADA_VAPID={_b64(privada)}")
print("CONTATO_VAPID=mailto:ti@spi.sp.gov.br")
