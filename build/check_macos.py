"""Confere o dist/Distribuidor.app do macOS: entitlement do seletor de arquivos no viewer do Flet,
assinatura e o selfcheck do próprio app. Só roda no macOS."""
import os
import plistlib
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "dist" / "Distribuidor.app"
ENTITLEMENT = "com.apple.security.files.user-selected.read-write"


def check_viewer_entitlement() -> None:
    archives = [Path(d) / n for d, _, names in os.walk(APP, followlinks=True) for n in names
                if n == "flet-macos.tar.gz"]
    if not archives:
        found = [str(Path(d) / n) for d, _, names in os.walk(APP, followlinks=True) for n in names
                 if "flet" in n.lower()][:40]
        raise SystemExit(f"Nenhum flet-macos.tar.gz no bundle. Arquivos com 'flet': {found}")
    with tempfile.TemporaryDirectory(prefix="distrib-view-check-") as folder:
        with tarfile.open(archives[0]) as tar:
            tar.extractall(folder, filter="data")
        viewer = next(Path(folder).glob("*.app"), None)
        if viewer is None:
            raise SystemExit("O flet-macos.tar.gz não contém um .app")
        out = subprocess.run(["codesign", "--display", "--entitlements", "-", "--xml", str(viewer)],
                             capture_output=True, check=True).stdout
        entitlements = plistlib.loads(out) if out else {}
        if not entitlements.get(ENTITLEMENT):
            raise SystemExit(f"O viewer do Flet perdeu o entitlement {ENTITLEMENT}: {entitlements}")
    print("entitlement do viewer ok")


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("check_macos.py só roda no macOS")
    if not APP.is_dir():
        raise SystemExit("Falta dist/Distribuidor.app: rode build/pack.py")
    check_viewer_entitlement()
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(APP)], check=True)
    print("assinatura ok")
    result = subprocess.run([str(APP / "Contents" / "MacOS" / "Distribuidor"), "--module",
                             "distrib.runners.selfcheck"], capture_output=True, text=True, timeout=300)
    print(result.stdout.strip()[-500:])
    if result.returncode != 0 or "selfcheck ok" not in result.stdout:
        raise SystemExit(f"selfcheck falhou (código {result.returncode}): {result.stderr.strip()[-800:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
