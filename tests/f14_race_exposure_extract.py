"""F14 P16: extract the real name-query function and #145's /who writer.

Usage: python3 -I tests/f14_race_exposure_extract.py <core checkout> <git repo> <out dir>

Writes, unchanged:
  SendNameQueryOpcode.inc  WorldSession::SendNameQueryOpcode, QueryHandler.cpp
                           L32-L62 at Grimfeather 8daffda (blob eb0142a)
  WhoListingPolicy.h       #145's /who writer at 01c6b32 (blob e66f72c)
Both are checked by blob hash and anchor lines, so drift fails here.
"""
from pathlib import Path
import subprocess
import sys

CORE_PIN = "8daffdabe9202c228e45d833c9a1d399597a15cd"
QUERY = "src/server/game/Handlers/QueryHandler.cpp"
QUERY_BLOB = "eb0142aa4c0e0db85e72c5b0746003f37d7fe519"
FIRST, LAST = 32, 62
WHO_REV = "01c6b32a956b83dd92cb9d9b2f9103941497936b"
WHO_PATH = "src/Systems/WhoListingPolicy.h"
WHO_BLOB = "e66f72c374af179945508addcd71c0525271f837"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2
    core, repo, out = Path(argv[1]), Path(argv[2]), Path(argv[3])
    if git(core, "rev-parse", "HEAD").strip() != CORE_PIN:
        print("WRONG CORE PIN")
        return 1
    blob = git(core, "rev-parse", f"HEAD:{QUERY}").strip()
    if blob != QUERY_BLOB:
        print(f"WRONG QueryHandler.cpp BLOB: {blob}")
        return 1
    lines = (core / QUERY).read_text().splitlines()
    body = lines[FIRST - 1:LAST]
    if body[0] != "void WorldSession::SendNameQueryOpcode(ObjectGuid guid)" or body[-1] != "}":
        print(f"ANCHOR DRIFT: {body[0]!r} .. {body[-1]!r}")
        return 1

    if git(repo, "rev-parse", f"{WHO_REV}:{WHO_PATH}").strip() != WHO_BLOB:
        print("WRONG WhoListingPolicy.h BLOB")
        return 1

    out.mkdir(parents=True, exist_ok=True)
    (out / "SendNameQueryOpcode.inc").write_text("\n".join(body) + "\n")
    (out / "WhoListingPolicy.h").write_text(git(repo, "show", f"{WHO_REV}:{WHO_PATH}"))
    print(f"extracted {QUERY} L{FIRST}-L{LAST} (blob {QUERY_BLOB[:7]}) and "
          f"{WHO_PATH} @ {WHO_REV[:7]} (blob {WHO_BLOB[:7]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
