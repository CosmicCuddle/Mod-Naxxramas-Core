/*
 * Naxxramas Core — save and restore human hunter pet autocast across
 * Individual Progression rank swaps.
 *
 * IP unlearns the old rank and learnSpell's the new one. The new rank is
 * already autocast OFF; ToggleAutocast(false) does not write that byte.
 * This file turns the new rank ON when the previous rank of that chain was
 * ON. Events are queued on the pet, and Pet::Update does not run them while
 * the pet is still loading. Default OFF. No SQL.
 */

#include "HunterPetAutocastRestore.h"

#include "AccountMgr.h"
#include "Config.h"
#include "DataMap.h"
#include "EventProcessor.h"
#include "ObjectAccessor.h"
#include "Pet.h"
#include "PetPackets.h"
#include "PetScript.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ServerScript.h"
#include "SharedDefines.h"
#include "SpellMgr.h"
#include "WorldSession.h"

#include <string>
#include <unordered_map>
#include <utility>

namespace
{
using namespace NaxxramasCore::HunterPetAutocastRestore;

bool FeatureEnabled = false;
uint64_t PreferenceSequence = 1;

char const* PendingKey = "naxx_a02_hunter_pet_autocast_restore";

class PendingAutocastRestore : public DataMap::Base
{
public:
    bool pending = false;
};

struct MemoryKey
{
    uint64_t playerLow = 0;
    uint32_t petNumber = 0;

    bool operator==(MemoryKey const& other) const
    {
        return playerLow == other.playerLow && petNumber == other.petNumber;
    }
};

struct MemoryKeyHash
{
    std::size_t operator()(MemoryKey const& key) const
    {
        return std::hash<uint64_t>()(key.playerLow) ^ (std::hash<uint32_t>()(key.petNumber) << 1);
    }
};

struct PetMemory
{
    uint32_t petNumber = 0;
    bool snapshotCommitted = false;
    std::map<uint32_t, Preference> snapshot;
    std::map<uint32_t, Preference> packet;
};

std::unordered_map<MemoryKey, PetMemory, MemoryKeyHash> PetMemories;

bool IsBotAccount(Player* player)
{
    if (!player || !player->GetSession())
        return false;

    std::string accountName;
    bool const found = AccountMgr::GetName(player->GetSession()->GetAccountId(), accountName);
    std::string const pattern = sConfigMgr->GetOption<std::string>(BotAccountsRegexKey, DefaultBotAccountsRegex);
    return AccountIsBot(found, accountName.c_str(), pattern.c_str());
}

bool IsHumanHunter(Player* player)
{
    return player && player->getClass() == CLASS_HUNTER && !IsBotAccount(player);
}

uint32_t PetNumberOf(Pet* pet)
{
    if (!pet || !pet->GetCharmInfo())
        return 0;
    return pet->GetCharmInfo()->GetPetNumber();
}

uint64_t PlayerLow(Player* player)
{
    return player ? static_cast<uint64_t>(player->GetGUID().GetCounter()) : 0;
}

PetMemory* FindMemory(Player* player, uint32_t petNumber)
{
    if (!player || petNumber == 0)
        return nullptr;

    auto found = PetMemories.find(MemoryKey{ PlayerLow(player), petNumber });
    if (found == PetMemories.end())
        return nullptr;
    return &found->second;
}

PetMemory& BeginCycle(Player* player, uint32_t petNumber)
{
    PetMemory& memory = PetMemories[MemoryKey{ PlayerLow(player), petNumber }];
    memory.petNumber = petNumber;
    memory.snapshot.clear();
    memory.snapshotCommitted = false;
    return memory;
}

void ForgetPlayer(Player* player)
{
    if (!player)
        return;

    uint64_t const low = PlayerLow(player);
    for (auto it = PetMemories.begin(); it != PetMemories.end();)
    {
        if (it->first.playerLow == low)
            it = PetMemories.erase(it);
        else
            ++it;
    }
}

std::vector<BookSpell> ReadBook(Pet* pet)
{
    std::vector<BookSpell> book;
    if (!pet)
        return book;

    for (auto const& entry : pet->m_spells)
    {
        SpellInfo const* info = sSpellMgr->GetSpellInfo(entry.first);
        if (!info)
            continue;

        SpellInfo const* first = info->GetFirstRankSpell();
        BookSpell spell;
        spell.id = entry.first;
        spell.chainFirst = first ? first->Id : entry.first;
        spell.autocastable = info->IsAutocastable();
        spell.removed = entry.second.state == PETSPELL_REMOVED;
        spell.autocastOn = entry.second.active == ACT_ENABLED;
        book.push_back(spell);
    }
    return book;
}

void ApplyRestores(Player* player, Pet* pet, std::vector<ChainRestore> const& plans, PetMemory& memory)
{
    bool any = false;
    for (ChainRestore const& plan : plans)
    {
        if (!plan.apply || !plan.desiredOn || !pet->HasSpell(plan.newSpellId))
            continue;

        SpellInfo const* current = sSpellMgr->GetSpellInfo(plan.newSpellId);
        if (!current || !current->IsAutocastable())
            continue;

        pet->ToggleAutocast(current, true);
        if (CharmInfo* charm = pet->GetCharmInfo())
            charm->SetSpellAutocast(current, true);

        NoteRestored(memory.snapshot, memory.packet, plan, ++PreferenceSequence);
        any = true;
    }

    if (any)
        player->PetSpellInitialize();
}

void RestorePet(Player* player, Pet* pet)
{
    uint32_t const petNumber = PetNumberOf(pet);
    PetMemory* memory = FindMemory(player, petNumber);
    if (!memory)
        return;

    bool const allowRemovedFallback = !memory->snapshotCommitted;
    ApplyRestores(
        player,
        pet,
        PlanRestores(ReadBook(pet), memory->snapshot, memory->packet, allowRemovedFallback),
        *memory);
}

void ClearPending(Pet* pet)
{
    if (!pet)
        return;
    if (PendingAutocastRestore* pending = pet->CustomData.Get<PendingAutocastRestore>(PendingKey))
        pending->pending = false;
}

class HunterPetAutocastEvent : public BasicEvent
{
public:
    HunterPetAutocastEvent(ObjectGuid owner, uint32_t petNumber, uint32_t offsetMs, bool restorePhase)
        : _owner(owner), _petNumber(petNumber), _offsetMs(offsetMs), _restorePhase(restorePhase)
    {
    }

    bool Execute(uint64 /*eventTime*/, uint32 /*delta*/) override
    {
        if (!FeatureEnabled)
        {
            if (Player* player = ObjectAccessor::FindPlayer(_owner))
                if (Pet* pet = player->GetPet())
                    if (PetNumberMatches(_petNumber, PetNumberOf(pet)))
                        ClearPending(pet);
            return true;
        }

        Player* player = ObjectAccessor::FindPlayer(_owner);
        if (!IsHumanHunter(player))
            return true;

        Pet* pet = player->GetPet();
        if (!pet || pet->getPetType() != HUNTER_PET || !PetNumberMatches(_petNumber, PetNumberOf(pet)))
            return true;

        if (_restorePhase)
        {
            RestorePet(player, pet);
            ClearPending(pet);
            return true;
        }

        PollDecision const decision = DecideSnapshotPoll(_offsetMs, !pet->isBeingLoaded());
        if (decision.action == PollAction::DeferBeforeIp)
        {
            if (decision.rescheduleMs == 0u || _offsetMs >= LastIpOpportunityMs())
            {
                ClearPending(pet);
                return true;
            }

            pet->m_Events.AddEvent(
                new HunterPetAutocastEvent(_owner, _petNumber, _offsetMs + decision.rescheduleMs, false),
                pet->m_Events.CalculateTime(decision.rescheduleMs));
            return true;
        }

        if (decision.action == PollAction::GiveUp)
        {
            ClearPending(pet);
            return true;
        }

        if (decision.action == PollAction::CommitSnapshot)
        {
            PetMemory& memory = BeginCycle(player, _petNumber);
            memory.snapshot = SnapshotChains(ReadBook(pet), ++PreferenceSequence);
            memory.snapshotCommitted = true;
        }

        if (decision.rescheduleMs == 0u)
        {
            ClearPending(pet);
            return true;
        }

        pet->m_Events.AddEvent(
            new HunterPetAutocastEvent(_owner, _petNumber, _offsetMs + decision.rescheduleMs, true),
            pet->m_Events.CalculateTime(decision.rescheduleMs));
        return true;
    }

private:
    ObjectGuid _owner;
    uint32_t _petNumber = 0;
    uint32_t _offsetMs = 0;
    bool _restorePhase = false;
};

void Schedule(Pet* pet)
{
    if (!FeatureEnabled || !pet || pet->getPetType() != HUNTER_PET)
        return;

    Player* owner = pet->GetOwner();
    if (!IsHumanHunter(owner))
        return;

    uint32_t const petNumber = PetNumberOf(pet);
    if (petNumber == 0)
        return;

    PendingAutocastRestore* pending = pet->CustomData.GetDefault<PendingAutocastRestore>(PendingKey);
    if (pending->pending)
        return;

    pending->pending = true;
    BeginCycle(owner, petNumber);
    pet->m_Events.AddEvent(
        new HunterPetAutocastEvent(owner->GetGUID(), petNumber, FirstPollDelayMs(), false),
        pet->m_Events.CalculateTime(FirstPollDelayMs()));
}

class NaxxramasCoreHunterPetAutocastConfig : public WorldScript
{
public:
    NaxxramasCoreHunterPetAutocastConfig()
        : WorldScript("NaxxramasCoreHunterPetAutocastConfig", { WORLDHOOK_ON_BEFORE_CONFIG_LOAD })
    {
    }

    void OnBeforeConfigLoad(bool /*reload*/) override
    {
        FeatureEnabled = sConfigMgr->GetOption<bool>(EnabledConfigKey, false);
    }
};

class NaxxramasCoreHunterPetAutocastPet : public PetScript
{
public:
    NaxxramasCoreHunterPetAutocastPet()
        : PetScript(
            "NaxxramasCoreHunterPetAutocastPet",
            { PETHOOK_ON_PET_ADD_TO_WORLD, PETHOOK_ON_INIT_STATS_FOR_LEVEL })
    {
    }

    void OnPetAddToWorld(Pet* pet) override
    {
        Schedule(pet);
    }

    void OnInitStatsForLevel(Guardian* guardian, uint8 /*petlevel*/) override
    {
        if (!guardian)
            return;
        Schedule(guardian->ToPet());
    }
};

class NaxxramasCoreHunterPetAutocastPackets : public ServerScript
{
public:
    NaxxramasCoreHunterPetAutocastPackets()
        : ServerScript("NaxxramasCoreHunterPetAutocastPackets", { SERVERHOOK_CAN_PACKET_RECEIVE })
    {
    }

    /* The design name OnPacketReceive is CanPacketReceive at both pinned cores. */
    bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override
    {
        if (!FeatureEnabled || !session || packet.GetOpcode() != CMSG_PET_SPELL_AUTOCAST)
            return true;

        try
        {
            WorldPacket clone(packet);
            WorldPackets::Pet::PetSpellAutocast parsed(std::move(clone));
            parsed.Read();

            Player* player = session->GetPlayer();
            if (!IsHumanHunter(player))
                return true;

            Pet* pet = player->GetPet();
            if (!pet || pet->getPetType() != HUNTER_PET || pet->GetGUID() != parsed.PetGUID)
                return true;

            SpellInfo const* info = sSpellMgr->GetSpellInfo(parsed.SpellID);
            if (!info || !info->IsAutocastable())
                return true;

            SpellInfo const* first = info->GetFirstRankSpell();
            uint32_t const chain = first ? first->Id : info->Id;
            uint32_t const petNumber = PetNumberOf(pet);
            if (chain == 0 || petNumber == 0)
                return true;

            Preference preference;
            preference.spellId = parsed.SpellID;
            preference.autocastOn = parsed.AutocastEnabled;
            preference.present = true;
            preference.sequence = ++PreferenceSequence;
            PetMemories[MemoryKey{ PlayerLow(player), petNumber }].packet[chain] = preference;
        }
        catch (ByteBufferException const&)
        {
        }

        return true;
    }
};

class NaxxramasCoreHunterPetAutocastPlayer : public PlayerScript
{
public:
    NaxxramasCoreHunterPetAutocastPlayer()
        : PlayerScript("NaxxramasCoreHunterPetAutocastPlayer", { PLAYERHOOK_ON_BEFORE_LOGOUT })
    {
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        ForgetPlayer(player);
    }
};
} // namespace

void AddHunterPetAutocastRestoreScripts()
{
    new NaxxramasCoreHunterPetAutocastConfig();
    new NaxxramasCoreHunterPetAutocastPet();
    new NaxxramasCoreHunterPetAutocastPackets();
    new NaxxramasCoreHunterPetAutocastPlayer();
}
