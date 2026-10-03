"""HELLO na placa: python main.py --module distrib.runners.hello COM5"""
import sys

from pokeldn.ldn import esp32


def main(argv=None) -> int:
    port = (argv if argv is not None else sys.argv[1:])[0]
    radio = esp32.Radio.open_serial(port)
    try:
        print(radio.hello().text, flush=True)
    finally:
        radio.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
