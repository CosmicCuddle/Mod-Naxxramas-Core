"""Build and run the P4-H Master Loot harness against the pinned core (A04_CORE).

Besides the #262 bodies, this extracts the ORIGINAL tail of pinned
WorldSession::HandleLootMasterGiveOpcode (from the slot range check to the
end of the function) into OUT/stock_master_give.inc, byte for byte with a
#line marker. Only the three `_player->SendLootError(lootguid, ` calls are
redirected to a recorder, because the harness Player has no SendLootError.
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
A04 = ROOT / "tests" / "a04_native"
sys.path.insert(0, str(A04))
import build  # noqa: E402  (the #262 helpers, unchanged)

LOOT_HANDLER = "src/server/game/Handlers/LootHandler.cpp"
LOOT_HANDLER_BLOB = "a18781f0e9b24b9d35ea587e48baf6829ba917fa"
SIGNATURE = "void WorldSession::HandleLootMasterGiveOpcode(WorldPacket& recvData)"
TAIL_START = "    if (slotid >= loot->items.size() + loot->quest_items.size())"
ERROR_CALL = "_player->SendLootError(lootguid, "
ERROR_CALLS = 3
ITEM_H = "src/server/game/Entities/Item/Item.h"
# Enum values the harness defines because the #262 stub enum lacks them.
ITEM_H_FACTS = [
    "    EQUIP_ERR_YOU_CAN_NEVER_USE_THAT_ITEM        = 10,",
    "    EQUIP_ERR_CANT_CARRY_MORE_OF_THIS            = 17,",
]


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def extract_tail(core: Path) -> str:
    data = (core / LOOT_HANDLER).read_bytes()
    got = blob_sha(data)
    if got != LOOT_HANDLER_BLOB:
        raise SystemExit(f"BLOB MISMATCH {LOOT_HANDLER}: {got} != {LOOT_HANDLER_BLOB}")
    lines = data.decode().split("\n")
    sig = [i for i, l in enumerate(lines) if l == SIGNATURE]
    if len(sig) != 1:
        raise SystemExit(f"signature must occur once ({len(sig)})")
    end = next(j for j in range(sig[0] + 1, len(lines)) if lines[j] == "}")
    starts = [i for i in range(sig[0], end) if lines[i] == TAIL_START]
    if len(starts) != 1:
        raise SystemExit(f"tail start must occur once in the handler ({len(starts)})")
    tail = "\n".join(lines[starts[0]:end]) + "\n"
    if tail.count(ERROR_CALL) != ERROR_CALLS or tail.count("SendLootError") != ERROR_CALLS:
        raise SystemExit("unexpected SendLootError calls in the handler tail")
    tail = tail.replace(ERROR_CALL, "StockLootError(_player, lootguid, ")
    item_h = (core / ITEM_H).read_text().split("\n")
    for fact in ITEM_H_FACTS:
        if item_h.count(fact) != 1:
            raise SystemExit(f"pinned fact must occur once in {ITEM_H}: {fact}")
    return f'#line {starts[0] + 1} "{LOOT_HANDLER}"\n' + tail


def run(core: Path, out: Path, header_include: Path = None, cxx=None):
    """Prepare the pinned bodies and the handler tail, compile, run.

    Returns (compiled, returncode, output)."""
    build.prepare(core, out)
    (out / "stock_master_give.inc").write_text(extract_tail(core))
    cxx = cxx or os.environ.get("CXX", "g++")
    header_include = header_include or (ROOT / "src" / "Systems")
    exe = out / "p4_h_master_loot_harness"
    cmd = [cxx, "-std=c++20", "-O0", "-g", "-DFMT_HEADER_ONLY",
           "-I", str(header_include), "-I", str(out), "-I", str(A04), "-I", str(A04 / "stubs")]
    for inc in build.CORE_INCLUDES:
        cmd += ["-I", str(core / inc)]
    cmd += [str(out / "pinned_bodies.cpp"), str(HERE / "master_loot_harness.cpp"), "-o", str(exe)]
    made = subprocess.run(cmd, capture_output=True, text=True)
    if made.returncode != 0:
        return False, None, made.stdout + made.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    return True, ran.returncode, ran.stdout + ran.stderr


parse_checks = build.parse_checks


def main():
    core = Path(os.environ["A04_CORE"])
    out = Path(os.environ.get("P4H_OUT", "/tmp/p4-h-master-loot"))
    out.mkdir(parents=True, exist_ok=True)
    compiled, rc, output = run(core, out)
    print(output)
    if not compiled:
        return 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
