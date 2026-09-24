/*
 * Naxxramas Core
 *
 * Green Whelp Armor
 * Restores the custom proc level cap used by the server.
 */

#include "ScriptMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"

// 9160 - Sleep
class spell_naxx_green_whelp_armor : public AuraScript
{
    PrepareAuraScript(spell_naxx_green_whelp_armor);

    bool CheckProc(ProcEventInfo& eventInfo)
    {
        if (eventInfo.GetActor() && eventInfo.GetActor()->GetLevel() <= 63)
            return true;

        return false;
    }

    void Register() override
    {
        DoCheckProc += AuraCheckProcFn(
            spell_naxx_green_whelp_armor::CheckProc);
    }
};

void AddNaxxramasItemSpellScripts()
{
    RegisterSpellScript(spell_naxx_green_whelp_armor);
}