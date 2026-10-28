// F14 P5 test stub: WorldSession::IsSocketClosed (core WorldSession.cpp
// L639-642: !m_Socket || !m_Socket->IsOpen()).
#ifndef F14_STUB_WORLD_SESSION_H
#define F14_STUB_WORLD_SESSION_H
class WorldSession
{
public:
    bool socketClosed = true;    // bot sessions are built with a null socket
    mutable int reads = 0;
    bool IsSocketClosed() const { ++reads; return socketClosed; }
};
#endif
