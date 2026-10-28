// F14 P5 test stub: RandomPlayerbotMgr::IsRandomBot(Player*) keeps the
// pinned shape (RandomPlayerbotMgr.cpp L2239-2261): SelfBots are never
// random; otherwise membership of the live random-bot set.
#ifndef F14_STUB_RANDOM_PLAYERBOT_MGR_H
#define F14_STUB_RANDOM_PLAYERBOT_MGR_H
#include "PlayerbotMgr.h"
#include <set>

class RandomPlayerbotMgr
{
public:
    std::set<Player const*> current;
    int lookups = 0;

    static RandomPlayerbotMgr& instance()
    {
        static RandomPlayerbotMgr mgr;
        return mgr;
    }

    bool IsRandomBot(Player* bot)
    {
        ++lookups;
        if (PlayerbotAI* ai = PlayerbotsMgr::instance().GetPlayerbotAI(bot))
            if (ai->GetMaster() == bot)
                return false;
        return bot && current.count(bot) != 0;
    }
};
#define sRandomPlayerbotMgr RandomPlayerbotMgr::instance()
#endif
