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
#include "GolemaggActionAuditTrace.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SpellAuras.h"

#include <algorithm>
#include <cstdint>
#include <string>

namespace
{
    constexpr uint32 MOLTEN_CORE_MAP = 409;
    constexpr uint32 MAGMA_SPLASH_SPELL = 13880;
    // From exact pinned Playerbots MCHelpers.h; context, NOT a movement veto.
    constexpr uint32 MAGMA_SPLASH_RETREAT_STACKS = 20;
    constexpr uint32 AUDIT_WARMUP_START_STACKS = 15;
    constexpr uint8 MAX_PRE_RETREAT_SAMPLES = 4;
    constexpr float MAGMA_SPLASH_RETREAT_YARDS = 12.0f;
    constexpr uint32 SAMPLE_INTERVAL_MS = 2500;
    constexpr uint8 MAX_SAMPLES_PER_BOT = 24;
    constexpr size_t MAX_ACTION_TEXT = 320;
    constexpr char const* AUDIT_STATE_KEY = "NaxxramasCore.GolemaggActionAudit.BotState";

    // State belongs to each Player object; never share one mutable map
    // between concurrently ticking Worldserver map threads.
    struct SampleState final : DataMap::Base
    {
        uint32 elapsedMs = 0;
        uint8 samples = 0;
        uint8 preRetreatSamples = 0;
        std::string lastTrace;
        bool sawGolemaggInThisCombat = false;
        bool lastLookupPresent = false;
        // Bounded threshold telemetry. Store no pointers, GUIDs or action mutators.
        bool hasLastSample = false;
        bool lastAtRetreatStacks = false;
        bool lastInsideRetreatDistance = false;
    };

    struct AuditConfig
    {
        bool enabled = false;
        std::string allowedBot;
    };

    // Only called from the config hook below, on the world thread.
    AuditConfig ReadAuditConfig()
    {
        AuditConfig loaded;
        loaded.enabled = sConfigMgr->GetOption<bool>(
            "NaxxramasCore.Playerbots.GolemaggActionAudit.Enabled", false);
        loaded.allowedBot = sConfigMgr->GetOption<std::string>(
            "NaxxramasCore.Playerbots.GolemaggActionAudit.AllowedBotName", "");
        return loaded;
    }

    // Written only by the startup config load, which runs in
    // World::SetInitialWorldSettings before MapMgr starts any map worker.
    // Never written again, so map threads read it without a lock and never
    // call ConfigMgr. Until it is written, the observer is OFF.
    AuditConfig StartupAuditConfig;

    // Takes the settings snapshot. World::LoadConfigSettings calls this hook
    // on the world thread: at startup before any map worker exists, and for
    // ".reload config" while no map worker runs. A reload keeps the startup
    // values (restart-only) and warns if they changed.
    class NaxxramasCoreGolemaggActionAuditConfig final : public WorldScript
    {
    public:
        NaxxramasCoreGolemaggActionAuditConfig()
            : WorldScript("NaxxramasCoreGolemaggActionAuditConfig", { WORLDHOOK_ON_AFTER_CONFIG_LOAD })
        {
        }

        void OnAfterConfigLoad(bool reload) override
        {
            AuditConfig const loaded = ReadAuditConfig();
            if (!reload)
            {
                StartupAuditConfig = loaded;
                return;
            }

            if (loaded.enabled != StartupAuditConfig.enabled ||
                loaded.allowedBot != StartupAuditConfig.allowedBot)
                LOG_WARN("module",
                    "GolemaggActionAudit: settings changed by .reload config are ignored until "
                    "Worldserver restarts; still Enabled={} AllowedBotName='{}'.",
                    StartupAuditConfig.enabled, StartupAuditConfig.allowedBot);
        }
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
            // Startup snapshot only: no ConfigMgr access on a map thread.
            // Config changes require a restart.
            AuditConfig const& config = StartupAuditConfig;
            if (!config.enabled || !player)
                return;

            // SECOND independent opt-in: a single exact Altbot character
            // name is required even after Enabled has been explicitly set.
            std::string const& allowedBot = config.allowedBot;
            if (!NaxxramasGolemaggActionAudit::IsAllowedBotName(player->GetName(), allowedBot))
                return;

            if (player->GetMapId() != MOLTEN_CORE_MAP ||
                !player->IsAlive() || !player->IsInCombat())
            {
                player->CustomData.Erase(AUDIT_STATE_KEY);
                return;
            }

            PlayerbotAI* ai = PlayerbotsMgr::instance().GetPlayerbotAI(player);
            if (!ai || !ai->IsAltBot() ||
                PlayerbotAI::IsTank(player) || !PlayerbotAI::IsDps(player) ||
                !PlayerbotAI::IsMelee(player))
            {
                player->CustomData.Erase(AUDIT_STATE_KEY);
                return;
            }

            SampleState* state = player->CustomData.GetDefault<SampleState>(AUDIT_STATE_KEY);
            if (state->samples >= MAX_SAMPLES_PER_BOT)
                return;

            state->elapsedMs += std::min(diff, SAMPLE_INTERVAL_MS);
            if (state->elapsedMs < SAMPLE_INTERVAL_MS)
                return;
            state->elapsedMs = 0;

            // Public Playerbots context lookup, used by its own MC triggers.
            // Never access PlayerbotAI::currentEngine or register a listener.
            AiObjectContext* context = ai->GetAiObjectContext();
            auto* found = context ? context->GetValue<Unit*>(
                "find target", "golemagg the incinerator") : nullptr;
            Unit* boss = found ? found->Get() : nullptr;

            // Pinned FindTargetValue only searches this bot's own threat list.
            // A temporary threat lookup miss can coincide with the suspected
            // retreat/return movement. Capture the recent action tail in that
            // case ONLY after this same Player has observed a living Golemagg
            // during its current eligible combat window. Never retain a
            // potentially stale Unit* or begin sampling other MC encounters.
            if (boss && (!boss->IsAlive() ||
                boss->GetMapId() != MOLTEN_CORE_MAP))
            {
                player->CustomData.Erase(AUDIT_STATE_KEY);
                return;
            }

            bool const lookupPresent = boss != nullptr;
            if (lookupPresent)
                state->sawGolemaggInThisCombat = true;

            if (!state->sawGolemaggInThisCombat)
                return;

            // This public branch returns a RECENT action-log tail (not one
            // guaranteed action/event). It does not Execute an AI action.
            // Sample BOTH the recent action tail and the pinned Magma Splash
            // retreat thresholds. A repeated action tail must not mask a
            // transition across 20 stacks or 12 yards; those transitions
            // are essential to distinguishing expected retreat from an
            // unrelated pursuit action. This remains a 2.5s, 24-line probe.
            Aura* splash = player->GetAura(MAGMA_SPLASH_SPELL);
            uint32 const stacks = splash ? splash->GetStackAmount() : 0;
            int32 const remainingMs = splash ? splash->GetDuration() : 0;
            float const bossDistanceYards =
                lookupPresent ? player->GetDistance2d(boss) : -1.0f;
            bool const atRetreatStacks = stacks >= MAGMA_SPLASH_RETREAT_STACKS;
            bool const insideRetreatDistance =
                lookupPresent && bossDistanceYards < MAGMA_SPLASH_RETREAT_YARDS;
            // -1 = unknown (boss threat lookup absent), not "out of melee".
            // This is a range predicate, NOT measured melee attack uptime.
            int32 const bossInMeleeRange = lookupPresent ?
                (player->IsWithinMeleeRange(boss) ? 1 : 0) : -1;
            bool const thresholdChanged = !state->hasLastSample ||
                atRetreatStacks != state->lastAtRetreatStacks ||
                insideRetreatDistance != state->lastInsideRetreatDistance;

            // Preserve most of the 24-line budget for >=20 stacks. Below
            // 15 stacks, capture only a single high-to-low transition; at
            // 15-19 stacks, at most four ordinary warm-up records. The
            // existing per-combat total cap always applies.
            bool const wasAtRetreatStacks =
                state->hasLastSample && state->lastAtRetreatStacks;
            if (stacks < AUDIT_WARMUP_START_STACKS && !wasAtRetreatStacks)
                return;
            if (!atRetreatStacks &&
                state->preRetreatSamples >= MAX_PRE_RETREAT_SAMPLES &&
                !wasAtRetreatStacks)
                return;

            // Playerbots returns a RECENT action-log tail, NOT the exact
            // action responsible for this movement. Never execute an action.
            std::string trace = ai->HandleRemoteCommand("action");
            // An empty recent-action history does NOT mean the Magma Splash
            // or boss-lookup observations are empty. Use an explicit bounded
            // missing-history marker so threshold transitions are still
            // reported, but repeated identical samples remain suppressed.
            // This text is an observation sentinel, NOT a bot action.
            if (trace.empty())
                trace = "(no recent action)";
            // Bound and normalise BEFORE the duplicate check and the cache:
            // lastTrace never holds more than MAX_ACTION_TEXT bytes, and a
            // tail that differs only in text the log would drop does not
            // spend one of the 24 samples on an identical-looking line.
            NaxxramasGolemaggActionAudit::BoundActionTrace(trace, MAX_ACTION_TEXT);
            if (trace == state->lastTrace &&
                lookupPresent == state->lastLookupPresent &&
                !thresholdChanged)
                return;

            state->lastTrace = trace;
            state->lastLookupPresent = lookupPresent;
            state->hasLastSample = true;
            state->lastAtRetreatStacks = atRetreatStacks;
            state->lastInsideRetreatDistance = insideRetreatDistance;
            std::string target = ai->HandleRemoteCommand("target");
            if (target.size() > 64)
                target.resize(64);
            std::replace(target.begin(), target.end(), '\n', ' ');
            std::replace(target.begin(), target.end(), '\r', ' ');

            // One sample at most every 2.5 seconds and 24 reports per bot.
            // Do not draw movement-causality conclusions from this alone.
            ++state->samples;
            if (!atRetreatStacks && !wasAtRetreatStacks)
                ++state->preRetreatSamples;
            LOG_INFO("module",
                "GolemaggActionAudit READ ONLY: bot={} samples={}/{} "
                "splash_stacks={} splash_remaining_ms={} retreat_stacks_20={} "
                "inside_retreat_12yd={} boss_lookup_present={} "
                "boss_hp_pct={} boss_distance_yards={} boss_in_melee_range={} "
                "current_target={} recent_actions={}",
                player->GetName(), static_cast<uint32>(state->samples),
                static_cast<uint32>(MAX_SAMPLES_PER_BOT),
                stacks, remainingMs, atRetreatStacks, insideRetreatDistance,
                lookupPresent,
                lookupPresent ? boss->GetHealthPct() : -1.0f,
                bossDistanceYards, bossInMeleeRange,
                target, trace);
        }

        void OnPlayerLogout(Player* player) override
        {
            if (player)
                player->CustomData.Erase(AUDIT_STATE_KEY);
        }

    };
}

void AddBotGolemaggActionAuditScripts()
{
    new NaxxramasCoreGolemaggActionAuditConfig();
    new NaxxramasCoreGolemaggActionAudit();
}
