#!/usr/bin/env python3
"""F14 S1: fingerprint the core /who handler a module mirror would copy.

A module-owned /who filter (docs/research/F14-WHO-LISTING-S1.md) has to
repeat WorldSession::HandleWhoOpcode. This script hashes that function
and the CMSG_WHO opcode row in an AzerothCore checkout, so a core pin
change that touches either one is caught before the mirror drifts.

Usage: check_f14_who_handler_fingerprint.py <core-checkout> [--print]
Exit 0 when both hashes match the reviewed pin, 1 otherwise.
"""
import hashlib
import sys
from pathlib import Path

REVIEWED_CORE = "8daffdabe9202c228e45d833c9a1d399597a15cd"
HANDLER_FILE = "src/server/game/Handlers/MiscHandler.cpp"
HANDLER_SIGNATURE = "void WorldSession::HandleWhoOpcode(WorldPacket& recvData)"
OPCODE_FILE = "src/server/game/Server/Protocol/Opcodes.cpp"
OPCODE_NEEDLE = "DEFINE_HANDLER(CMSG_WHO,"

# sha256 of the exact bytes at REVIEWED_CORE (see function_text / opcode_row).
EXPECTED_HANDLER_SHA256 = "e6e6faca12a307088b8a9f83ed5f2c5b73e3a7786364f49f96f8f51e4e5f1f2e"
EXPECTED_OPCODE_SHA256 = "a86c1a56c832e96f995fb36244c3bb7d473f7ec7ebdaccf7c13963be2d7cdbc3"


def function_text(source, signature):
    """Signature through the matching closing brace, byte for byte."""
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise ValueError("unbalanced braces after " + signature)


def opcode_row(source):
    rows = [line.strip() for line in source.splitlines() if OPCODE_NEEDLE in line]
    if len(rows) != 1:
        raise ValueError("expected one CMSG_WHO row, found %d" % len(rows))
    return rows[0]


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprints(core_root):
    root = Path(core_root)
    handler = (root / HANDLER_FILE).read_text(encoding="utf-8")
    opcodes = (root / OPCODE_FILE).read_text(encoding="utf-8")
    return sha256(function_text(handler, HANDLER_SIGNATURE)), sha256(opcode_row(opcodes))


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    handler_sha, opcode_sha = fingerprints(argv[1])
    if "--print" in argv[2:]:
        print("handler", handler_sha)
        print("opcode ", opcode_sha)
    ok = True
    if handler_sha != EXPECTED_HANDLER_SHA256:
        print("HandleWhoOpcode changed since %s: %s" % (REVIEWED_CORE, handler_sha))
        ok = False
    if opcode_sha != EXPECTED_OPCODE_SHA256:
        print("CMSG_WHO opcode row changed since %s: %s" % (REVIEWED_CORE, opcode_sha))
        ok = False
    if ok:
        print("OK: /who handler and CMSG_WHO row match core %s" % REVIEWED_CORE)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
