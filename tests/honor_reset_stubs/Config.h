// P10 test stub for the ConfigMgr calls HonorReset.cpp makes (typed values).
#ifndef P10_STUB_CONFIG_H
#define P10_STUB_CONFIG_H
#include "Define.h"
#include <map>
#include <string>

class StubConfigMgr
{
public:
    std::map<std::string, bool> bools;
    std::map<std::string, uint32> uints;
    std::map<std::string, std::string> strings;

    template <typename T> T GetOption(std::string const& name, T def);
    static StubConfigMgr& instance() { static StubConfigMgr m; return m; }
};

template <> inline bool StubConfigMgr::GetOption<bool>(std::string const& n, bool d)
{ auto it = bools.find(n); return it == bools.end() ? d : it->second; }
template <> inline uint32 StubConfigMgr::GetOption<uint32>(std::string const& n, uint32 d)
{ auto it = uints.find(n); return it == uints.end() ? d : it->second; }
template <> inline std::string StubConfigMgr::GetOption<std::string>(std::string const& n, std::string d)
{ auto it = strings.find(n); return it == strings.end() ? d : it->second; }

#define sConfigMgr (&StubConfigMgr::instance())
#endif
