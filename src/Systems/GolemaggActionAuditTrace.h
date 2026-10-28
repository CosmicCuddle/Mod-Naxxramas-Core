#ifndef NAXXRAMAS_CORE_GOLEMAGG_ACTION_AUDIT_TRACE_H
#define NAXXRAMAS_CORE_GOLEMAGG_ACTION_AUDIT_TRACE_H

#include <algorithm>
#include <cstddef>
#include <string>

namespace NaxxramasGolemaggActionAudit
{
    // Bound a Playerbots recent-action tail to what the audit logs: keep the
    // newest maxBytes bytes and turn line breaks into spaces. The audit runs
    // this BEFORE its duplicate check and before caching the text, so the
    // per-bot cache never holds more than maxBytes and two tails that would
    // log identically are treated as the same sample.
    inline void BoundActionTrace(std::string& trace, std::size_t maxBytes)
    {
        if (trace.size() > maxBytes)
            trace.erase(0, trace.size() - maxBytes);
        std::replace(trace.begin(), trace.end(), '\n', ' ');
        std::replace(trace.begin(), trace.end(), '\r', ' ');
    }
}

#endif // NAXXRAMAS_CORE_GOLEMAGG_ACTION_AUDIT_TRACE_H
