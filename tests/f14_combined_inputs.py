"""F14 P15: verify and stage the two sibling inputs (#224 P12, #228 P14).

Usage: python3 -I tests/f14_combined_inputs.py <git repo> <out dir>

Read-only. Nothing is committed and no branch is touched. The script checks:
  - both sibling heads are children of #202 205d958 and add only their own
    test/doc/workflow paths (no src/, conf or stub change, no shared path);
  - every sibling file still has the blob hash reviewed by CS01;
  - git merge-tree of the two heads is clean and gives tree c426cd5.
It then writes into <out dir>:
  combined/  the merged tree (git archive of the merge-tree result)
  seam/      #145's WhoListingPolicy.h and the P14 seam variant, made by
             running #228's own extractor from the combined tree
"""
from pathlib import Path
import io
import subprocess
import sys
import tarfile

BASE = "205d958c3fddc8943c8eeef9822213f810e47c2d"
P12 = "33bf0d3feed7f51e10ad6470625d5f14dc601765"
P14 = "eec8211ec9f170468d2ed970a325b3bfbd571e6e"
MERGED_TREE = "c426cd5f964b4214af592e5ea0814595c4fcaf44"

SIBLING_BLOBS = {
    P12: {
        ".github/workflows/f14-selfbot-masking.yml": "9186fe4cbd7c5053e20f587402d9a3839a5ef566",
        "docs/research/F14-P12-SELFBOT-MASKING.md": "f6111b92483640e7468a5612d8246c9510685b00",
        "tests/f14_selfbot_masking_facts.py": "982968e21bf908dc91cf96973b3628cedfc1567a",
        "tests/f14_selfbot_masking_mutants.py": "b7511deb52b7367b68dedc88136fda15ac6a703a",
        "tests/f14_selfbot_masking_tests.cpp": "d8b0b212a383fe07413fe23c11d6228fceb50666",
    },
    P14: {
        ".github/workflows/f14-visibility-seam.yml": "e81da14898b295897199773896f29b06e2086cc0",
        "docs/research/F14-P14-VISIBILITY-SEAM.md": "e126a2efcd68a5046691b4cd0ed914abe48ec92f",
        "tests/f14_visibility_seam_extract.py": "a276167929d8451fbe4dae686b24779ab6f184a9",
        "tests/f14_visibility_seam_facts.py": "44361992d4cf31aec47eb063787c7675f454eacd",
        "tests/f14_visibility_seam_mutants.py": "889ec5e55495fc004ce6bcb3a14c81492cf04f4a",
        "tests/f14_visibility_seam_tests.cpp": "6bca1835db3bcb9d510cc079ae95515e0ea11e8b",
    },
}


def git(repo, *args, binary=False):
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {out.stderr.decode(errors='replace').strip()}")
    return out.stdout if binary else out.stdout.decode()


def fail(msg):
    print(f"FAIL {msg}")
    return 1


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    repo, out = Path(argv[1]), Path(argv[2])

    for head, blobs in SIBLING_BLOBS.items():
        name = "P12 #224" if head == P12 else "P14 #228"
        if subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", BASE, head]).returncode:
            return fail(f"{name} {head[:7]} is not a child of #202 {BASE[:7]}")
        status = [l.split("\t") for l in git(repo, "diff", "--name-status", BASE, head).splitlines()]
        if sorted(p for _, p in status) != sorted(blobs) or any(s != "A" for s, _ in status):
            return fail(f"{name} changes {status}, expected additions of exactly {sorted(blobs)}")
        for path, blob in blobs.items():
            got = git(repo, "rev-parse", f"{head}:{path}").strip()
            if got != blob:
                return fail(f"{name} {path} blob {got[:7]} != reviewed {blob[:7]}")
        print(f"OK   {name} {head[:7]}: {len(blobs)} added paths, reviewed blobs")

    if set(SIBLING_BLOBS[P12]) & set(SIBLING_BLOBS[P14]):
        return fail("siblings share a path")
    if any(p.startswith(("src/", "conf/", "tests/f14_facts_stubs/"))
           for blobs in SIBLING_BLOBS.values() for p in blobs):
        return fail("a sibling touches src/, conf/ or the stubs")
    print("OK   disjoint paths; neither sibling touches src/, conf/ or tests/f14_facts_stubs/")

    merged = subprocess.run(["git", "-C", str(repo), "merge-tree", "--write-tree", P12, P14],
                            capture_output=True, text=True)
    tree = merged.stdout.splitlines()[0].strip() if merged.stdout else ""
    if merged.returncode != 0 or tree != MERGED_TREE:
        return fail(f"merge-tree rc={merged.returncode} tree={tree} (expected clean {MERGED_TREE[:7]})")
    print(f"OK   merge-tree {P12[:7]} + {P14[:7]} is clean: tree {tree[:7]}")

    combined = out / "combined"
    combined.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(git(repo, "archive", tree, binary=True))) as tar:
        tar.extractall(combined, filter="data")
    # The combined tree is #202 plus both siblings' added files, nothing else.
    for head, blobs in SIBLING_BLOBS.items():
        for path in blobs:
            if not (combined / path).is_file():
                return fail(f"combined tree lacks {path}")

    seam = out / "seam"
    run = subprocess.run([sys.executable, "-I", str(combined / "tests/f14_visibility_seam_extract.py"),
                          str(repo), str(seam)], capture_output=True, text=True)
    print(run.stdout.strip())
    if run.returncode != 0:
        return fail(f"#228 extractor: {run.stderr.strip()}")
    print(f"PASS: siblings staged at {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
