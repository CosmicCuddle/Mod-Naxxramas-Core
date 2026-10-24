/*
 * Naxxramas Core — A02 S2c human Hunter pet autocast restore.
 *
 * Default OFF. While either cached flag is false both pet hooks return
 * before any pet read, config lookup, or CustomData allocation.
 *
 * Seam, inside one Pet::Update after m_loading is false (Unit.cpp:510-517,
 * Object.cpp:1074-1085): OnUnitUpdate stores a consistent chain snapshot
 * on this pet's CustomData, Individual Progression's delayed event runs
 * from m_Events, and OnWorldObjectUpdate may apply an addon opt-in onto
 * one same-chain successor. There is no process-global pet map. The
 * opt-in store is keyed by player GUID. Map threads copy one immutable
 * snapshot under that store's mutex and do not look at Playerbots.
 * The live MapUpdate.Threads value was not read and is UNKNOWN; the
 * owner states 8.
 *
 * A write requires a published addon opt-in. ClassifyOwnerOnMapThread
 * stays Uncertain and is not consulted. A listed spell the pet does not
 * have is not learned, including Cower 1742 after Individual Progression
 * removes it. When the pet still has that spell, the explicit choice is
 * applied. An unchanged book at the same opt-in generation
 * returns before FillBook and DecideChains. Protocol:
 * docs/A02-ADDON-PROTOCOL.md. In-game behaviour is NOT TESTED.
 */

#include "HunterPetAutocastAddon.h"

#include "Config.h"
#include "Pet.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SpellMgr.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <memory>
#include <string>
#include <vector>

namespace
{
    namespace Policy = NaxxramasHunterPetAutocast;

    std::atomic<bool> RestoreHumanChainEnabled{false};
    std::atomic<bool> AddonOptInEnabled{false};

    Policy::OptInStore& AddonStore()
    {
        static Policy::OptInStore store;
        return store;
    }

    uint64_t NowMs()
    {
        return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count());
    }

    Policy::SpellLookup LookupPetSpell(uint32_t spellId, void const* /*ctx*/)
    {
        Policy::SpellLookup lookup;
        SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId);
        if (!info || !info->IsAutocastable())
            return lookup;
        lookup.Autocastable = true;
        uint32_t const chain = sSpellMgr->GetFirstSpellInChain(spellId);
        lookup.ChainId = chain == 0 ? spellId : chain;
        return lookup;
    }
    // Process-lifetime key. DataMap::Get takes std::string const&
    // (DataMap.h:29). A string literal would construct a temporary on
    // every tick. This object is built once, then find() does not allocate.
    // It is not a pet dictionary.
    std::string const BaselineKey("NaxxramasCore.HunterPetAutocast.Baseline");

    struct Baseline final : DataMap::Base
    {
        std::vector<Policy::SpellView> Book;
        std::vector<Policy::SpellView> Scratch;
        bool Pending = false;
        uint64_t AppliedGeneration = 0;

        Baseline()
        {
            Book.reserve(16);
            Scratch.reserve(16);
        }
    };

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

    // Same filter and order as FillBook. Stack SpellView only: no vector,
    // no push_back, no temporary book. Used to skip FillBook and DecideChains
    // when every stored field still matches the live pet.
    bool LiveBookMatches(Pet* pet, std::vector<Policy::SpellView> const& book)
    {
        std::size_t index = 0;
        for (PetSpellMap::const_iterator itr = pet->m_spells.begin(); itr != pet->m_spells.end(); ++itr)
        {
            if (itr->second.state == PETSPELL_REMOVED)
                continue;
            if (index >= book.size())
                return false;
            if (!Policy::ViewFieldsEqual(ReadSpell(pet, itr->first), book[index]))
                return false;
            ++index;
        }
        return index == book.size();
    }

    void CopyBook(std::vector<Policy::SpellView>& dst, std::vector<Policy::SpellView> const& src)
    {
        dst.clear();
        dst.insert(dst.end(), src.begin(), src.end());
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
            bool const restore = sConfigMgr->GetOption<bool>("NaxxramasCore.HunterPetAutocast.RestoreHumanChain", false);
            bool const addon = sConfigMgr->GetOption<bool>("NaxxramasCore.HunterPetAutocast.AddonOptIn", false);
            RestoreHumanChainEnabled.store(restore, std::memory_order_release);
            AddonOptInEnabled.store(addon, std::memory_order_release);
            if (!addon)
                AddonStore().ClearAll();
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
            if (!AddonOptInEnabled.load(std::memory_order_acquire))
                return;

            Pet* pet = nullptr;
            Player* owner = nullptr;
            if (!InScope(unit, pet, owner))
                return;
            // The human check is intentionally not done on this tick.
            (void)owner;

            Baseline* state = pet->CustomData.GetDefault<Baseline>(BaselineKey);
            if (LiveBookMatches(pet, state->Book))
            {
                state->Pending = true;
                return;
            }
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
            // The addon store is a player GUID map, not a pet map.
            if (!RestoreHumanChainEnabled.load(std::memory_order_acquire))
                return;
            if (!AddonOptInEnabled.load(std::memory_order_acquire))
                return;

            if (!object)
                return;

            Pet* pet = nullptr;
            Player* owner = nullptr;
            if (!InScope(object->ToUnit(), pet, owner))
                return;

            Baseline* state = pet->CustomData.Get<Baseline>(BaselineKey);
            if (!state || !state->Pending)
                return;

            state->Pending = false;
            std::shared_ptr<Policy::PreferenceSnapshot const> optIn;
            uint64_t publishedGeneration = AddonStore().Read(owner->GetGUID().GetCounter(), optIn);
            if (LiveBookMatches(pet, state->Book) && state->AppliedGeneration == publishedGeneration)
                return;

            FillBook(pet, state->Scratch);
            // No published addon opt-in: do not toggle. The book is stored
            // so the next unchanged ticks stay on the fast path. This does
            // not call IsRealPlayer and does not read _playerbotsAIMap.
            if (!optIn)
            {
                CopyBook(state->Book, state->Scratch);
                state->AppliedGeneration = publishedGeneration;
                return;
            }

            Policy::AddonPlan plan = Policy::BuildAddonPlan(
                state->Book,
                state->Scratch,
                optIn.get(),
                publishedGeneration,
                state->AppliedGeneration);
            if (!plan.OptedIn || plan.Toggles.empty())
            {
                CopyBook(state->Book, state->Scratch);
                state->AppliedGeneration = publishedGeneration;
                return;
            }

            if (owner->GetPet() != pet)
            {
                CopyBook(state->Book, state->Scratch);
                state->AppliedGeneration = publishedGeneration;
                return;
            }

            bool claimed = false;
            for (Policy::PlannedToggle const& toggle : plan.Toggles)
            {
                SpellInfo const* info = sSpellMgr->GetSpellInfo(toggle.SpellId);
                if (!info || !info->IsAutocastable())
                    continue;

                bool const wantEnabled = toggle.Enable;
                Policy::SpellView before = ReadSpell(pet, info->Id);
                if (!before.Present)
                    continue;
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
            FillBook(pet, state->Book);
            state->AppliedGeneration = publishedGeneration;
        }
    };

    class NaxxramasHunterPetAutocastAddonScript final : public PlayerScript
    {
    public:
        NaxxramasHunterPetAutocastAddonScript()
            : PlayerScript("NaxxramasHunterPetAutocastAddonScript",
                {
                    PLAYERHOOK_ON_BEFORE_SEND_CHAT_MESSAGE,
                    PLAYERHOOK_ON_LOGIN,
                    PLAYERHOOK_ON_LOGOUT
                })
        {
        }

        void OnPlayerBeforeSendChatMessage(Player* player, uint32& type, uint32& lang, std::string& msg) override
        {
            if (!AddonOptInEnabled.load(std::memory_order_acquire))
                return;
            if (!player || type != CHAT_MSG_WHISPER || lang != LANG_ADDON)
                return;
            AddonStore().Accept(
                player->GetGUID().GetCounter(),
                player->IsClass(CLASS_HUNTER),
                msg,
                NowMs(),
                &LookupPetSpell,
                nullptr);
        }

        void OnPlayerLogin(Player* player) override
        {
            if (!player)
                return;
            AddonStore().OnLogin(player->GetGUID().GetCounter());
        }

        void OnPlayerLogout(Player* player) override
        {
            if (!player)
                return;
            AddonStore().OnLogout(player->GetGUID().GetCounter());
        }
    };
}

void AddHunterPetAutocastScripts()
{
    new NaxxramasHunterPetAutocastConfigScript();
    new NaxxramasHunterPetAutocastSnapshotScript();
    new NaxxramasHunterPetAutocastRestoreScript();
    new NaxxramasHunterPetAutocastAddonScript();
}
