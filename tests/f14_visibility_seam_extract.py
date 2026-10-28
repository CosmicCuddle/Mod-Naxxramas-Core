"""F14 P14: extract #145's real /who writer and build a test-only seam variant.

Usage: python3 -I tests/f14_visibility_seam_extract.py <git repo> <out dir>

Reads src/Systems/WhoListingPolicy.h from #145 head 01c6b32 (blob e66f72c,
checked), and writes into <out dir>:

  WhoListingPolicy.h  the header byte-for-byte
  WhoListingSeam.h    the same header with exactly three edits: include
                      guard, namespace, and the one HideRow call, which
                      becomes ctx.HideRowFor(race, isObserver, guid) so a
                      test context can feed it an identity

Nothing here touches src/ or #145. Every anchor must match exactly, so a
change to #145's writer fails the extraction instead of testing stale code.
"""
from pathlib import Path
import subprocess
import sys

REV = "01c6b32a956b83dd92cb9d9b2f9103941497936b"
PATH = "src/Systems/WhoListingPolicy.h"
BLOB = "e66f72c374af179945508addcd71c0525271f837"

GUARD = ("NAXXRAMAS_CORE_WHO_LISTING_POLICY_H", "NAXXRAMAS_CORE_WHO_LISTING_SEAM_H", 3)
NAMESPACE = ("namespace NaxxramasWhoListing\n", "namespace NaxxramasWhoListingSeam\n", 1)
CALL = ("            if (hide && HideRow(static_cast<std::uint8_t>(race), "
        "ctx.observerGuid == target.GetGuid()))\n",
        "            if (hide && ctx.HideRowFor(static_cast<std::uint8_t>(race), "
        "ctx.observerGuid == target.GetGuid(), target.GetGuid()))\n", 1)


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True).stdout


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    repo, out = Path(argv[1]), Path(argv[2])
    blob = git(repo, "rev-parse", f"{REV}:{PATH}").strip()
    if blob != BLOB:
        print(f"WRONG BLOB: {blob} != {BLOB}")
        return 1
    original = git(repo, "show", f"{REV}:{PATH}")

    seam = original
    for old, new, count in (GUARD, NAMESPACE, CALL):
        found = seam.count(old)
        if found != count:
            print(f"ANCHOR DRIFT: {old.strip()!r} found {found}, expected {count}")
            return 1
        seam = seam.replace(old, new)

    a, b = original.splitlines(), seam.splitlines()
    changed = [i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y]
    if len(a) != len(b) or len(changed) != 5:
        print(f"UNEXPECTED SEAM DIFF: lines {changed}")
        return 1

    out.mkdir(parents=True, exist_ok=True)
    (out / "WhoListingPolicy.h").write_text(original)
    (out / "WhoListingSeam.h").write_text(seam)
    print(f"extracted {PATH} @ {REV[:7]} (blob {BLOB[:7]}); seam differs on lines {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
