// F14 P5 test stub: PlayerbotAI::GetMaster (PlayerbotAI.h L557).
#ifndef F14_STUB_PLAYERBOT_AI_H
#define F14_STUB_PLAYERBOT_AI_H
class Player;
class PlayerbotAI
{
public:
    Player* master = nullptr;
    Player* GetMaster() { return master; }
};
#endif
