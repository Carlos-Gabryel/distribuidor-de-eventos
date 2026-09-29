"""Imprime um valor da configuração (config.toml + config.local.toml), com "~" = $HOME.

    python3 windows/config_valor.py <pasta do projeto> <chave>

Usado pelo iniciar.ps1 e pelo instalar.ps1 (roda com o python3 do sistema, sem o venv).
"""
import os
import sys
import tomllib

project, key = sys.argv[1], sys.argv[2]
data = {}
for name in ("config.toml", "config.local.toml"):
    path = os.path.join(project, name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            data.update(tomllib.load(f))
value = str(data[key])
print(os.path.join(os.environ["HOME"], value[2:]) if value.startswith("~/") else value)
