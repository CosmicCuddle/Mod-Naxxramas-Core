#define CHECK(expression) do { ++checks; if (!(expression)) { std::cerr << "FAIL at line " << __LINE__ << '\n'; return 1; } } while (false)
WorldPacket packet(unsigned count, uint32 money = 0, uint32 cod = 0, std::string body = "body") {
    WorldPacket result;
    result.fields = {ObjectGuid(HighGuid::Player, 900), std::string("recipient"), std::string("subject"), body,
                     uint32(0), uint32(0), uint8(count)};
    for (unsigned index = 0; index < count; ++index) {
        result.fields.emplace_back(uint8(index));
        result.fields.emplace_back(ObjectGuid(HighGuid::Player, 100 + index));
    }
    result.fields.insert(result.fields.end(), {money, cod, uint64(0), uint8(0)});
    return result;
}
void reset() {
    cache = Cache{}; world = World{};
    CharacterDatabase.commits = 0; CharacterDatabase.committed.reset();
    ObjectAccessor::online = nullptr; enableCustom = allowSend = true;
    admissionCalls = draftCalls = 0;
}
void attach(Player& player, unsigned count) {
    for (unsigned index = 0; index < count; ++index) player.inventory.emplace(100 + index, new Item(100 + index));
}
int main() {
    unsigned checks = 0, cases = 0;
    for (bool online : {false, true}) for (bool custom : {false, true})
    for (uint32 account : {5u, 9u, 0u}) for (uint32 senderCache : {5u, 0u})
    for (unsigned count : {0u, 1u, 3u, 12u}) for (uint32 money : {0u, 40u})
    for (auto body : {std::string(), std::string("body")}) for (uint32 delay : {0u, 3600u}) {
        reset(); Player sender, receiver; receiver.guid = ObjectGuid(HighGuid::Player, 2);
        receiver.session.account = account;
        cache.receiverAccount = account; cache.senderAccount = senderCache;
        ObjectAccessor::online = online ? &receiver : nullptr;
        enableCustom = custom; world.delay = delay; attach(sender, count);
        auto request = packet(count, money, 0, body); sender.session.HandleSendMail(request);
        CHECK(sender.lastResult == MAIL_OK && CharacterDatabase.commits == 1 && sender.saved == 1);
        CHECK(admissionCalls == (count ? count : 1) && draftCalls == 1);
        CHECK(draftHadItems == (count != 0) && draftMoney == money && draftCOD == 0);
        uint32 nativeDelay = count && account != 5 ? delay : 0;
        CHECK(baselineDelay == nativeDelay);
        uint32 expected = nativeDelay;
        if (custom && count && senderCache == 5 && account == 5) expected = delay;
        auto const& rows = CharacterDatabase.committed->rows;
        CHECK(rows.size() == 1 + count && rows[0].values.at(10) == std::to_string(1000 + expected));
        CHECK(rows[0].values.at(11) == std::to_string(money) && rows[0].values.at(7) == body);
        CHECK(rows[0].values.at(13) == std::to_string(body.empty() ? MAIL_CHECK_MASK_COPIED : MAIL_CHECK_MASK_HAS_BODY));
        CHECK(sender.funds == 1000000 - money - (count ? count * 30 : 30));
        CHECK(sender.inventory.empty() && sender.moved == count);
        if (online) CHECK(receiver.mails.size() == 1 && receiver.items.size() == count &&
                          receiver.mails[0]->deliver_time == time_t(1000 + expected));
        ++cases;
    }
    for (unsigned count : {0u, 1u}) {
        reset(); Player sender; attach(sender, count);
        auto request = packet(count, 0, 99); sender.session.HandleSendMail(request);
        CHECK(draftCOD == (count ? 99u : 0u));
        CHECK(CharacterDatabase.committed->rows[0].values.at(12) == (count ? "99" : "0")); ++cases;
    }
    reset(); { Player sender; sender.gm = true; attach(sender, 1);
        auto request = packet(1); sender.session.HandleSendMail(request);
        CHECK(CharacterDatabase.committed->rows[0].values.at(10) == "1000"); ++cases;
    }
    // Native admission failures must not move items, debit money or reach the draft hook/queue.
    for (int failure = 0; failure < 23; ++failure) {
        reset(); Player sender; attach(sender, 1); auto request = packet(1);
        Item* item = sender.inventory.at(100);
        switch (failure) {
            case 0: request.fields[6] = uint8(MAX_MAIL_ITEMS + 1); break;
            case 1: sender.interact = false; break;
            case 2: request.fields[1] = std::string(); break;
            case 3: world.trialRestrictions = true; sender.session.trial = true; break;
            case 4: sender.level = 0; break;
            case 5: cache.receiverId = 0; break;
            case 6: cache.receiverId = 1; break;
            case 7: request.fields[9] = uint32(1); request.fields[10] = uint32(1); break;
            case 8: sender.funds = 0; break;
            case 9: cache.recipient.MailCount = 101; break;
            case 10: cache.receiverAccount = 9; cache.recipient.Race = 1; break;
            case 11: request.fields[8] = ObjectGuid(); break;
            case 12: item->bag = true; break;
            case 13: item->tradable = false; break;
            case 14: item->prototype.conjured = true; break;
            case 15: item->wrapped = true; request.fields[10] = uint32(1); break;
            case 16: allowSend = false; break;
            case 17: request.fields[9] = uint32(UINT32_MAX); break; // postage overflow
            case 18: request.fields[8] = ObjectGuid(HighGuid::Player, 999); break; // absent inventory item
            case 19: item->accountBound = item->soulbound = true; cache.receiverAccount = 9; break;
            case 20: item->duration = 1; break;
            case 21: request.fields[0] = sender.GetGUID(); break; // remote mailbox permission absent
            case 22: request.fields[0] = ObjectGuid(HighGuid::Player, 500); break; // unsupported mailbox type
        }
        uint32 before = sender.funds; sender.session.HandleSendMail(request);
        CHECK(CharacterDatabase.commits == 0 && draftCalls == 0);
        CHECK(sender.moved == 0 && sender.saved == 0 && sender.funds == before);
        CHECK(sender.inventory.size() == 1); ++cases;
    }
    // Positive native permission paths still reach the same draft/send hook.
    for (int route = 0; route < 3; ++route) {
        reset(); Player sender; attach(sender, 1); auto request = packet(1);
        if (route == 0) {
            request.fields[0] = sender.GetGUID(); sender.session.permissions.insert(rbac::RBAC_PERM_COMMAND_MAILBOX);
        } else if (route == 1) {
            request.fields[0] = ObjectGuid(HighGuid::Player, 901);
        } else {
            cache.receiverAccount = 9; cache.recipient.Race = 1;
            sender.session.permissions.insert(rbac::RBAC_PERM_TWO_SIDE_INTERACTION_MAIL);
        }
        sender.session.HandleSendMail(request);
        CHECK(sender.lastResult == MAIL_OK && CharacterDatabase.commits == 1 && draftCalls == 1);
        CHECK(CharacterDatabase.committed->rows[0].values.at(10) == "4600"); ++cases;
    }
    std::cout << cases << " actual HandleSendMail cases / " << checks << " assertions PASS\n";
}
