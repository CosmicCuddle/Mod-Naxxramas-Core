"""Must-fail mutants for tests/f15_integrated_disposable_runner.py.

Usage: python3 -I tests/f15_integrated_runner_mutants.py

Each mutant breaks one safety property in a temporary copy of the runner; the
end-to-end test file must then fail. Exits 1 if any mutant survives. All work
happens in a tempfile.TemporaryDirectory.
"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNNER = "tests/f15_integrated_disposable_runner.py"
TESTS = "tests/test_f15_integrated_disposable_runner.py"
POLICY = "tools/f15/console_archive_policy.py"

MUTANTS = [
    ("seal ignores the observation day",
     "            if record.day != day:\n                continue\n", ""),
    ("segments may split a UTF-8 codepoint",
     "                tail = incomplete_utf8_tail(chunk)\n", "                tail = 0\n"),
    ("time moving backwards is accepted",
     "            if now < last:\n", "            if False:\n"),
    ("hardlinked source is accepted",
     "        if meta.st_nlink != 1:\n            os.close(fd)\n",
     "        if False:\n            os.close(fd)\n"),
    ("retention trusts a changed archive",
     "                owned = self._is_ours(dfd, name, entry[\"dev\"], entry[\"ino\"], entry[\"sha256\"]) is True\n",
     "                owned = True\n"),
    ("no adoption of records published before a stop",
     "            nxt = [r for r in self.records(stream) if r.seq == ck[\"seq\"] + 1]\n",
     "            nxt = []\n"),
    ("bootstrap backfills history",
     "\"bootstrap-skip\", meta.st_dev, meta.st_ino, meta.st_size, now,",
     "\"bootstrap-skip\", meta.st_dev, meta.st_ino, 0, now,"),
    ("restart deletes any *.pending file",
     "                if not self._owned_pending(directory, path.name):\n",
     "                if not path.name.endswith(\".pending\"):\n"),
    ("replacement and truncation are not recorded",
     "            if plan.event in (\"replaced\", \"truncated\"):\n",
     "            if False:\n"),
    ("corrupt journal records are trusted",
     "        if _sha(data) != record.sha:\n", "        if False:\n"),
    ("a foreign sidecar does not block retention",
     "                if side is False:\n", "                if False:\n"),
    ("sidecar identity is not recorded at sealing",
     "sidecar_sha256=_sha(provenance))", "sidecar_sha256=None)"),
    ("two streams may share one source file",
     "        if len(set(names.values())) != len(names):\n", "        if False:\n"),
]


def main():
    source = (ROOT / RUNNER).read_text()
    caught = 0
    with tempfile.TemporaryDirectory(prefix="f15-runner-mutants-") as tmp:
        work = Path(tmp)
        (work / "tests").mkdir()
        (work / "tools" / "f15").mkdir(parents=True)
        shutil.copy(ROOT / TESTS, work / TESTS)
        shutil.copy(ROOT / POLICY, work / POLICY)
        for name, old, new in MUTANTS:
            if source.count(old) != 1:
                print(f"ANCHOR NOT UNIQUE: {name}")
                return 1
            (work / RUNNER).write_text(source.replace(old, new))
            run = subprocess.run([sys.executable, "-I", "-B", "-W", "error", str(work / TESTS)],
                                 capture_output=True, text=True, timeout=300)
            last = (run.stderr.strip().splitlines() or ["(no output)"])[-1]
            survived = run.returncode == 0
            print(("SURVIVED " if survived else "CAUGHT ") + f"{name}: {last}")
            caught += not survived
    print(f"{caught}/{len(MUTANTS)} mutants caught")
    return 0 if caught == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
