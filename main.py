"""Ponto de entrada do Distribuidor: `python main.py` no desenvolvimento, ou o próprio .exe."""
import sys


def main() -> None:
    argv = sys.argv[1:]
    from distrib import runner
    if runner.is_child(argv):
        from distrib.config import load
        runner.child(argv, load().pokeldn_dir)
        return
    from ui.app import run
    run()


if __name__ == "__main__":
    main()
