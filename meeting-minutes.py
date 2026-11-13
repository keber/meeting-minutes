"""Entrypoint standalone: `python meeting-minutes.py <transcripcion>`.

La implementacion vive en el paquete `tgd`.
"""

import sys

from tgd.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
