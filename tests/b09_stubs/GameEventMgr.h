// B09 test stub with the GameEventMgr surface used by the calendar, matching
// Grimfeather 8daffda GameEventMgr.h L29-L37, L107-L120 and L204.
#ifndef B09_STUB_GAME_EVENT_MGR_H
#define B09_STUB_GAME_EVENT_MGR_H
#include "Define.h"
#include <set>
#include <vector>

enum GameEventState
{
    GAMEEVENT_NORMAL = 0,
    GAMEEVENT_WORLD_INACTIVE = 1,
    GAMEEVENT_WORLD_CONDITIONS = 2,
    GAMEEVENT_WORLD_NEXTPHASE = 3,
    GAMEEVENT_WORLD_FINISHED = 4,
    GAMEEVENT_INTERNAL = 5,
};

struct GameEventData
{
    GameEventState State{GAMEEVENT_NORMAL};
};

class GameEventMgr
{
public:
    typedef std::vector<GameEventData> GameEventDataMap;

    static GameEventMgr* instance()
    {
        static GameEventMgr mgr;
        return &mgr;
    }

    GameEventDataMap const& GetEventMap() const
    {
        ++mapReads;
        return events;
    }

    bool IsActiveEvent(uint16 eventId)
    {
        ++activeQueries;
        return active.count(eventId) != 0;
    }

    void StartInternalEvent(uint16 eventId)
    {
        starts.push_back(eventId);
        if (startSucceeds)
            active.insert(eventId);
    }

    void StopEvent(uint16 eventId, bool /*overwrite*/ = false)
    {
        stops.push_back(eventId);
        active.erase(eventId);
    }

    // Test controls and observations.
    GameEventDataMap events;
    std::set<uint16> active;
    bool startSucceeds = true;
    mutable int mapReads = 0;
    int activeQueries = 0;
    std::vector<uint16> starts;
    std::vector<uint16> stops;

    int Touches() const { return mapReads + activeQueries + int(starts.size() + stops.size()); }
};

#define sGameEventMgr GameEventMgr::instance()
#endif
