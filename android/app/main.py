"""Entrada do APK do Distribuidor: o mesmo main.py do PC (staging feito por build/pack_android.py)."""
import sys


def main() -> None:
    from ui.app import run
    run()


if __name__ == "__main__":
    main()
