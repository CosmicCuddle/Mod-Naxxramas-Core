// Test-only stand-in for the pinned ConditionMgr.h, which pulls in the whole
// condition system. The pinned LootMgr.h only needs the ConditionList type.
#pragma once
#include <vector>
struct Condition;
typedef std::vector<Condition*> ConditionList;
// The real ConditionMgr.h forward-declares WorldObject, which LootMgr.h uses.
class WorldObject;
