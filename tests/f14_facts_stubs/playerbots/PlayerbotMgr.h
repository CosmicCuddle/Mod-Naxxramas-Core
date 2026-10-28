// F14 P5 test stub: PlayerbotsMgr::GetPlayerbotAI keeps the pinned
// behaviour that matters here (PlayerbotMgr.cpp L1858-1872): nullptr for
// everyone while Playerbots is disabled, else the attached AI if any.
#ifndef F14_STUB_PLAYERBOT_MGR_H
#define F14_STUB_PLAYERBOT_MGR_H
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include <map>

class Player;
class PlayerbotsMgr
{
public:
    std::map<Player const*, PlayerbotAI*> ais;
    int lookups = 0;

    static PlayerbotsMgr& instance()
    {
        static PlayerbotsMgr mgr;
        return mgr;
    }

    PlayerbotAI* GetPlayerbotAI(Player* player)
    {
        ++lookups;
        if (!sPlayerbotAIConfig.Enabled || !player)
            return nullptr;
        auto const it = ais.find(player);
        return it == ais.end() ? nullptr : it->second;
    }
};
#endif
