#!/usr/bin/env python3
"""Dump a token table. Offline, standard library only."""
import argparse


def main(argv=None):
    ap = argparse.ArgumentParser(prog="run.py")
    ap.add_argument("--input", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    print("input=%s" % args.input)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
