#!/usr/bin/env python3
"""Pinned source-only IP Hunter pet family coverage (no pet, SQL, or rank edits)."""
from pathlib import Path
import argparse
import re

def check(ip):
    code = (ip / "src/IndividualProgressionSpells.cpp").read_text("utf-8")
    start = "void IndividualProgression::checkHunterPetSpells("
    end = "void IndividualProgression::checkWarlockPetSpells("
    assert code.count(start) == 1 and code.count(end) == 1
    source = code.split(start, 1)[1].split(end, 1)[0]
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = "\n".join(s.split("//", 1)[0] for s in source.splitlines())
    pattern = re.compile(r'\b(?:if|else if)\s*\(familyName\s*==\s*"([^"]+)"\)')
    pattern_calls = re.compile(r'\breconcile\s*\(\s*\{([^}]+)\}\s*,\s*\{([^}]*)\}\s*\)')
    families = list(pattern.finditer(source))
    assert len(families) == 26, "IP family scope changed"
    counts = [0, 0, 0]
    names = set()
    for i, family in enumerate(families):
        assert family.group(1) not in names, "Duplicate family"
        names.add(family.group(1))
        body = source[family.start():families[i + 1].start()
                      if i + 1 < len(families) else len(source)]
        calls = list(pattern_calls.finditer(body))
        assert calls, "No IP calls: " + family.group(1)
        for call in calls:
            wipe = [int(n.strip()) for n in call.group(1).split(",") if n.strip()]
            dummy = [int(n.strip()) for n in call.group(2).split(",") if n.strip()]
            assert wipe, "Empty wipe list"
            assert all(n - 600000 in wipe for n in dummy), (
                "Dummy-to-rank mapping changed: " + family.group(1))
            counts[0] += 1
            counts[1 if dummy else 2] += 1
    assert tuple(counts) == (89, 52, 37), "IP coverage changed; review source"
    print("PASS: 26 pet-family branches, 89 active calls; 52 dummy backed, 37 removal-only.")
    print("BLOCKED: source list alone cannot authorize autocast, legal rank or IP completion.")
    print("This is a source-only audit; nothing installed, learned, toggled, or persisted.")

if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--ip", type=Path, required=True)
    check(args.parse_args().ip.resolve())
