#!/usr/bin/env bash
# Read-only source checkout revision checker, NOT a running binary check.
set -euo pipefail

if (( $# < 1 || $# > 4 )); then
  printf '%s\n' 'Usage: bash scripts/check_ep_source_revisions.sh CORE_SOURCE_ROOT [PLAYERBOTS_DIR] [IP_DIR] [NAXX_DIR]' >&2
  exit 2
fi
if ! command -v git >/dev/null 2>&1; then
  printf 'ERROR: Git not found. No changes made.\n' >&2
  exit 2
fi

core="$1"
bots="$core/modules/mod-playerbots"
ip="$core/modules/mod-individual-progression"
naxx="$core/modules/mod-naxxramas-core"
if (( $# >= 2 )); then bots="$2"; fi
if (( $# >= 3 )); then ip="$3"; fi
if (( $# >= 4 )); then naxx="$4"; fi
missing=0
different=0

check_source() {
  local label="$1" path="$2" pinned="$3"
  local canonical="" root="" canonical_root="" sha=""
  printf '\n[%s]\n' "$label"
  if [[ ! -d "$path" ]] || ! canonical="$(cd -- "$path" && pwd -P)"; then
    printf 'MISSING FOLDER: %s\n' "$path"
    missing=1
    return
  fi
  if ! root="$(git -C "$canonical" rev-parse --show-toplevel 2>/dev/null)" ||
     ! canonical_root="$(cd -- "$root" && pwd -P)"; then
    printf 'NOT A GIT REPOSITORY: %s\n' "$canonical"
    missing=1
    return
  fi
  if [[ "$canonical_root" != "$canonical" ]]; then
    printf 'WRONG CHECKOUT ROOT: requested %s but Git uses %s\n' "$canonical" "$canonical_root"
    printf 'Refusing to substitute the parent AzerothCore SHA.\n'
    missing=1
    return
  fi
  if ! sha="$(git -C "$canonical" rev-parse --verify HEAD 2>/dev/null)"; then
    printf 'UNAVAILABLE GIT HEAD: %s\n' "$canonical"
    missing=1
    return
  fi
  printf 'Source path: %s\nSHA: %s\n' "$canonical" "$sha"
  if [[ -z "$pinned" ]]; then
    printf 'Compare the Naxxramas Core SHA against the current PR #21 separately.\n'
  elif [[ "$sha" == "$pinned" ]]; then
    printf 'Pinned test revision: MATCH\n'
  else
    printf 'Pinned test revision: DIFFERENT (API review needed, not proof of failure)\n'
    printf 'Pinned SHA: %s\n' "$pinned"
    different=1
  fi
}

printf '%s\n' 'READ-ONLY checkout check (NO Git update, SQL, reboot, or file changes)'
check_source AzerothCore "$core" b7f06a16ac7120b5abc2e8d3f96a94265a363224
check_source Playerbots "$bots" 037c01418b5d01506917a3db9b44fd56ac5f965c
check_source 'Individual Progression' "$ip" 283abe12774801e5671da746ea8bf535cc0252e0
check_source 'Naxxramas Core' "$naxx" ''
printf '\n%s\n' 'This is SOURCE checkout metadata only; uncommitted changes and running binary were NOT checked.'
if (( missing )); then
  printf '%s\n' 'STOP: checkout path missing or nested in another repository. Supply exact paths, do not initialise or switch branches.'
  exit 2
fi
if (( different )); then
  printf '%s\n' 'REVIEW REQUIRED: upstream checkout differs from pinned CI. Check compatibility before staging.'
  exit 3
fi
printf '%s\n' 'Pinned source revisions match. Separate binary and staging validation are still required.'
