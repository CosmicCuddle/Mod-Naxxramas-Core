/*
 * Naxxramas Core - Playerbots talent expansion config compatibility.
 *
 * Older mod-playerbots releases declare limitTalentsExpansion; newer releases
 * declare LimitTalentsExpansion. Keep the module compatible with both without
 * editing Playerbots or changing the existing config setting's behaviour.
 */
#pragma once

namespace NaxxramasPlayerbotCompat
{
    template <typename Config>
    auto LimitTalentsExpansionEnabled(Config const& config, int)
        -> decltype(config.LimitTalentsExpansion)
    {
        return config.LimitTalentsExpansion;
    }

    template <typename Config>
    auto LimitTalentsExpansionEnabled(Config const& config, long)
        -> decltype(config.limitTalentsExpansion)
    {
        return config.limitTalentsExpansion;
    }

    template <typename Config>
    bool LimitTalentsExpansionEnabled(Config const& config)
    {
        return LimitTalentsExpansionEnabled(config, 0);
    }
}
