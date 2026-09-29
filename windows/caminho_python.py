"""Imprime o Python configurado (config.toml + config.local.toml), com "~" = $HOME. Usado pelo iniciar.ps1."""
import os
import sys
import tomllib

data = {}
for name in ("config.toml", "config.local.toml"):
    path = os.path.join(sys.argv[1], name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            data.update(tomllib.load(f))
python = data["python"]
print(os.path.join(os.environ["HOME"], python[2:]) if python.startswith("~/") else python)
