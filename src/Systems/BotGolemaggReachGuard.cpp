/*
 * Naxxramas Core — optional Golemagg melee reach guard (default OFF).
 *
 * Playerbots backs non-tank melee away from Golemagg at 20 Magma Splash
 * stacks and blocks their attacks until the stack expires, but its
 * GolemaggMultiplier does not cover the generic "reach melee" movement.
 * Bots therefore walk back in, get pushed out again, and deal no damage
 * while they shuttle. This guard denies only "reach melee" for eligible
 * Altbots while Playerbots' own back-off conditions hold, so the bot waits
 * out the stack and then resumes normal combat.
 *
 * Uses the public Playerbots engine listener API: one listener per combat
 * engine, owned and deleted by that engine. No Playerbots, core, SQL or DBC
 * changes. See docs/MC-GOLEMAGG-REACH-GUARD.md.
 */
#include "Config.h"
#include "Engine.h"
#include "GolemaggActionAuditAllowlist.h"
#include "GolemaggReachGuardPolicy.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SpellAuras.h"
#include "Timer.h"

#include <atomic>
#include <string>
#include <type_traits>
#include <utility>

namespace
{
    using namespace NaxxramasGolemaggReachGuard;

    constexpr char const* GUARD_RECORD_KEY = "NaxxramasCore.GolemaggReachGuard.Registration";
    constexpr uint32 DEBUG_LOG_INTERVAL_MS = 5000;

    struct GuardConfig
    {
        bool enabled = false;
        bool debug = false;
        // Exactly one Altbot name; empty means the guard applies to nobody.
        std::string allowedBotName;
    };

    bool IsGuardedBotName(GuardConfig const& config, std::string const& name)
    {
        // Same exact, case-insensitive, single-name rule as the P5 observer.
        return NaxxramasGolemaggActionAudit::IsAllowedBotName(name, config.allowedBotName);
    }

    bool SameGuardConfig(GuardConfig const& a, GuardConfig const& b)
    {
        return a.enabled == b.enabled && a.debug == b.debug && a.allowedBotName == b.allowedBotName;
    }

    // Only called from the config hook below, on the world thread.
    GuardConfig ReadGuardConfig()
    {
        GuardConfig loaded;
        loaded.enabled = sConfigMgr->GetOption<bool>(
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled", false);
        loaded.debug = sConfigMgr->GetOption<bool>(
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Debug", false);
        loaded.allowedBotName = sConfigMgr->GetOption<std::string>(
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName", "");
        return loaded;
    }

    // Written only by the startup config load, which runs in
    // World::SetInitialWorldSettings before MapMgr starts any map worker.
    // Never written again, so map threads read it without a lock and never
    // call ConfigMgr. Until it is written, the guard is OFF.
    GuardConfig StartupGuardConfig;

    GuardConfig const& GetGuardConfig()
    {
        return StartupGuardConfig;
    }

    // Older Playerbots revisions (for example 037c014) have no public
    // PlayerbotAI::GetCurrentEngine(). There the guard compiles to a no-op.
    template <typename T, typename = void>
    struct HasPublicCurrentEngine : std::false_type
    {
    };

    template <typename T>
    struct HasPublicCurrentEngine<T, std::void_t<decltype(std::declval<T&>().GetCurrentEngine())>>
        : std::true_type
    {
    };

    template <typename T>
    Engine* CurrentEngineOf(T* ai)
    {
        if constexpr (HasPublicCurrentEngine<T>::value)
            return ai->GetCurrentEngine();
        else
            return nullptr;
    }

    class GolemaggReachGuardListener final : public ActionExecutionListener
    {
    public:
        GolemaggReachGuardListener(PlayerbotAI* ai, LivenessToken alive)
            : _ai(ai), _alive(std::move(alive))
        {
        }

        ~GolemaggReachGuardListener() override
        {
            // Runs when Playerbots deletes the engine. Never touch _ai here.
            if (_alive)
                _alive->store(false);
        }

        // The only place the guard denies anything. Before() returning false
        // makes the engine log the action as FAILED without executing it.
        bool Before(Action* action, Event /*event*/) override
        {
            if (!action || action->getName() != REACH_MELEE_ACTION)
                return true;

            if (!ShouldDenyReachMelee(BuildContext(action)))
                return true;

            LogDeny();
            return false;
        }

        // Never deny here: a false result is reported to the engine as a
        // successful execution of an action that did not run.
        bool AllowExecution(Action* /*action*/, Event /*event*/) override { return true; }

        void After(Action* /*action*/, bool /*executed*/, Event /*event*/) override { }

        bool OverrideResult(Action* /*action*/, bool executed, Event /*event*/) override { return executed; }

    private:
        // The target is the unit this "reach melee" would move toward:
        // ReachTargetAction resolves the bot's "current target" value both
        // here (Action::GetTarget) and when it executes.
        ReachMeleeContext BuildContext(Action* action) const
        {
            ReachMeleeContext context;
            GuardConfig const& config = GetGuardConfig();
            context.enabled = config.enabled;

            Player* bot = _ai ? _ai->GetBot() : nullptr;
            if (!bot)
                return context;

            context.botAlive = bot->IsAlive();
            context.mapId = bot->GetMapId();
            if (context.mapId != MOLTEN_CORE_MAP)
                return context;

            context.isAltBot = _ai->IsAltBot();
            context.isTank = PlayerbotAI::IsTank(bot);
            context.isDps = PlayerbotAI::IsDps(bot);
            context.isMelee = PlayerbotAI::IsMelee(bot);
            context.nameAllowed = IsGuardedBotName(config, bot->GetName());

            Unit* target = action->GetTarget();
            if (target && target->IsInWorld() && target->GetMapId() == bot->GetMapId())
            {
                context.targetPresent = true;
                context.targetEntry = target->GetEntry();
                context.targetAlive = target->IsAlive();
                context.targetInCombat = target->IsInCombat();
                context.targetHealthPct = target->GetHealthPct();
            }

            if (Aura* splash = bot->GetAura(MAGMA_SPLASH_SPELL))
                context.magmaSplashStacks = splash->GetStackAmount();

            return context;
        }

        void LogDeny()
        {
            if (!GetGuardConfig().debug)
                return;

            uint32 const now = getMSTime();
            if (_lastLogMs != 0 && getMSTimeDiff(_lastLogMs, now) < DEBUG_LOG_INTERVAL_MS)
                return;
            _lastLogMs = now;

            Player* bot = _ai->GetBot();
            Aura* splash = bot->GetAura(MAGMA_SPLASH_SPELL);
            LOG_INFO("module",
                "GolemaggMeleeGuard: denied 'reach melee' for bot={} splash_stacks={} splash_remaining_ms={}",
                bot->GetName(),
                splash ? static_cast<uint32>(splash->GetStackAmount()) : 0u,
                splash ? splash->GetDuration() : 0);
        }

        PlayerbotAI* _ai;
        LivenessToken _alive;
        uint32 _lastLogMs = 0;
    };

    // Takes the settings snapshot. World::LoadConfigSettings calls this hook
    // on the world thread: at startup before any map worker exists, and for
    // ".reload config" from World::UpdateSessions or ProcessCliCommands,
    // neither of which overlaps MapMgr::Update's map workers. A reload keeps
    // the startup values (restart-only) and warns if they changed.
    class NaxxramasCoreGolemaggReachGuardConfig final : public WorldScript
    {
    public:
        NaxxramasCoreGolemaggReachGuardConfig()
            : WorldScript("NaxxramasCoreGolemaggReachGuardConfig", { WORLDHOOK_ON_AFTER_CONFIG_LOAD })
        {
        }

        void OnAfterConfigLoad(bool reload) override
        {
            if (ApplyStartupOnlyConfig(StartupGuardConfig, ReadGuardConfig(), reload, SameGuardConfig))
                LOG_WARN("module",
                    "GolemaggMeleeGuard: settings changed by .reload config are ignored until "
                    "Worldserver restarts; still Enabled={} AllowedBotName='{}' Debug={}.",
                    StartupGuardConfig.enabled, StartupGuardConfig.allowedBotName,
                    StartupGuardConfig.debug);
        }
    };

    struct GuardRegistrationData final : DataMap::Base
    {
        RegistrationRecord<PlayerbotAI, Engine> record;
    };

    class NaxxramasCoreGolemaggReachGuard final : public PlayerScript
    {
    public:
        NaxxramasCoreGolemaggReachGuard()
            : PlayerScript("NaxxramasCoreGolemaggReachGuard", { PLAYERHOOK_ON_UPDATE })
        {
        }

        // Runs on the same player-update thread as Playerbots' own AI update
        // (Playerbots calls UpdateAI from OnPlayerAfterUpdate), so adding a
        // listener here cannot race the engine's listener loop.
        void OnPlayerUpdate(Player* player, uint32 /*diff*/) override
        {
            GuardConfig const& config = GetGuardConfig();
            if (!config.enabled || !player || player->GetMapId() != MOLTEN_CORE_MAP ||
                !player->IsInCombat())
                return;

            // The single exact-name gate runs before the Playerbots manager
            // lookup, which reads an unlocked shared map. With an empty or
            // non-matching AllowedBotName the guard performs no lookup and
            // creates no per-Player record.
            bool const nameAllowed = IsGuardedBotName(config, player->GetName());

            // Never erased: keeping the record for the Player's lifetime is
            // what prevents a second listener on the same engine.
            GuardRegistrationData* data = nameAllowed
                ? player->CustomData.GetDefault<GuardRegistrationData>(GUARD_RECORD_KEY)
                : nullptr;

            // While this bot's listener is alive its AI still exists, so the
            // named bot also skips the lookup. It is looked up only until the
            // listener is registered, and again after Playerbots deletes it.
            if (data && HasLiveRegistration(data->record))
                return;

            PlayerbotAI* ai = LookupAfterNameGate(
                nameAllowed,
                [player] { return PlayerbotsMgr::instance().GetPlayerbotAI(player); });
            if (!ai || !ai->IsAltBot() ||
                PlayerbotAI::IsTank(player) || !PlayerbotAI::IsDps(player) ||
                !PlayerbotAI::IsMelee(player))
                return;

            // Only the combat engine needs the listener.
            if (ai->GetState() != BOT_STATE_COMBAT)
                return;

            Engine* engine = CurrentEngineOf(ai);
            if (!engine)
            {
                static std::atomic<bool> reported{ false };
                if (!reported.exchange(true))
                    LOG_WARN("module",
                        "GolemaggMeleeGuard: this Playerbots revision has no public "
                        "PlayerbotAI::GetCurrentEngine(); the guard is inactive.");
                return;
            }

            if (!NeedsRegistration(data->record, ai, engine))
                return;

            // Ownership passes to the engine, which deletes it with the AI.
            engine->AddActionExecutionListener(
                new GolemaggReachGuardListener(ai, data->record.alive));

            if (config.debug)
                LOG_INFO("module", "GolemaggMeleeGuard: listener registered for bot={}",
                    player->GetName());
        }
    };
}

void AddBotGolemaggReachGuardScripts()
{
    new NaxxramasCoreGolemaggReachGuardConfig();
    new NaxxramasCoreGolemaggReachGuard();
}
