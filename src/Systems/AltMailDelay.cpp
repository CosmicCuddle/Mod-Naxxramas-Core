/*
 * Naxxramas Core
 *
 * Alt Mail Delivery Delay
 *
 * Restores the configured mail delivery delay for player mail sent
 * between characters on the same account.
 *
 * AzerothCore normally bypasses MailDeliveryDelay for same-account mail.
 * This script makes same-account player mail use the normal configured
 * MailDeliveryDelay value again.
 */

#include "CharacterCache.h"
#include "Mail.h"
#include "ScriptMgr.h"
#include "ScriptDefines/MailScript.h"
#include "World.h"

class NaxxramasCoreAltMailDelay : public MailScript
{
public:
    NaxxramasCoreAltMailDelay()
        : MailScript(
            "NaxxramasCoreAltMailDelay",
            {
                MAILHOOK_ON_BEFORE_MAIL_DRAFT_SEND_MAIL_TO
            })
    {
    }

    void OnBeforeMailDraftSendMailTo(
        MailDraft* /*mailDraft*/,
        MailReceiver const& receiver,
        MailSender const& sender,
        MailCheckMask& checked,
        uint32& deliverDelay,
        uint32& /*customExpiration*/,
        bool& /*deleteMailItemsFromDB*/,
        bool& /*sendMail*/) override
    {
        // Only normal player-to-player mail.
        if (sender.GetMailMessageType() != MAIL_NORMAL)
            return;

        // Do not delay GM/customer-support mail.
        if (sender.GetStationery() == MAIL_STATIONERY_GM)
            return;

        // Returned mail and COD payments should keep their normal behavior.
        if ((checked & MAIL_CHECK_MASK_RETURNED) ||
            (checked & MAIL_CHECK_MASK_COD_PAYMENT))
            return;

        ObjectGuid::LowType senderGuid = sender.GetSenderId();
        ObjectGuid::LowType receiverGuid = receiver.GetPlayerGUIDLow();

        // Ignore invalid/self mail.
        if (!senderGuid || !receiverGuid || senderGuid == receiverGuid)
            return;

        uint32 senderAccount =
            sCharacterCache->GetCharacterAccountIdByGuid(
                ObjectGuid(HighGuid::Player, senderGuid));

        uint32 receiverAccount =
            sCharacterCache->GetCharacterAccountIdByGuid(
                ObjectGuid(HighGuid::Player, receiverGuid));

        if (!senderAccount || !receiverAccount)
            return;

        // Only change mail sent between alts on the same account.
        if (senderAccount != receiverAccount)
            return;

        deliverDelay = sWorld->getIntConfig(CONFIG_MAIL_DELIVERY_DELAY);
    }
};

void AddAltMailDelayScripts()
{
    new NaxxramasCoreAltMailDelay();
}
