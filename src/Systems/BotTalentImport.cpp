/*
 * Naxxramas Core - NT1 talent import, Phase 1: safe read-only validation.
 *
 * Source of truth for the NT1 wire format:
 *   Naxxramas-Resource-Hub/talents/calculator.js
 *
 * WARNING: Neither command in this phase alters character talents.
 * The "apply" command is intentionally a validation-only safety gate until
 * snapshot/rollback, persistence and Playerbots maintenance coordination
 * have been implemented and tested.
 *
 * No Playerbots, Individual Progression or AzerothCore source changes.
 */

#include "Chat.h"
#include "CommandScript.h"
#include "Config.h"
#include "DBCStores.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "PlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "SpellMgr.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

using namespace Acore::ChatCommands;

namespace NaxxramasBotTalentImport
{
    constexpr size_t MAX_CODE_LENGTH = 2048;
    constexpr size_t MAX_ENTRIES = 120;

    struct Era
    {
        char const* Name;
        uint32 MaximumLevel;
        uint32 MaximumRow;
    };

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
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.BotTalentImport.Enabled", false);
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
    // Vanilla: Stormstrike 901 (tab 263); Dark Pact 1022 (tab 302).
    // TBC: Divine Illumination 1747 (tab 382).
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
        if (std::string(era.Name) == "vanilla")
        {
            if (tab == 263)
                return id == 901;
            if (tab == 302)
                return id == 1022;
        }
        else if (std::string(era.Name) == "tbc" && tab == 382)
        {
            return id == 1747;
        }

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

        std::string name;
        std::string code;
        if (!ReadArguments(args, name, code))
        {
            handler->SendSysMessage(
                "Usage: .naxxbot talents preview <online-botname> <NT1-code>");
            return false;
        }

        bot = ObjectAccessor::FindPlayerByName(name);
        if (!bot || !PlayerbotsMgr::instance().GetPlayerbotAI(bot))
        {
            handler->SendSysMessage(
                "That bot is not online or is not managed by Playerbots.");
            return false;
        }

        std::string error;
        if (!ParseCode(code, bot, build, error))
        {
            handler->PSendSysMessage("NT1 rejected: {}", error);
            return false;
        }

        return true;
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
            {"preview", HandlePreview, SEC_GAMEMASTER, Console::No},
            {"apply", HandleApply, SEC_GAMEMASTER, Console::No},
        };
        static ChatCommandTable naxxbot = {
            {"talents", talents}
        };
        return {{"naxxbot", naxxbot}};
    }

    static bool HandlePreview(ChatHandler* handler, char const* args)
    {
        Player* bot = nullptr;
        NaxxramasBotTalentImport::ValidatedBuild build;
        if (!NaxxramasBotTalentImport::ValidateRequest(
                handler, args, bot, build))
            return false;

        NaxxramasBotTalentImport::PrintPreview(handler, bot, build);
        return true;
    }

    static bool HandleApply(ChatHandler* handler, char const* args)
    {
        Player* bot = nullptr;
        NaxxramasBotTalentImport::ValidatedBuild build;
        if (!NaxxramasBotTalentImport::ValidateRequest(
                handler, args, bot, build))
            return false;

        NaxxramasBotTalentImport::PrintPreview(handler, bot, build);
        handler->SendSysMessage(
            "APPLY NOT ENABLED: Phase 1 only validates. No talents were changed. "
            "Snapshot, rollback and persistent build protection must be tested first.");
        return true;
    }
};

void AddBotTalentImportScripts()
{
    new NaxxramasBotTalentImportCommands();
}
