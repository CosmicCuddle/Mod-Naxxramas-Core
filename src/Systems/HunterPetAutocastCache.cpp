/*
 * Naxxramas Core — hunter pet autocast cache. Default off. Module only.
 *
 * OnPetAddToWorld runs before _LoadSpells. This file does not snapshot
 * there and does not read the charm bar as the saved book. The pet event
 * waits until !isBeingLoaded(), then reads character_pet and pet_spell.
 * Cache rows are accepted only for that same character_pet life.
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
#include "Log.h"
#include "ObjectAccessor.h"
#include "Pet.h"
#include "PetScript.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "SpellMgr.h"
#include "WorldSession.h"

#include <algorithm>
#include <atomic>
#include <map>
#include <string>
#include <vector>

namespace
{
using namespace NaxxramasCore::HunterPetAutocastCache;

static_assert(!CharmBarIsAuthoritativeSavedSpellbook(), "charm bar is not the saved spellbook");
static_assert(!MayTouchDatabase(false), "disabled feature does not touch the database");

std::atomic<bool> FeatureEnabled{ false };
std::atomic<uint8_t> CacheSchema{ 0 };

char const* CycleKey = "naxx_a02_hunter_pet_autocast_cache";

class PetAutocastCacheCycle : public DataMap::Base
{
public:
    uint64_t ownerGuid = 0;
    uint64_t petGuid = 0;
    uint32_t petNumber = 0;
    uint32_t generation = 0;
    bool pending = false;
    bool finished = false;
    bool bornThisSession = false;
    bool snapshotReady = false;
    bool suppressPlayerSave = false;
    bool needsSavetimeRefresh = false;
    LoadDecision decision;
    std::map<uint32_t, bool> lastWritten;
    ChainLists lists;
    OrderState order;
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

bool CacheTablePresent()
{
    uint8_t const known = CacheSchema.load(std::memory_order_acquire);
    if (known == 1)
        return true;
    if (known == 2)
        return false;

    QueryResult result = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = '{}' "
        "AND column_name IN ('owner_guid','pet_number','creature_entry','created_by_spell','seen_savetime','spell_first','active')",
        CacheTableName);
    bool present = false;
    if (result)
        present = result->Fetch()[0].Get<uint64>() == ExpectedCacheColumnCount;
    CacheSchema.store(present ? 1 : 2, std::memory_order_release);
    if (!present)
    {
        LOG_WARN("module",
            "Naxxramas Core: hunter pet autocast cache table is missing or is not the revised 7-column shape. "
            "Saved pet_spell bits can still be restored. New damage chains are not turned on, and nothing is written. "
            "The characters SQL file is not applied by this module.");
    }
    return present;
}

OwnerProof ReadOwner(uint32_t ownerLow, uint32_t petNumber)
{
    OwnerProof proof;
    if (ownerLow == 0 || petNumber == 0)
        return proof;

    QueryResult result = CharacterDatabase.Query(
        "SELECT `entry`, `CreatedBySpell`, `savetime` FROM `character_pet` WHERE `owner` = {} AND `id` = {}",
        ownerLow, petNumber);
    if (!result)
        return proof;

    uint32_t rows = 0;
    do
    {
        ++rows;
        if (rows == 1)
        {
            Field* fields = result->Fetch();
            proof.creatureEntry = fields[0].Get<uint32>();
            proof.createdBySpell = fields[1].Get<uint32>();
            proof.savetime = fields[2].Get<uint32>();
        }
    } while (result->NextRow());

    if (rows == 1 && proof.creatureEntry != 0)
        proof.lookup = OwnerLookup::Unique;
    else if (rows > 1)
        proof.lookup = OwnerLookup::Ambiguous;
    else
        proof.lookup = OwnerLookup::Unproven;
    return proof;
}

std::vector<StoredCacheRow> ReadCache(uint32_t ownerLow, uint32_t petNumber, DatabaseRead& status)
{
    std::vector<StoredCacheRow> rows;
    status = DatabaseRead::Failed;
    if (ownerLow == 0 || petNumber == 0)
        return rows;

    QueryResult result = CharacterDatabase.Query(
        "SELECT `spell_first`, `active`, `creature_entry`, `created_by_spell`, `seen_savetime` "
        "FROM `{}` WHERE `owner_guid` = {} AND `pet_number` = {}",
        CacheTableName, ownerLow, petNumber);
    status = DatabaseRead::Ok;
    if (!result)
        return rows;

    do
    {
        Field* fields = result->Fetch();
        StoredCacheRow row;
        row.chainFirst = fields[0].Get<uint32>();
        row.on = fields[1].Get<uint8>() != 0;
        row.creatureEntry = fields[2].Get<uint32>();
        row.createdBySpell = fields[3].Get<uint32>();
        row.seenSavetime = fields[4].Get<uint32>();
        if (row.chainFirst != 0)
            rows.push_back(row);
    } while (result->NextRow());
    return rows;
}

std::vector<SourceSpell> ReadPetSpell(uint32_t petNumber, DatabaseRead& status)
{
    std::vector<SourceSpell> rows;
    status = DatabaseRead::Failed;
    if (petNumber == 0)
        return rows;

    QueryResult result = CharacterDatabase.Query(
        "SELECT `spell`, `active` FROM `pet_spell` WHERE `guid` = {}", petNumber);
    status = DatabaseRead::Ok;
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

void DeleteStoredCache(uint32_t ownerLow, uint32_t petNumber)
{
    if (ownerLow == 0 || petNumber == 0)
        return;
    CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
    trans->Append(
        "DELETE FROM `{}` WHERE `owner_guid` = {} AND `pet_number` = {}",
        CacheTableName, ownerLow, petNumber);
    CharacterDatabase.CommitTransaction(trans);
}

void DeleteOrphans(uint32_t ownerLow)
{
    if (ownerLow == 0)
        return;
    CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
    trans->Append(
        "DELETE c FROM `{}` c "
        "LEFT JOIN `character_pet` p ON p.`id` = c.`pet_number` AND p.`owner` = c.`owner_guid` "
        "WHERE c.`owner_guid` = {} AND p.`id` IS NULL",
        CacheTableName, ownerLow);
    CharacterDatabase.CommitTransaction(trans);
}

void WriteCache(uint32_t ownerLow, uint32_t petNumber, LoadDecision const& decision, std::map<uint32_t, bool> const& rows)
{
    if (ownerLow == 0 || petNumber == 0 || decision.creatureEntry == 0)
        return;

    CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
    trans->Append(
        "DELETE FROM `{}` WHERE `owner_guid` = {} AND `pet_number` = {}",
        CacheTableName, ownerLow, petNumber);
    for (auto const& entry : rows)
    {
        trans->Append(
            "INSERT INTO `{}` (`owner_guid`, `pet_number`, `creature_entry`, `created_by_spell`, `seen_savetime`, `spell_first`, `active`) "
            "VALUES ({}, {}, {}, {}, {}, {}, {})",
            CacheTableName, ownerLow, petNumber, decision.creatureEntry, decision.createdBySpell,
            decision.seenSavetime, entry.first, entry.second ? 1 : 0);
    }
    CharacterDatabase.CommitTransaction(trans);
}

void RefreshSavetime(uint32_t ownerLow, uint32_t petNumber, LoadDecision const& decision)
{
    OwnerProof const proof = ReadOwner(ownerLow, petNumber);
    if (proof.lookup != OwnerLookup::Unique)
        return;
    if (proof.creatureEntry != decision.creatureEntry || proof.createdBySpell != decision.createdBySpell)
        return;
    CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
    trans->Append(
        "UPDATE `{}` SET `seen_savetime` = {} "
        "WHERE `owner_guid` = {} AND `pet_number` = {} AND `creature_entry` = {} AND `created_by_spell` = {}",
        CacheTableName, proof.savetime, ownerLow, petNumber, decision.creatureEntry, decision.createdBySpell);
    CharacterDatabase.CommitTransaction(trans);
}

bool ApplyReconcile(Player* player, Pet* pet, std::vector<ReconcileTarget> const& targets)
{
    bool changed = false;
    for (ReconcileTarget const& target : targets)
    {
        if (target.spellId == 0 || !pet->HasSpell(target.spellId))
            continue;
        SpellInfo const* info = sSpellMgr->GetSpellInfo(target.spellId);
        if (!info || !info->IsAutocastable())
            continue;
        auto itr = pet->m_spells.find(target.spellId);
        if (itr == pet->m_spells.end() || itr->second.state == PETSPELL_REMOVED)
            continue;
        if ((itr->second.active == ACT_ENABLED) == target.desiredOn)
            continue;

        pet->ToggleAutocast(info, target.desiredOn);
        if (CharmInfo* charm = pet->GetCharmInfo())
            charm->SetSpellAutocast(info, target.desiredOn);
        changed = true;
    }

    std::vector<AutocastEntry> autos;
    for (uint32 spellId : pet->m_autospells)
    {
        AutocastEntry entry;
        entry.spellId = spellId;
        SourceSpell const row = FromSpell(spellId, true, false);
        entry.chainFirst = row.chainFirst;
        entry.stillInBook = pet->HasSpell(spellId);
        if (entry.chainFirst != 0)
            autos.push_back(entry);
    }
    for (uint32_t spellId : StaleAutocastIds(autos, targets))
    {
        auto found = std::find(pet->m_autospells.begin(), pet->m_autospells.end(), spellId);
        if (found == pet->m_autospells.end())
            continue;
        pet->m_autospells.erase(found);
        changed = true;
    }

    if (changed)
        player->PetSpellInitialize();
    return changed;
}

void PersistDecision(Player* player, Pet* pet, PetAutocastCacheCycle& cycle, std::vector<SourceSpell> const& book)
{
    if (!cycle.decision.writeAllowed)
        return;
    CacheCommit const batch = PlanCacheCommit(cycle.decision, book, cycle.lists);
    if (!batch.commit || batch.rows == cycle.lastWritten)
        return;
    WriteCache(player->GetGUID().GetCounter(), cycle.petNumber, cycle.decision, batch.rows);
    cycle.lastWritten = batch.rows;
}

class HunterPetAutocastCacheEvent : public BasicEvent
{
public:
    HunterPetAutocastCacheEvent(ObjectGuid owner, uint64_t petGuid, uint32_t generation)
        : _owner(owner), _petGuid(petGuid), _generation(generation)
    {
    }

    bool Execute(uint64 eventTime, uint32 /*delta*/) override
    {
        if (!MayTouchDatabase(IsFeatureEnabled()))
            return true;

        Player* player = ObjectAccessor::FindPlayer(_owner);
        Pet* pet = player ? player->GetPet() : nullptr;
        if (!pet || GuidRaw(pet->GetGUID()) != _petGuid)
            return true;

        PetAutocastCacheCycle* cycle = pet->CustomData.Get<PetAutocastCacheCycle>(CycleKey);
        if (!cycle || cycle->generation != _generation)
            return true;
        if (cycle->finished && !cycle->needsSavetimeRefresh)
            return true;
        if (cycle->finished)
        {
            if (cycle->needsSavetimeRefresh && cycle->decision.writeAllowed)
                RefreshSavetime(player->GetGUID().GetCounter(), cycle->petNumber, cycle->decision);
            cycle->needsSavetimeRefresh = false;
            return true;
        }

        Binding live;
        live.ownerGuid = GuidRaw(player->GetGUID());
        live.petGuid = GuidRaw(pet->GetGUID());
        live.petNumber = PetNumberOf(pet);

        if (live.petNumber == 0 && !cycle->snapshotReady)
        {
            if (!pet->isBeingLoaded())
            {
                cycle->finished = true;
                cycle->pending = false;
                return true;
            }
            pet->m_Events.AddEvent(
                new HunterPetAutocastCacheEvent(_owner, _petGuid, _generation),
                pet->m_Events.CalculateTime(LoadPollMs));
            return true;
        }

        Binding bound;
        bound.ownerGuid = cycle->ownerGuid;
        bound.petGuid = cycle->petGuid;
        bound.petNumber = cycle->petNumber;

        IdentityResult const identity = CheckIdentity(
            bound, live, cycle->snapshotReady, pet->IsInWorld(), pet->IsDuringRemoveFromWorld(), false);
        if (identity == IdentityResult::Abort)
        {
            cycle->finished = true;
            cycle->pending = false;
            cycle->suppressPlayerSave = true;
            return true;
        }
        if (identity == IdentityResult::UpdatedNumber)
            cycle->petNumber = bound.petNumber;

        if (!IsEligibleHumanHunter(player) || pet->getPetType() != HUNTER_PET || cycle->petNumber == 0)
        {
            cycle->finished = true;
            cycle->pending = false;
            cycle->suppressPlayerSave = true;
            return true;
        }

        OrderStep const step = AdvanceOrder(cycle->order, pet->isBeingLoaded(), eventTime);
        if (step.snapshot)
            TakeSnapshot(player, pet, *cycle);

        if (step.apply && cycle->snapshotReady)
        {
            std::vector<SourceSpell> const book = ReadBook(pet);
            std::vector<ReconcileTarget> const targets = PlanReconcile(
                cycle->decision.chains, book, cycle->lists, cycle->decision.allowDefaultOn);
            ApplyReconcile(player, pet, targets);
            if (AllowCacheWrite(WriteCause::VerifiedRestore, true))
                PersistDecision(player, pet, *cycle, book);
        }

        if (cycle->needsSavetimeRefresh && !pet->isBeingLoaded() && cycle->decision.writeAllowed)
        {
            RefreshSavetime(player->GetGUID().GetCounter(), cycle->petNumber, cycle->decision);
            cycle->needsSavetimeRefresh = false;
        }

        if (cycle->order.finished || (!step.requeue && !step.snapshot && !step.apply))
        {
            cycle->finished = true;
            cycle->pending = false;
            return true;
        }

        if (step.requeue)
        {
            pet->m_Events.AddEvent(
                new HunterPetAutocastCacheEvent(_owner, _petGuid, _generation),
                pet->m_Events.CalculateTime(step.delayMs));
        }
        return true;
    }

private:
    static void TakeSnapshot(Player* player, Pet* pet, PetAutocastCacheCycle& cycle)
    {
        uint32_t const ownerLow = player->GetGUID().GetCounter();
        bool const tablePresent = CacheTablePresent();
        OwnerProof const owner = ReadOwner(ownerLow, cycle.petNumber);
        DatabaseRead cacheRead = DatabaseRead::NotRun;
        std::vector<StoredCacheRow> cache;
        if (tablePresent && owner.lookup == OwnerLookup::Unique)
            cache = ReadCache(ownerLow, cycle.petNumber, cacheRead);

        DatabaseRead petSpellRead = DatabaseRead::NotRun;
        std::vector<SourceSpell> petSpell;
        if (owner.lookup == OwnerLookup::Unique)
            petSpell = ReadPetSpell(cycle.petNumber, petSpellRead);

        cycle.decision = DecideLoad(
            tablePresent, cacheRead, cache, petSpellRead, petSpell, owner, cycle.bornThisSession, cycle.lists.utility);
        cycle.snapshotReady = true;
        if (cycle.decision.deleteStoredCache && tablePresent)
            DeleteStoredCache(ownerLow, cycle.petNumber);
        if (tablePresent && owner.lookup == OwnerLookup::Unique)
            DeleteOrphans(ownerLow);
    }

    ObjectGuid _owner;
    uint64_t _petGuid = 0;
    uint32_t _generation = 0;
};

void QueueEvent(Player* player, Pet* pet, PetAutocastCacheCycle& cycle)
{
    pet->m_Events.AddEvent(
        new HunterPetAutocastCacheEvent(player->GetGUID(), cycle.petGuid, cycle.generation),
        pet->m_Events.CalculateTime(0));
}

void QueueWatch(Player* player, Pet* pet)
{
    if (!player || !pet)
        return;

    PetAutocastCacheCycle* cycle = pet->CustomData.GetDefault<PetAutocastCacheCycle>(CycleKey);
    bool const born = cycle->bornThisSession || (!pet->isBeingLoaded() && pet->m_spells.empty());
    if (cycle->pending && cycle->petGuid == GuidRaw(pet->GetGUID()))
    {
        cycle->bornThisSession = cycle->bornThisSession || born;
        return;
    }

    uint64_t const petGuid = GuidRaw(pet->GetGUID());
    if (petGuid == 0)
        return;

    cycle->ownerGuid = GuidRaw(player->GetGUID());
    cycle->petGuid = petGuid;
    cycle->petNumber = PetNumberOf(pet);
    cycle->generation += 1u;
    cycle->pending = true;
    cycle->finished = false;
    cycle->bornThisSession = born;
    cycle->snapshotReady = false;
    cycle->suppressPlayerSave = false;
    cycle->needsSavetimeRefresh = false;
    cycle->decision = LoadDecision();
    cycle->lastWritten.clear();
    cycle->lists = ListsFromConfig();
    cycle->order = OrderState();
    QueueEvent(player, pet, *cycle);
}

void RememberBirth(Pet* pet)
{
    if (!pet || pet->isBeingLoaded() || !pet->m_spells.empty())
        return;
    PetAutocastCacheCycle* cycle = pet->CustomData.GetDefault<PetAutocastCacheCycle>(CycleKey);
    cycle->bornThisSession = true;
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
        CacheSchema.store(0, std::memory_order_release);
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
        if (!IsFeatureEnabled() || !pet || pet->getPetType() != HUNTER_PET || pet->IsDuringRemoveFromWorld())
            return;
        Player* owner = pet->GetOwner();
        if (!IsEligibleHumanHunter(owner) || OwnerLoggingOut(owner) || !owner->IsInWorld())
            return;
        QueueWatch(owner, pet);
    }

    void OnInitStatsForLevel(Guardian* guardian, uint8 /*petlevel*/) override
    {
        if (!IsFeatureEnabled() || !guardian)
            return;
        Pet* pet = guardian->ToPet();
        if (!pet || pet->getPetType() != HUNTER_PET || pet->IsDuringRemoveFromWorld())
            return;
        Player* owner = pet->GetOwner();
        if (!IsEligibleHumanHunter(owner) || OwnerLoggingOut(owner) || !owner->IsInWorld())
            return;
        RememberBirth(pet);
        QueueWatch(owner, pet);
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
        if (!MayTouchDatabase(IsFeatureEnabled()) || !IsEligibleHumanHunter(player) || !player)
            return;

        Pet* pet = player->GetPet();
        if (!pet || pet->getPetType() != HUNTER_PET || pet->isBeingLoaded() || pet->IsDuringRemoveFromWorld())
            return;

        PetAutocastCacheCycle* cycle = pet->CustomData.Get<PetAutocastCacheCycle>(CycleKey);
        if (!cycle || cycle->petGuid != GuidRaw(pet->GetGUID()) || cycle->suppressPlayerSave || !cycle->snapshotReady)
            return;
        if (cycle->petNumber == 0 || PetNumberOf(pet) != cycle->petNumber)
            return;

        bool const restoreActive = cycle->pending && !cycle->finished;
        std::vector<SourceSpell> const book = ReadBook(pet);
        bool const previousDefault = cycle->decision.allowDefaultOn;
        if (restoreActive)
        {
            std::vector<ReconcileTarget> const targets = PlanReconcile(
                cycle->decision.chains, book, cycle->lists, cycle->decision.allowDefaultOn);
            ApplyReconcile(player, pet, targets);
            if (!AllowCacheWrite(WriteCause::VerifiedRestore, true))
                return;
            PersistDecision(player, pet, *cycle, ReadBook(pet));
        }
        else
        {
            if (!AllowCacheWrite(WriteCause::PlayerSave, false) || !cycle->decision.writeAllowed)
                return;
            cycle->decision.chains = PlayerToggleRows(book, cycle->lists.utility);
            cycle->decision.allowDefaultOn = false;
            PersistDecision(player, pet, *cycle, book);
            cycle->decision.allowDefaultOn = previousDefault;
        }
        if (cycle->decision.writeAllowed)
        {
            cycle->needsSavetimeRefresh = true;
            if (!cycle->pending)
            {
                pet->m_Events.AddEvent(
                    new HunterPetAutocastCacheEvent(player->GetGUID(), cycle->petGuid, cycle->generation),
                    pet->m_Events.CalculateTime(SameUpdateGuardMs));
            }
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
            cycle->suppressPlayerSave = false;
    }
};
} // namespace

void AddHunterPetAutocastCacheScripts()
{
    new NaxxramasCoreHunterPetAutocastCacheConfig();
    new NaxxramasCoreHunterPetAutocastCachePet();
    new NaxxramasCoreHunterPetAutocastCachePlayer();
}
