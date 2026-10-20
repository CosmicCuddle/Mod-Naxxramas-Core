/* Test double for ConfigMgr::GetOption<std::string>.
 * Not part of the module. The worldserver still uses Grimfeather's Config.cpp.
 */

#include "Config.h"

#include <cstdlib>
#include <iostream>
#include <string>

ConfigMgr* ConfigMgr::instance()
{
    static ConfigMgr mgr;
    return &mgr;
}

template<class T>
T ConfigMgr::GetOption(std::string const& name, T const& def, bool showLogs) const
{
    std::cout << "KEY=" << name << " DEF=" << def << " LOGS=" << (showLogs ? 1 : 0) << "\n";
    if (name == "NaxxramasCore.HallowsEnd.SoloFire.Enabled")
        return T("1");
    if (name == "NaxxramasCore.HallowsEnd.SoloFire.PeriodMultiplier")
        return T("4");
    std::cerr << "unexpected config key\n";
    std::abort();
}

template std::string ConfigMgr::GetOption<std::string>(
    std::string const& name,
    std::string const& def,
    bool showLogs) const;
