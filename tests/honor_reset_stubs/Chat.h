// P10 test stub: ChatHandler(session).PSendSysMessage(...).
#ifndef P10_STUB_CHAT_H
#define P10_STUB_CHAT_H
inline int StubChatMessages = 0;
class WorldSession;
class ChatHandler
{
public:
    explicit ChatHandler(WorldSession*) {}
    template <typename... Args> void PSendSysMessage(char const*, Args&&...) { ++StubChatMessages; }
};
#endif
