// B09 test stub for the ConfigMgr calls ElementalInvasionCalendar.cpp makes.
// Values are stored already typed; core string parsing is not modelled.
#ifndef B09_STUB_CONFIG_H
#define B09_STUB_CONFIG_H
#include "Define.h"
#include <map>
#include <string>

class StubConfigMgr
{
public:
    std::map<std::string, bool> bools;
    std::map<std::string, uint32> uints;
    int reads = 0;

    template <typename T>
    T GetOption(std::string const& name, T def);

    static StubConfigMgr& instance()
    {
        static StubConfigMgr mgr;
        return mgr;
    }
};

template <>
inline bool StubConfigMgr::GetOption<bool>(std::string const& name, bool def)
{
    ++reads;
    auto const it = bools.find(name);
    return it == bools.end() ? def : it->second;
}

template <>
inline uint32 StubConfigMgr::GetOption<uint32>(std::string const& name, uint32 def)
{
    ++reads;
    auto const it = uints.find(name);
    return it == uints.end() ? def : it->second;
}

#define sConfigMgr (&StubConfigMgr::instance())
#endif
