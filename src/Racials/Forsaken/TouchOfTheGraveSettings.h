#ifndef NAXXRAMAS_CORE_TOUCH_OF_THE_GRAVE_SETTINGS_H
#define NAXXRAMAS_CORE_TOUCH_OF_THE_GRAVE_SETTINGS_H

// Touch of the Grave: Individual Progression settings snapshot and the pure
// compensation maths, in standard C++ so native tests can check them.
//
// The six IndividualProgression.* values used to be read through sConfigMgr
// on every cast (SpellScript OnHit) and every heal (UnitScript), both on map
// threads. They are now read once per config load on the world thread
// (WorldScript::OnAfterConfigLoad) and published here; map threads only load
// the atomics. Behaviour, defaults and .reload config are unchanged.

#include <atomic>
#include <cmath>
#include <cstdint>

namespace NaxxramasTouchOfTheGrave
{
    constexpr std::uint8_t PROGRESSION_PRE_TBC = 8;
    constexpr std::uint8_t PROGRESSION_TBC_TIER_5 = 13;

    // Defaults are the sConfigMgr defaults the old code passed.
    struct IpSettings
    {
        bool enabled = true;                  // IndividualProgression.Enable
        std::uint8_t progressionLimit = 0;    // IndividualProgression.ProgressionLimit
        float vanillaPower = 1.0f;            // IndividualProgression.VanillaPowerAdjustment
        float tbcPower = 1.0f;                // IndividualProgression.TBCPowerAdjustment
        float vanillaHealing = 1.0f;          // IndividualProgression.VanillaHealingAdjustment
        float tbcHealing = 1.0f;              // IndividualProgression.TBCHealingAdjustment
    };

    // Written only from the world thread's config hook; read from any
    // thread. Each value is its own lock-free atomic.
    class SettingsSnapshot
    {
    public:
        void Store(IpSettings const& s)
        {
            _enabled.store(s.enabled, std::memory_order_relaxed);
            _progressionLimit.store(s.progressionLimit, std::memory_order_relaxed);
            _vanillaPower.store(s.vanillaPower, std::memory_order_relaxed);
            _tbcPower.store(s.tbcPower, std::memory_order_relaxed);
            _vanillaHealing.store(s.vanillaHealing, std::memory_order_relaxed);
            _tbcHealing.store(s.tbcHealing, std::memory_order_relaxed);
        }

        IpSettings Load() const
        {
            IpSettings s;
            s.enabled = _enabled.load(std::memory_order_relaxed);
            s.progressionLimit = _progressionLimit.load(std::memory_order_relaxed);
            s.vanillaPower = _vanillaPower.load(std::memory_order_relaxed);
            s.tbcPower = _tbcPower.load(std::memory_order_relaxed);
            s.vanillaHealing = _vanillaHealing.load(std::memory_order_relaxed);
            s.tbcHealing = _tbcHealing.load(std::memory_order_relaxed);
            return s;
        }

    private:
        std::atomic<bool> _enabled{IpSettings{}.enabled};
        std::atomic<std::uint8_t> _progressionLimit{IpSettings{}.progressionLimit};
        std::atomic<float> _vanillaPower{IpSettings{}.vanillaPower};
        std::atomic<float> _tbcPower{IpSettings{}.tbcPower};
        std::atomic<float> _vanillaHealing{IpSettings{}.vanillaHealing};
        std::atomic<float> _tbcHealing{IpSettings{}.tbcHealing};
    };

    inline bool HasPassedProgression(std::uint8_t progression, std::uint8_t requiredProgression,
                                     std::uint8_t progressionLimit)
    {
        if (!requiredProgression)
            return false;

        if (progressionLimit && requiredProgression > progressionLimit)
            return false;

        return progression >= requiredProgression;
    }

    // Same maths as before; only the settings source changed.
    inline float ProgressionMultiplier(bool enabled, std::uint8_t progressionLimit,
                                       std::uint8_t progression, std::uint8_t level,
                                       float vanillaAdjustment, float tbcAdjustment)
    {
        if (!enabled)
            return 1.0f;

        // Vanilla progression: Individual Progression's own formula,
        // 1 - (1 - adjustment) * (level - 10) / 50.
        if (!HasPassedProgression(progression, PROGRESSION_PRE_TBC, progressionLimit))
        {
            if (level <= 10)
                return 1.0f;

            float adjustmentApplyPercent = (float(level) - 10.0f) / 50.0f;
            return 1.0f - ((1.0f - vanillaAdjustment) * adjustmentApplyPercent);
        }

        // TBC progression.
        if (!HasPassedProgression(progression, PROGRESSION_TBC_TIER_5, progressionLimit))
            return tbcAdjustment;

        // WotLK progression.
        return 1.0f;
    }
}

#endif // NAXXRAMAS_CORE_TOUCH_OF_THE_GRAVE_SETTINGS_H
