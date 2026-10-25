-- PAK-D1 client contract witnesses against a frozen PetAutocastKeeper tree.
-- Lua 5.1. Does not modify the addon. Does not claim in-game behaviour.
-- Usage: lua5.1 tests/research/test_a02_pak_d1_addon_contract.lua <addon-dir>

local dir = arg and arg[1]
if not dir or dir == "" then
  print("NOT TESTED: pass the PetAutocastKeeper directory")
  os.exit(2)
end

local EXPECT = {
  ["Logic.lua"] = "f9f298d7b6aeedadf8f97650efe868bce031c9442ac9be793532fa526ebe1197",
  ["Core.lua"] = "9cff769e2259df711f43c3bc7878070e5289267a6585c87c0c4b44b87c0e234d",
  ["HANDOVER.md"] = "3b9327986eeeb3134d7a68cc68cabf7d8bbab8717f417011d9c05e41d2de3253",
  ["README.md"] = "7cd46eec44b9fef75bc652dc580cacef6913865f177a3246c9f65cf3b0c4c861",
}

local function sha256(path)
  local cmd = "sha256sum " .. string.format("%q", path)
  local pipe = assert(io.popen(cmd))
  local line = pipe:read("*l")
  pipe:close()
  return line and line:match("^(%x+)")
end

local function read_all(path)
  local handle = assert(io.open(path, "r"))
  local text = handle:read("*a")
  handle:close()
  return text
end

local pass, fail = 0, 0
local function ok(cond, name)
  if cond then
    pass = pass + 1
  else
    fail = fail + 1
    print("FAIL: " .. name)
  end
end

for name, hash in pairs(EXPECT) do
  local got = sha256(dir .. "/" .. name)
  ok(got == hash, name .. " sha256 " .. tostring(got))
end

if fail > 0 then
  print(string.format("addon hash mismatch; passed %d, failed %d", pass, fail))
  os.exit(1)
end

dofile(dir .. "/Logic.lua")
local L = PetAutocastKeeper.Logic
local P = L.Protocol

ok(P.PREFIX == "NXCPAK" and not P.PREFIX:find("\t"), "prefix has no tab")
ok(P.MAX_PAYLOAD == 233 and P.MAX_LINE == 255, "client budgets 233 and 255")
ok(P.RATE_MAX == 8 and P.RATE_WINDOW == 11.0, "client window is 8 per 11s")
ok(P.ClearPayload() == "v1|clear" and P.Validate("v1|clear"), "clear payload has no pet field")
ok(#P.ClearPayload() == 8 and not P.ClearPayload():find("|", 4, true), "clear payload is exactly 8 bytes and has no second field")

ok(L.PetKey("Fluffy", "Wolf") == "name:Fluffy", "named pet keys by name")
ok(L.PetKey("Fluffy", "Cat") == "name:Fluffy", "same name different family collides")
ok(L.PetKey("Fluffy", "Wolf") == L.PetKey("Fluffy", "Wolf"), "two same-name wolves collide")
ok(L.PetKey(nil, "Serpent") == "family:Serpent", "empty name falls back to family")
ok(L.PetKey("Unknown", "Wolf") == "family:Wolf", "Unknown name falls back to family")
ok(L.PetKey("", "Serpent") == "family:Serpent", "blank name falls back to family")

local saves = {}
local key_a = L.PetKey("Fluffy", "Wolf")
local key_b = L.PetKey("Fluffy", "Wolf")
saves[key_a] = { Bite = false }
saves[key_b].Bite = true
ok(saves[key_a].Bite == true, "same PetKey overwrites the other pet's Bite")

local built = P.BuildPayloads(7, { { id = 17259, on = true }, { id = 1742, on = false } })
ok(#built == 1 and built[1] == "v1|7|1/1|1742=0,17259=1", "v1 doc example has no pet token")
ok(not built[1]:find("v2|"), "example is not v2")

local seq, wrapped = P.NextSeq(999999999)
ok(seq == 1 and wrapped == true, "seq wrap returns 1 and asks for clear")
local wrap_state = L.NewState()
wrap_state.seq = 999999999
local wrapped_msgs = L.RelayDecide(wrap_state, { { id = 1, on = true } }, 0)
ok(wrapped_msgs[1] == "v1|clear" and wrapped_msgs[2] == "v1|1|1/1|1=1", "wrap sends unscoped v1|clear then seq 1")

local state = L.NewState()
local first = L.RelayDecide(state, { { id = 17259, on = false } }, 1)
L.OnPetReset(state)
local second = L.RelayDecide(state, { { id = 17259, on = false } }, 2)
local function v1_shape(text)
  return type(text) == "string" and text:match("^v1|%d+|%d+/%d+|[%d=,]*$") ~= nil
end
ok(first and v1_shape(first[1]) and first[1] == "v1|1|1/1|17259=0", "first relay is v1 seq 1")
ok(second and v1_shape(second[1]) and second[1] == "v1|2|1/1|17259=0", "pet reset sends a new seq and still no pet id")

L.OnPetReset(state)
local empty = L.RelayDecide(state, {}, 3)
ok(empty and empty[1]:match("^v1|%d+|1/1|$") ~= nil, "empty spellbook still sends an empty v1 set")

local function has_id(entries, id)
  for _, entry in ipairs(entries) do
    if entry.id == id then return true end
  end
  return false
end

local missing_book, missing_names = L.RelayEntries(
  { Bite = false, Cower = true },
  { Bite = {} },
  { Bite = 17259, Cower = 1742 }
)
ok(#missing_book == 1 and missing_book[1].id == 17259 and missing_book[1].on == false,
  "spell absent from the bar is omitted")
ok(not has_id(missing_book, 1742), "Cower absent from the bar is omitted")
ok(#missing_names == 0, "absent bar spell is not reported as an unresolved id")

local no_id, unresolved = L.RelayEntries(
  { Bite = false, Cower = true },
  { Bite = {}, Cower = {} },
  { Bite = 17259 }
)
ok(#no_id == 1 and not has_id(no_id, 1742), "Cower with no spell id is not written into the relay")
ok(unresolved[1] == "Cower", "Cower present on the bar but missing from the book is unresolved")

local cower_on = L.RelayEntries({ Cower = false }, { Cower = {} }, { Cower = 1742 })
ok(#cower_on == 1 and cower_on[1].id == 1742 and cower_on[1].on == false,
  "Cower present is eligible for the v1 relay")

local core = read_all(dir .. "/Core.lua")
ok(not core:find("CHAT_MSG_ADDON", 1, true), "Core.lua does not register CHAT_MSG_ADDON")
ok(core:find("P.ClearPayload()", 1, true) ~= nil, "reset sends the protocol clear")
ok(core:find("db.pets[k] = nil", 1, true) ~= nil, "reset deletes only the current PetKey locally")

local readme = read_all(dir .. "/README.md")
local handover = read_all(dir .. "/HANDOVER.md")
ok(readme:find("The server never toggles Cower (1742)", 1, true) ~= nil,
  "README still says the server never toggles 1742")
ok(handover:find("7b21bc0", 1, true) ~= nil, "HANDOVER still names head 7b21bc0")
ok(handover:find("The server never toggles Cower 1742.", 1, true) ~= nil,
  "HANDOVER still says the server never toggles 1742")

print(string.format("lua contract passed %d, failed %d", pass, fail))
if fail > 0 then os.exit(1) end
