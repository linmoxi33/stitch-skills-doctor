#!/usr/bin/env python3
import argparse

import zzz_not_a_module


def main(argv=None):
    ap = argparse.ArgumentParser(prog="report.py")
    ap.add_argument("--input", required=True)
    args = ap.parse_args(argv)
    print(args.input)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
