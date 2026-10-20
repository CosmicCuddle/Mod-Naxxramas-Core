/*
 * Naxxramas Core — hunter pet autocast cache. Default off. Module only.
 *
 * Snapshot on the map thread that owns the pet, then re-apply from a
 * pet-queued event. Cycle state is Pet::CustomData. There is no
 * process-global pet map. Cache writes are the snapshot or the verified
 * decision, never a post-IP read, except OnPlayerSave after the window.
 *
 * The characters table is created by data/sql/db-characters/
 * 2026_10_20_00_hunter_pet_autocast_cache.sql. This file does not apply it.
 */

#include "HunterPetAutocastCache.h"

#include "AccountMgr.h"
#include "CharmInfo.h"
#include "Config.h"
#include "DatabaseEnv.h"
#include "DataMap.h"
#include "EventProcessor.h"
#include "ObjectAccessor.h"
#include "Pet.h"
#include "PetScript.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "SpellMgr.h"
#include "WorldSession.h"

#include <atomic>
#include <map>
#include <string>
#include <vector>

namespace
{
using namespace NaxxramasCore::HunterPetAutocastCache;

std::atomic<bool> FeatureEnabled{ false };

char const* CycleKey = "naxx_a02_hunter_pet_autocast_cache";

class PetAutocastCacheCycle : public DataMap::Base
{
public:
    uint64_t ownerGuid = 0;
    uint64_t petGuid = 0;
    uint32_t petNumber = 0;
    uint32_t generation = 0;
    bool pending = false;
    bool windowOpen = false;
    bool finished = false;
    bool snapshotWritten = false;
    bool suppressPlayerSave = false;
    std::map<uint32_t, bool> snapshot;
    std::map<uint32_t, bool> lastWritten;
    ChainLists lists;
    Clock clock;
};

bool IsFeatureEnabled()
{
    return FeatureEnabled.load(std::memory_order_acquire);
}

std::string Unquote(std::string text)
{
    if (text.size() >= 2 && text.front() == '"' && text.back() == '"')
        return text.substr(1, text.size() - 2);
    return text;
}

AccountVerdict ClassifyPlayer(Player* player)
{
    if (!player || !player->GetSession())
        return AccountVerdict::Ineligible;

    std::string accountName;
    bool const found = AccountMgr::GetName(player->GetSession()->GetAccountId(), accountName);
    std::string const pattern = Unquote(sConfigMgr->GetOption<std::string>(BotAccountsRegexKey, DefaultBotAccountsRegex));
    return ClassifyAccount(found, found ? accountName.c_str() : nullptr, pattern.c_str());
}

bool IsEligibleHumanHunter(Player* player)
{
    return player && player->getClass() == CLASS_HUNTER &&
        ClassifyPlayer(player) == AccountVerdict::ConfirmedHuman;
}

uint32_t PetNumberOf(Pet* pet)
{
    if (!pet || !pet->GetCharmInfo())
        return 0;
    return pet->GetCharmInfo()->GetPetNumber();
}

uint64_t GuidRaw(ObjectGuid guid)
{
    return guid.GetRawValue();
}

uint32_t FirstRank(SpellInfo const* info)
{
    if (!info)
        return 0;
    SpellInfo const* first = info->GetFirstRankSpell();
    return first ? first->Id : info->Id;
}

bool OwnerLoggingOut(Player* player)
{
    if (!player)
        return true;
    WorldSession* session = player->GetSession();
    return !session || session->IsLoggingOut() || session->PlayerLogout();
}

ChainLists ListsFromConfig()
{
    ChainLists lists;
    std::string const damage = Unquote(sConfigMgr->GetOption<std::string>(DamageSpellIdsKey, DefaultDamageSpellIdsRaw));
    std::string const utility = Unquote(sConfigMgr->GetOption<std::string>(UtilitySpellIdsKey, DefaultUtilitySpellIdsRaw));
    std::string const optionalOn = Unquote(sConfigMgr->GetOption<std::string>(OptionalSpellIdsKey, DefaultOptionalSpellIdsRaw));
    lists.damage = ParseSpellIds(damage.c_str());
    lists.utility = ParseSpellIds(utility.c_str());
    lists.optionalOn = ParseSpellIds(optionalOn.c_str());
    return lists;
}

SourceSpell FromSpell(uint32_t spellId, bool on, bool removed)
{
    SourceSpell row;
    SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId);
    if (!info)
        return row;
    row.chainFirst = FirstRank(info);
    row.spellId = info->Id;
    row.autocastable = info->IsAutocastable();
    row.removed = removed;
    row.autocastOn = on;
    return row;
}

std::vector<SourceSpell> ReadBook(Pet* pet)
{
    std::vector<SourceSpell> book;
    if (!pet)
        return book;

    for (auto const& entry : pet->m_spells)
    {
        SourceSpell row = FromSpell(entry.first, entry.second.active == ACT_ENABLED, entry.second.state == PETSPELL_REMOVED);
        if (row.chainFirst != 0)
            book.push_back(row);
    }
    return book;
}

std::vector<SourceSpell> ReadCharm(Pet* pet)
{
    std::vector<SourceSpell> rows;
    CharmInfo* charm = pet ? pet->GetCharmInfo() : nullptr;
    if (!charm)
        return rows;

    for (uint8 index = 0; index < MAX_UNIT_ACTION_BAR_INDEX; ++index)
    {
        UnitActionBarEntry const* entry = charm->GetActionBarEntry(index);
        if (!entry || !entry->GetAction() || !entry->IsActionBarForSpell())
            continue;
        ActiveStates const type = entry->GetType();
        if (type != ACT_ENABLED && type != ACT_DISABLED)
            continue;
        SourceSpell row = FromSpell(entry->GetAction(), type == ACT_ENABLED, false);
        if (row.chainFirst != 0)
            rows.push_back(row);
    }
    return rows;
}

std::vector<SourceSpell> ReadCache(uint32_t ownerLow, uint32_t petNumber)
{
    std::vector<SourceSpell> rows;
    if (ownerLow == 0 || petNumber == 0)
        return rows;

    QueryResult result = CharacterDatabase.Query(
        "SELECT `spell_first`, `active` FROM `{}` WHERE `owner_guid` = {} AND `pet_number` = {}",
        CacheTableName, ownerLow, petNumber);
    if (!result)
        return rows;

    do
    {
        Field* fields = result->Fetch();
        SourceSpell row;
        row.chainFirst = fields[0].Get<uint32>();
        row.spellId = row.chainFirst;
        row.autocastable = true;
        row.removed = false;
        row.autocastOn = fields[1].Get<uint8>() != 0;
        if (row.chainFirst != 0)
            rows.push_back(row);
    } while (result->NextRow());
    return rows;
}

std::vector<SourceSpell> ReadPetSpell(uint32_t petNumber)
{
    std::vector<SourceSpell> rows;
    if (petNumber == 0)
        return rows;

    QueryResult result = CharacterDatabase.Query(
        "SELECT `spell`, `active` FROM `pet_spell` WHERE `guid` = {}", petNumber);
    if (!result)
        return rows;

    do
    {
        Field* fields = result->Fetch();
        uint32_t const spellId = fields[0].Get<uint32>();
        uint8_t const active = fields[1].Get<uint8>();
        SourceSpell row = FromSpell(spellId, active == ACT_ENABLED, false);
        if (row.chainFirst != 0)
            rows.push_back(row);
    } while (result->NextRow());
    return rows;
}

void WriteCache(uint32_t ownerLow, uint32_t petNumber, std::map<uint32_t, bool> const& rows)
{
    if (ownerLow == 0 || petNumber == 0)
        return;

    CharacterDatabase.DirectExecute(
        "DELETE FROM `{}` WHERE `owner_guid` = {} AND `pet_number` = {}",
        CacheTableName, ownerLow, petNumber);

    for (auto const& entry : rows)
    {
        CharacterDatabase.DirectExecute(
            "INSERT INTO `{}` (`owner_guid`, `pet_number`, `spell_first`, `active`) VALUES ({}, {}, {}, {})",
            CacheTableName, ownerLow, petNumber, entry.first, entry.second ? 1 : 0);
    }
}

bool SameRows(std::map<uint32_t, bool> const& left, std::map<uint32_t, bool> const& right)
{
    return left == right;
}

bool ApplyActions(Player* player, Pet* pet, std::vector<ApplyAction> const& actions)
{
    bool changed = false;
    for (ApplyAction const& action : actions)
    {
        if (action.spellId == 0 || !pet->HasSpell(action.spellId))
            continue;
        SpellInfo const* info = sSpellMgr->GetSpellInfo(action.spellId);
        if (!info || !info->IsAutocastable())
            continue;

        auto itr = pet->m_spells.find(action.spellId);
        if (itr == pet->m_spells.end() || itr->second.state == PETSPELL_REMOVED)
            continue;
        if ((itr->second.active == ACT_ENABLED) == action.desiredOn)
            continue;

        pet->ToggleAutocast(info, action.desiredOn);
        if (CharmInfo* charm = pet->GetCharmInfo())
            charm->SetSpellAutocast(info, action.desiredOn);
        changed = true;
    }

    if (changed)
        player->PetSpellInitialize();
    return changed;
}

class HunterPetAutocastCacheEvent : public BasicEvent
{
public:
    HunterPetAutocastCacheEvent(ObjectGuid owner, uint64_t petGuid, uint32_t generation)
        : _owner(owner), _petGuid(petGuid), _generation(generation)
    {
    }

    bool Execute(uint64 /*eventTime*/, uint32 /*delta*/) override
    {
        if (!IsFeatureEnabled())
            return true;

        Player* player = ObjectAccessor::FindPlayer(_owner);
        Pet* pet = player ? player->GetPet() : nullptr;
        if (!pet || GuidRaw(pet->GetGUID()) != _petGuid)
            return true;

        PetAutocastCacheCycle* cycle = pet->CustomData.Get<PetAutocastCacheCycle>(CycleKey);
        if (!cycle || cycle->generation != _generation || cycle->finished)
            return true;

        bool const loggingOut = OwnerLoggingOut(player);
        Binding bound;
        bound.ownerGuid = cycle->ownerGuid;
        bound.petGuid = cycle->petGuid;
        bound.petNumber = cycle->petNumber;
        Binding live;
        live.ownerGuid = GuidRaw(player->GetGUID());
        live.petGuid = GuidRaw(pet->GetGUID());
        live.petNumber = PetNumberOf(pet);

        IdentityResult const identity = CheckIdentity(
            bound, live, cycle->windowOpen, pet->IsInWorld(), pet->IsDuringRemoveFromWorld(), loggingOut);
        if (identity == IdentityResult::Abort)
        {
            cycle->finished = true;
            cycle->pending = false;
            cycle->windowOpen = false;
            cycle->suppressPlayerSave = true;
            return true;
        }
        cycle->petNumber = bound.petNumber;

        if (!IsEligibleHumanHunter(player) || pet->getPetType() != HUNTER_PET)
        {
            cycle->finished = true;
            cycle->pending = false;
            cycle->windowOpen = false;
            cycle->suppressPlayerSave = true;
            return true;
        }

        TickDecision const tick = OnTick(cycle->clock, pet->isBeingLoaded());
        cycle->windowOpen = cycle->clock.open && !cycle->clock.done;
        if (tick.apply)
        {
            std::vector<SourceSpell> const book = ReadBook(pet);
            if (!book.empty() && AllowCacheWrite(WriteCause::VerifiedRestore, true))
            {
                std::map<uint32_t, bool> const rows = VerifiedCacheRows(cycle->snapshot, book, cycle->lists);
                if (!cycle->snapshotWritten || !SameRows(cycle->lastWritten, rows))
                {
                    WriteCache(player->GetGUID().GetCounter(), cycle->petNumber, rows);
                    cycle->lastWritten = rows;
                    cycle->snapshotWritten = true;
                }
            }
            ApplyActions(player, pet, PlanApply(cycle->snapshot, book, cycle->lists));
        }

        if (tick.closed)
        {
            cycle->finished = true;
            cycle->pending = false;
            cycle->windowOpen = false;
            return true;
        }

        if (tick.requeue)
        {
            pet->m_Events.AddEvent(
                new HunterPetAutocastCacheEvent(_owner, _petGuid, _generation),
                pet->m_Events.CalculateTime(tick.delayMs));
        }
        return true;
    }

private:
    ObjectGuid _owner;
    uint64_t _petGuid = 0;
    uint32_t _generation = 0;
};

void QueueEvent(Player* player, Pet* pet, PetAutocastCacheCycle& cycle)
{
    pet->m_Events.AddEvent(
        new HunterPetAutocastCacheEvent(player->GetGUID(), cycle.petGuid, cycle.generation),
        pet->m_Events.CalculateTime(RestoreTickMs));
}

void BeginCycle(Player* player, Pet* pet, SnapshotResult const& snapshot)
{
    if (!player || !pet)
        return;

    PetAutocastCacheCycle* cycle = pet->CustomData.GetDefault<PetAutocastCacheCycle>(CycleKey);
    if (cycle->pending && cycle->petGuid == GuidRaw(pet->GetGUID()))
    {
        Binding bound;
        bound.ownerGuid = cycle->ownerGuid;
        bound.petGuid = cycle->petGuid;
        bound.petNumber = cycle->petNumber;
        Binding live;
        live.ownerGuid = GuidRaw(player->GetGUID());
        live.petGuid = GuidRaw(pet->GetGUID());
        live.petNumber = PetNumberOf(pet);
        if (CheckIdentity(bound, live, cycle->windowOpen, true, false, false) == IdentityResult::UpdatedNumber)
            cycle->petNumber = bound.petNumber;
        return;
    }

    uint32_t const petNumber = PetNumberOf(pet);
    if (petNumber == 0 || GuidRaw(pet->GetGUID()) == 0)
        return;

    cycle->ownerGuid = GuidRaw(player->GetGUID());
    cycle->petGuid = GuidRaw(pet->GetGUID());
    cycle->petNumber = petNumber;
    cycle->generation += 1u;
    cycle->pending = true;
    cycle->windowOpen = false;
    cycle->finished = false;
    cycle->snapshotWritten = false;
    cycle->suppressPlayerSave = false;
    cycle->snapshot = snapshot.chains;
    cycle->lastWritten.clear();
    cycle->lists = ListsFromConfig();
    cycle->clock = Clock();
    QueueEvent(player, pet, *cycle);
}

void OnLoad(Pet* pet)
{
    if (!IsFeatureEnabled() || !pet || pet->getPetType() != HUNTER_PET || !pet->isBeingLoaded())
        return;
    if (pet->IsDuringRemoveFromWorld())
        return;

    Player* owner = pet->GetOwner();
    if (!IsEligibleHumanHunter(owner) || OwnerLoggingOut(owner) || !owner->IsInWorld())
        return;

    uint32_t const petNumber = PetNumberOf(pet);
    if (petNumber == 0)
        return;

    ChainLists const lists = ListsFromConfig();
    std::vector<SourceSpell> const cacheRows = ReadCache(owner->GetGUID().GetCounter(), petNumber);
    std::vector<SourceSpell> const petSpellRows = ReadPetSpell(petNumber);
    std::vector<SourceSpell> const charmRows = ReadCharm(pet);
    BeginCycle(owner, pet, ChooseLoadSnapshot(cacheRows, petSpellRows, charmRows, lists.utility));
}

void OnLevelOrTame(Pet* pet)
{
    if (!IsFeatureEnabled() || !pet || pet->getPetType() != HUNTER_PET || pet->isBeingLoaded())
        return;
    if (pet->IsDuringRemoveFromWorld())
        return;

    Player* owner = pet->GetOwner();
    if (!IsEligibleHumanHunter(owner) || OwnerLoggingOut(owner) || !owner->IsInWorld())
        return;

    ChainLists const lists = ListsFromConfig();
    BeginCycle(owner, pet, CollapseLiveBook(ReadBook(pet), lists.utility));
}

class NaxxramasCoreHunterPetAutocastCacheConfig : public WorldScript
{
public:
    NaxxramasCoreHunterPetAutocastCacheConfig()
        : WorldScript("NaxxramasCoreHunterPetAutocastCacheConfig", { WORLDHOOK_ON_BEFORE_CONFIG_LOAD })
    {
    }

    void OnBeforeConfigLoad(bool /*reload*/) override
    {
        FeatureEnabled.store(sConfigMgr->GetOption<bool>(EnabledConfigKey, false), std::memory_order_release);
    }
};

class NaxxramasCoreHunterPetAutocastCachePet : public PetScript
{
public:
    NaxxramasCoreHunterPetAutocastCachePet()
        : PetScript(
            "NaxxramasCoreHunterPetAutocastCachePet",
            { PETHOOK_ON_PET_ADD_TO_WORLD, PETHOOK_ON_INIT_STATS_FOR_LEVEL })
    {
    }

    void OnPetAddToWorld(Pet* pet) override
    {
        OnLoad(pet);
    }

    void OnInitStatsForLevel(Guardian* guardian, uint8 /*petlevel*/) override
    {
        if (!guardian)
            return;
        OnLevelOrTame(guardian->ToPet());
    }
};

class NaxxramasCoreHunterPetAutocastCachePlayer : public PlayerScript
{
public:
    NaxxramasCoreHunterPetAutocastCachePlayer()
        : PlayerScript(
            "NaxxramasCoreHunterPetAutocastCachePlayer",
            { PLAYERHOOK_ON_SAVE, PLAYERHOOK_ON_BEFORE_LOGOUT })
    {
    }

    void OnPlayerSave(Player* player) override
    {
        if (!IsFeatureEnabled() || !IsEligibleHumanHunter(player) || OwnerLoggingOut(player))
            return;

        Pet* pet = player->GetPet();
        if (!pet || pet->getPetType() != HUNTER_PET || pet->isBeingLoaded() || pet->IsDuringRemoveFromWorld())
            return;

        PetAutocastCacheCycle* cycle = pet->CustomData.Get<PetAutocastCacheCycle>(CycleKey);
        if (cycle && cycle->petGuid == GuidRaw(pet->GetGUID()) && cycle->suppressPlayerSave)
            return;
        bool const restoreActive = cycle && cycle->petGuid == GuidRaw(pet->GetGUID()) && cycle->pending && !cycle->finished;
        if (!AllowCacheWrite(WriteCause::PlayerSave, restoreActive))
            return;

        uint32_t const petNumber = PetNumberOf(pet);
        if (petNumber == 0)
            return;

        ChainLists lists = cycle && cycle->petGuid == GuidRaw(pet->GetGUID()) ? cycle->lists : ListsFromConfig();
        std::map<uint32_t, bool> const rows = PlayerToggleRows(ReadBook(pet), lists.utility);
        WriteCache(player->GetGUID().GetCounter(), petNumber, rows);
        if (cycle && cycle->petGuid == GuidRaw(pet->GetGUID()))
        {
            cycle->lastWritten = rows;
            cycle->snapshotWritten = true;
        }
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        if (!player)
            return;
        Pet* pet = player->GetPet();
        if (!pet)
            return;
        PetAutocastCacheCycle* cycle = pet->CustomData.Get<PetAutocastCacheCycle>(CycleKey);
        if (!cycle || cycle->petGuid != GuidRaw(pet->GetGUID()))
            return;
        if (cycle->pending && !cycle->finished)
            cycle->suppressPlayerSave = true;
        cycle->finished = true;
        cycle->pending = false;
        cycle->windowOpen = false;
    }
};
} // namespace

void AddHunterPetAutocastCacheScripts()
{
    new NaxxramasCoreHunterPetAutocastCacheConfig();
    new NaxxramasCoreHunterPetAutocastCachePet();
    new NaxxramasCoreHunterPetAutocastCachePlayer();
}
