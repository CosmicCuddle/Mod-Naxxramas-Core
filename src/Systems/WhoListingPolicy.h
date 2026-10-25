#ifndef NAXXRAMAS_CORE_WHO_LISTING_POLICY_H
#define NAXXRAMAS_CORE_WHO_LISTING_POLICY_H

#include <array>
#include <cstdint>
#include <string>

// F14 S2: `/who` hiding of Blood Elf and Draenei rows for Vanilla-stage
// observers. Pure standard C++ so the native tests can compare wire bytes.
//
// ReadWhoRequest and WriteWhoReply mirror the stock
// WorldSession::HandleWhoOpcode at Grimfeather 8daffda (MiscHandler.cpp
// L220-L414) line for line. The only addition is the HideRow test, which
// runs before the core's `matchCount++`, so a hidden row leaves both counts.
// scripts/check_f14_who_handler_fingerprint.py fails CI if the core handler
// changes, which forces this mirror to be re-reviewed.
namespace NaxxramasWhoListing
{
    constexpr std::uint8_t RACE_BLOODELF = 10;
    constexpr std::uint8_t RACE_DRAENEI = 11;
    constexpr std::uint32_t MAX_ZONES = 10;   // client limit, stock early return
    constexpr std::uint32_t MAX_STRINGS = 4;  // client limit, stock early return

    // R1-R3 of docs/research/F14-WHO-LISTING-S1.md. When this is false the
    // module returns true and the unmodified stock handler answers.
    struct ObserverContext
    {
        bool hideTbcRaces = false;     // NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces
        bool gmBypass = true;          // NaxxramasCore.ExpansionRaceVisibility.GMBypass
        bool observerIsVanilla = false;
        bool observerAboveSecPlayer = false;
    };

    inline bool InterceptWho(ObserverContext const& o)
    {
        if (!o.hideTbcRaces || !o.observerIsVanilla)
            return false;                          // R1, R2
        return !(o.gmBypass && o.observerAboveSecPlayer); // R3
    }

    // R4 (provisional owner choice O1): the observer's own row is kept.
    // R5: Blood Elf and Draenei rows are hidden, whoever owns them.
    inline bool HideRow(std::uint8_t race, bool rowIsObserver)
    {
        if (rowIsObserver)
            return false;
        return race == RACE_BLOODELF || race == RACE_DRAENEI;
    }

    struct WhoRequest
    {
        std::uint32_t levelMin = 0;
        std::uint32_t levelMax = 0;
        std::uint32_t racemask = 0;
        std::uint32_t classmask = 0;
        std::uint32_t zonesCount = 0;
        std::uint32_t strCount = 0;
        std::array<std::uint32_t, MAX_ZONES> zoneids = {};
        std::wstring str[MAX_STRINGS];
        std::wstring playerName;
        std::wstring guildName;
    };

    // Returns false exactly where the stock handler returns without a reply.
    // A short packet throws from the reader, as in stock.
    // Text supplies Utf8toWStr / wstrToLower (core Util.h in the module).
    template <typename Text, typename Reader>
    bool ReadWhoRequest(Reader& in, WhoRequest& req, std::uint32_t maxLevel, std::uint32_t strongMaxLevel)
    {
        std::string packetPlayerName;
        std::string packetGuildName;

        in >> req.levelMin;
        in >> req.levelMax;
        in >> packetPlayerName;
        in >> packetGuildName;
        in >> req.racemask;
        in >> req.classmask;
        in >> req.zonesCount;

        if (req.zonesCount > MAX_ZONES)
            return false;

        for (std::uint32_t i = 0; i < req.zonesCount; ++i)
        {
            std::uint32_t temp;
            in >> temp;
            req.zoneids[i] = temp;
        }

        in >> req.strCount;

        if (req.strCount > MAX_STRINGS)
            return false;

        for (std::uint32_t i = 0; i < req.strCount; ++i)
        {
            std::string temp;
            in >> temp;

            if (!Text::ToWide(temp, req.str[i]))
                continue;

            Text::Lower(req.str[i]);
        }

        if (!(Text::ToWide(packetPlayerName, req.playerName) &&
              Text::ToWide(packetGuildName, req.guildName)))
            return false;

        Text::Lower(req.playerName);
        Text::Lower(req.guildName);

        if (req.levelMax >= maxLevel)
            req.levelMax = strongMaxLevel;

        return true;
    }

    // Ctx supplies, for the observer: team, canSeeOtherTeam (RBAC 28),
    // canSeeAllSecLevels (RBAC 35), gmLevelInWhoList, observerGuid,
    // observerIsPlayerAccount, observerSecurity, maxReturn and AreaName(zone).
    // Text also supplies FitTo (Utf8FitTo). hide == false gives stock output.
    template <typename Text, typename Rows, typename Ctx, typename Out>
    void WriteWhoReply(WhoRequest const& req, Rows const& rows, Ctx const& ctx, bool hide, Out& data)
    {
        std::uint32_t matchCount = 0;
        std::uint32_t displaycount = 0;

        data << std::uint32_t(matchCount);   // placeholder, count of players matching criteria
        data << std::uint32_t(displaycount); // placeholder, count of players displayed

        for (auto const& target : rows)
        {
            if (target.GetTeamId() != ctx.team && !ctx.canSeeOtherTeam)
                continue;

            if (!ctx.canSeeAllSecLevels && target.GetSecurity() > ctx.gmLevelInWhoList)
                continue;

            if ((ctx.observerGuid != target.GetGuid() && !target.IsVisible()) &&
                (ctx.observerIsPlayerAccount || target.GetSecurity() > ctx.observerSecurity))
                continue;

            std::uint8_t lvl = target.GetLevel();
            if (lvl < req.levelMin || lvl > req.levelMax)
                continue;

            std::uint8_t class_ = target.GetClass();
            if (!(req.classmask & (1 << class_)))
                continue;

            std::uint32_t race = target.GetRace();
            if (!(req.racemask & (1 << race)))
                continue;

            std::uint32_t playerZoneId = target.GetZoneId();
            std::uint8_t gender = target.GetGender();

            bool showZones = true;
            for (std::uint32_t i = 0; i < req.zonesCount; ++i)
            {
                if (req.zoneids[i] == playerZoneId)
                {
                    showZones = true;
                    break;
                }

                showZones = false;
            }

            if (!showZones)
                continue;

            std::wstring const& wideplayername = target.GetWidePlayerName();
            if (!(req.playerName.empty() || wideplayername.find(req.playerName) != std::wstring::npos))
                continue;

            std::wstring const& wideguildname = target.GetWideGuildName();
            if (!(req.guildName.empty() || wideguildname.find(req.guildName) != std::wstring::npos))
                continue;

            std::string aname = ctx.AreaName(playerZoneId);

            bool s_show = true;
            for (std::uint32_t i = 0; i < req.strCount; ++i)
            {
                if (!req.str[i].empty())
                {
                    if (wideguildname.find(req.str[i]) != std::wstring::npos ||
                        wideplayername.find(req.str[i]) != std::wstring::npos ||
                        Text::FitTo(aname, req.str[i]))
                    {
                        s_show = true;
                        break;
                    }

                    s_show = false;
                }
            }

            if (!s_show)
                continue;

            // F14: the only line not in the stock handler. It runs before
            // the count, so a hidden row is in neither count.
            if (hide && HideRow(static_cast<std::uint8_t>(race), ctx.observerGuid == target.GetGuid()))
                continue;

            if ((matchCount++) >= ctx.maxReturn)
                continue;

            data << target.GetPlayerName();
            data << target.GetGuildName();
            data << std::uint32_t(lvl);
            data << std::uint32_t(class_);
            data << std::uint32_t(race);
            data << std::uint8_t(gender);
            data << std::uint32_t(playerZoneId);

            ++displaycount;
        }

        data.put(0, displaycount);
        data.put(4, matchCount);
    }
}

#endif // NAXXRAMAS_CORE_WHO_LISTING_POLICY_H
