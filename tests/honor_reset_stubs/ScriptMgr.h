// P10 test stub for the WorldScript surface (8daffda WorldScript.h).
#ifndef P10_STUB_SCRIPT_MGR_H
#define P10_STUB_SCRIPT_MGR_H
#include "Define.h"
#include <utility>
#include <vector>
enum WorldHook
{
    WORLDHOOK_ON_OPEN_STATE_CHANGE, WORLDHOOK_ON_AFTER_CONFIG_LOAD, WORLDHOOK_ON_LOAD_CUSTOM_DATABASE_TABLE,
    WORLDHOOK_ON_BEFORE_CONFIG_LOAD, WORLDHOOK_ON_MOTD_CHANGE, WORLDHOOK_ON_SHUTDOWN_INITIATE,
    WORLDHOOK_ON_SHUTDOWN_CANCEL, WORLDHOOK_ON_UPDATE, WORLDHOOK_ON_STARTUP, WORLDHOOK_END
};
class WorldScript
{
public:
    WorldScript(char const*, std::vector<uint16_t> hooks = {}) : Hooks(std::move(hooks)) {}
    virtual ~WorldScript() = default;
    virtual void OnBeforeConfigLoad(bool) {}
    virtual void OnStartup() {}
    virtual void OnUpdate(uint32) {}
    std::vector<uint16_t> Hooks;
};
#endif
