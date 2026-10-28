// F14 P5: MUST NOT COMPILE. Without a WorldThreadSamplingGrant no code can
// make the token SampleFacts requires. CI compiles each VARIANT and requires
// every one to fail; VARIANT 0 is the control that must compile.
#include "PlayerIdentityFacts.h"

using namespace NaxxramasPlayerIdentity;

#if VARIANT == 0
Facts Control(WorldThreadSampling const& token, Player* p) { return SampleFacts(token, p); }
#elif VARIANT == 1
Facts Bypass(Player* p) { return SampleFacts(WorldThreadSampling{}, p); }
#elif VARIANT == 2
Facts Bypass(Player* p) { return SampleFacts(WorldThreadSampling(), p); }
#elif VARIANT == 3
Facts Bypass(Player* p) { WorldThreadSampling token; return SampleFacts(token, p); }
#elif VARIANT == 4
struct Wrapper : WorldThreadSampling {};
Facts Bypass(Player* p) { return SampleFacts(Wrapper{}, p); }
#elif VARIANT == 5
Facts Bypass(Player* p) { return SampleFacts({}, p); }
#endif
