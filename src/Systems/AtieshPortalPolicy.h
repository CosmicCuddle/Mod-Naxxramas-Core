/*
 * Naxxramas Core - Atiesh "Portal to Karazhan" policy (F13).
 *
 * Dependency-free decision for a click on GO 181146, so it can be
 * unit-tested without the server. AtieshKarazhanPortal.cpp gathers the
 * live facts and acts on the result. Design: docs/ATIESH-KARAZHAN-PORTAL.md.
 */

#ifndef NAXXRAMAS_CORE_ATIESH_PORTAL_POLICY_H
#define NAXXRAMAS_CORE_ATIESH_PORTAL_POLICY_H

#include <cstdint>

namespace NaxxramasAtieshPortalPolicy
{
    constexpr uint32_t GO_ATIESH_PORTAL_TO_KARAZHAN = 181146;
    constexpr uint32_t SPELL_TELEPORT_KARAZHAN = 28147;
    constexpr uint32_t AREATRIGGER_KARAZHAN_MAIN_EXIT = 4436;
    constexpr uint32_t OUTSIDE_MAP = 0;
    constexpr uint32_t GO_TYPE_SPELLCASTER = 22;

    struct Facts
    {
        // Which object and template this is.
        uint32_t Entry = 0;
        uint32_t GoType = 0;
        uint32_t TemplateSpell = 0;

        // Switch, clicker and era.
        bool Enabled = false;
        bool GameMaster = false;
        bool VanillaStage = false;

        // Native SPELLCASTER partyOnly rule (GameObject.cpp L1920-1934).
        bool PartyOnly = false;
        bool HasOwner = false;
        bool ClickerIsOwner = false;
        bool ClickerGroupHasOwner = false;

        bool BeingTeleported = false;

        // Runtime areatrigger_teleport 4436 validation.
        bool ExitRowExists = false;
        uint32_t ExitRowMap = 0;
        bool ExitRowCoordValid = false;
    };

    enum class Action
    {
        Stock,       // return false: the core handles the click unchanged
        Ignore,      // return true, do nothing (a teleport is already pending)
        FailClosed,  // return true with a message, never the inside cast
        Teleport,    // return true and teleport to the 4436 exit row
    };

    inline bool IsAtieshPortal(Facts const& f)
    {
        return f.Entry == GO_ATIESH_PORTAL_TO_KARAZHAN &&
            f.GoType == GO_TYPE_SPELLCASTER &&
            f.TemplateSpell == SPELL_TELEPORT_KARAZHAN;
    }

    // Same result as the native rule: with an owner, a non-owner must be in
    // a group containing the owner's GUID. Ownerless portals are allowed.
    inline bool PassesPartyRule(Facts const& f)
    {
        if (!f.PartyOnly || !f.HasOwner || f.ClickerIsOwner)
            return true;
        return f.ClickerGroupHasOwner;
    }

    inline bool ExitRowValid(Facts const& f)
    {
        return f.ExitRowExists && f.ExitRowMap == OUTSIDE_MAP && f.ExitRowCoordValid;
    }

    inline Action Decide(Facts const& f)
    {
        if (!IsAtieshPortal(f) || !f.Enabled || f.GameMaster || !f.VanillaStage)
            return Action::Stock;

        // A click the native rule would refuse is left for the core to
        // refuse, exactly as today.
        if (!PassesPartyRule(f))
            return Action::Stock;

        if (f.BeingTeleported)
            return Action::Ignore;

        if (!ExitRowValid(f))
            return Action::FailClosed;

        return Action::Teleport;
    }
}

#endif
