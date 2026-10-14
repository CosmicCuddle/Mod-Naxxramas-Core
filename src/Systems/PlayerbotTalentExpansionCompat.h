/*
 * Naxxramas Core - Playerbots talent expansion config compatibility.
 *
 * Older mod-playerbots releases use lowercase initial letters for the talent
 * expansion flag and some command/template config fields. Newer releases use
 * uppercase initial letters. Keep this module compatible with both versions
 * without editing Playerbots or changing their existing config behaviour.
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

    // The returned reference preserves the original std::string or array.
    template <typename Config>
    auto CommandSeparator(Config const& config, int)
        -> decltype((config.CommandSeparator))
    {
        return config.CommandSeparator;
    }

    template <typename Config>
    auto CommandSeparator(Config const& config, long)
        -> decltype((config.commandSeparator))
    {
        return config.commandSeparator;
    }

    template <typename Config>
    auto CommandSeparator(Config const& config)
        -> decltype(CommandSeparator(config, 0))
    {
        return CommandSeparator(config, 0);
    }


    // The returned reference preserves the original std::string or array.
    template <typename Config>
    auto CommandPrefix(Config const& config, int)
        -> decltype((config.CommandPrefix))
    {
        return config.CommandPrefix;
    }

    template <typename Config>
    auto CommandPrefix(Config const& config, long)
        -> decltype((config.commandPrefix))
    {
        return config.commandPrefix;
    }

    template <typename Config>
    auto CommandPrefix(Config const& config)
        -> decltype(CommandPrefix(config, 0))
    {
        return CommandPrefix(config, 0);
    }


    // The returned reference preserves the original std::string or array.
    template <typename Config>
    auto PremadeSpecName(Config const& config, int)
        -> decltype((config.PremadeSpecName))
    {
        return config.PremadeSpecName;
    }

    template <typename Config>
    auto PremadeSpecName(Config const& config, long)
        -> decltype((config.premadeSpecName))
    {
        return config.premadeSpecName;
    }

    template <typename Config>
    auto PremadeSpecName(Config const& config)
        -> decltype(PremadeSpecName(config, 0))
    {
        return PremadeSpecName(config, 0);
    }


    // The returned reference preserves the original std::string or array.
    template <typename Config>
    auto ParsedSpecLinkOrder(Config const& config, int)
        -> decltype((config.ParsedSpecLinkOrder))
    {
        return config.ParsedSpecLinkOrder;
    }

    template <typename Config>
    auto ParsedSpecLinkOrder(Config const& config, long)
        -> decltype((config.parsedSpecLinkOrder))
    {
        return config.parsedSpecLinkOrder;
    }

    template <typename Config>
    auto ParsedSpecLinkOrder(Config const& config)
        -> decltype(ParsedSpecLinkOrder(config, 0))
    {
        return ParsedSpecLinkOrder(config, 0);
    }

}
