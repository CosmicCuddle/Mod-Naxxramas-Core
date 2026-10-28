/*
 * Naxxramas Core - F14 P5 identity facts adapter (NOT WIRED, default OFF).
 *
 * Read-only: no hook, no script registration, no snapshot, no mutation.
 * See PlayerIdentityFacts.h for the world-thread-only call contract.
 */
#include "PlayerIdentityFacts.h"

#include "Player.h"
#include "WorldSession.h"

#if __has_include("PlayerbotAIConfig.h") && __has_include("PlayerbotMgr.h") && \
    __has_include("PlayerbotAI.h") && __has_include("RandomPlayerbotMgr.h")
#define NAXXRAMAS_IDENTITY_HAS_PLAYERBOTS 1
#include "PlayerbotAI.h"
#include "PlayerbotAIConfig.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
#else
#define NAXXRAMAS_IDENTITY_HAS_PLAYERBOTS 0
#endif

namespace NaxxramasPlayerIdentity
{
    bool AdapterHasPlayerbots()
    {
        return NAXXRAMAS_IDENTITY_HAS_PLAYERBOTS != 0;
    }

    Facts SampleFacts(WorldThreadSampling const& /*onWorldThread*/, Player* player)
    {
        Facts facts;
#if NAXXRAMAS_IDENTITY_HAS_PLAYERBOTS
        if (!player)
            return facts;

        WorldSession const* const session = player->GetSession();
        facts.inWorld = player->IsInWorld();
        facts.hasSession = session != nullptr;
        // Every Playerbots bot session is created with a null socket
        // (PlayerbotMgr.cpp L159, RandomPlayerbotFactory.cpp L733).
        facts.socketOpen = session && !session->IsSocketClosed();

        // GetPlayerbotAI returns nullptr for everyone while this is false,
        // so "no AI" is only meaningful when it is true (Classify knows).
        facts.playerbotsEnabled = sPlayerbotAIConfig.Enabled;
        if (PlayerbotAI* const ai = PlayerbotsMgr::instance().GetPlayerbotAI(player))
        {
            facts.botAiAttached = true;
            facts.botMasterIsSelf = ai->GetMaster() == player;
        }
        // IsRandomBot returns false for SelfBots and requires the random
        // account list plus the live random-bot set.
        facts.randomBotListed = sRandomPlayerbotMgr.IsRandomBot(player);
#else
        (void)player; // No Playerbots in this build: never claim an identity.
#endif
        return facts;
    }
}
