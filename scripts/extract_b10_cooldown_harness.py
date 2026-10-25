#!/usr/bin/env python3
"""Build a TSAN harness from #120's PRODUCTION cooldown code, byte for byte.

Test-only. Extracts, verbatim, from src/Systems/BotRaidConsumables.cpp:
  - the `std::mutex ConsumableCooldownLock;` declaration,
  - the `ConsumableCooldownUntil` map declaration,
  - GetConsumableCooldownRemaining, StartConsumableCooldown and
    ResetConsumableCooldownForGroup (signature through matching brace),
checks their combined SHA-256 against the reviewed #120 head 599d1cb, and
splices them unchanged into tests/b10_cooldown_tsan_driver.cpp at its
marker. Nothing is reimplemented: if the production text changes, the
digest check fails and the harness must be re-reviewed.

--unlocked removes the three `std::lock_guard` statements from the
extracted text AFTER the digest check, to build the negative control that
ThreadSanitizer must flag.

Usage: extract_b10_cooldown_harness.py <BotRaidConsumables.cpp> <driver.cpp> <out.cpp> [--unlocked]
Exit 0 on success, 3 when the production text differs from the reviewed one.
"""
import hashlib
import re
import sys

REVIEWED_HEAD = "599d1cbb211e6f108a2a6ff9fec78242ffe7a37c"
EXPECTED_SHA256 = "535574bb1573e2b82d209c84deeb5c0dc5af4782164c2e3220f4bdf0eab895d5"
MARKER = "// @@B10_EXTRACTED_PRODUCTION_COOLDOWN_CODE@@"

DECLARATIONS = (
    r"std::mutex ConsumableCooldownLock;",
    r"std::unordered_map<ObjectGuid::LowType, uint64>\s+ConsumableCooldownUntil;",
)
FUNCTIONS = (
    "uint32 GetConsumableCooldownRemaining(",
    "void StartConsumableCooldown(",
    "void ResetConsumableCooldownForGroup(",
)
LOCK = re.compile(r"std::lock_guard<std::mutex> lock\(\s*ConsumableCooldownLock\);")


def function_text(source, signature):
    if source.count(signature) != 1:
        raise ValueError("expected exactly one definition of " + signature)
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


def extract(source):
    pieces = []
    for pattern in DECLARATIONS:
        found = re.findall(pattern, source)
        if len(found) != 1:
            raise ValueError("expected exactly one declaration matching " + pattern)
        pieces.append(found[0])
    pieces.extend(function_text(source, sig) for sig in FUNCTIONS)
    return pieces


def digest(pieces):
    return hashlib.sha256("\x00".join(pieces).encode("utf-8")).hexdigest()


def main(argv):
    if len(argv) < 4:
        print(__doc__.strip())
        return 2
    source = open(argv[1], encoding="utf-8").read()
    driver = open(argv[2], encoding="utf-8").read()
    pieces = extract(source)
    found = digest(pieces)
    if found != EXPECTED_SHA256:
        print("production cooldown code differs from reviewed %s: %s" % (REVIEWED_HEAD, found))
        return 3
    body = "\n\n".join(pieces)
    mode = "production text"
    if "--unlocked" in argv[4:]:
        body, removed = LOCK.subn("/* lock removed: negative control */", body)
        if removed != 3:
            print("negative control expected 3 lock_guard statements, found %d" % removed)
            return 3
        mode = "UNLOCKED negative control"
    if driver.count(MARKER) != 1:
        print("driver must contain the marker exactly once")
        return 2
    open(argv[3], "w", encoding="utf-8").write(driver.replace(MARKER, body))
    print("OK: %s, %d pieces, sha256 %s (reviewed %s)" % (mode, len(pieces), found, REVIEWED_HEAD[:7]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
