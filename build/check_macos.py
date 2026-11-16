"""Confere o dist/Distribuidor.app do macOS: entitlement do seletor de arquivos no viewer do Flet,
assinatura e o selfcheck do próprio app. Só roda no macOS."""
import plistlib
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "dist" / "Distribuidor.app"
EXE = APP / "Contents" / "MacOS" / "Distribuidor"
ENTITLEMENT = "com.apple.security.files.user-selected.read-write"


def check_viewer_entitlement() -> None:
    # o .app é onefile: o tar do viewer só existe na extração do PyInstaller, com o app rodando
    with tempfile.TemporaryDirectory(prefix="distrib-view-check-") as folder:
        archive = Path(folder) / "flet-macos.tar.gz"
        got = subprocess.run([str(EXE), "--module", "distrib.runners.viewer_tar", str(archive)],
                             capture_output=True, text=True, timeout=300)
        if got.returncode != 0 or not archive.is_file():
            raise SystemExit(f"Não consegui extrair o viewer do app: {got.stdout.strip()} {got.stderr.strip()[-800:]}")
        with tarfile.open(archive) as tar:
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
    result = subprocess.run([str(EXE), "--module",
                             "distrib.runners.selfcheck"], capture_output=True, text=True, timeout=300)
    print(result.stdout.strip()[-500:])
    if result.returncode != 0 or "selfcheck ok" not in result.stdout:
        raise SystemExit(f"selfcheck falhou (código {result.returncode}): {result.stderr.strip()[-800:]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
