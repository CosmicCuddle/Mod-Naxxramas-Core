#ifndef NAXXRAMAS_CORE_GOLEMAGG_ACTION_AUDIT_ALLOWLIST_H
#define NAXXRAMAS_CORE_GOLEMAGG_ACTION_AUDIT_ALLOWLIST_H

#include <algorithm>
#include <cctype>
#include <string>

// Pure standard-C++ policy: exact one-character-name opt-in, no wildcards.
// This does NOT identify or authenticate a bot; caller independently verifies
// that PlayerbotAI reports an eligible Altbot. ASCII names match ignoring case.
namespace NaxxramasGolemaggActionAudit
{
    inline bool IsAllowedBotName(std::string const& actual,
                                 std::string const& configured)
    {
        size_t const first = configured.find_first_not_of(" \t\r\n");
        if (first == std::string::npos)
            return false;

        size_t const last = configured.find_last_not_of(" \t\r\n");
        std::string const expected = configured.substr(first, last - first + 1);
        if (expected.empty() || expected.size() != actual.size())
            return false;

        return std::equal(expected.begin(), expected.end(), actual.begin(),
            [](char lhs, char rhs)
            {
                return std::tolower(static_cast<unsigned char>(lhs)) ==
                       std::tolower(static_cast<unsigned char>(rhs));
            });
    }
}

#endif // NAXXRAMAS_CORE_GOLEMAGG_ACTION_AUDIT_ALLOWLIST_H
