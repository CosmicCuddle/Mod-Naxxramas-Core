/*
 * Naxxramas Core — A02 S2 human Hunter pet autocast restore.
 *
 * Default OFF. While the cached flag is false both hooks return before
 * any pet read, config lookup, or CustomData allocation.
 *
 * Seam, inside one Pet::Update after m_loading is false (Unit.cpp:510-517,
 * Object.cpp:1074-1085): OnUnitUpdate stores a consistent chain snapshot
 * on this pet's CustomData, Individual Progression's delayed event runs
 * from m_Events, and OnWorldObjectUpdate may copy that byte onto one
 * same-chain successor. There is no process-global pet map. Map threads
 * do not share a dictionary. The live MapUpdate.Threads value was not
 * read and is UNKNOWN; the owner states 8.
 *
 * Real humans only. IsRealPlayer runs only when a restore is about to
 * be written. Without Playerbots.h the writer stays off. Cower 1742 is
 * not learned. In-game behaviour is NOT TESTED.
 */

#include "HunterPetAutocastPolicy.h"

#include "Config.h"
#include "Pet.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SpellMgr.h"

#if __has_include("Playerbots.h")
#include "Playerbots.h"
#define NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_HAS_PLAYERBOTS 1
#else
#define NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_HAS_PLAYERBOTS 0
#endif

#include <algorithm>
#include <atomic>
#include <vector>

namespace
{
    namespace Policy = NaxxramasHunterPetAutocast;

    std::atomic<bool> RestoreHumanChainEnabled{false};
    constexpr char const* BASELINE_KEY = "NaxxramasCore.HunterPetAutocast.Baseline";

    struct Baseline final : DataMap::Base
    {
        std::vector<Policy::SpellView> Book;
        std::vector<Policy::SpellView> Scratch;
        bool Pending = false;

        Baseline()
        {
            Book.reserve(16);
            Scratch.reserve(16);
        }
    };

    // Playerbots.h present: public IsRealPlayer. Header absent: not a human.
    // The unlocked _playerbotsAIMap read stays inside that call, and only
    // the write path below reaches it.
    bool OwnerIsRealHuman(Player* owner)
    {
#if NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_HAS_PLAYERBOTS
        return IsRealPlayer(owner);
#else
        (void)owner;
        return false;
#endif
    }

    bool InScope(Unit* unit, Pet*& pet, Player*& owner)
    {
        pet = nullptr;
        owner = nullptr;
        if (!unit || !unit->IsPet())
            return false;

        pet = unit->ToPet();
        if (!pet || pet->getPetType() != HUNTER_PET || pet->isBeingLoaded())
            return false;

        owner = pet->GetOwner();
        if (!owner || !owner->IsInWorld() || !owner->IsClass(CLASS_HUNTER))
            return false;

        return true;
    }

    void FillBar(Pet* pet, Policy::SpellView& view)
    {
        view.HasBar = false;
        view.Bar = 0;
        view.BarDuplicated = false;

        CharmInfo* charm = pet->GetCharmInfo();
        if (!charm)
            return;

        uint8_t matches = 0;
        uint8_t bar = 0;
        for (uint8_t index = 0; index < MAX_UNIT_ACTION_BAR_INDEX; ++index)
        {
            UnitActionBarEntry const* entry = charm->GetActionBarEntry(index);
            if (!entry || !entry->IsActionBarForSpell() || entry->GetAction() != view.SpellId)
                continue;
            ++matches;
            bar = static_cast<uint8_t>(entry->GetType());
        }

        if (matches == 1)
        {
            view.HasBar = true;
            view.Bar = bar;
        }
        else if (matches > 1)
        {
            view.HasBar = true;
            view.Bar = bar;
            view.BarDuplicated = true;
        }
    }

    Policy::SpellView ReadSpell(Pet* pet, uint32 spellId)
    {
        Policy::SpellView view;
        view.SpellId = spellId;
        view.ChainId = sSpellMgr->GetFirstSpellInChain(spellId);

        auto itr = pet->m_spells.find(spellId);
        view.Present = itr != pet->m_spells.end() && itr->second.state != PETSPELL_REMOVED;
        if (view.Present)
            view.Active = static_cast<uint8_t>(itr->second.active);

        SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId);
        view.Autocastable = info && info->IsAutocastable();
        view.InAutospells = std::find(pet->m_autospells.begin(), pet->m_autospells.end(), spellId)
            != pet->m_autospells.end();
        FillBar(pet, view);
        return view;
    }

    void FillBook(Pet* pet, std::vector<Policy::SpellView>& book)
    {
        book.clear();
        for (PetSpellMap::const_iterator itr = pet->m_spells.begin(); itr != pet->m_spells.end(); ++itr)
        {
            if (itr->second.state == PETSPELL_REMOVED)
                continue;
            book.push_back(ReadSpell(pet, itr->first));
        }
    }

    class NaxxramasHunterPetAutocastConfigScript final : public WorldScript
    {
    public:
        NaxxramasHunterPetAutocastConfigScript()
            : WorldScript("NaxxramasHunterPetAutocastConfigScript",
                {WORLDHOOK_ON_BEFORE_CONFIG_LOAD})
        {
        }

        void OnBeforeConfigLoad(bool /*reload*/) override
        {
            RestoreHumanChainEnabled.store(
                sConfigMgr->GetOption<bool>("NaxxramasCore.HunterPetAutocast.RestoreHumanChain", false),
                std::memory_order_release);
        }
    };

    class NaxxramasHunterPetAutocastSnapshotScript final : public UnitScript
    {
    public:
        NaxxramasHunterPetAutocastSnapshotScript()
            : UnitScript("NaxxramasHunterPetAutocastSnapshotScript", true,
                {UNITHOOK_ON_UNIT_UPDATE})
        {
        }

        void OnUnitUpdate(Unit* unit, uint32 /*diff*/) override
        {
            if (!RestoreHumanChainEnabled.load(std::memory_order_acquire))
                return;

            Pet* pet = nullptr;
            Player* owner = nullptr;
            if (!InScope(unit, pet, owner))
                return;
            // The human check is intentionally not done on this tick.
            (void)owner;

            Baseline* state = pet->CustomData.GetDefault<Baseline>(BASELINE_KEY);
            FillBook(pet, state->Book);
            state->Pending = true;
        }
    };

    class NaxxramasHunterPetAutocastRestoreScript final : public WorldObjectScript
    {
    public:
        NaxxramasHunterPetAutocastRestoreScript()
            : WorldObjectScript("NaxxramasHunterPetAutocastRestoreScript",
                {WORLDOBJECTHOOK_ON_WORLD_OBJECT_UPDATE})
        {
        }

        void OnWorldObjectUpdate(WorldObject* object, uint32 /*diff*/) override
        {
            // Later OnWorldObjectUpdate subscribers are UNKNOWN. Registration
            // order is not a last-writer contract. This hook does not
            // register a second pass and does not keep a process-global map.
            if (!RestoreHumanChainEnabled.load(std::memory_order_acquire))
                return;

            if (!object)
                return;

            Pet* pet = nullptr;
            Player* owner = nullptr;
            if (!InScope(object->ToUnit(), pet, owner))
                return;

            Baseline* state = pet->CustomData.Get<Baseline>(BASELINE_KEY);
            if (!state || !state->Pending)
                return;

            state->Pending = false;
            FillBook(pet, state->Scratch);

            std::vector<Policy::ChainOutcome> outcomes = Policy::DecideChains(state->Book, state->Scratch);
            if (!Policy::WantsWrite(outcomes))
                return;

#if NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_HAS_PLAYERBOTS
            bool const apiPresent = true;
#else
            bool const apiPresent = false;
#endif
            Policy::HumanGate gate = Policy::AuthorizeRestore(
                apiPresent,
                apiPresent && OwnerIsRealHuman(owner),
                owner->GetPet() == pet);
            if (gate.Gate != Policy::WriteGate::Write)
                return;

            bool claimed = false;
            for (Policy::ChainOutcome const& outcome : outcomes)
            {
                bool const wantEnabled = outcome.Result == Policy::Outcome::RestoreEnabled;
                if (!wantEnabled && outcome.Result != Policy::Outcome::RestoreDisabled)
                    continue;
                if (outcome.BaselineSpellId == Policy::COWER_SPELL_ID
                    || outcome.SuccessorSpellId == Policy::COWER_SPELL_ID
                    || outcome.SuccessorSpellId == outcome.BaselineSpellId)
                    continue;

                SpellInfo const* info = sSpellMgr->GetSpellInfo(outcome.SuccessorSpellId);
                if (!info || !info->IsAutocastable())
                    continue;

                Policy::SpellView before = ReadSpell(pet, info->Id);
                if (!Policy::StoresAgree(before, before.Active))
                    continue;
                if ((before.Active == Policy::ACT_ENABLED) == wantEnabled)
                    continue;

                pet->ToggleAutocast(info, wantEnabled);
                if (CharmInfo* charm = pet->GetCharmInfo())
                    charm->SetSpellAutocast(info, wantEnabled);

                uint8_t const wantByte = wantEnabled ? Policy::ACT_ENABLED : Policy::ACT_DISABLED;
                Policy::SpellView after = ReadSpell(pet, info->Id);
                if (!Policy::StoresAgree(after, wantByte))
                {
                    bool const wasEnabled = before.Active == Policy::ACT_ENABLED;
                    pet->ToggleAutocast(info, wasEnabled);
                    if (CharmInfo* charm = pet->GetCharmInfo())
                        charm->SetSpellAutocast(info, wasEnabled);
                    continue;
                }

                claimed = true;
            }

            if (claimed)
                owner->PetSpellInitialize();
        }
    };
}

void AddHunterPetAutocastScripts()
{
    new NaxxramasHunterPetAutocastConfigScript();
    new NaxxramasHunterPetAutocastSnapshotScript();
    new NaxxramasHunterPetAutocastRestoreScript();
}
