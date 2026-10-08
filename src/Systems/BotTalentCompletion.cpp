/*
 * Naxxramas Core - Playerbot talent completion
 *
 * Completes legal talent ranks left unspent after a Playerbot no-cost respec,
 * without changing Playerbots source or resetting the bot a second time.
 *
 * The active AiPlayerbot.LimitTalentsExpansion row limits remain authoritative.
 * AzerothCore's Player::LearnTalent performs all real rank, dependency and
 * prerequisite validation; this script never grants talents directly.
 *
 * Disabled by default until compiled and tested:
 * NaxxramasCore.BotTalentCompletion.Enabled = 0
 */

#include "Config.h"
#include "DBCStores.h"
#include "Log.h"
#include "Player.h"
#include "PlayerbotAIConfig.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"

#include <algorithm>
#include <cstdint>
#include <unordered_map>
#include <utility>
#include <vector>

namespace NaxxramasBotTalentCompletion
{
    constexpr uint32 QUIET_PERIOD_MS = 1200;
    constexpr uint32 MAX_ATTEMPTS_PER_POINT = 256;

    struct PendingRespec
    {
        uint32 MillisecondsRemaining = QUIET_PERIOD_MS;
        uint8 Spec = 0;
        bool LearnedSomething = false;
        uint32 PreviousSpecNo = 0;
    };

    struct TalentChoice
    {
        TalentEntry const* Talent = nullptr;
        uint8 Tab = 0;
    };

    struct TemplateMatch
    {
        std::unordered_map<uint32, uint8> DesiredRanks;
        uint32 MatchingPoints = 0;
    };

    std::unordered_map<ObjectGuid::LowType, PendingRespec> Pending;

    bool Enabled()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.BotTalentCompletion.Enabled", false);
    }

    bool IsSupportedBot(Player* player)
    {
        return player &&
            player->GetLevel() >= 10 &&
            player->GetLevel() <= 70 &&
            sPlayerbotAIConfig.limitTalentsExpansion &&
            PlayerbotsMgr::instance().GetPlayerbotAI(player);
    }

    // Exactly mirrors AiPlayerbot.LimitTalentsExpansion's row filter.
    bool IsRowAllowed(uint8 level, TalentEntry const* talent)
    {
        if (level <= 60)
            return talent->Row < 6 ||
                (talent->Row == 6 && talent->Col == 1);

        if (level <= 70)
            return talent->Row < 8 ||
                (talent->Row == 8 && talent->Col == 1);

        return true;
    }

    uint8 CurrentRank(Player* bot, TalentEntry const* talent)
    {
        for (int rank = MAX_TALENT_RANK - 1; rank >= 0; --rank)
        {
            if (talent->RankID[rank] &&
                bot->HasTalent(talent->RankID[rank], bot->GetActiveSpec()))
            {
                return static_cast<uint8>(rank + 1);
            }
        }

        return 0;
    }

    uint8 MaximumRank(TalentEntry const* talent)
    {
        uint8 result = 0;
        for (uint8 rank = 0; rank < MAX_TALENT_RANK; ++rank)
        {
            if (talent->RankID[rank])
                result = rank + 1;
        }
        return result;
    }

    std::vector<TalentChoice> GetLegalTalents(Player* bot)
    {
        std::vector<TalentChoice> choices;
        uint32 const classMask = bot->getClassMask();

        for (uint32 i = 0; i < sTalentStore.GetNumRows(); ++i)
        {
            TalentEntry const* talent = sTalentStore.LookupEntry(i);
            if (!talent || !IsRowAllowed(bot->GetLevel(), talent))
                continue;

            TalentTabEntry const* tab = sTalentTabStore.LookupEntry(talent->TalentTab);
            if (!tab || !(tab->ClassMask & classMask) || tab->tabpage >= 3)
                continue;

            if (!MaximumRank(talent))
                continue;

            choices.push_back({talent, static_cast<uint8>(tab->tabpage)});
        }
        return choices;
    }

    // Resolve a premade spec link's talent position against the actual server
    // DBC. This also supports Naxxramas Core's custom Talent.dbc entries.
    TalentChoice const* FindChoice(
        std::vector<TalentChoice> const& choices,
        uint32 tab, uint32 row, uint32 col)
    {
        for (TalentChoice const& choice : choices)
        {
            if (choice.Tab == tab &&
                choice.Talent->Row == row &&
                choice.Talent->Col == col)
            {
                return &choice;
            }
        }
        return nullptr;
    }

    // A build is matched from its already-learned ranks, not from a guessed
    // specialisation name. This avoids trusting an old 'specNo' when the user
    // has applied a custom talent link.
    std::unordered_map<uint32, uint8> FindMatchingTemplate(
        Player* bot, std::vector<TalentChoice> const& choices,
        uint32 previousSpecNo)
    {
        uint32 const cls = bot->getClass();
        uint32 alreadySpent = 0;
        for (TalentChoice const& choice : choices)
            alreadySpent += CurrentRank(bot, choice.Talent);

        if (alreadySpent < 10)
            return {};

        TemplateMatch best;

        // Playerbots sets this to selected premade index + 1 after a named
        // spec change. A custom imported link does not update this field.
        uint32 const currentSpecNo = sRandomPlayerbotMgr.GetValue(bot, "specNo");
        uint32 const explicitlyChangedSpecNo =
            (currentSpecNo != previousSpecNo) ? currentSpecNo : 0;

        for (uint32 specNo = 0; specNo < MAX_SPECNO; ++specNo)
        {
            if (sPlayerbotAIConfig.premadeSpecName[cls][specNo].empty())
                continue;

            // Pick the closest configured plan to the bot's actual level.
            // Previously we always preferred the level-80 plan, even at 60.
            // That could import WotLK secondary-tree talent preferences.
            // If equally distant, prefer the lower-level template.
            std::vector<std::vector<uint32>> const* parsed = nullptr;
            uint32 bestDistance = 81;
            uint32 bestLevel = 81;
            uint32 const botLevel = bot->GetLevel();

            for (uint32 level = 10; level <= 80 && level < MAX_LEVEL; ++level)
            {
                auto const& candidate =
                    sPlayerbotAIConfig.parsedSpecLinkOrder[cls][specNo][level];
                if (candidate.empty())
                    continue;

                uint32 const distance = level > botLevel
                    ? level - botLevel : botLevel - level;

                if (distance < bestDistance ||
                    (distance == bestDistance && level < bestLevel))
                {
                    parsed = &candidate;
                    bestDistance = distance;
                    bestLevel = level;
                }
            }

            if (!parsed)
                continue;

            TemplateMatch match;

            for (std::vector<uint32> const& entry : *parsed)
            {
                if (entry.size() < 4)
                    continue;

                TalentChoice const* choice =
                    FindChoice(choices, entry[0], entry[1], entry[2]);

                if (!choice)
                    continue;

                uint8 desired = static_cast<uint8>(
                    std::min<uint32>(entry[3], MaximumRank(choice->Talent)));

                if (desired)
                {
                    uint8& slot = match.DesiredRanks[choice->Talent->TalentID];
                    slot = std::max(slot, desired);
                }
            }

            for (TalentChoice const& choice : choices)
            {
                uint8 actual = CurrentRank(bot, choice.Talent);
                auto it = match.DesiredRanks.find(choice.Talent->TalentID);
                if (it != match.DesiredRanks.end())
                    match.MatchingPoints += std::min(actual, it->second);
            }

            // Prefer the exact named spec when its stored index changed;
            // require the same close-overlap safeguard as ordinary matching.
            if (explicitlyChangedSpecNo == specNo + 1 &&
                match.MatchingPoints * 100 >= alreadySpent * 85)
            {
                return match.DesiredRanks;
            }

            if (match.MatchingPoints > best.MatchingPoints)
                best = std::move(match);
        }

        // Only follow a premade plan when it closely matches what the bot
        // actually learned. Custom links otherwise receive conservative,
        // deterministic finishing choices below.
        if (best.MatchingPoints * 100 < alreadySpent * 85)
            return {};

        return best.DesiredRanks;
    }

    // When the chosen template or learned talent distribution already has a
    // secondary tree, keep that same tree rather than inventing a third.
    // A Wrack-focused Affliction Warlock may use Demonology as its secondary
    // even if the stock level-60 template lists only Affliction talents.
    uint8 ChooseSecondaryTab(
        Player* bot, std::vector<TalentChoice> const& choices,
        std::unordered_map<uint32, uint8> const& desiredRanks,
        uint8 primaryTab, bool& wrackProfile)
    {
        uint8 points[3] = {0, 0, 0};
        bot->GetTalentTreePoints(points);

        uint32 planned[3] = {0, 0, 0};
        for (TalentChoice const& choice : choices)
        {
            auto it = desiredRanks.find(choice.Talent->TalentID);
            if (it != desiredRanks.end())
                planned[choice.Tab] += it->second;
        }

        // Never reinterpret an existing Affliction/Destruction custom hybrid
        // as a 31/20/0 Wrack build. A chosen template which explicitly wants
        // Destruction also takes precedence.
        wrackProfile =
            bot->getClass() == CLASS_WARLOCK &&
            bot->GetLevel() <= 60 &&
            primaryTab == 0 &&
            bot->HasTalent(18275, bot->GetActiveSpec()) &&
            points[2] == 0 &&
            planned[2] == 0;

        if (wrackProfile)
            return 1; // Affliction + Demonology, never inject Destruction.

        uint8 secondary = 3; // No second tree established.
        for (uint8 tab = 0; tab < 3; ++tab)
        {
            if (tab == primaryTab)
                continue;

            if (points[tab] &&
                (secondary == 3 || points[tab] > points[secondary]))
            {
                secondary = tab;
            }
        }

        if (secondary != 3)
            return secondary;

        for (uint8 tab = 0; tab < 3; ++tab)
        {
            if (tab == primaryTab)
                continue;

            if (planned[tab] &&
                (secondary == 3 || planned[tab] > planned[secondary]))
            {
                secondary = tab;
            }
        }

        return secondary;
    }

    bool AttemptNextRank(Player* bot, TalentChoice const& choice)
    {
        uint8 const current = CurrentRank(bot, choice.Talent);
        uint8 const maximum = MaximumRank(choice.Talent);

        if (current >= maximum || !bot->GetFreeTalentPoints())
            return false;

        uint32 const before = bot->GetFreeTalentPoints();

        // Rank indices are zero-based. Request exactly one additional point.
        // AzerothCore checks prerequisite talents, row points and valid spells.
        bot->LearnTalent(choice.Talent->TalentID, current);

        return bot->GetFreeTalentPoints() < before;
    }

    uint32 ScoreChoice(
        Player* bot,
        TalentChoice const& choice,
        uint8 primaryTab,
        std::unordered_map<uint32, uint8> const& desiredRanks,
        bool templateOnly)
    {
        uint8 current = CurrentRank(bot, choice.Talent);
        if (current >= MaximumRank(choice.Talent))
            return 0;

        auto it = desiredRanks.find(choice.Talent->TalentID);
        bool const desired =
            it != desiredRanks.end() && current < it->second;

        if (templateOnly && !desired)
            return 0;

        // The build's planned ranks come first, followed by an existing
        // partially invested talent, then legal choices in its main tree.
        uint32 score = desired ? 100000u : 0u;
        if (choice.Tab == primaryTab)
            score += 10000u;
        if (current)
            score += 1000u;

        // Prefer existing/deeper eligible talents over arbitrary first-row
        // fillers, but leave real eligibility checks to Player::LearnTalent.
        score += choice.Talent->Row * 100u + current * 10u;
        return score + 1u;
    }

    uint32 Finish(Player* bot, uint32 previousSpecNo)
    {
        if (!IsSupportedBot(bot) || !bot->GetFreeTalentPoints())
            return 0;

        std::vector<TalentChoice> const choices = GetLegalTalents(bot);
        if (choices.empty())
            return 0;

        uint8 const primaryTab = bot->GetMostPointsTalentTree();
        auto const desiredRanks = FindMatchingTemplate(
            bot, choices, previousSpecNo);
        bool wrackProfile = false;
        uint8 const secondaryTab = ChooseSecondaryTab(
            bot, choices, desiredRanks, primaryTab, wrackProfile);
        uint32 totalSpent = 0;

        // Each pass buys at most one rank. Candidate order is stable, and
        // failed attempts are not repeated in the same pass.
        while (bot->GetFreeTalentPoints() &&
            totalSpent < bot->CalculateTalentsPoints())
        {
            bool bought = false;

            uint8 points[3] = {0, 0, 0};
            bot->GetTalentTreePoints(points);
            bool const preferWrackDemo =
                wrackProfile && points[0] >= 31 && points[1] < 20;

            // Phase 0: for a Wrack build, reach towards the 31/20/0
            // Affliction/Demonology distribution (without removing points
            // already assigned by Playerbots).
            // Phase 1: finish unspent legal ranks from the level-specific plan.
            // Phase 2: deterministic legal filler within the existing trees.
            for (uint8 phase = 0; phase < 3 && !bought; ++phase)
            {
                auto score = [&](uint32 index) -> uint32
                {
                    TalentChoice const& choice = choices[index];

                    if (choice.Tab != primaryTab &&
                        choice.Tab != secondaryTab)
                        return 0;

                    if (phase == 0)
                    {
                        if (!preferWrackDemo || choice.Tab != 1)
                            return 0;

                        return ScoreChoice(bot, choice, primaryTab,
                            desiredRanks, false);
                    }

                    return ScoreChoice(bot, choice, primaryTab,
                        desiredRanks, phase == 1);
                };

                std::vector<uint32> order(choices.size());
                for (uint32 i = 0; i < choices.size(); ++i)
                    order[i] = i;

                std::stable_sort(order.begin(), order.end(),
                    [&](uint32 a, uint32 b)
                    {
                        return score(a) > score(b);
                    });

                uint32 attempts = 0;
                for (uint32 index : order)
                {
                    if (++attempts > MAX_ATTEMPTS_PER_POINT)
                        break;

                    if (!score(index))
                        break;

                    if (AttemptNextRank(bot, choices[index]))
                    {
                        ++totalSpent;
                        bought = true;
                        break;
                    }
                }
            }

            if (!bought)
                break; // Nothing valid: never force points or loop forever.
        }

        if (totalSpent)
            bot->SendTalentsInfoData(false);

        if (bot->GetFreeTalentPoints())
        {
            LOG_WARN("module", "Naxxramas Core: Playerbot {} could not spend {} remaining talent point(s) after legal template completion",
                bot->GetName(), bot->GetFreeTalentPoints());
        }

        return totalSpent;
    }
}

class NaxxramasCoreBotTalentCompletion : public PlayerScript
{
public:
    NaxxramasCoreBotTalentCompletion()
        : PlayerScript("NaxxramasCoreBotTalentCompletion",
            {
                PLAYERHOOK_ON_TALENTS_RESET,
                PLAYERHOOK_ON_PLAYER_LEARN_TALENTS,
                PLAYERHOOK_ON_AFTER_SPEC_SLOT_CHANGED,
                PLAYERHOOK_ON_BEFORE_UPDATE,
                PLAYERHOOK_ON_LOGOUT
            })
    {
    }

    void OnPlayerTalentsReset(Player* bot, bool noCost) override
    {
        if (!noCost || !NaxxramasBotTalentCompletion::Enabled() ||
            !NaxxramasBotTalentCompletion::IsSupportedBot(bot))
        {
            return;
        }

        NaxxramasBotTalentCompletion::Pending[bot->GetGUID().GetCounter()] =
            {NaxxramasBotTalentCompletion::QUIET_PERIOD_MS,
             bot->GetActiveSpec(), false,
             sRandomPlayerbotMgr.GetValue(bot, "specNo")};
    }

    void OnPlayerLearnTalents(
        Player* bot, uint32, uint32, uint32) override
    {
        if (!bot)
            return;

        auto it = NaxxramasBotTalentCompletion::Pending.find(
            bot->GetGUID().GetCounter());

        if (it != NaxxramasBotTalentCompletion::Pending.end())
        {
            it->second.LearnedSomething = true;
            it->second.MillisecondsRemaining =
                NaxxramasBotTalentCompletion::QUIET_PERIOD_MS;
        }
    }

    void OnPlayerBeforeUpdate(Player* bot, uint32 diff) override
    {
        if (!bot)
            return;

        auto it = NaxxramasBotTalentCompletion::Pending.find(
            bot->GetGUID().GetCounter());

        if (it == NaxxramasBotTalentCompletion::Pending.end())
            return;

        if (!NaxxramasBotTalentCompletion::Enabled() ||
            !NaxxramasBotTalentCompletion::IsSupportedBot(bot) ||
            bot->GetActiveSpec() != it->second.Spec)
        {
            NaxxramasBotTalentCompletion::Pending.erase(it);
            return;
        }

        if (it->second.MillisecondsRemaining > diff)
        {
            it->second.MillisecondsRemaining -= diff;
            return;
        }

        // Wait for a real template assignment; do not fill an intentionally
        // empty build or interfere with the bot while it is fighting.
        if (!it->second.LearnedSomething)
        {
            NaxxramasBotTalentCompletion::Pending.erase(it);
            return;
        }

        if (bot->IsInCombat())
            return;

        uint32 const previousSpecNo = it->second.PreviousSpecNo;
        NaxxramasBotTalentCompletion::Pending.erase(it);
        NaxxramasBotTalentCompletion::Finish(bot, previousSpecNo);
    }

    void OnPlayerAfterSpecSlotChanged(Player* bot, uint8) override
    {
        if (bot)
            NaxxramasBotTalentCompletion::Pending.erase(
                bot->GetGUID().GetCounter());
    }

    void OnPlayerLogout(Player* bot) override
    {
        if (bot)
            NaxxramasBotTalentCompletion::Pending.erase(
                bot->GetGUID().GetCounter());
    }
};

void AddBotTalentCompletionScripts()
{
    new NaxxramasCoreBotTalentCompletion();
}
