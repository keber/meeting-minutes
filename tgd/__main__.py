"""Permite `python -m tgd <transcripcion>`."""

import sys

from .cli import main

raise SystemExit(main(sys.argv[1:]))
