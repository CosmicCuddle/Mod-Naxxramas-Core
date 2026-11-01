"""Build and run the P4-H follow-on harnesses against the pinned core (A04_CORE).

seam_harness.cpp: the ORIGINAL prefix of pinned HandleLootMasterGiveOpcode
(everything before the slot range check) and #272's ORIGINAL PermitMasterGive
and CanPacketReceive bodies, extracted byte for byte with #line markers and
compiled against tests/p4_h_interop/seam_env.h.

go_loot_harness.cpp: gameobject loot on the #262 original bodies, with the
original handler tail (extracted by ../p4_h_master_loot/build_master_loot.py)
against the real #272 header.
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
A04 = ROOT / "tests" / "a04_native"
sys.path.insert(0, str(A04))
sys.path.insert(0, str(ROOT / "tests" / "p4_h_master_loot"))
import build  # noqa: E402  (the #262 helpers, unchanged)
import build_master_loot  # noqa: E402  (#272 tail extraction, unchanged)

MODULE_CPP = ROOT / "src" / "Systems" / "MasterLootQuestGive.cpp"
PERMIT_SIGNATURE = "    bool PermitMasterGive(Player* leader, ObjectGuid lootGuid, uint8 slot, ObjectGuid targetGuid)"
PACKET_SIGNATURE = "    bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override"


def extract_stock_prefix(core: Path) -> str:
    """Handler body from its first statement up to (not including) the slot range check."""
    data = (core / build_master_loot.LOOT_HANDLER).read_bytes()
    got = build_master_loot.blob_sha(data)
    if got != build_master_loot.LOOT_HANDLER_BLOB:
        raise SystemExit(f"BLOB MISMATCH {build_master_loot.LOOT_HANDLER}: {got}")
    lines = data.decode().split("\n")
    sig = [i for i, l in enumerate(lines) if l == build_master_loot.SIGNATURE]
    if len(sig) != 1 or lines[sig[0] + 1] != "{":
        raise SystemExit("handler signature must occur once, followed by '{'")
    end = next(j for j in range(sig[0] + 1, len(lines)) if lines[j] == "}")
    starts = [i for i in range(sig[0], end) if lines[i] == build_master_loot.TAIL_START]
    if len(starts) != 1:
        raise SystemExit("tail start must occur once in the handler")
    first = sig[0] + 2
    return f'#line {first + 1} "{build_master_loot.LOOT_HANDLER}"\n' + "\n".join(lines[first:starts[0]]) + "\n"


def extract_member(text: str, signature: str, path: str, drop_override: bool) -> str:
    """A 4-space-indented function from its signature to the first line that is exactly '    }'."""
    lines = text.split("\n")
    hits = [i for i, l in enumerate(lines) if l == signature]
    if len(hits) != 1 or lines[hits[0] + 1] != "    {":
        raise SystemExit(f"signature must occur once, followed by '    {{': {signature}")
    end = next(j for j in range(hits[0] + 1, len(lines)) if lines[j] == "    }")
    body = lines[hits[0]:end + 1]
    if drop_override:
        if not body[0].endswith(" override"):
            raise SystemExit("expected an override")
        body[0] = body[0][: -len(" override")]
    return f'#line {hits[0] + 1} "{path}"\n' + "\n".join(body) + "\n"


def prepare_seam(core: Path, out: Path, module_cpp: Path = None):
    module_cpp = module_cpp or MODULE_CPP
    text = module_cpp.read_text()
    out.mkdir(parents=True, exist_ok=True)
    (out / "stock_prefix.inc").write_text(extract_stock_prefix(core))
    rel = "src/Systems/MasterLootQuestGive.cpp"
    (out / "module_permit.inc").write_text(extract_member(text, PERMIT_SIGNATURE, rel, False))
    (out / "module_packet.inc").write_text(extract_member(text, PACKET_SIGNATURE, rel, True))


def _compile_and_run(cmd, exe):
    made = subprocess.run(cmd, capture_output=True, text=True)
    if made.returncode != 0:
        return False, None, made.stdout + made.stderr
    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    return True, ran.returncode, ran.stdout + ran.stderr


def run_seam(core: Path, out: Path, module_cpp: Path = None, cxx=None):
    prepare_seam(core, out, module_cpp)
    cxx = cxx or os.environ.get("CXX", "g++")
    exe = out / "p4_h_seam_harness"
    cmd = [cxx, "-std=c++20", "-O0", "-g", "-Wall", "-I", str(out), "-I", str(HERE),
           str(HERE / "seam_harness.cpp"), "-o", str(exe)]
    return _compile_and_run(cmd, exe)


def run_go(core: Path, out: Path, header_include: Path = None, cxx=None):
    build.prepare(core, out)
    (out / "stock_master_give.inc").write_text(build_master_loot.extract_tail(core))
    cxx = cxx or os.environ.get("CXX", "g++")
    header_include = header_include or (ROOT / "src" / "Systems")
    exe = out / "p4_h_go_loot_harness"
    cmd = [cxx, "-std=c++20", "-O0", "-g", "-DFMT_HEADER_ONLY",
           "-I", str(header_include), "-I", str(out), "-I", str(A04), "-I", str(A04 / "stubs")]
    for inc in build.CORE_INCLUDES:
        cmd += ["-I", str(core / inc)]
    cmd += [str(out / "pinned_bodies.cpp"), str(HERE / "go_loot_harness.cpp"), "-o", str(exe)]
    return _compile_and_run(cmd, exe)


parse_checks = build.parse_checks


def main():
    core = Path(os.environ["A04_CORE"])
    base = Path(os.environ.get("P4H_OUT", "/tmp/p4-h-interop"))
    rc_all = 0
    for name, fn in (("seam", run_seam), ("go", run_go)):
        out = base / name
        out.mkdir(parents=True, exist_ok=True)
        compiled, rc, output = fn(core, out)
        print(f"== {name}\n{output}")
        if not compiled or rc != 0:
            rc_all = 1
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
