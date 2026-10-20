/*
 * Naxxramas Core — hunter pet autocast cache. Default off. Module only.
 *
 * OnPetAddToWorld runs before _LoadSpells. This file does not snapshot
 * there and does not read the charm bar as the saved book. The pet event
 * waits until !isBeingLoaded(), then reads character_pet and pet_spell.
 * Cache rows are accepted only for that same character_pet life.
 *
 * The characters table is described by docs/install/manual_hunter_pet_autocast_cache.sql.
 * That file is outside data/sql. This file does not apply it.
 *
 * A null QueryResult is not an empty read. COUNT(*) distinguishes a
 * verified zero from a failed statement. CommitTransaction and
 * DirectCommitTransaction do not report success to the caller.
 * AsyncCommitTransaction's callback bool is the only success signal,
 * and lastWritten / seen_savetime change only when that bool is true.
 * That bool is not an accepted client toggle and not a dismiss barrier.
 * Functional ON/OFF persistence is not complete. No extra delay is added
 * for HandlePetSetAction, HandlePetSpellAutocastOpcode, or RemovePet.
 *
 * IsRealPlayer from PlayerbotAI.h is the human gate. The account regex
 * is second. If that header is absent, no pet is mutated.
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

#if __has_include("PlayerbotAI.h")
#include "PlayerbotAI.h"
#define NAXXRAMAS_CORE_HAS_PLAYERBOT_AI 1
#else
#define NAXXRAMAS_CORE_HAS_PLAYERBOT_AI 0
#endif

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
static_assert(!NullQueryResultIsVerifiedEmpty(), "a null QueryResult is not an empty read");
static_assert(!VoidCommitTransactionIsSuccessSignal(), "void CommitTransaction is not a success signal");
static_assert(!DirectCommitExposesErrorCode(), "DirectCommitTransaction hides the error code");
static_assert(AsyncCommitCallbackBoolIsSuccessSignal(), "the async callback bool is the success signal");
static_assert(!PacketBeforeHandlerIsAcceptedChoice(), "packet-before-handler is not an accepted choice");
static_assert(!MayApplyFromPlayerSave(), "player save does not reapply the snapshot");
static_assert(!DismissBeforeApplyPreservesChoice(), "dismiss before the apply does not preserve the choice");
static_assert(SameEntryRecycleAfterSavetimeRebindIsIndistinguishable(), "same-entry savetime rebind stays indistinguishable");
static_assert(!MissingPlayerbotApiMayMutatePet(), "a missing Playerbots header is not a human");
static_assert(!FunctionalOnOffPersistenceIsComplete(), "ON/OFF persistence is not complete");
static_assert(MaxApplies == 1u, "apply at most once");

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
    bool savetimeRefreshSubmitted = false;
    bool writeVerified = false;
    bool writeInFlight = false;
    uint32_t writeEpoch = 0;
    LoadDecision decision;
    std::map<uint32_t, bool> lastWritten;
    std::map<uint32_t, bool> lastSubmitted;
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

PlayerbotIdentity IdentityOf(Player* player)
{
#if NAXXRAMAS_CORE_HAS_PLAYERBOT_AI
    if (!player)
        return PlayerbotIdentity::Unavailable;
    if (IsRealPlayer(player))
        return PlayerbotIdentity::RealPlayer;
    if (IsSelfBot(player))
        return PlayerbotIdentity::SelfBot;
    return PlayerbotIdentity::Playerbot;
#else
    (void)player;
    return PlayerbotIdentity::Unavailable;
#endif
}

bool IsEligibleHumanHunter(Player* player)
{
    if (!player || player->getClass() != CLASS_HUNTER)
        return false;
    return MayMutateHunterPet(IdentityOf(player), ClassifyPlayer(player));
}

LivePetIdentity LiveIdentityOf(Pet* pet)
{
    LivePetIdentity live;
    if (!pet)
        return live;
    live.creatureEntry = pet->GetEntry();
    uint32_t const created = pet->GetUInt32Value(UNIT_CREATED_BY_SPELL);
    live.createdBySpell = created;
    live.createdBySpellAvailable = created != 0;
    return live;
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
    lists.restoreUtility = sConfigMgr->GetOption<bool>(RestoreUtilityKey, false);
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

SchemaProbe ProbeSchema()
{
    uint8_t const known = CacheSchema.load(std::memory_order_acquire);
    if (known == 1)
        return SchemaProbe::Present;
    if (known == 2)
        return SchemaProbe::Absent;

    QueryResult result = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = '{}' "
        "AND column_name IN ('owner_guid','pet_number','creature_entry','created_by_spell','seen_savetime','spell_first','active')",
        CacheTableName);
    uint64_t const count = result ? result->Fetch()[0].Get<uint64>() : 0;
    SchemaProbe const probe = InterpretSchemaCount(result != nullptr, count);
    if (probe == SchemaProbe::Present)
        CacheSchema.store(1, std::memory_order_release);
    else if (probe == SchemaProbe::Absent)
        CacheSchema.store(2, std::memory_order_release);
    if (probe == SchemaProbe::Unknown)
    {
        LOG_WARN("module",
            "Naxxramas Core: hunter pet autocast cache schema probe failed. "
            "No pet is changed and no new damage chain is turned on.");
    }
    else if (probe == SchemaProbe::Absent)
    {
        LOG_WARN("module",
            "Naxxramas Core: hunter pet autocast cache table is missing or is not the revised 7-column shape. "
            "Saved pet_spell bits can still be restored. New damage chains are not turned on, and nothing is written. "
            "The manual characters SQL file is not applied by this module.");
    }
    return probe;
}

OwnerProof ReadOwner(uint32_t ownerLow, uint32_t petNumber, LivePetIdentity const& live)
{
    if (ownerLow == 0 || petNumber == 0 || live.creatureEntry == 0)
        return InterpretOwnerAggregate(false, 0, 0, 0, 0, 0, live);

    QueryResult result = CharacterDatabase.Query(
        "SELECT COUNT(*), "
        "COUNT(CASE WHEN `entry` = {} THEN 1 END), "
        "COALESCE(MAX(CASE WHEN `entry` = {} THEN `CreatedBySpell` END), 0), "
        "COALESCE(MAX(CASE WHEN `entry` = {} THEN `savetime` END), 0), "
        "COALESCE(MAX(`entry`), 0) "
        "FROM `character_pet` WHERE `owner` = {} AND `id` = {}",
        live.creatureEntry, live.creatureEntry, live.creatureEntry, ownerLow, petNumber);
    if (!result)
        return InterpretOwnerAggregate(false, 0, 0, 0, 0, 0, live);

    Field* fields = result->Fetch();
    return InterpretOwnerAggregate(
        true,
        fields[0].Get<uint64>(),
        fields[1].Get<uint64>(),
        fields[2].Get<uint32>(),
        fields[3].Get<uint32>(),
        fields[4].Get<uint32>(),
        live);
}

std::vector<StoredCacheRow> ReadCache(uint32_t ownerLow, uint32_t petNumber, DatabaseRead& status)
{
    std::vector<StoredCacheRow> rows;
    status = DatabaseRead::Failed;
    if (ownerLow == 0 || petNumber == 0)
        return rows;

    QueryResult countResult = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM `{}` WHERE `owner_guid` = {} AND `pet_number` = {}",
        CacheTableName, ownerLow, petNumber);
    CountRead const counted = InterpretCountQuery(
        countResult != nullptr, countResult ? countResult->Fetch()[0].Get<uint64>() : 0);
    status = counted.status;
    if (status != DatabaseRead::Ok || counted.verifiedEmpty)
        return rows;

    QueryResult result = CharacterDatabase.Query(
        "SELECT `spell_first`, `active`, `creature_entry`, `created_by_spell`, `seen_savetime` "
        "FROM `{}` WHERE `owner_guid` = {} AND `pet_number` = {}",
        CacheTableName, ownerLow, petNumber);
    if (!result)
    {
        status = DatabaseRead::Failed;
        return rows;
    }

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

    QueryResult countResult = CharacterDatabase.Query(
        "SELECT COUNT(*) FROM `pet_spell` WHERE `guid` = {}", petNumber);
    CountRead const counted = InterpretCountQuery(
        countResult != nullptr, countResult ? countResult->Fetch()[0].Get<uint64>() : 0);
    status = counted.status;
    if (status != DatabaseRead::Ok || counted.verifiedEmpty)
        return rows;

    QueryResult result = CharacterDatabase.Query(
        "SELECT `spell`, `active` FROM `pet_spell` WHERE `guid` = {}", petNumber);
    if (!result)
    {
        status = DatabaseRead::Failed;
        return rows;
    }

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

void SubmitUnverified(Player* player, CharacterDatabaseTransaction trans)
{
    if (!player || !player->GetSession())
        return;
    player->GetSession()->AddTransactionCallback(CharacterDatabase.AsyncCommitTransaction(trans)).AfterComplete([](bool /*success*/)
    {
    });
}

void DeleteStoredCache(Player* player, uint32_t ownerLow, uint32_t petNumber)
{
    if (!player || ownerLow == 0 || petNumber == 0)
        return;
    CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
    trans->Append(
        "DELETE FROM `{}` WHERE `owner_guid` = {} AND `pet_number` = {}",
        CacheTableName, ownerLow, petNumber);
    SubmitUnverified(player, trans);
}

void DeleteOrphans(Player* player, uint32_t ownerLow)
{
    if (!player || ownerLow == 0)
        return;
    CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
    trans->Append(
        "DELETE c FROM `{}` c "
        "LEFT JOIN `character_pet` p ON p.`id` = c.`pet_number` AND p.`owner` = c.`owner_guid` "
        "WHERE c.`owner_guid` = {} AND p.`id` IS NULL",
        CacheTableName, ownerLow);
    SubmitUnverified(player, trans);
}

void QueueRefreshEvent(Pet* pet, ObjectGuid owner, PetAutocastCacheCycle& cycle);

void PersistDecision(Player* player, PetAutocastCacheCycle& cycle, std::vector<SourceSpell> const& book)
{
    if (!player || !player->GetSession() || !cycle.decision.writeAllowed)
        return;
    CacheCommit const batch = PlanCacheCommit(cycle.decision, book, cycle.lists);
    if (!batch.commit)
        return;
    if (cycle.writeVerified && batch.rows == cycle.lastWritten)
        return;
    if (cycle.writeInFlight && batch.rows == cycle.lastSubmitted)
        return;

    cycle.lastSubmitted = batch.rows;
    cycle.writeInFlight = true;
    cycle.writeVerified = false;
    uint32_t const epoch = ++cycle.writeEpoch;
    uint32_t const ownerLow = player->GetGUID().GetCounter();
    uint32_t const petNumber = cycle.petNumber;
    LoadDecision const decision = cycle.decision;
    std::map<uint32_t, bool> const rows = batch.rows;
    ObjectGuid const owner = player->GetGUID();
    uint64_t const petGuid = cycle.petGuid;
    uint32_t const generation = cycle.generation;

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

    player->GetSession()->AddTransactionCallback(CharacterDatabase.AsyncCommitTransaction(trans)).AfterComplete(
        [owner, petGuid, generation, epoch, rows](bool success)
        {
            Player* found = ObjectAccessor::FindPlayer(owner);
            Pet* livePet = found ? found->GetPet() : nullptr;
            if (!livePet || GuidRaw(livePet->GetGUID()) != petGuid)
                return;
            PetAutocastCacheCycle* live = livePet->CustomData.Get<PetAutocastCacheCycle>(CycleKey);
            if (!live || live->generation != generation || live->writeEpoch != epoch)
                return;
            live->writeInFlight = false;
            if (!MarkWriteVerified(true, success))
                return;
            live->lastWritten = rows;
            live->writeVerified = true;
            live->needsSavetimeRefresh = true;
            live->savetimeRefreshSubmitted = false;
            if (!live->pending)
                QueueRefreshEvent(livePet, owner, *live);
        });
}

void SubmitSavetimeRefresh(Player* player, Pet* pet, PetAutocastCacheCycle& cycle)
{
    if (!player || !pet || !player->GetSession() || cycle.savetimeRefreshSubmitted || !cycle.decision.writeAllowed)
        return;

    uint32_t const ownerLow = player->GetGUID().GetCounter();
    OwnerProof const proof = ReadOwner(ownerLow, cycle.petNumber, LiveIdentityOf(pet));
    cycle.savetimeRefreshSubmitted = true;
    if (proof.lookup != OwnerLookup::Unique || !proof.liveBound)
        return;
    if (proof.creatureEntry != cycle.decision.creatureEntry || proof.createdBySpell != cycle.decision.createdBySpell)
        return;

    uint32_t const newSavetime = proof.savetime;
    ObjectGuid const owner = player->GetGUID();
    uint64_t const petGuid = cycle.petGuid;
    uint32_t const generation = cycle.generation;
    uint32_t const petNumber = cycle.petNumber;
    uint32_t const creatureEntry = cycle.decision.creatureEntry;
    uint32_t const createdBySpell = cycle.decision.createdBySpell;

    CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
    trans->Append(
        "UPDATE `{}` SET `seen_savetime` = {} "
        "WHERE `owner_guid` = {} AND `pet_number` = {} AND `creature_entry` = {} AND `created_by_spell` = {}",
        CacheTableName, newSavetime, ownerLow, petNumber, creatureEntry, createdBySpell);
    player->GetSession()->AddTransactionCallback(CharacterDatabase.AsyncCommitTransaction(trans)).AfterComplete(
        [owner, petGuid, generation, newSavetime](bool success)
        {
            if (!MarkSavetimeRebound(true, success))
                return;
            Player* found = ObjectAccessor::FindPlayer(owner);
            Pet* livePet = found ? found->GetPet() : nullptr;
            if (!livePet || GuidRaw(livePet->GetGUID()) != petGuid)
                return;
            PetAutocastCacheCycle* live = livePet->CustomData.Get<PetAutocastCacheCycle>(CycleKey);
            if (!live || live->generation != generation)
                return;
            live->decision.seenSavetime = newSavetime;
            live->needsSavetimeRefresh = false;
        });
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
                SubmitSavetimeRefresh(player, pet, *cycle);
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

        if (step.apply && cycle->snapshotReady && cycle->order.applies == MaxApplies)
        {
            std::vector<SourceSpell> const book = ReadBook(pet);
            std::vector<ReconcileTarget> const targets = PlanReconcile(
                cycle->decision.chains, book, cycle->lists, cycle->decision.allowDefaultOn);
            ApplyReconcile(player, pet, targets);
            if (AllowCacheWrite(WriteCause::VerifiedRestore, true))
                PersistDecision(player, *cycle, book);
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
        SchemaProbe const probe = ProbeSchema();
        if (probe == SchemaProbe::Unknown)
        {
            cycle.decision = LoadDecision();
            cycle.snapshotReady = true;
            return;
        }

        LivePetIdentity const live = LiveIdentityOf(pet);
        OwnerProof const owner = ReadOwner(ownerLow, cycle.petNumber, live);
        bool const ownerBound = owner.lookup == OwnerLookup::Unique && owner.liveBound;
        DatabaseRead cacheRead = DatabaseRead::NotRun;
        std::vector<StoredCacheRow> cache;
        if (probe == SchemaProbe::Present && ownerBound)
            cache = ReadCache(ownerLow, cycle.petNumber, cacheRead);

        DatabaseRead petSpellRead = DatabaseRead::NotRun;
        std::vector<SourceSpell> petSpell;
        bool const cacheFailed = probe == SchemaProbe::Present && cacheRead != DatabaseRead::Ok;
        if (ownerBound && !cacheFailed)
            petSpell = ReadPetSpell(cycle.petNumber, petSpellRead);

        cycle.decision = DecideLoad(
            probe, cacheRead, cache, petSpellRead, petSpell, owner, cycle.bornThisSession,
            cycle.lists.utility, cycle.lists.restoreUtility);
        cycle.snapshotReady = true;
        if (probe == SchemaProbe::Present && owner.lookup == OwnerLookup::Absent)
            DeleteStoredCache(player, ownerLow, cycle.petNumber);
        else if (cycle.decision.deleteStoredCache && probe == SchemaProbe::Present)
            DeleteStoredCache(player, ownerLow, cycle.petNumber);
        if (probe == SchemaProbe::Present && ownerBound)
            DeleteOrphans(player, ownerLow);
    }

    ObjectGuid _owner;
    uint64_t _petGuid = 0;
    uint32_t _generation = 0;
};

void QueueRefreshEvent(Pet* pet, ObjectGuid owner, PetAutocastCacheCycle& cycle)
{
    if (!pet)
        return;
    pet->m_Events.AddEvent(
        new HunterPetAutocastCacheEvent(owner, cycle.petGuid, cycle.generation),
        pet->m_Events.CalculateTime(SameUpdateGuardMs));
}

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
    cycle->savetimeRefreshSubmitted = false;
    cycle->writeVerified = false;
    cycle->writeInFlight = false;
    cycle->writeEpoch = 0;
    cycle->decision = LoadDecision();
    cycle->lastWritten.clear();
    cycle->lastSubmitted.clear();
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
#if !NAXXRAMAS_CORE_HAS_PLAYERBOT_AI
        LOG_WARN("module",
            "Naxxramas Core: hunter pet autocast cache cannot see PlayerbotAI.h. "
            "No pet is changed. A missing bot API is not treated as a human.");
#endif
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
        if (!MayTouchDatabase(IsFeatureEnabled()) || !player || !IsEligibleHumanHunter(player))
            return;

        Pet* pet = player->GetPet();
        if (!pet || pet->getPetType() != HUNTER_PET || pet->isBeingLoaded() || pet->IsDuringRemoveFromWorld())
            return;

        PetAutocastCacheCycle* cycle = pet->CustomData.Get<PetAutocastCacheCycle>(CycleKey);
        if (!cycle || cycle->petGuid != GuidRaw(pet->GetGUID()) || cycle->suppressPlayerSave || !cycle->snapshotReady)
            return;
        if (cycle->petNumber == 0 || PetNumberOf(pet) != cycle->petNumber)
            return;
        if (!MayPersistChoiceBeforeSingleApply(cycle->order.applies))
            return;
        if (!AllowCacheWrite(WriteCause::PlayerSave, false) || !cycle->decision.writeAllowed)
            return;

        bool const previousDefault = cycle->decision.allowDefaultOn;
        std::vector<SourceSpell> const book = ReadBook(pet);
        cycle->decision.chains = PlayerToggleRows(book, cycle->lists.utility, cycle->lists.restoreUtility);
        cycle->decision.allowDefaultOn = false;
        PersistDecision(player, *cycle, book);
        cycle->decision.allowDefaultOn = previousDefault;
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
