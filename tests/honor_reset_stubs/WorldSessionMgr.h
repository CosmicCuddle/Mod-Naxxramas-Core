// P10 test stub: sWorldSessionMgr->DoForAllOnlinePlayers (8daffda
// WorldSessionMgr.h L94).
#ifndef P10_STUB_WORLD_SESSION_MGR_H
#define P10_STUB_WORLD_SESSION_MGR_H
#include "Player.h"
#include <functional>
#include <vector>
struct StubWorldSessionMgr
{
    std::vector<Player*> online;
    void DoForAllOnlinePlayers(std::function<void(Player*)> exec) { for (Player* p : online) exec(p); }
    static StubWorldSessionMgr* instance() { static StubWorldSessionMgr m; return &m; }
};
#define sWorldSessionMgr StubWorldSessionMgr::instance()
#endif
