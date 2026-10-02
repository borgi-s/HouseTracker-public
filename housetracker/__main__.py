"""Executable module entry so `python -m housetracker <args>` drives the CLI — used by the
systemd lifecycle service ExecStart."""
import sys

from housetracker.cli import main

raise SystemExit(main(sys.argv[1:], sys.stdout))
