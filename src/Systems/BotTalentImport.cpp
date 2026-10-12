/*
 * Naxxramas Core - NT1 talent import, Phase 1: safe read-only validation.
 *
 * Source of truth for the NT1 wire format:
 *   Naxxramas-Resource-Hub/talents/calculator.js
 *
 * Preview remains read-only. AccessMode 1/2 permits experimental application
 * and requires a character DB backup and tested recovery before live use.
 * Grouped random Playerbots are supported only for the current controlled
 * session; their builds can be replaced by normal Playerbots maintenance.
 * Full persistence across automatic randomization remains pending.
 *
 * No Playerbots, Individual Progression or AzerothCore source changes.
 */

#include "Chat.h"
#include "CommandScript.h"
#include "Config.h"
#include "DBCStores.h"
#include "DatabaseEnv.h"
#include "Group.h"
#include "Item.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "SpellMgr.h"
#include "WorldSession.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

// Keep IndividualProgression.h out of this translation unit:
// it and PlayerbotAI.h both declare the global enum value GENERAL.
// Read current IP's rewarded hidden quests through Player instead,
// as the existing Naxxramas Core Battlemaster integration already does.

using namespace Acore::ChatCommands;

namespace NaxxramasBotTalentImport
{
    constexpr size_t MAX_CODE_LENGTH = 2048;
    constexpr size_t MAX_ENTRIES = 120;

    // This guard scopes exceptions to the explicit Naxxramas Core import
    // while allowing original Playerbots talent commands to work unchanged.
    thread_local Player const* ActiveImport = nullptr;

    bool IsImportOperation(Player const* bot)
    {
        return bot && ActiveImport == bot;
    }

    bool IsImportOffCentreCapstone(Player const* bot, TalentEntry const* talent)
    {
        if (!IsImportOperation(bot) || !talent)
            return false;

        uint32 const tab = talent->TalentTab;
        uint32 const id = talent->TalentID;
        // Vanilla Enhancement and Affliction both use the natural
        // centre-column capstones: Dual Wield (1690) and Contagion (1669).
        // Stormstrike (901) and Dark Pact (1022) are not Vanilla exceptions.
        // The sole off-centre capstone is TBC Holy Divine Illumination.
        return bot->GetLevel() > 60 && bot->GetLevel() <= 70 &&
            tab == 382 && id == 1747;
    }

    struct ImportScope
    {
        Player const* Previous = nullptr;
        explicit ImportScope(Player const* bot) : Previous(ActiveImport)
        {
            ActiveImport = bot;
        }
        ~ImportScope() { ActiveImport = Previous; }
        ImportScope(ImportScope const&) = delete;
        ImportScope& operator=(ImportScope const&) = delete;
    };

    // One setting controls access to the entire NT1 system.
    // 0 = disabled; 1 = GM preview/apply; 2 = authorised player preview/apply.
    // 3 = GM-only read-only diagnostics and projection (NO Apply).
    // 4 = authorised ordinary players and GMs READ-ONLY (NO Apply).
    // Modes 1/2 are experimental and permit destructive talent changes.
    // Default remains OFF; undocumented values fail closed.
    uint32 AccessMode()
    {
        uint32 const mode = sConfigMgr->GetOption<uint32>(
            "NaxxramasCore.BotTalentImport.AccessMode", 0);
        return mode <= 4 ? mode : 0;
    }

    // SEC_PLAYER registration allows us to enforce the selected access mode
    // plus bot-control permissions for ordinary players inside the handler.
    bool AllowNonGMPlayers()
    {
        // 2 allows current experimental Apply; 4 permits ONLY
        // read-only inspection on account-owned/directly mastered bots.
        return AccessMode() == 2 || AccessMode() == 4;
    }

    bool IsReadOnlyAccessMode()
    {
        uint32 const mode = AccessMode();
        return mode == 3 || mode == 4;
    }

    bool IsGM(ChatHandler* handler)
    {
        WorldSession* session = handler ? handler->GetSession() : nullptr;
        return session && session->GetSecurity() >= SEC_GAMEMASTER;
    }

    // Case-insensitive whole character-name matching. Ignore surrounding
    // whitespace so configurations like "Takali, Drakka, Sequoia," work.
    // Never use substring matching: "Takali" must not authorise "Takalina".
    std::string NormalizeAllowedCharacterName(std::string value)
    {
        size_t const begin = value.find_first_not_of(" \t\r\n");
        if (begin == std::string::npos)
            return {};

        size_t const end = value.find_last_not_of(" \t\r\n");
        value = value.substr(begin, end - begin + 1);
        std::transform(value.begin(), value.end(), value.begin(),
            [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
        return value;
    }

    // Additional ALT BOT protection; applies to the issuing human character,
    // NOT the target bot's name. Empty list = deny every Alt Bot NT1 apply.
    // This supplements AccessMode and the existing non-GM ownership checks;
    // it does not grant new privileges or affect Random Playerbots.
    bool CanApplyToAltBot(Player* issuer, std::string& error)
    {
        if (!issuer || !issuer->GetSession() ||
            PlayerbotsMgr::instance().GetPlayerbotAI(issuer))
        {
            error = "Alt Bot NT1 apply requires an authorised human player. "
                    "No talents changed.";
            return false;
        }

        std::string const name = NormalizeAllowedCharacterName(issuer->GetName());
        std::string const allowed = sConfigMgr->GetOption<std::string>(
            "NaxxramasCore.BotTalentImport.AltBotAllowedPlayers", "");

        std::istringstream entries(allowed);
        std::string entry;
        while (std::getline(entries, entry, ','))
        {
            if (!name.empty() && NormalizeAllowedCharacterName(entry) == name)
                return true;
        }

        error = "Alt Bot NT1 apply denied: your character is not in "
                "NaxxramasCore.BotTalentImport.AltBotAllowedPlayers. "
                "No talents changed.";
        return false;
    }

    // For normal players, the bot must belong to their account or have
    // explicitly selected them as its Playerbots master. Group membership
    // alone is never authority to change someone else's talent build.
    bool CanControlBot(Player* player, Player* bot, PlayerbotAI* ai)
    {
        if (!player || !bot || !ai || player == bot ||
            !player->GetSession() || !bot->GetSession())
            return false;

        if (player->GetSession()->GetAccountId() ==
            bot->GetSession()->GetAccountId())
            return true;

        Player* master = ai->GetMaster();
        return master && master->GetGUID() == player->GetGUID();
    }

    struct Era
    {
        char const* Name;
        uint32 MaximumLevel;
        uint32 MaximumRow;
    };

    // Current Individual Progression milestones; match the existing
    // MeetingStoneProgression/BattlemasterQueueProgression integration.
    // Stage 8 opens TBC; stage 13 opens WotLK.
    constexpr uint32 IP_TBC_ENTRY = 8;
    constexpr uint32 IP_WOTLK_ENTRY = 13;
    constexpr uint32 IP_MAX_STAGE = 18;
    constexpr uint32 IP_HIDDEN_QUEST_START = 66000;

    // The requesting HUMAN character's IP expansion is authoritative.
    // Never infer it from a random bot's often-exempt progression state,
    // the requested code, or an artificially raised GM/bot level.
    // IP-disabled realms retain their existing level-based importer checks.
    bool CheckPlayerProgressionEra(Player* issuer, Era const& requested,
        std::string& error)
    {
        if (!issuer || !issuer->IsInWorld())
        {
            error = "Cannot verify the requesting player's progression.";
            return false;
        }

        if (!sConfigMgr->GetOption<bool>("IndividualProgression.Enable", true))
            return true;

        // Modern Individual Progression stores achieved stages in hidden,
        // rewarded quest IDs 66001..66018. Reading Player quest state
        // avoids conflicting IP/Playerbots headers and matches the modern
        // GetPlayerProgressionFromQuests() highest-stage semantics.
        // This path targets the current hidden-quest IP schema (not older
        // player-settings-based variants).
        uint32 stage = 0;
        for (uint32 i = 1; i <= IP_MAX_STAGE; ++i)
            if (issuer->GetQuestStatus(IP_HIDDEN_QUEST_START + i) ==
                QUEST_STATUS_REWARDED)
                stage = i;

        uint32 const limit = sConfigMgr->GetOption<uint32>(
            "IndividualProgression.ProgressionLimit", 0);
        if (limit != 0 && stage > limit)
            stage = limit;

        char const* playerEra = stage >= IP_WOTLK_ENTRY ? "wotlk" :
            stage >= IP_TBC_ENTRY ? "tbc" : "vanilla";
        if (std::string(requested.Name) != playerEra)
        {
            error = "NT1 era blocked by Individual Progression: your "
                "character is in " + std::string(playerEra) +
                " but this talent code is for " + requested.Name +
                ". Choose a build for your current expansion. "
                "No talents changed.";
            return false;
        }

        return true;
    }

    struct TalentSelection
    {
        uint32 Id = 0;
        uint8 Rank = 0;
        TalentEntry const* Talent = nullptr;
        TalentTabEntry const* Tab = nullptr;
    };

    struct ValidatedBuild
    {
        Era Progression = {"", 0, 0};
        std::string Class;
        std::vector<TalentSelection> Ordered;
        uint32 Spent = 0;
        uint32 Available = 0;
        std::array<uint32, 3> Trees = {{0, 0, 0}};
    };

    bool Enabled()
    {
        return AccessMode() != 0;
    }

    // Keep the declared class independent of Playerbots' positional links.
    // NT1 contains the actual Talent.dbc IDs in base 36.
    char const* ClassName(uint8 cls)
    {
        switch (cls)
        {
            case CLASS_WARRIOR:      return "warrior";
            case CLASS_PALADIN:      return "paladin";
            case CLASS_HUNTER:       return "hunter";
            case CLASS_ROGUE:        return "rogue";
            case CLASS_PRIEST:       return "priest";
            case CLASS_DEATH_KNIGHT: return "deathknight";
            case CLASS_SHAMAN:       return "shaman";
            case CLASS_MAGE:         return "mage";
            case CLASS_WARLOCK:      return "warlock";
            case CLASS_DRUID:        return "druid";
            default:                 return nullptr;
        }
    }

    bool DecodeBase36(std::string const& encoded, uint32& result)
    {
        if (encoded.empty())
            return false;

        uint32 number = 0;
        for (char c : encoded)
        {
            uint32 digit = 0;
            if (c >= '0' && c <= '9')
                digit = static_cast<uint32>(c - '0');
            else if (c >= 'a' && c <= 'z')
                digit = static_cast<uint32>(c - 'a') + 10u;
            else
                return false;

            if (number > (std::numeric_limits<uint32>::max() - digit) / 36u)
                return false;

            number = number * 36u + digit;
        }

        result = number;
        return true;
    }

    bool ReadEra(std::string const& label, Era& era)
    {
        if (label == "vanilla")
            era = {"vanilla", 60, 6};
        else if (label == "tbc")
            era = {"tbc", 70, 8};
        else if (label == "wotlk")
            era = {"wotlk", 80, 10};
        else
            return false;
        return true;
    }

    // Exact off-centre capstone exceptions from the published calculator.
    // TalentTab.dbc and Talent.dbc IDs, NOT spell IDs:
    // Current calculator: Vanilla always selects centre-column capstones.
    // Shaman Enhancement has Dual Wield 1690 (NOT Stormstrike 901).
    // Warlock Affliction has Contagion 1669 (NOT Dark Pact 1022).
    // The only off-centre exception is TBC Divine Illumination 1747
    // on TalentTab 382. These are Talent.dbc IDs, NOT spell IDs.
    bool AvailableInEra(TalentSelection const& selection, Era const& era)
    {
        TalentEntry const* talent = selection.Talent;
        if (talent->Row < era.MaximumRow)
            return true;
        if (talent->Row > era.MaximumRow)
            return false;
        if (std::string(era.Name) == "wotlk")
            return true;

        uint32 const tab = talent->TalentTab;
        uint32 const id = talent->TalentID;
        if (std::string(era.Name) == "tbc" && tab == 382)
            return id == 1747;

        return talent->Col == 1;
    }

    bool ParseCode(std::string const& code, Player* bot,
        ValidatedBuild& build, std::string& error)
    {
        if (code.empty() || code.size() > MAX_CODE_LENGTH)
        {
            error = "Empty or oversized NT1 build code.";
            return false;
        }

        std::array<std::string, 4> parts;
        size_t pos = 0;
        for (size_t i = 0; i < 3; ++i)
        {
            size_t const colon = code.find(':', pos);
            if (colon == std::string::npos)
            {
                error = "Expected NT1:<era>:<class>:<talents>.";
                return false;
            }
            parts[i] = code.substr(pos, colon - pos);
            pos = colon + 1;
        }
        parts[3] = code.substr(pos);
        if (parts[3].find(':') != std::string::npos || parts[0] != "NT1")
        {
            error = "Unknown talent code version or invalid NT1 structure.";
            return false;
        }

        if (!ReadEra(parts[1], build.Progression))
        {
            error = "Unknown NT1 progression era.";
            return false;
        }

        if (!bot)
        {
            error = "Bot is not available.";
            return false;
        }

        char const* botClass = ClassName(bot->getClass());
        if (!botClass || parts[2] != botClass)
        {
            error = "Talent code class does not match the bot's class.";
            return false;
        }
        build.Class = parts[2];

        if (build.Class == "deathknight" &&
            parts[1] != "wotlk")
        {
            error = "Death Knights require a WotLK-era build.";
            return false;
        }

        if (bot->GetLevel() < 10 ||
            bot->GetLevel() > build.Progression.MaximumLevel)
        {
            error = "The bot's level is outside the selected era's level range (10-"
                + std::to_string(build.Progression.MaximumLevel) + ").";
            return false;
        }

        build.Available = bot->CalculateTalentsPoints();
        std::unordered_set<uint32> duplicates;
        std::vector<TalentSelection> selections;

        if (!parts[3].empty())
        {
            size_t begin = 0;
            while (begin < parts[3].size())
            {
                size_t const end = parts[3].find('.', begin);
                std::string const pair = parts[3].substr(begin,
                    end == std::string::npos ? std::string::npos : end - begin);

                size_t const dash = pair.find('-');
                if (dash == std::string::npos ||
                    pair.find('-', dash + 1) != std::string::npos ||
                    pair.size() != dash + 2 ||
                    pair[dash + 1] < '1' || pair[dash + 1] > '5')
                {
                    error = "Invalid talent entry: " + pair;
                    return false;
                }

                uint32 id = 0;
                if (!DecodeBase36(pair.substr(0, dash), id) || id == 0 ||
                    !duplicates.insert(id).second)
                {
                    error = "Duplicate or invalid talent ID in NT1 code.";
                    return false;
                }

                TalentEntry const* talent = sTalentStore.LookupEntry(id);
                if (!talent)
                {
                    error = "Talent ID " + std::to_string(id) +
                        " does not exist in the loaded server Talent.dbc.";
                    return false;
                }

                TalentTabEntry const* tab = sTalentTabStore.LookupEntry(talent->TalentTab);
                if (!tab || !(tab->ClassMask & bot->getClassMask()) ||
                    tab->tabpage >= 3)
                {
                    error = "Talent ID " + std::to_string(id) +
                        " does not belong to this bot's class.";
                    return false;
                }

                uint8 const rank = static_cast<uint8>(pair[dash + 1] - '0');
                if (rank > MAX_TALENT_RANK)
                {
                    error = "Talent rank exceeds server maximum.";
                    return false;
                }

                for (uint8 step = 0; step < rank; ++step)
                {
                    uint32 spellId = talent->RankID[step];
                    if (!spellId || !sSpellMgr->GetSpellInfo(spellId))
                    {
                        error = "Talent ID " + std::to_string(id) +
                            " is missing a requested spell rank in the loaded Spell.dbc.";
                        return false;
                    }
                }

                TalentSelection selection{id, rank, talent, tab};
                if (!AvailableInEra(selection, build.Progression))
                {
                    error = "Talent ID " + std::to_string(id) +
                        " is outside the allowed rows for " + parts[1] + ".";
                    return false;
                }

                selections.push_back(selection);
                build.Spent += rank;
                build.Trees[tab->tabpage] += rank;

                if (selections.size() > MAX_ENTRIES)
                {
                    error = "Too many talent entries.";
                    return false;
                }

                if (end == std::string::npos)
                    break;
                begin = end + 1;
                if (begin == parts[3].size())
                {
                    error = "Talent code ends with an empty entry.";
                    return false;
                }
            }
        }

        if (build.Spent > build.Available)
        {
            error = "Build requires " + std::to_string(build.Spent) +
                " points, but this level-" + std::to_string(bot->GetLevel()) +
                " bot only has " + std::to_string(build.Available) + ".";
            return false;
        }

        std::unordered_map<uint32, uint8> requested;
        for (TalentSelection const& entry : selections)
            requested[entry.Id] = entry.Rank;

        // Validate actual server DBC dependencies. DependsOnRank is zero-based.
        for (TalentSelection const& entry : selections)
        {
            uint32 const dependency = entry.Talent->DependsOn;
            if (!dependency)
                continue;

            TalentEntry const* prerequisite = sTalentStore.LookupEntry(dependency);
            if (!prerequisite)
            {
                error = "Missing server DBC prerequisite talent " +
                    std::to_string(dependency) + " for " + std::to_string(entry.Id) + ".";
                return false;
            }

            auto const found = requested.find(dependency);
            uint32 const required = entry.Talent->DependsOnRank + 1;
            if (found == requested.end() || found->second < required)
            {
                error = "Talent ID " + std::to_string(entry.Id) +
                    " requires talent " + std::to_string(dependency) +
                    " at rank " + std::to_string(required) + ".";
                return false;
            }
        }

        // Create an order in which regular Player::LearnTalent can buy each
        // requested rank after a reset. This does NOT learn anything.
        std::sort(selections.begin(), selections.end(),
            [](TalentSelection const& a, TalentSelection const& b)
            {
                if (a.Talent->Row != b.Talent->Row)
                    return a.Talent->Row < b.Talent->Row;
                if (a.Tab->tabpage != b.Tab->tabpage)
                    return a.Tab->tabpage < b.Tab->tabpage;
                return a.Id < b.Id;
            });

        std::unordered_map<uint32, uint8> planned;
        while (!selections.empty())
        {
            bool progress = false;
            for (auto it = selections.begin(); it != selections.end(); ++it)
            {
                uint32 const dep = it->Talent->DependsOn;
                if (dep && planned[dep] < it->Talent->DependsOnRank + 1)
                    continue;

                uint32 earlierPoints = 0;
                for (TalentSelection const& purchased : build.Ordered)
                    if (purchased.Talent->TalentTab == it->Talent->TalentTab &&
                        purchased.Talent->Row < it->Talent->Row)
                        earlierPoints += purchased.Rank;

                if (earlierPoints < it->Talent->Row * MAX_TALENT_RANK)
                    continue;

                planned[it->Id] = it->Rank;
                build.Ordered.push_back(*it);
                selections.erase(it);
                progress = true;
                break;
            }

            if (!progress)
            {
                error = "Build cannot be learned in a legal rank/prerequisite order.";
                return false;
            }
        }

        return true;
    }


    std::string EncodeBase36(uint32 id)
    {
        std::string result;
        do
        {
            uint32 const digit = id % 36u;
            result.push_back(digit < 10 ? static_cast<char>('0' + digit) :
                static_cast<char>('a' + digit - 10));
            id /= 36u;
        } while (id);

        std::reverse(result.begin(), result.end());
        return result;
    }

    // NT1L1 is an EXPLICIT levelling-order format:
    //   NT1L1:<era>:<class>:<talent-id>-<added-ranks>.<id>-<added-ranks>...
    // Each entry advances ranks contiguously; a repeated talent ID resumes
    // that talent later. Unlike NT1 final-rank allocations, the order has
    // meaning. There is deliberately NO apply path for NT1L1.
    //
    // This is pure validation and projection: no Playerbot mutations, talent
    // learning, DB writes or equipment operations. A projected NT1 is
    // revalidated by the existing, read-only ParseCode before it is shown.
    bool ProjectPriorityCode(std::string const& code, Player* bot,
        ValidatedBuild& projected, std::string& projectedCode,
        uint32& sourcePoints, std::string& error)
    {
        if (!bot || code.empty() || code.size() > MAX_CODE_LENGTH)
        {
            error = "Missing bot or empty/oversized NT1L1 code.";
            return false;
        }

        std::array<std::string, 4> parts;
        size_t pos = 0;
        for (size_t i = 0; i < 3; ++i)
        {
            size_t const colon = code.find(':', pos);
            if (colon == std::string::npos)
            {
                error = "Expected NT1L1:<era>:<class>:<ordered-rank-steps>.";
                return false;
            }
            parts[i] = code.substr(pos, colon - pos);
            pos = colon + 1;
        }
        parts[3] = code.substr(pos);
        if (parts[0] != "NT1L1" || parts[3].empty() ||
            parts[3].find(':') != std::string::npos)
        {
            error = "Invalid NT1L1 version or missing rank priorities.";
            return false;
        }

        Era era;
        if (!ReadEra(parts[1], era))
        {
            error = "Unknown NT1L1 expansion.";
            return false;
        }

        char const* cls = ClassName(bot->getClass());
        if (!cls || parts[2] != cls ||
            (parts[2] == "deathknight" && parts[1] != "wotlk"))
        {
            error = "NT1L1 class/expansion does not match this bot.";
            return false;
        }

        if (bot->GetLevel() < 10 || bot->GetLevel() > era.MaximumLevel)
        {
            error = "Bot level is outside the NT1L1 expansion range.";
            return false;
        }

        uint32 const targetPoints = bot->CalculateTalentsPoints();
        // The initial protocol describes a complete, standard, maximum-level
        // talent template for the named expansion, with 51/61/71 ranks.
        // A different/custom source-level budget needs a future version.
        uint32 const fullPoints = era.MaximumLevel - 9;
        if (targetPoints == 0 || targetPoints > fullPoints)
        {
            error = "Bot talent-point budget is unsupported by NT1L1 v1.";
            return false;
        }

        sourcePoints = 0;
        std::unordered_map<uint32, uint8> sourceRanks;
        std::unordered_map<uint32, uint8> targetRanks;
        size_t entryCount = 0;
        size_t begin = 0;
        while (begin < parts[3].size())
        {
            size_t const end = parts[3].find('.', begin);
            std::string const entry = parts[3].substr(begin,
                end == std::string::npos ? std::string::npos : end - begin);
            size_t const dash = entry.find('-');
            if (dash == std::string::npos ||
                entry.find('-', dash + 1) != std::string::npos ||
                entry.size() != dash + 2 ||
                entry[dash + 1] < '1' || entry[dash + 1] > '5')
            {
                error = "Invalid NT1L1 priority entry: " + entry;
                return false;
            }

            uint32 id = 0;
            if (!DecodeBase36(entry.substr(0, dash), id) || id == 0)
            {
                error = "Invalid NT1L1 talent ID: " + entry;
                return false;
            }

            uint8 const addedRanks = static_cast<uint8>(entry[dash + 1] - '0');
            TalentEntry const* talent = sTalentStore.LookupEntry(id);
            TalentTabEntry const* tab = talent ?
                sTalentTabStore.LookupEntry(talent->TalentTab) : nullptr;
            if (!talent || !tab || !(tab->ClassMask & bot->getClassMask()) ||
                tab->tabpage >= 3)
            {
                error = "NT1L1 talent is missing or belongs to another class: " +
                    std::to_string(id);
                return false;
            }

            if (!AvailableInEra({id, 1, talent, tab}, era))
            {
                error = "NT1L1 talent is outside the permitted expansion rows: " +
                    std::to_string(id);
                return false;
            }

            if (++entryCount > MAX_ENTRIES)
            {
                error = "Too many NT1L1 priority entries.";
                return false;
            }

            // Validate EVERY individual rank step, including those after
            // the target's current level. Source priorities must themselves
            // form a fully legal levelling sequence.
            for (uint8 i = 0; i < addedRanks; ++i)
            {
                uint32 const nextRank = sourceRanks[id] + 1;
                if (nextRank > MAX_TALENT_RANK ||
                    !talent->RankID[nextRank - 1] ||
                    !sSpellMgr->GetSpellInfo(talent->RankID[nextRank - 1]))
                {
                    error = "Invalid NT1L1 talent rank/spell for talent " +
                        std::to_string(id);
                    return false;
                }

                if (talent->DependsOn &&
                    sourceRanks[talent->DependsOn] <
                        talent->DependsOnRank + 1)
                {
                    error = "NT1L1 prerequisite is not yet satisfied for " +
                        std::to_string(id);
                    return false;
                }

                uint32 earlierPoints = 0;
                for (auto const& rank : sourceRanks)
                {
                    TalentEntry const* spentTalent =
                        sTalentStore.LookupEntry(rank.first);
                    if (spentTalent &&
                        spentTalent->TalentTab == talent->TalentTab &&
                        spentTalent->Row < talent->Row)
                        earlierPoints += rank.second;
                }
                if (earlierPoints < talent->Row * MAX_TALENT_RANK)
                {
                    error = "NT1L1 talent row is not unlocked at this step: " +
                        std::to_string(id);
                    return false;
                }

                if (++sourcePoints > fullPoints)
                {
                    error = "NT1L1 contains more ranks than the expansion allows.";
                    return false;
                }

                sourceRanks[id] = static_cast<uint8>(nextRank);
                if (sourcePoints <= targetPoints)
                    targetRanks[id] = static_cast<uint8>(nextRank);
            }

            if (end == std::string::npos)
                break;
            begin = end + 1;
            if (begin == parts[3].size())
            {
                error = "NT1L1 has a trailing empty priority entry.";
                return false;
            }
        }

        if (sourcePoints != fullPoints)
        {
            error = "NT1L1 requires a complete " +
                std::to_string(fullPoints) + "-point " + parts[1] +
                " source template; received " + std::to_string(sourcePoints) +
                " points.";
            return false;
        }

        // Canonicalize the derived final rank allocation. Ordinary NT1
        // remains the only existing Apply wire format. This code path
        // never invokes ApplyValidated or any equipment operation.
        std::vector<uint32> ids;
        ids.reserve(targetRanks.size());
        for (auto const& rank : targetRanks)
            ids.push_back(rank.first);
        std::sort(ids.begin(), ids.end());

        projectedCode = "NT1:" + parts[1] + ":" + parts[2] + ":";
        bool first = true;
        for (uint32 id : ids)
        {
            if (!first)
                projectedCode += ".";
            first = false;
            projectedCode += EncodeBase36(id) + "-" +
                std::to_string(targetRanks[id]);
        }

        ValidatedBuild plan;
        if (!ParseCode(projectedCode, bot, plan, error))
        {
            error = "Level-adjusted NT1 failed final DBC validation: " + error;
            return false;
        }
        if (plan.Spent != targetPoints || plan.Available != targetPoints)
        {
            error = "Level-adjusted NT1 does not spend the bot's full budget.";
            return false;
        }

        projected = std::move(plan);
        return true;
    }

    // Capture the current active spec before any reset. We make a canonical
    // NT1 snapshot and require ParseCode to prove it can be restored.
    std::string EncodeExisting(Player* bot, Era const& era)
    {
        std::vector<std::pair<uint32, uint32>> ranks;
        for (uint32 i = 0; i < sTalentStore.GetNumRows(); ++i)
        {
            TalentEntry const* talent = sTalentStore.LookupEntry(i);
            if (!talent)
                continue;
            TalentTabEntry const* tab = sTalentTabStore.LookupEntry(talent->TalentTab);
            if (!tab || !(tab->ClassMask & bot->getClassMask()))
                continue;

            uint32 rank = 0;
            for (uint32 j = 0; j < MAX_TALENT_RANK; ++j)
                if (talent->RankID[j] &&
                    bot->HasTalent(talent->RankID[j], bot->GetActiveSpec()))
                    rank = j + 1;
            if (rank)
                ranks.emplace_back(talent->TalentID, rank);
        }

        std::sort(ranks.begin(), ranks.end());
        std::string code = "NT1:" + std::string(era.Name) +
            ":" + std::string(ClassName(bot->getClass())) + ":";
        bool first = true;
        for (auto const& [id, rank] : ranks)
        {
            if (!first)
                code += ".";
            first = false;
            code += EncodeBase36(id) + "-" + std::to_string(rank);
        }
        return code;
    }

    // Inspect ONLY the currently active spec, using the exact imported-era
    // row/capstone filter already used by ParseCode. No talents are reset or
    // learned. This is diagnostic evidence, NOT a recovery snapshot.
    struct OutOfEraTalent
    {
        uint32 Id = 0;
        uint32 Rank = 0;
        uint32 Row = 0;
        uint32 Col = 0;
        uint32 Tree = 0;
    };

    std::vector<OutOfEraTalent> GetOutOfEraTalents(
        Player const* bot, Era const& era)
    {
        std::vector<OutOfEraTalent> result;
        if (!bot)
            return result;

        for (uint32 i = 0; i < sTalentStore.GetNumRows(); ++i)
        {
            TalentEntry const* talent = sTalentStore.LookupEntry(i);
            if (!talent)
                continue;

            TalentTabEntry const* tab = sTalentTabStore.LookupEntry(
                talent->TalentTab);
            if (!tab || !(tab->ClassMask & bot->getClassMask()) ||
                tab->tabpage >= 3)
                continue;

            uint32 rank = 0;
            for (uint32 j = 0; j < MAX_TALENT_RANK; ++j)
                if (talent->RankID[j] &&
                    bot->HasTalent(talent->RankID[j], bot->GetActiveSpec()))
                    rank = j + 1;

            if (rank && !AvailableInEra(
                {talent->TalentID, static_cast<uint8>(rank), talent, tab},
                era))
            {
                result.push_back({talent->TalentID, rank,
                    talent->Row, talent->Col, tab->tabpage});
            }
        }
        return result;
    }

    // Read-only volatile observation of what the server currently exposes.
    // NOT an offline database backup, restore token, cryptographic signature,
    // or proof that talent reset will preserve these records. In particular
    // Player::GetGlyph(slot) only reads the ACTIVE spec, so inactive-spec
    // glyphs must be checked against the separate OFFLINE DB backup.
    struct AltBotProtectedState
    {
        uint32 CharacterGuid = 0;
        uint32 Level = 0;
        uint8 ActiveSpec = 0;
        uint8 SpecsCount = 0;
        std::array<std::vector<uint32>, MAX_TALENT_SPECS> Talents;
        std::array<std::vector<uint32>, MAX_TALENT_SPECS> Spells;
        std::array<uint32, MAX_GLYPH_SLOT_INDEX> ActiveGlyphs = {};
        std::array<uint32, EQUIPMENT_SLOT_END> EquippedItemGuids = {};
    };

    AltBotProtectedState CaptureAltBotProtectedState(Player const* bot)
    {
        AltBotProtectedState snapshot;
        if (!bot)
            return snapshot;

        snapshot.CharacterGuid = bot->GetGUID().GetCounter();
        snapshot.Level = bot->GetLevel();
        snapshot.ActiveSpec = bot->GetActiveSpec();
        snapshot.SpecsCount = bot->GetSpecsCount();

        // The maps include BOTH specializations, unlike active-spec-only
        // HasTalent/HasSpell tests. Copy spell IDs with their spec bit.
        for (auto const& [spellId, talent] : bot->GetTalentMap())
        {
            if (!talent || talent->State == PLAYERSPELL_REMOVED)
                continue;
            for (uint8 spec = 0; spec < MAX_TALENT_SPECS; ++spec)
                if ((talent->specMask & (1u << spec)) != 0)
                    snapshot.Talents[spec].push_back(spellId);
        }

        for (auto const& [spellId, spell] : bot->GetSpellMap())
        {
            if (!spell || spell->State == PLAYERSPELL_REMOVED)
                continue;
            for (uint8 spec = 0; spec < MAX_TALENT_SPECS; ++spec)
                if ((spell->specMask & (1u << spec)) != 0)
                    snapshot.Spells[spec].push_back(spellId);
        }

        // Unordered_map iteration is nondeterministic; stabilize order.
        for (uint8 spec = 0; spec < MAX_TALENT_SPECS; ++spec)
        {
            std::sort(snapshot.Talents[spec].begin(),
                snapshot.Talents[spec].end());
            std::sort(snapshot.Spells[spec].begin(),
                snapshot.Spells[spec].end());
        }

        for (uint8 slot = 0; slot < MAX_GLYPH_SLOT_INDEX; ++slot)
            snapshot.ActiveGlyphs[slot] = bot->GetGlyph(slot);

        // Equipment identities only. Bag contents, bank, mail and pet DB
        // state are NOT captured. They require an offline characters backup.
        for (uint8 slot = EQUIPMENT_SLOT_START;
            slot < EQUIPMENT_SLOT_END; ++slot)
        {
            Item const* item = bot->GetItemByPos(INVENTORY_SLOT_BAG_0, slot);
            snapshot.EquippedItemGuids[slot] =
                item ? item->GetGUID().GetCounter() : 0;
        }

        return snapshot;
    }

    // A deterministic, diagnostic 64-bit FNV-style checksum of the current
    // in-memory observation, NOT a security credential or proof of recovery.
    void MixStateFingerprint(uint64& hash, uint32 value)
    {
        for (uint32 shift = 0; shift < 32; shift += 8)
        {
            hash ^= (value >> shift) & 0xffu;
            hash *= 1099511628211ULL;
        }
    }

    uint64 BeginStateFingerprint()
    {
        return 14695981039346656037ULL;
    }

    uint64 FingerprintAltBotTalentsAndSpells(
        AltBotProtectedState const& snapshot)
    {
        uint64 hash = BeginStateFingerprint();
        MixStateFingerprint(hash, snapshot.CharacterGuid);
        MixStateFingerprint(hash, snapshot.Level);
        MixStateFingerprint(hash, snapshot.SpecsCount);
        MixStateFingerprint(hash, snapshot.ActiveSpec);
        for (uint32 spec = 0; spec < MAX_TALENT_SPECS; ++spec)
        {
            MixStateFingerprint(hash, 0x11000000u + spec);
            MixStateFingerprint(hash,
                static_cast<uint32>(snapshot.Talents[spec].size()));
            for (uint32 id : snapshot.Talents[spec])
                MixStateFingerprint(hash, id);

            MixStateFingerprint(hash, 0x22000000u + spec);
            MixStateFingerprint(hash,
                static_cast<uint32>(snapshot.Spells[spec].size()));
            for (uint32 id : snapshot.Spells[spec])
                MixStateFingerprint(hash, id);
        }
        return hash;
    }

    uint64 FingerprintAltBotEquipment(AltBotProtectedState const& snapshot)
    {
        uint64 hash = BeginStateFingerprint();
        MixStateFingerprint(hash, snapshot.CharacterGuid);
        for (uint32 slot = EQUIPMENT_SLOT_START;
            slot < EQUIPMENT_SLOT_END; ++slot)
        {
            MixStateFingerprint(hash, slot);
            MixStateFingerprint(hash, snapshot.EquippedItemGuids[slot]);
        }
        return hash;
    }

    uint64 FingerprintAltBotActiveGlyphs(AltBotProtectedState const& snapshot)
    {
        uint64 hash = BeginStateFingerprint();
        MixStateFingerprint(hash, snapshot.CharacterGuid);
        MixStateFingerprint(hash, snapshot.ActiveSpec);
        for (uint32 slot = 0; slot < MAX_GLYPH_SLOT_INDEX; ++slot)
        {
            MixStateFingerprint(hash, slot);
            MixStateFingerprint(hash, snapshot.ActiveGlyphs[slot]);
        }
        return hash;
    }

    std::string HexStateFingerprint(uint64 fingerprint)
    {
        std::ostringstream output;
        output << std::hex << fingerprint;
        return output.str();
    }

    void PrintAltBotProtectedState(ChatHandler* handler, Player const* bot)
    {
        AltBotProtectedState const state = CaptureAltBotProtectedState(bot);
        uint32 equippedSlots = 0;
        uint32 filledGlyphs = 0;
        for (uint32 guid : state.EquippedItemGuids)
            if (guid)
                ++equippedSlots;
        for (uint32 glyph : state.ActiveGlyphs)
            if (glyph)
                ++filledGlyphs;

        handler->PSendSysMessage(
            "NT1 ALT STATE TALENTS (rank-spell records): spec1 {}, spec2 {}. "
            "Learned spell records: spec1 {}, spec2 {}.",
            state.Talents[0].size(), state.Talents[1].size(),
            state.Spells[0].size(), state.Spells[1].size());
        handler->PSendSysMessage(
            "NT1 ALT STATE active-spec glyphs: {} of {} slots; "
            "inactive glyphs require OFFLINE DB backup.",
            filledGlyphs, static_cast<uint32>(MAX_GLYPH_SLOT_INDEX));
        handler->PSendSysMessage(
            "NT1 ALT STATE equipment: {} of {} slots occupied. "
            "Equipment ID checksum: {}.",
            equippedSlots, static_cast<uint32>(EQUIPMENT_SLOT_END),
            HexStateFingerprint(FingerprintAltBotEquipment(state)));
        handler->PSendSysMessage(
            "NT1 ALT STATE volatile talent/spell checksum: {}. "
            "Active glyph checksum: {}.",
            HexStateFingerprint(FingerprintAltBotTalentsAndSpells(state)),
            HexStateFingerprint(FingerprintAltBotActiveGlyphs(state)));
        handler->SendSysMessage(
            "NT1 ALT STATE NOT A BACKUP: no bag/bank/mail or inactive "
            "glyph values captured. Checksums are not restore tokens.");
    }

    // Cross-class, READ-ONLY hazard classifier for ALL Alt Bot classes.
    // Mirror only the observable branches in Player::AutoUnequipOffhandIfNeed;
    // we deliberately DO NOT predict hook outcomes or remove the actual
    // conservative offhand/pet block in CheckApplyReadiness.
    //
    // resetTalents(true) clears Titan's Grip, may remove talent-granted
    // dual wield, dismisses pets and invokes other modules' reset hooks.
    // ActivateSpec() is a different operation with additional glyph/action
    // bar/pet effects; NEVER call it to inspect the inactive specialization.
    void PrintAltBotCrossClassSafetyAudit(ChatHandler* handler, Player const* bot)
    {
        if (!handler || !bot)
            return;

        Item const* main = bot->GetItemByPos(
            INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_MAINHAND);
        Item const* off = bot->GetItemByPos(
            INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND);
        ItemTemplate const* const mainType = main ? main->GetTemplate() : nullptr;
        ItemTemplate const* const offType = off ? off->GetTemplate() : nullptr;

        handler->PSendSysMessage(
            "NT1 ALT CROSS-CLASS AUDIT: {} level {}, spec {} of {}. "
            "Read-only observation, NOT reset approval.",
            ClassName(bot->getClass()), bot->GetLevel(),
            static_cast<uint32>(bot->GetActiveSpec() + 1),
            static_cast<uint32>(bot->GetSpecsCount()));

        if (!off)
        {
            handler->SendSysMessage(
                "NT1 ALT OFFHAND: EMPTY. No current offhand item to "
                "relocate; this is NOT proof the talent reset is safe.");
        }
        else if (!offType || (main && !mainType))
        {
            handler->SendSysMessage(
                "NT1 ALT OFFHAND: UNKNOWN item template. Keep equipment "
                "guard BLOCKED; cannot inspect potential relocation.");
        }
        else
        {
            bool const offWeapon =
                offType->InventoryType == INVTYPE_WEAPONOFFHAND ||
                offType->InventoryType == INVTYPE_WEAPON;
            bool const offTwoHand =
                offType->InventoryType == INVTYPE_2HWEAPON;
            bool const mainForces =
                mainType &&
                (mainType->SubClass == ITEM_SUBCLASS_WEAPON_POLEARM ||
                 mainType->SubClass == ITEM_SUBCLASS_WEAPON_STAFF ||
                 mainType->SubClass == ITEM_SUBCLASS_WEAPON_FISHING_POLE);
            bool const mainTwoHand = bot->IsTwoHandUsed();
            // This reads LIVE abilities, not necessarily abilities AFTER
            // resetTalents has removed talent-granted spell/auras.
            bool const dualWieldRisk =
                offWeapon && (!bot->CanDualWield() ||
                    !bot->HasSpell(674));
            bool const titansGripRisk = offTwoHand ||
                (mainTwoHand && !bot->CanTitanGrip());

            handler->PSendSysMessage(
                "NT1 ALT EQUIPMENT: main item {}, type {}; "
                "offhand item {}, type {}. CanDualWield {}. CanTitanGrip {}.",
                main ? main->GetEntry() : 0,
                mainType ? static_cast<uint32>(mainType->InventoryType) : 0,
                off->GetEntry(), static_cast<uint32>(offType->InventoryType),
                bot->CanDualWield() ? "YES" : "NO",
                bot->CanTitanGrip() ? "YES" : "NO");

            if (mainForces || dualWieldRisk || titansGripRisk)
            {
                handler->PSendSysMessage(
                    "NT1 ALT OFFHAND RISK: CORE RELOCATION CONDITIONS "
                    "MAY APPLY (main forced {}, dual wield {}, 2H/TitanGrip {}). "
                    "KEEP BLOCKED; could move or MAIL original item.",
                    mainForces ? "YES" : "NO",
                    dualWieldRisk ? "YES" : "NO",
                    titansGripRisk ? "YES" : "NO");
            }
            else if (offWeapon)
            {
                handler->SendSysMessage(
                    "NT1 ALT OFFHAND RISK: WEAPON-ABILITY DEPENDENT. "
                    "Dual Wield may change during talent reset. "
                    "KEEP BLOCKED; current abilities are not a guarantee.");
            }
            else
            {
                handler->SendSysMessage(
                    "NT1 ALT OFFHAND RISK: no current CORE relocation "
                    "condition observed for non-weapon offhand. "
                    "STILL BLOCKED; hooks and post-reset state unverified.");
            }
        }

        // Class-specific risk reminders, NOT a prediction that a particular
        // bot has the described talent, spell, pet or item.
        char const* classRisks = nullptr;
        switch (bot->getClass())
        {
            case CLASS_WARRIOR:
                classRisks = "Warrior: Titan's Grip/dual-2H and stance spells";
                break;
            case CLASS_PALADIN:
                classRisks = "Paladin: shield/2H transitions and active auras";
                break;
            case CLASS_HUNTER:
                classRisks = "Hunter: permanent/exotic pet and pet talent state";
                break;
            case CLASS_ROGUE:
                classRisks = "Rogue: dual-wield gear and talent-granted spells";
                break;
            case CLASS_PRIEST:
                classRisks = "Priest: caster focus and temporary summon effects";
                break;
            case CLASS_DEATH_KNIGHT:
                classRisks = "Death Knight: dual-wield setup and ghoul state";
                break;
            case CLASS_SHAMAN:
                classRisks = "Shaman: talent-dependent Dual Wield and shield";
                break;
            case CLASS_MAGE:
                classRisks = "Mage: Water Elemental and caster focus";
                break;
            case CLASS_WARLOCK:
                classRisks = "Warlock: demons/Felguard, pet slots and auras";
                break;
            case CLASS_DRUID:
                classRisks = "Druid: form-linked passives and caster focus";
                break;
            default:
                classRisks = "Unknown class: unsupported risks; keep blocked";
                break;
        }
        handler->PSendSysMessage(
            "NT1 ALT CLASS REVIEW: {}. Check both specs before any "
            "future destructive test.", classRisks);

        // GetPet() may be null with a temporarily unsummoned/stabled pet.
        // GetGlyph(slot) exposes ACTIVE spec only; spec-switching to inspect
        // the other glyph set would itself modify player state.
        handler->PSendSysMessage(
            "NT1 ALT PET CHECK: active pet {}. "
            "Unslotted/stabled pet and guardian data UNKNOWN without "
            "offline characters DB inspection.",
            bot->GetPet() ? "YES" : "NO");
        handler->PSendSysMessage(
            "NT1 ALT COMPLETION HOOK: BotTalentCompletion.Enabled {}. "
            "Other Playerbots talent changes require separate verification.",
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.BotTalentCompletion.Enabled", false)
                ? "ON" : "OFF");
        handler->SendSysMessage(
            "NT1 ALT SPEC SWITCH RISK: core can change action bars, "
            "glyph effects, pets and offhand on spec activation. "
            "INACTIVE glyphs/actions not inspected; NO spec switch performed.");
        handler->SendSysMessage(
            "NT1 ALT SAFETY VERDICT: INSPECTION ONLY. No offhand "
            "exceptions, item moves, pet changes, talent reset or "
            "database writes authorised by this report.");
    }

    // Must run inside ImportScope. Never use PlayerbotFactory's default
    // importer, which may automatically fill unspent talent points.
    bool LearnValidated(Player* bot, ValidatedBuild const& plan,
        std::string& error)
    {
        for (TalentSelection const& selection : plan.Ordered)
        {
            bot->LearnTalent(selection.Id, selection.Rank - 1);
            uint32 const spellId = selection.Talent->RankID[selection.Rank - 1];
            if (!bot->HasTalent(spellId, bot->GetActiveSpec()))
            {
                error = "AzerothCore rejected talent ID " +
                    std::to_string(selection.Id) + " at rank " +
                    std::to_string(selection.Rank) + ".";
                return false;
            }
        }

        if (bot->GetFreeTalentPoints() != plan.Available - plan.Spent)
        {
            error = "Unexpected remaining talent points after application.";
            return false;
        }

        // Verify every class talent: no stale ranks from the prior build.
        for (uint32 i = 0; i < sTalentStore.GetNumRows(); ++i)
        {
            TalentEntry const* talent = sTalentStore.LookupEntry(i);
            if (!talent)
                continue;
            TalentTabEntry const* tab = sTalentTabStore.LookupEntry(talent->TalentTab);
            if (!tab || !(tab->ClassMask & bot->getClassMask()))
                continue;

            uint32 expected = 0;
            for (TalentSelection const& selection : plan.Ordered)
                if (selection.Id == talent->TalentID)
                {
                    expected = selection.Rank;
                    break;
                }

            uint32 actual = 0;
            for (uint32 j = 0; j < MAX_TALENT_RANK; ++j)
                if (talent->RankID[j] &&
                    bot->HasTalent(talent->RankID[j], bot->GetActiveSpec()))
                    actual = j + 1;

            if (actual != expected)
            {
                error = "Final talent comparison failed for talent ID " +
                    std::to_string(talent->TalentID) + ".";
                return false;
            }
        }

        return true;
    }

    // Keep random-bot application limited to a live human-controller session.
    // A group by itself is insufficient if another player is its master.
    // If no master is assigned, only the actual group leader may apply.
    // This does not prevent upstream Playerbots from changing talents later.
    bool CanApplyToGroupedRandomBot(Player* issuer, Player* bot,
        std::string& error)
    {
        if (!issuer || !issuer->GetSession() ||
            PlayerbotsMgr::instance().GetPlayerbotAI(issuer))
        {
            error = "Random bot NT1 application requires an online human player.";
            return false;
        }

        Group* group = issuer->GetGroup();
        if (!group || group != bot->GetGroup() ||
            !group->IsMember(issuer->GetGUID()) ||
            !group->IsMember(bot->GetGUID()))
        {
            error = "Random bot NT1 application requires you and the bot "
                    "to be in the same active party or raid.";
            return false;
        }

        PlayerbotAI* ai = PlayerbotsMgr::instance().GetPlayerbotAI(bot);
        if (!ai)
        {
            error = "Target is not an active Playerbot.";
            return false;
        }

        Player* master = ai->GetMaster();
        if ((master && master != issuer) ||
            (!master && !group->IsLeader(issuer->GetGUID())))
        {
            error = "Random bot NT1 application requires its current "
                    "human master, or the group leader if it has no master.";
            return false;
        }

        return true;
    }

    // Shared, READ-ONLY readiness check. Used by Preview to report whether
    // Apply can currently proceed, and rerun immediately before any reset.
    // It can query the database and read bot state, but NEVER resets,
    // learns, saves or mutates the bot. No persistent confirmation token yet.
    bool CheckApplyReadiness(Player* issuer, Player* bot,
        ValidatedBuild const& requested, std::string& error,
        ValidatedBuild* existingSnapshot = nullptr)
    {
        if (!Enabled())
        {
            error = "NT1 talent importer is disabled.";
            return false;
        }

        if (!issuer || !issuer->GetSession() ||
            PlayerbotsMgr::instance().GetPlayerbotAI(issuer))
        {
            error = "An online human player is required.";
            return false;
        }

        if (!bot || !bot->IsInWorld() || bot == issuer ||
            !PlayerbotsMgr::instance().GetPlayerbotAI(bot))
        {
            error = "Target is not an eligible online Playerbot.";
            return false;
        }

        bool const gm = issuer->GetSession()->GetSecurity() >= SEC_GAMEMASTER;
        if (!gm && (!AllowNonGMPlayers() ||
            !CanControlBot(issuer, bot,
                PlayerbotsMgr::instance().GetPlayerbotAI(bot))))
        {
            error = "NT1 access denied: player is not permitted to "
                    "control this bot.";
            return false;
        }

        // The validated plan comes from ParseCode, but keep the live
        // character level, class and point budget bound to its original plan.
        if (requested.Class != ClassName(bot->getClass()) ||
            bot->GetLevel() < 10 ||
            bot->GetLevel() > requested.Progression.MaximumLevel ||
            requested.Available != bot->CalculateTalentsPoints())
        {
            error = "Bot class, level or available talent points changed "
                    "since plan validation.";
            return false;
        }

        if (bot->IsInCombat() || !bot->IsAlive())
        {
            error = "The bot must be alive and out of combat.";
            return false;
        }

        bool const randomBot = sRandomPlayerbotMgr.IsRandomBot(bot);
        if (randomBot && !CanApplyToGroupedRandomBot(issuer, bot, error))
            return false;

        // Alt Bot talent application requires an explicit administrator
        // allowlist IN ADDITION to AccessMode and ordinary-player control.
        // Check before resetTalents, profile writes or character DB saves.
        // There is deliberately NO Alt Bot equipment automation here:
        // their equipped items must be left untouched by NT1 and by any
        // future role-gearing feature.
        if (!randomBot && !CanApplyToAltBot(issuer, error))
            return false;

        // Recheck inside the destructive path as well as ValidateRequest.
        // A GM and an authorised ordinary player must obey the same era.
        if (!CheckPlayerProgressionEra(issuer, requested.Progression, error))
            return false;

        // NT1 imports must use the bot's ENTIRE talent-point budget.
        // Keep this out of ParseCode: preview must still explain an incomplete
        // build, and snapshot/rollback must remain able to restore a bot
        // whose ORIGINAL spec legitimately has unspent talent points.
        // ParseCode already rejects overspending.
        if (requested.Spent < requested.Available)
        {
            error = "Full talent allocation required: level-" +
                std::to_string(bot->GetLevel()) + " bot has " +
                std::to_string(requested.Available) +
                " available points, but this build spends " +
                std::to_string(requested.Spent) + " (" +
                std::to_string(requested.Available - requested.Spent) +
                " unspent). No talents changed.";
            return false;
        }

        // Our existing expansion guard is level-based. Reject a later-era
        // plan before any reset could fail to buy its final-row ranks.
        if ((bot->GetLevel() <= 60 &&
                std::string(requested.Progression.Name) != "vanilla") ||
            (bot->GetLevel() > 60 && bot->GetLevel() <= 70 &&
                std::string(requested.Progression.Name) != "tbc"))
        {
            error = "Build era does not match the current level-based "
                    "Playerbots talent row restrictions.";
            return false;
        }

        // Fail closed if the module-owned persistence table is missing.
        // Database deployment is an explicit, backed-up administrator step.
        if (!CharacterDatabase.Query(
                "SELECT 1 FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME = 'mod_naxxramas_bot_talent_import' LIMIT 1"))
        {
            error = "Missing characters DB table "
                    "mod_naxxramas_bot_talent_import. "
                    "Apply the reviewed SQL migration before testing.";
            return false;
        }

        // Ensure the CURRENT active spec has a valid, restorable snapshot.
        // Previous/legacy builds may legitimately contain unspent points.
        std::string const previous = EncodeExisting(bot, requested.Progression);
        ValidatedBuild snapshot;
        std::string snapshotError;
        if (!ParseCode(previous, bot, snapshot, snapshotError))
        {
            error = "Existing talents cannot be safely restored: " +
                snapshotError + ". No changes made.";
            return false;
        }

        if (bot->GetFreeTalentPoints() != snapshot.Available - snapshot.Spent)
        {
            error = "Existing talents and remaining points disagree. "
                    "No changes made.";
            return false;
        }

        // Strict fail-closed guard for Alt Bots only. AzerothCore's
        // Player::resetTalents(true) can remove a pet and may automatically
        // unequip OR MAIL offhand equipment. Until a verified alternative
        // prevents every such item/pet side effect, refuse these states
        // BEFORE calling resetTalents. This deliberately includes offhands
        // that might happen to remain equipped: better a false-positive
        // rejection than silently moving an earned Alt Bot item.
        //
        // Note: this is a conservative known-risk guard, NOT proof that
        // arbitrary OnPlayerTalentsReset hooks cannot change something else.
        // The dedicated Alt Bot repair Apply feature is NOT implemented.
        if (!randomBot)
        {
            if (bot->GetItemByPos(
                INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND) != nullptr)
            {
                error = "Alt Bot NT1 Apply blocked: an offhand item is "
                        "equipped. Talent reset could move or MAIL it. "
                        "No talents or equipment changed.";
                return false;
            }

            if (bot->GetPet() != nullptr)
            {
                error = "Alt Bot NT1 Apply blocked: the bot has an active "
                        "pet. Talent reset could dismiss it. "
                        "No talents or equipment changed.";
                return false;
            }
        }

        // Both mode 3 (GM-only) and mode 4 (authorised normal players)
        // are read-only. This preflight report comes AFTER old-build checks
        // so repairpreview can still explain invalid original Priest ranks.
        // ApplyValidated independently refuses both modes at entry.
        if (IsReadOnlyAccessMode())
        {
            error = "NT1 READ-ONLY MODE: Apply is disabled in "
                    "AccessMode 3 or 4. Preview/project/repairpreview "
                    "do not change talents.";
            return false;
        }

        if (existingSnapshot)
            *existingSnapshot = std::move(snapshot);
        return true;
    }

    bool ApplyValidated(Player* issuer, Player* bot, std::string const& code,
        ValidatedBuild const& requested, std::string& error)
    {
        // Independent fail-closed barrier, even if this helper is called
        // without the chat handler. No reset is reachable in mode 3/4.
        if (IsReadOnlyAccessMode())
        {
            error = "NT1 READ-ONLY MODE: Apply is disabled in mode 3 or 4.";
            return false;
        }

        // Do not rely on an earlier Preview or ValidateRequest: ownership,
        // master/group, live point count and snapshot can all change.
        ValidatedBuild snapshot;
        if (!CheckApplyReadiness(issuer, bot, requested, error, &snapshot))
            return false;

        bool const randomBot = sRandomPlayerbotMgr.IsRandomBot(bot);
        uint8 const spec = bot->GetActiveSpec();
        ImportScope const scope(bot);
        bot->resetTalents(true);

        if (bot->GetActiveSpec() != spec)
        {
            error = "Unexpected specialization change during reset. "
                    "Manual recovery may be required.";
            return false;
        }

        if (LearnValidated(bot, requested, error))
        {
            bot->SendTalentsInfoData(false);
            // Alt bots keep their requested NT1 profile in the persistent
            // intent table. Random bots are session-scoped: do NOT store a
            // persistent NT1 lock for a later player or randomization cycle.
            if (!randomBot)
            {
                // ParseCode allows only ASCII-safe NT1 code tokens.
                CharacterDatabase.DirectExecute(
                    "INSERT INTO mod_naxxramas_bot_talent_import "
                    "(guid, spec, code) VALUES ({}, {}, '{}') "
                    "ON DUPLICATE KEY UPDATE code = VALUES(code)",
                    bot->GetGUID().GetCounter(), static_cast<uint32>(spec), code);
            }

            // AzerothCore saves normal character talents. For random bots
            // this does NOT guarantee persistence: Playerbots may reroll
            // talents at any later maintenance pass, including while grouped.
            bot->SaveToDB(false, false);
            return true;
        }

        // This is a recovery attempt, not a transactional guarantee.
        std::string const failed = error;
        bot->resetTalents(true);
        std::string rollbackError;
        if (!LearnValidated(bot, snapshot, rollbackError))
        {
            error = failed + " ROLLBACK FAILED: " + rollbackError +
                ". Do not log out or restart; investigate immediately.";
            bot->SendTalentsInfoData(false);
            return false;
        }

        bot->SendTalentsInfoData(false);
        bot->SaveToDB(false, false);
        error = failed + " Original talents restored successfully.";
        return false;
    }

    bool ReadArguments(char const* args, std::string& name,
        std::string& code)
    {
        std::istringstream input(args ? args : "");
        std::string extra;
        return bool(input >> name >> code) && !(input >> extra);
    }

    bool ValidateRequest(ChatHandler* handler, char const* args,
        Player*& bot, ValidatedBuild& build)
    {
        if (!Enabled())
        {
            handler->SendSysMessage(
                "Naxxramas bot talent importer is disabled in the active configuration.");
            return false;
        }

        bool const gm = IsGM(handler);
        if (!gm && !AllowNonGMPlayers())
        {
            handler->SendSysMessage(
                "NT1 access denied: player talent commands are disabled in "
                "the Naxxramas Core configuration.");
            return false;
        }

        std::string name;
        std::string code;
        if (!ReadArguments(args, name, code))
        {
            handler->SendSysMessage(
                "Usage: .naxxbot talents preview <online-botname> <NT1-code>");
            return false;
        }

        bot = ObjectAccessor::FindPlayerByName(name);
        PlayerbotAI* ai = bot ? PlayerbotsMgr::instance().GetPlayerbotAI(bot) : nullptr;
        if (!bot || !ai)
        {
            handler->SendSysMessage(
                "That bot is not online or is not managed by Playerbots.");
            return false;
        }

        if (!gm && (!handler->GetSession() ||
            !CanControlBot(handler->GetSession()->GetPlayer(), bot, ai)))
        {
            handler->SendSysMessage(
                "NT1 access denied: you may only manage your own account "
                "bots or a Playerbot that recognises you as its master.");
            return false;
        }

        std::string error;
        if (!ParseCode(code, bot, build, error))
        {
            handler->PSendSysMessage("NT1 rejected: {}", error);
            return false;
        }

        // Preview must not advertise an expansion-mismatched NT1 build as
        // usable, and apply must fail before resetting the target's talents.
        if (!CheckPlayerProgressionEra(
                handler->GetSession()->GetPlayer(), build.Progression, error))
        {
            handler->PSendSysMessage("NT1 rejected: {}", error);
            return false;
        }

        return true;
    }

    // Diagnostic-only Alt Bot repair preview. No repair/Apply route exists.
    // Callers must pass normal command security AND AltBotAllowedPlayers
    // before receiving the current character's selected-spec details.
    void PrintAltBotRepairPreview(ChatHandler* handler, Player* issuer,
        Player* bot, ValidatedBuild const& proposed)
    {
        std::vector<OutOfEraTalent> const illegal =
            GetOutOfEraTalents(bot, proposed.Progression);

        handler->PSendSysMessage(
            "NT1 ALT BOT REPAIR INSPECTION: {} (level {}, active spec {}). "
            "Requested {} build: {} / {} points.",
            bot->GetName(), bot->GetLevel(),
            static_cast<uint32>(bot->GetActiveSpec()),
            proposed.Progression.Name, proposed.Spent, proposed.Available);

        handler->PSendSysMessage(
            "Existing active-spec talents outside {} policy: {}.",
            proposed.Progression.Name, illegal.size());

        // Avoid spamming the 3.3.5a chat buffer with a malformed old build.
        // These are Talent.dbc IDs and ZERO-BASED tab row/column indices.
        constexpr size_t MAX_DIAGNOSTIC_ENTRIES = 12;
        for (size_t i = 0; i < illegal.size() &&
            i < MAX_DIAGNOSTIC_ENTRIES; ++i)
        {
            OutOfEraTalent const& t = illegal[i];
            handler->PSendSysMessage(
                "Existing invalid Talent.dbc ID {}: rank {}, tree {}, "
                "row {}, column {} (zero-based).",
                t.Id, t.Rank, t.Tree, t.Row, t.Col);
        }
        if (illegal.size() > MAX_DIAGNOSTIC_ENTRIES)
            handler->PSendSysMessage(
                "{} additional invalid talents omitted from chat.",
                illegal.size() - MAX_DIAGNOSTIC_ENTRIES);

        // PR #7's shared PRE-RESET eligibility check is reused here. A valid
        // target NT1 does not imply Apply can safely roll back the old build.
        std::string reason;
        if (CheckApplyReadiness(issuer, bot, proposed, reason))
            handler->SendSysMessage(
                "NT1 ALT REPAIR DIAGNOSTIC: ordinary talent preflight is "
                "currently READY; a special repair is not required.");
        else
            handler->PSendSysMessage(
                "NT1 ALT REPAIR DIAGNOSTIC BLOCKED: {}", reason);

        if (proposed.Spent != proposed.Available)
            handler->SendSysMessage(
                "NT1 ALT REPAIR INCOMPLETE: the requested build must "
                "spend every available talent point.");

        // A normal AzerothCore reset can dismiss pets and invoke
        // AutoUnequipOffhandIfNeed. This intentionally exposes only a
        // READ-ONLY risk indicator, not an inventory snapshot or a safety
        // authorization. Even an empty offhand slot cannot prove that every
        // possible reset side effect has been accounted for.
        bool const hasOffhand =
            bot->GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND)
                != nullptr;
        bool const hasActivePet = bot->GetPet() != nullptr;
        handler->PSendSysMessage(
            "NT1 ALT RECOVERY CHECK: active specialization {} of {}. "
            "Offhand slot occupied: {}. Active pet: {}.",
            static_cast<uint32>(bot->GetActiveSpec() + 1),
            static_cast<uint32>(bot->GetSpecsCount()),
            hasOffhand ? "YES" : "NO",
            hasActivePet ? "YES" : "NO");
        handler->SendSysMessage(
            "NT1 ALT GUARD: ordinary Apply refuses Alt Bots with an "
            "occupied offhand or active pet before talent reset.");
        handler->SendSysMessage(
            "NT1 ALT RECOVERY NOT VERIFIED: reset may affect other "
            "state via hooks; full recovery is still unproven.");
        handler->SendSysMessage(
            "NT1 ALT BACKUP REQUIRED: full characters database backup "
            "and tested OFFLINE restoration; not verifiable by this command.");

        // Read-only equipment/class/pet/spec risks; no guard is loosened.
        PrintAltBotCrossClassSafetyAudit(handler, bot);

        // Protected-state data is volatile, never persisted to a table,
        // and visible only to a human who passed the Alt Bot allowlist.
        PrintAltBotProtectedState(handler, bot);

        handler->SendSysMessage(
            "NT1 ALT REPAIR DISABLED: no repair Apply command exists. "
            "Normal reset may affect offhand gear; recovery is unverified.");
        handler->SendSysMessage(
            "READ ONLY: no talents, spells, equipment, bags or database "
            "records have been changed by this inspection.");
    }

    void PrintPreview(ChatHandler* handler, Player* bot, ValidatedBuild const& build)
    {
        handler->PSendSysMessage(
            "NT1 valid for {} (level {} {}, era {}).", bot->GetName(),
            bot->GetLevel(), build.Class, build.Progression.Name);
        handler->PSendSysMessage(
            "Points: {} planned / {} available; {} deliberately unspent.",
            build.Spent, build.Available, build.Available - build.Spent);
        handler->PSendSysMessage(
            "Talent trees (server tab order): {} / {} / {}; {} talent entries.",
            build.Trees[0], build.Trees[1], build.Trees[2], build.Ordered.size());
        // Report ACTUAL Apply eligibility, not just valid NT1 syntax.
        // No state change, token or permission grant is created by Preview.
        std::string reason;
        Player* issuer = handler && handler->GetSession() ?
            handler->GetSession()->GetPlayer() : nullptr;
        if (CheckApplyReadiness(issuer, bot, build, reason))
            handler->SendSysMessage(
                "NT1 PREFLIGHT READY (current state only): Apply will "
                "recheck all requirements before changing talents.");
        else
            handler->PSendSysMessage("NT1 PREFLIGHT BLOCKED: {}", reason);

        handler->SendSysMessage(
            "Read-only validation: no talents have been reset or applied.");
    }
}

class NaxxramasBotTalentImportCommands : public CommandScript
{
public:
    NaxxramasBotTalentImportCommands()
        : CommandScript("NaxxramasBotTalentImportCommands")
    {
    }

    ChatCommandTable GetCommands() const override
    {
        static ChatCommandTable talents = {
            {"preview", HandlePreview, SEC_PLAYER, Console::No},
            {"project", HandleProject, SEC_PLAYER, Console::No},
            {"repairpreview", HandleRepairPreview, SEC_PLAYER, Console::No},
            {"apply", HandleApply, SEC_PLAYER, Console::No},
        };
        static ChatCommandTable naxxbot = {
            {"talents", talents}
        };
        return {{"naxxbot", naxxbot}};
    }

    // AzerothCore treats false as a request to show generic command help.
    // Our handlers already explain validation and application failures, so
    // return true after reporting them to avoid confusing extra USAGE lines.
    static bool HandlePreview(ChatHandler* handler, char const* args)
    {
        Player* bot = nullptr;
        NaxxramasBotTalentImport::ValidatedBuild build;
        if (!NaxxramasBotTalentImport::ValidateRequest(
                handler, args, bot, build))
            return true;

        NaxxramasBotTalentImport::PrintPreview(handler, bot, build);
        return true;
    }

    // Only a read-only projection preview is supported for NT1L1.
    // There is no NT1L1 apply handler and no automatic level adjustment
    // in the existing destructive NT1 Apply command.
    static bool HandleProject(ChatHandler* handler, char const* args)
    {
        using namespace NaxxramasBotTalentImport;

        if (!Enabled())
        {
            handler->SendSysMessage(
                "Naxxramas bot talent importer is disabled.");
            return true;
        }
        bool const gm = IsGM(handler);
        if (!gm && !AllowNonGMPlayers())
        {
            handler->SendSysMessage(
                "NT1L1 access denied: player talent commands are disabled.");
            return true;
        }

        std::string name, code;
        if (!ReadArguments(args, name, code))
        {
            handler->SendSysMessage(
                "Usage: .naxxbot talents project <online-botname> <NT1L1-code>");
            return true;
        }

        Player* issuer = handler && handler->GetSession() ?
            handler->GetSession()->GetPlayer() : nullptr;
        Player* bot = ObjectAccessor::FindPlayerByName(name);
        PlayerbotAI* ai = bot ?
            PlayerbotsMgr::instance().GetPlayerbotAI(bot) : nullptr;
        if (!issuer || !ai || !bot || !bot->IsInWorld() ||
            (!gm && !CanControlBot(issuer, bot, ai)))
        {
            handler->SendSysMessage(
                "NT1L1 denied: online bot and valid controlling player required.");
            return true;
        }

        ValidatedBuild plan;
        std::string projectedCode, error;
        uint32 sourcePoints = 0;
        if (!ProjectPriorityCode(code, bot, plan, projectedCode,
            sourcePoints, error))
        {
            handler->PSendSysMessage("NT1L1 rejected: {}", error);
            return true;
        }
        if (!CheckPlayerProgressionEra(issuer, plan.Progression, error))
        {
            handler->PSendSysMessage("NT1L1 rejected: {}", error);
            return true;
        }

        handler->PSendSysMessage(
            "NT1L1 projection for {} (level {} {}, era {}): {} / {} points "
            "from ordered {}-point source.",
            bot->GetName(), bot->GetLevel(), plan.Class, plan.Progression.Name,
            plan.Spent, plan.Available, sourcePoints);
        handler->PSendSysMessage(
            "Projected tree points (server order): {} / {} / {}.",
            plan.Trees[0], plan.Trees[1], plan.Trees[2]);
        // Paginate output as rank pairs, not a potentially truncated
        // chat-length NT1 string. The full projected code is for internal
        // read-only ParseCode validation, not a new Apply transport.
        size_t const lastColon = projectedCode.rfind(':');
        std::istringstream entries(projectedCode.substr(lastColon + 1));
        std::string pair, rankLine;
        while (std::getline(entries, pair, '.'))
        {
            if (rankLine.size() + pair.size() + 2 > 135)
            {
                handler->PSendSysMessage(
                    "Projected Talent.dbc ID-rank entries: {}", rankLine);
                rankLine.clear();
            }
            if (!rankLine.empty())
                rankLine += ", ";
            rankLine += pair;
        }
        if (!rankLine.empty())
            handler->PSendSysMessage(
                "Projected Talent.dbc ID-rank entries: {}", rankLine);

        if (CheckApplyReadiness(issuer, bot, plan, error))
            handler->SendSysMessage(
                "NT1L1 PREFLIGHT READY (read-only only): there is NO "
                "automatic level-projection Apply command.");
        else
            handler->PSendSysMessage(
                "NT1L1 PREFLIGHT BLOCKED: {}", error);

        handler->SendSysMessage(
            "NT1L1 projection only: no talents, equipment or bot data changed.");
        return true;
    }

    static bool HandleRepairPreview(ChatHandler* handler, char const* args)
    {
        using namespace NaxxramasBotTalentImport;

        Player* bot = nullptr;
        ValidatedBuild build;
        // The existing request validator checks AccessMode, bot identity,
        // normal controller rights, DBC legality and the human's current IP.
        if (!ValidateRequest(handler, args, bot, build))
            return true;

        Player* issuer = handler && handler->GetSession() ?
            handler->GetSession()->GetPlayer() : nullptr;
        if (!issuer || !issuer->IsInWorld() ||
            PlayerbotsMgr::instance().GetPlayerbotAI(issuer))
        {
            handler->SendSysMessage(
                "NT1 ALT REPAIR DENIED: only a real online human player "
                "can inspect an Alt Bot.");
            return true;
        }

        if (sRandomPlayerbotMgr.IsRandomBot(bot))
        {
            handler->SendSysMessage(
                "NT1 ALT REPAIR DENIED: target is a Random Playerbot, "
                "not an account-controlled Alt Bot.");
            return true;
        }

        // The character-name allowlist is mandatory even for read-only
        // repair diagnostics; GM permissions cannot bypass this check.
        // It grants no authority to change inventory or equipment.
        std::string error;
        if (!CanApplyToAltBot(issuer, error))
        {
            handler->PSendSysMessage("NT1 ALT REPAIR DENIED: {}", error);
            return true;
        }

        PrintAltBotRepairPreview(handler, issuer, bot, build);
        return true;
    }

    static bool HandleApply(ChatHandler* handler, char const* args)
    {
        // Refuse before parsing or resolving the target. This also keeps
        // read-only test commands from becoming destructive by accident.
        if (NaxxramasBotTalentImport::IsReadOnlyAccessMode())
        {
            handler->SendSysMessage(
                "NT1 READ-ONLY MODE: Apply is disabled in mode 3 or 4. "
                "Use preview, project, or repairpreview instead.");
            return true;
        }

        Player* bot = nullptr;
        NaxxramasBotTalentImport::ValidatedBuild build;
        if (!NaxxramasBotTalentImport::ValidateRequest(
                handler, args, bot, build))
            return true;

        // ValidateRequest already blocks mode 0 and unauthorised callers.
        // Only modes 1 and 2 can ever reach experimental application.
        std::string name, code, error;
        if (!NaxxramasBotTalentImport::ReadArguments(args, name, code))
        {
            handler->SendSysMessage("Invalid talent import arguments.");
            return true;
        }

        Player* issuer = handler->GetSession() ?
            handler->GetSession()->GetPlayer() : nullptr;
        if (!NaxxramasBotTalentImport::ApplyValidated(
                issuer, bot, code, build, error))
        {
            handler->PSendSysMessage("NT1 apply aborted: {}", error);
            return true;
        }

        handler->PSendSysMessage(
            "NT1 build applied to {}: {} spent / {} unspent.",
            bot->GetName(), build.Spent, build.Available - build.Spent);
        if (sRandomPlayerbotMgr.IsRandomBot(bot))
            handler->SendSysMessage(
                "Random Playerbot: session-scoped build only. Playerbots "
                "may replace talents during randomization; no permanent "
                "NT1 profile was saved.");
        return true;
    }
};

void AddBotTalentImportScripts()
{
    new NaxxramasBotTalentImportCommands();
}
