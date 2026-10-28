// B09 test stub for the WorldScript surface used by the calendar, matching
// Grimfeather 8daffda ScriptDefines/WorldScript.h (constructor L46,
// OnBeforeConfigLoad L59, OnUpdate L71; hook enum names).
#ifndef B09_STUB_SCRIPT_MGR_H
#define B09_STUB_SCRIPT_MGR_H
#include "Define.h"
#include <utility>
#include <vector>

enum WorldHook
{
    WORLDHOOK_ON_OPEN_STATE_CHANGE,
    WORLDHOOK_ON_AFTER_CONFIG_LOAD,
    WORLDHOOK_ON_LOAD_CUSTOM_DATABASE_TABLE,
    WORLDHOOK_ON_BEFORE_CONFIG_LOAD,
    WORLDHOOK_ON_MOTD_CHANGE,
    WORLDHOOK_ON_SHUTDOWN_INITIATE,
    WORLDHOOK_ON_SHUTDOWN_CANCEL,
    WORLDHOOK_ON_UPDATE,
    WORLDHOOK_ON_STARTUP,
    WORLDHOOK_ON_SHUTDOWN,
    WORLDHOOK_ON_AFTER_UNLOAD_ALL_MAPS,
    WORLDHOOK_ON_BEFORE_FINALIZE_PLAYER_WORLD_SESSION,
    WORLDHOOK_ON_BEFORE_WORLD_INITIALIZED,
    WORLDHOOK_END
};

class WorldScript
{
public:
    WorldScript(char const* name, std::vector<uint16> enabledHooks = std::vector<uint16>())
        : Name(name), Hooks(std::move(enabledHooks))
    {
    }
    virtual ~WorldScript() = default;

    virtual void OnBeforeConfigLoad(bool /*reload*/) { }
    virtual void OnStartup() { }
    virtual void OnUpdate(uint32 /*diff*/) { }

    char const* Name;
    std::vector<uint16> Hooks;
};
#endif
