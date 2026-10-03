"""HELLO na placa: python main.py --module distrib.runners.hello COM5

Passa pelo aquietar (canal 13, fila vazia, de volta a 115200) antes do HELLO e imprime o texto dele
na última linha.
"""
import sys

from distrib.runners.quiet import quiet_info


def main(argv=None) -> int:
    port = (argv if argv is not None else sys.argv[1:])[0]
    text = quiet_info(port)
    if text is None:
        print(f"a placa em {port} não respondeu ao HELLO", file=sys.stderr, flush=True)
        return 1
    print(text, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
