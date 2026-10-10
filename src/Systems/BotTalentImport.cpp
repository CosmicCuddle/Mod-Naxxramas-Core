/*
 * Naxxramas Core - NT1 talent import, Phase 1: safe read-only validation.
 *
 * Source of truth for the NT1 wire format:
 *   Naxxramas-Resource-Hub/talents/calculator.js
 *
 * Phase 2: preview remains read-only. Apply is behind a separate OFF-by-default
 * switch and must not be enabled without compilation and a character DB backup.
 * Exact persistence across automatic Playerbots randomization remains pending.
 *
 * No Playerbots, Individual Progression or AzerothCore source changes.
 */

#include "Chat.h"
#include "CommandScript.h"
#include "Config.h"
#include "DBCStores.h"
#include "DatabaseEnv.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
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
        // Enhancement's Vanilla capstone is Dual Wield (1690) in the
        // centre column; Stormstrike (901) must not be exempt.
        return (bot->GetLevel() <= 60 && tab == 302 && id == 1022) ||
            (bot->GetLevel() > 60 && bot->GetLevel() <= 70 &&
                tab == 382 && id == 1747);
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

    bool ApplyEnabled()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.BotTalentImport.ApplyEnabled", false);
    }

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
    // Vanilla: Dark Pact 1022 (tab 302).
    // TBC: Divine Illumination 1747 (tab 382).
    // Vanilla Enhancement has Dual Wield 1690 at centre column 1;
    // Stormstrike 901 in the side column is only valid from TBC onward.
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

    bool ApplyValidated(Player* bot, std::string const& code,
        ValidatedBuild const& requested, std::string& error)
    {
        if (bot->IsInCombat() || !bot->IsAlive())
        {
            error = "The bot must be alive and out of combat.";
            return false;
        }

        if (sRandomPlayerbotMgr.IsRandomBot(bot))
        {
            error = "Applying to random bots is disabled until automatic "
                    "full-randomization behaviour has been verified.";
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

        // A legacy-invalid talent snapshot may not be restorable through
        // the normal talent API. Refuse to reset when that is the case.
        std::string const previous = EncodeExisting(bot, requested.Progression);
        ValidatedBuild snapshot;
        std::string snapshotError;
        if (!ParseCode(previous, bot, snapshot, snapshotError) ||
            bot->GetFreeTalentPoints() != snapshot.Available - snapshot.Spent)
        {
            error = "Existing talents cannot be safely restored: " +
                snapshotError + ". No changes made.";
            return false;
        }

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
            // ParseCode restricts the stored string to ASCII safe tokens
            // (letters, digits, colon, period and dash), never SQL quotes.
            CharacterDatabase.DirectExecute(
                "INSERT INTO mod_naxxramas_bot_talent_import "
                "(guid, spec, code) VALUES ({}, {}, '{}') "
                "ON DUPLICATE KEY UPDATE code = VALUES(code)",
                bot->GetGUID().GetCounter(), static_cast<uint32>(spec), code);
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

        if (!NaxxramasBotTalentImport::ApplyEnabled())
        {
            NaxxramasBotTalentImport::PrintPreview(handler, bot, build);
            handler->SendSysMessage(
                "APPLY DISABLED: validation only. Requires "
                "NaxxramasCore.BotTalentImport.ApplyEnabled=1, a characters "
                "database backup and explicit test approval.");
            return true;
        }

        std::string name, code, error;
        if (!NaxxramasBotTalentImport::ReadArguments(args, name, code))
        {
            handler->SendSysMessage("Invalid talent import arguments.");
            return false;
        }

        if (!NaxxramasBotTalentImport::ApplyValidated(bot, code, build, error))
        {
            handler->PSendSysMessage("NT1 apply aborted: {}", error);
            return false;
        }

        handler->PSendSysMessage(
            "NT1 build applied to {}: {} spent / {} unspent.",
            bot->GetName(), build.Spent, build.Available - build.Spent);
        return true;
    }
};

void AddBotTalentImportScripts()
{
    new NaxxramasBotTalentImportCommands();
}
