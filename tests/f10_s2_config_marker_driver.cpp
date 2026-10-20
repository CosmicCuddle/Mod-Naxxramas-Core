/* Calls the real F10 config readers. A pass is not gameplay acceptance. */

#include "HallowsEndSoloFire.h"

#include <cstdio>
#include <optional>

int main()
{
    int32_t enabled =
        NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireEnabledSetting();
    std::optional<int32_t> multiplier =
        NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireMultiplierSetting();
    int32_t oneBucket =
        NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireOneBucketSetting();

    if (enabled != 1)
        return 2;
    if (!multiplier || *multiplier != 4)
        return 3;
    if (oneBucket != 1)
        return 4;

    std::puts("F10_CONFIG_MARKER_OK");
    return 0;
}
