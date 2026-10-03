"""Authoritative setup command; the entry path imports only standard-library code."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))

from lunitora_machine.bootstrap import main

if __name__ == "__main__":
    raise SystemExit(main())
