#!/usr/bin/env python3
"""Gera o hash bcrypt de uma senha para a variável ADMIN_PASSWORD_HASH do backend/.env.

Uso: backend/.venv/bin/python scripts/gerar-hash-senha.py
A senha é lida sem eco no terminal e nunca é gravada em disco.
"""

import getpass

import bcrypt

senha = getpass.getpass("Senha: ")
if senha != getpass.getpass("Confirme a senha: "):
    raise SystemExit("As senhas não conferem.")
print(bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"))
