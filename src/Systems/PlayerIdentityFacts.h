#ifndef NAXXRAMAS_CORE_PLAYER_IDENTITY_FACTS_H
#define NAXXRAMAS_CORE_PLAYER_IDENTITY_FACTS_H

// F14 P5: build NaxxramasPlayerIdentity::Facts for one Player from the
// public pinned core (8daffda) and Playerbots (d750b4b) APIs.
//
// NOT WIRED. Nothing in the module calls SampleFacts, registers a hook for
// it or fills an IdentityBoard, so runtime behaviour is unchanged and F14
// stays default OFF. See docs/research/F14-PLAYER-IDENTITY-FACTS-ADAPTER.md.
//
// World-thread-only contract, enforced at compile time: SampleFacts needs a
// WorldThreadSampling token, whose only constructor is private and whose
// only friend, WorldThreadSamplingGrant, is defined NOWHERE in the module.
// A future caller has to define that grant in a reviewed world-thread hook
// (World::Update runs OnWorldUpdate after MapMgr::Update has waited for the
// map workers). Never sample from a map-thread hook or packet handler.

#include "PlayerIdentityPolicy.h"

class Player;

namespace NaxxramasPlayerIdentity
{
    struct WorldThreadSamplingGrant; // deliberately not defined in src/

    // User-provided (not "= default") so C++17 cannot aggregate-initialise
    // it with WorldThreadSampling{}; final so no subclass can wrap it.
    class WorldThreadSampling final
    {
        WorldThreadSampling() {}
        friend struct WorldThreadSamplingGrant;
    };

    // True only when this build has the Playerbots headers. Without them
    // SampleFacts returns empty Facts, which classify as Unknown.
    bool AdapterHasPlayerbots();

    // Reads the player, its session and Playerbots state; changes nothing
    // and keeps no pointer. A null player gives empty Facts (Unknown).
    Facts SampleFacts(WorldThreadSampling const& onWorldThread, Player* player);
}

#endif // NAXXRAMAS_CORE_PLAYER_IDENTITY_FACTS_H
