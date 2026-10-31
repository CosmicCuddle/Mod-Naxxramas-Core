"""Must-fail mutants for the A04 harness.

Usage: A04_CORE=/path/to/pinned/core python3 -I tests/a04_native/mutants.py

Each mutant changes one line group in the EXTRACTED ORIGINAL pinned text
(prepare_pinned.py MUTANTS), never the harness. The harness must still compile
and at least one check must then fail. This shows the checks depend on the
executed original code, not on anything the harness computes itself.
Exits 1 if any mutant survives or does not compile.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import prepare_pinned  # noqa: E402


def main():
    core = Path(os.environ["A04_CORE"])
    caught = 0
    for name in prepare_pinned.MUTANTS:
        with tempfile.TemporaryDirectory(prefix="a04-mutant-") as tmp:
            out = Path(tmp)
            build.prepare(core, out, mutant=name)
            compiled, rc, output = build.compile_and_run(core, out)
            if not compiled:
                print(f"NOT COMPILED {name}:\n{output[-2000:]}")
                continue
            failed = [cid for verdict, cid in build.parse_checks(output) if verdict == "FAIL"]
            if rc != 0 and failed:
                caught += 1
                print(f"CAUGHT {name}: {len(failed)} check(s) failed, first {failed[0]}")
            else:
                print(f"SURVIVED {name}")
    print(f"{caught}/{len(prepare_pinned.MUTANTS)} mutants caught")
    return 0 if caught == len(prepare_pinned.MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
