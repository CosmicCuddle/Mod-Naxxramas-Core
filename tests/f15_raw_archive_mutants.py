"""Must-fail mutants of scripts/f15_raw_archive.py.

Each mutant is written to a temporary scripts/ copy; the unit tests are run
against it with that directory first on sys.path. Every mutant must make at
least one test fail. Usage: python3 tests/f15_raw_archive_mutants.py
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "f15_raw_archive.py"

MUTANTS = [
    ("incomplete run accepted",
     '        raise Refused("run is not complete: no observed exit receipt")\n',
     '        return None\n'),
    ("fail_closed capture accepted",
     '    if ended["capture"] != "complete_for_observed_run" or ended["capture_error_type"] is not None:\n',
     '    if False:\n'),
    ("capture origin inode not checked",
     '                or type(origin["ino"]) is not int or origin["dev"] != info.st_dev\n'
     '                or origin["ino"] != info.st_ino):\n',
     '                or type(origin["ino"]) is not int):\n'),
    ("archived copy digest not re-verified",
     '            raise Refused("existing archived stream digest mismatch; manual review")\n',
     '            pass\n'),
    ("live source not compared with archive",
     '            raise Refused("source no longer matches its archive; manual review")\n',
     '            pass\n'),
    ("dry run copies by default",
     '                              args.run, execute=args.archive_owned_completed), sort_keys=True))\n',
     '                              args.run, execute=True), sort_keys=True))\n'),
    ("30-day flag wrong boundary",
     'RETENTION = timedelta(days=30)\n', 'RETENTION = timedelta(days=0)\n'),
    ("nested destination allowed",
     '                raise Refused("output, capture archive and raw archive roots must be separate and nonnested")\n',
     '                pass\n'),
    ("duplicate selection allowed",
     '        raise Refused("duplicate --run selection")\n', '        pass\n'),
    ("interrupted staging published anyway",
     '            raise KeyboardInterrupt("test interruption")  # staging stays for review\n',
     '            break\n'),
]


def main():
    source = SCRIPT.read_text()
    caught = 0
    for name, old, new in MUTANTS:
        if source.count(old) != 1:
            print("ANCHOR NOT UNIQUE: " + name)
            return 1
        with tempfile.TemporaryDirectory(prefix="f15-raw-mutant-") as tmp:
            scripts = Path(tmp) / "scripts"
            shutil.copytree(ROOT / "scripts", scripts)
            (scripts / "f15_raw_archive.py").write_text(source.replace(old, new))
            tests = Path(tmp) / "tests"
            tests.mkdir()
            shutil.copy(ROOT / "tests" / "test_f15_raw_archive.py", tests)
            ran = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(tests),
                                  "-p", "test_f15_raw_archive.py"],
                                 capture_output=True, text=True, timeout=300)
        if ran.returncode != 0:
            caught += 1
            print("CAUGHT " + name)
        else:
            print("SURVIVED " + name)
    print("%d/%d raw archive mutants caught" % (caught, len(MUTANTS)))
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
