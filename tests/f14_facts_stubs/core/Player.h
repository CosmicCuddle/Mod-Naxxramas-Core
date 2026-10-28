// F14 P5 test stub: only the Player members the adapter may read.
// Every accessor is const and counted; there is no mutator to call.
#ifndef F14_STUB_PLAYER_H
#define F14_STUB_PLAYER_H
class WorldSession;

class Player
{
public:
    bool inWorld = false;
    WorldSession* session = nullptr;
    mutable int reads = 0;

    bool IsInWorld() const { ++reads; return inWorld; }
    WorldSession* GetSession() const { ++reads; return session; }
};
#endif
