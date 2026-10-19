#!/usr/bin/env python3
"""Read-only proof of pinned EP tower-name/zone/faction announcement source route.

Checks one exact source tuple. Does not open a game server or send a message.
"""
import argparse
from pathlib import Path
import re


def strip_comments(code):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.DOTALL)


def block(code, first, end, name):
    a = code.find(first)
    if a < 0:
        raise ValueError(f"{name}: missing start {first}")
    z = code.find(end, a + len(first))
    if z < 0:
        raise ValueError(f"{name}: missing end {end}")
    return code[a:z]


def ensure(code, text, name):
    if text not in code:
        raise ValueError(f"{name}: missing contract {text}")


def scoped_body(code, marker, label):
    """Extract one braced C++ if-block, fail-closed on missing braces.

    Operates only on the already comment-stripped pinned source. No string
    literal with braces exists in this reviewed capture/lock region.
    """
    start = code.find(marker)
    if start < 0:
        raise ValueError(f"{label}: missing guard")
    opening = code.find("{", start + len(marker))
    if opening < 0:
        raise ValueError(f"{label}: missing opening brace")
    depth = 0
    for i in range(opening, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return code[opening + 1:i]
    raise ValueError(f"{label}: unbalanced braces")


def check(native_ep_h, native_map_h, native_map_cpp, module_cpp):
    header = strip_comments(native_ep_h)
    original_enum = block(header, "enum EP_Towers", "};", "pinned EP tower enum")
    original_order = re.findall(r"\b(EP_EWT|EP_NPT|EP_PWT|EP_CGT|EP_TOWER_NUM)\b",
                                original_enum)
    if original_order != ["EP_EWT", "EP_NPT", "EP_PWT", "EP_CGT", "EP_TOWER_NUM"]:
        raise ValueError("pinned EP tower enum order/count changed")
    ensure(header, "EP_EWT = 0", "pinned EP enum initial offset")
    ensure(header, "EP_GraveyardZone = AREA_EASTERN_PLAGUELANDS",
           "native zone constant")

    # The C++ signature can wrap across lines; normalize whitespace rather
    # than requiring the source/test fixture to use one particular layout.
    mh = " ".join(strip_comments(native_map_h).split())
    ensure(mh, "void SendZoneText(uint32 zoneId, char const* text,"
           " WorldSession const* self = nullptr, TeamId teamId = TEAM_NEUTRAL)",
           "native zone message default team")
    mc = strip_comments(native_map_cpp)
    sending = block(mc, "bool Map::SendZoneMessage(", "void Map::SendZoneText(",
                    "native zone filtering")
    for part in ("player->IsInWorld()", "player->GetZoneId() == zone",
                 "teamId == TEAM_NEUTRAL || player->GetTeamId() == teamId"):
        ensure(sending, part, "native zone delivery/filter")
    zone_text = block(mc, "void Map::SendZoneText(",
                      "void Map::SendZoneDynamicInfo(", "native zone text")
    ensure(zone_text, "SendZoneMessage(zoneId, &data, self, teamId);",
           "native zone text to message route")

    module = strip_comments(module_cpp)
    names = block(module, "char const* const TowerNames[EP_TOWER_NUM]", "};",
                  "four tower names")
    actual_names = re.findall(r'"([^"]+)"', names)
    expected_names = ["Eastwall Tower", "Northpass Tower",
                      "Plaguewood Tower", "Crown Guard Tower"]
    if actual_names != expected_names:
        raise ValueError("module tower display names no longer match pinned enum")
    for role in ("OPvPCapturePointEP_EWT, EP_EWT",
                 "OPvPCapturePointEP_NPT, EP_NPT",
                 "OPvPCapturePointEP_PWT, EP_PWT",
                 "OPvPCapturePointEP_CGT, EP_CGT"):
        ensure(module, role, "wrapper tower index mapping")

    update = block(module, "bool Update(uint32 diff) override",
                   "void CorrectLateNorthpassShrine(", "capture update")
    ensure(update, "if (_expiresAt)", "locked update guard")
    ensure(update, "OPvPCapturePoint::Update(0);", "no-progress locked tick")
    ensure(update, "OPvPCapturePoint::Update(diff);", "normal capture progress")
    for endpoint in ("this->_value >= this->_maxValue",
                     "this->_value <= -this->_maxValue",
                     "this->_maxValue > 0.0f"):
        ensure(update, endpoint, "signed 100 percent endpoint")
    guard = "if (PackLock(this->_team, expiresAt, packed))"
    persist = "sWorldState->setWorldState(TowerStateBase + Index, packed);"
    notify = "map->SendZoneText(EP_GraveyardZone, message.c_str());"
    for required in (guard, persist, notify, "message += TowerNames[Index]"):
        ensure(update, required, "full capture persistence/announcement")
    if not (update.index("OPvPCapturePoint::Update(diff);") <
            update.index(guard) < update.index(persist) < update.index(notify)):
        raise ValueError("EP announce no longer after successful lock persistence call")
    endpoint_body = scoped_body(update, "if (this->_maxValue > 0.0f &&",
                                "signed full-cap guard")
    lock_body = scoped_body(endpoint_body, guard, "successful PackLock guard")
    if persist not in lock_body or notify not in lock_body:
        raise ValueError("EP zone notice escaped the signed endpoint or PackLock scope")
    if lock_body.index(persist) >= lock_body.index(notify):
        raise ValueError("EP zone notice precedes lock persistence inside guard")
    if module.count("SendZoneText(") != 1 or update.count("SendZoneText(") != 1:
        raise ValueError("EP additional zone notifications outside lock-start path")
    ensure(module, "using EastwallTower = NaxxramasLockedEPTower<",
           "typed EP wrapper")
    ensure(module, "TowerLockSeconds = 90 * 60", "lock duration")
    restore = block(module, "void RestoreFromPersistentState()",
                    "void ResetToNeutral()", "restore path")
    reset = block(module, "void ResetToNeutral()",
                  "uint64 _expiresAt", "reset path")
    if "SendZoneText(" in restore or "SendZoneText(" in reset:
        raise ValueError("EP restore/reset unexpectedly announces capture")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("ep-header", "map-header", "map-source", "module"):
        parser.add_argument("--" + arg, type=Path, required=True)
    opts = parser.parse_args()
    try:
        check(*(getattr(opts, arg).read_text(encoding="utf-8")
                for arg in ("ep_header", "map_header", "map_source", "module")))
    except (ValueError, OSError) as error:
        print(f"FAIL: pinned EP zone announcement contract not certified: {error}")
        return 1
    print("PASS: pinned EP names, zone-neutral default routing and capture-lock"
          " announcement source order.")
    print("LIMIT: actual message delivery, installed SQL selection and gameplay"
          " are NOT verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
