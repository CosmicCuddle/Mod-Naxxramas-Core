// P10 test stub: the Player members HonorReset.cpp touches.
#ifndef P10_STUB_PLAYER_H
#define P10_STUB_PLAYER_H
#include "Define.h"
class WorldSession {};
class Player
{
public:
    uint32 honor = 100;
    WorldSession* session = nullptr;
    void SetHonorPoints(uint32 v) { honor = v; }
    WorldSession* GetSession() const { return session; }
};
#endif
