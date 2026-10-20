/*
 * Naxxramas Core - Hallow's End solo fire config read.
 *
 * Non-inline on purpose. The Shade script calls these functions.
 * GCC 13.3 at -O3 -DNDEBUG -std=gnu++20, the flags used for the
 * five-feature worldserver, keeps the GetOption call and the key
 * characters but does not leave either key as one contiguous literal.
 * A symbol check can see these functions. A binary string search cannot
 * see the keys.
 */

#include "Config.h"
#include "HallowsEndSoloFire.h"

#include <string>

namespace NaxxramasCore::HallowsEndSoloFire
{
__attribute__((noinline))
int32_t ReadHallowsEndSoloFireEnabledSetting()
{
    std::string raw = sConfigMgr->GetOption<std::string>(
        EnabledConfigKey,
        DefaultEnabledRaw,
        false);
    return EnabledFromRaw(raw);
}

__attribute__((noinline))
std::optional<int32_t> ReadHallowsEndSoloFireMultiplierSetting()
{
    std::string raw = sConfigMgr->GetOption<std::string>(
        MultiplierConfigKey,
        DefaultMultiplierRaw,
        false);
    return MultiplierFromRaw(raw);
}
}
