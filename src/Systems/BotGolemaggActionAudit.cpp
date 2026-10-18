/*
 * Naxxramas Core — experimental, READ-ONLY Golemagg Playerbot action probe.
 *
 * This is NOT the Golemagg melee guard. No Engine listeners, bot movement,
 * strategies, combat actions, SQL, packet injection or spell mutation.
 * Requires explicit operator choice to enable and compile/install later.
 */
#include "AiObjectContext.h"
#include "Config.h"
#include "GolemaggActionAuditAllowlist.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SpellAuras.h"

#include <algorithm>
#include <cstdint>
#include <string>
#include <unordered_map>

namespace
{
    constexpr uint32 MOLTEN_CORE_MAP = 409;
    constexpr uint32 MAGMA_SPLASH_SPELL = 13880;
    constexpr uint32 SAMPLE_INTERVAL_MS = 2500;
    constexpr uint8 MAX_SAMPLES_PER_BOT = 24;
    constexpr size_t MAX_ACTION_TEXT = 320;

    struct SampleState
    {
        uint32 elapsedMs = 0;
        uint8 samples = 0;
        std::string lastTrace;
    };

    class NaxxramasCoreGolemaggActionAudit final : public PlayerScript
    {
    public:
        NaxxramasCoreGolemaggActionAudit()
            : PlayerScript("NaxxramasCoreGolemaggActionAudit",
                { PLAYERHOOK_ON_UPDATE, PLAYERHOOK_ON_LOGOUT })
        {
        }

        void OnPlayerUpdate(Player* player, uint32 diff) override
        {
            // A constant and safe default. Config changes require a restart;
            // no per-tick config queries on a disabled feature.
            static bool const enabled = sConfigMgr->GetOption<bool>(
                "NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled", false);
            if (!enabled || !player)
                return;

            // SECOND independent opt-in: a single exact Altbot character
            // name is required even after Enabled has been explicitly set.
            static std::string const allowedBot = sConfigMgr->GetOption<std::string>(
                "NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName", "");
            if (!NaxxramasGolemaggActionAudit::IsAllowedBotName(player->GetName(), allowedBot))
                return;

            ObjectGuid::LowType const guid = player->GetGUID().GetCounter();
            if (player->GetMapId() != MOLTEN_CORE_MAP ||
                !player->IsAlive() || !player->IsInCombat())
            {
                _samples.erase(guid);
                return;
            }

            PlayerbotAI* ai = PlayerbotsMgr::instance().GetPlayerbotAI(player);
            if (!ai || !ai->IsAltBot() ||
                PlayerbotAI::IsTank(player) || !PlayerbotAI::IsDps(player) ||
                !PlayerbotAI::IsMelee(player))
            {
                _samples.erase(guid);
                return;
            }

            SampleState& state = _samples[guid];
            if (state.samples >= MAX_SAMPLES_PER_BOT)
                return;

            state.elapsedMs += std::min(diff, SAMPLE_INTERVAL_MS);
            if (state.elapsedMs < SAMPLE_INTERVAL_MS)
                return;
            state.elapsedMs = 0;

            // Public Playerbots context lookup, used by its own MC triggers.
            // Never access PlayerbotAI::currentEngine or register a listener.
            AiObjectContext* context = ai->GetAiObjectContext();
            auto* found = context ? context->GetValue<Unit*>(
                "find target", "golemagg the incinerator") : nullptr;
            Unit* boss = found ? found->Get() : nullptr;
            if (!boss || !boss->IsAlive() ||
                boss->GetMapId() != MOLTEN_CORE_MAP)
            {
                // Keep the per-combat sample budget during temporary boss
                // lookup/target loss. Erasing it here lets the same bot
                // replenish 24 log lines repeatedly as the context flickers.
                // Only combat exit, death, map exit, role loss or logout
                // resets the budget. This performs NO movement mutation.
                return;
            }

            // This public branch returns a RECENT action-log tail (not one
            // guaranteed action/event). It does not Execute an AI action.
            std::string trace = ai->HandleRemoteCommand("action");
            if (trace.empty() || trace == state.lastTrace)
                return;

            state.lastTrace = trace;
            if (trace.size() > MAX_ACTION_TEXT)
                trace.erase(0, trace.size() - MAX_ACTION_TEXT);
            std::replace(trace.begin(), trace.end(), '\n', ' ');
            std::replace(trace.begin(), trace.end(), '\r', ' ');

            Aura* splash = player->GetAura(MAGMA_SPLASH_SPELL);
            uint32 const stacks = splash ? splash->GetStackAmount() : 0;
            int32 const remainingMs = splash ? splash->GetDuration() : 0;
            std::string target = ai->HandleRemoteCommand("target");
            if (target.size() > 64)
                target.resize(64);
            std::replace(target.begin(), target.end(), '\n', ' ');
            std::replace(target.begin(), target.end(), '\r', ' ');

            // One sample at most every 2.5 seconds and 24 reports per bot.
            // Do not draw movement-causality conclusions from this alone.
            ++state.samples;
            LOG_INFO("module",
                "GolemaggActionAudit READ ONLY: bot={} samples={}/{} "
                "splash_stacks={} splash_remaining_ms={} boss_hp_pct={} "
                "boss_distance_yards={} current_target={} recent_actions={}",
                player->GetName(), static_cast<uint32>(state.samples),
                static_cast<uint32>(MAX_SAMPLES_PER_BOT),
                stacks, remainingMs, boss->GetHealthPct(),
                player->GetDistance2d(boss), target, trace);
        }

        void OnPlayerLogout(Player* player) override
        {
            if (player)
                _samples.erase(player->GetGUID().GetCounter());
        }

    private:
        std::unordered_map<ObjectGuid::LowType, SampleState> _samples;
    };
}

void AddBotGolemaggActionAuditScripts()
{
    new NaxxramasCoreGolemaggActionAudit();
}
