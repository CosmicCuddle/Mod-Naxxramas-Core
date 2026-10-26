/*
 * Naxxramas Core — A02 S2c addon opt-in for Hunter pet autocast.
 *
 * Dependency-free parser, assembler, and restore plan. The worldserver
 * translation unit publishes snapshots from the chat hook and reads them
 * on the map thread. Protocol: docs/A02-ADDON-PROTOCOL.md.
 *
 * The player map is guarded by a mutex. A published snapshot is immutable.
 * Callers copy the shared_ptr under the lock and read it after the unlock.
 * This header does not include Playerbots and does not classify bots.
 */

#ifndef NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_ADDON_H
#define NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_ADDON_H

#include "HunterPetAutocastPolicy.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace NaxxramasHunterPetAutocast
{
    // ChatHandler.cpp:292 at Grimfeather 8daffda drops a chat string longer
    // than this before the script hook. 255 itself still reaches the hook.
    constexpr std::size_t kMaxRawBytes = 255;
    constexpr std::size_t kPrefixBytes = 6;
    constexpr std::size_t kTabBytes = 1;
    // PetAutocastKeeper's own send budget for the payload after the tab.
    // The server accepts any payload whose prefix + tab + payload is at
    // most kMaxRawBytes. It does not apply a second 233 cutoff.
    constexpr std::size_t kAddonPayloadBudget = 233;
    constexpr uint32_t kMaxChunks = 8;
    constexpr uint32_t kMaxPairs = 64;
    constexpr uint32_t kMaxSeq = 999999999;
    constexpr uint32_t kMaxSpellIdDigits = 10;
    constexpr uint32_t kRateLimitCount = 8;
    constexpr uint64_t kRateLimitWindowMs = 10000;

    inline constexpr char const* AddonPrefix()
    {
        return "NXCPAK";
    }

    inline std::size_t AddonPayloadBudget()
    {
        return kAddonPayloadBudget;
    }

    enum class ParseKind : uint8_t
    {
        NotOurs,
        Malformed,
        Clear,
        Chunk
    };

    enum class IngestResult : uint8_t
    {
        NotOurs,
        IgnoredNotHunter,
        RateLimited,
        Malformed,
        Cleared,
        Partial,
        Published,
        StaleSeq
    };

    struct SpellLookup
    {
        bool Autocastable = false;
        uint32_t ChainId = 0;
    };

    using SpellLookupFn = SpellLookup (*)(uint32_t spellId, void const* ctx);

    struct ParseResult
    {
        ParseKind Kind = ParseKind::NotOurs;
        uint32_t Seq = 0;
        uint32_t Index = 0;
        uint32_t Total = 0;
        std::vector<std::pair<uint32_t, bool>> Pairs;
    };

    struct ChainChoice
    {
        uint32_t ChainId = 0;
        uint32_t SpellId = 0;
        bool Enabled = false;
    };

    struct PreferenceSnapshot
    {
        uint32_t Seq = 0;
        bool OptedIn = false;
        // Strong, server-side provenance only. The legacy v1 addon payload
        // does NOT authenticate a human manual click, current pet generation,
        // or a particular player-vs-SelfBot mode. AcceptChunk NEVER sets this.
        // A future independently reviewed v2/native post-acceptance path must
        // provide genuine proof before any module autocast restore is allowed.
        bool VerifiedHumanManualOrigin = false;
        std::vector<ChainChoice> Choices;
    };

    inline bool EligibleForAutomaticRestore(PreferenceSnapshot const* preference)
    {
        return preference && preference->OptedIn && preference->VerifiedHumanManualOrigin;
    }

    struct PlannedToggle
    {
        uint32_t SpellId = 0;
        bool Enable = false;
    };

    struct AddonPlan
    {
        bool OptedIn = false;
        bool UsedDecide = false;
        std::vector<PlannedToggle> Toggles;
    };

    inline bool ParseDecimal(std::string_view text, uint32_t maxDigits, uint64_t limit, uint64_t& value)
    {
        if (text.empty() || text.size() > maxDigits)
            return false;
        if (text.size() > 1 && text[0] == '0')
            return false;
        uint64_t parsed = 0;
        for (char c : text)
        {
            if (c < '0' || c > '9')
                return false;
            parsed = parsed * 10u + static_cast<uint64_t>(c - '0');
            if (parsed > limit)
                return false;
        }
        value = parsed;
        return true;
    }

    inline bool ParsePairs(std::string_view text, std::vector<std::pair<uint32_t, bool>>& pairs)
    {
        pairs.clear();
        if (text.empty())
            return true;
        if (text.find('\t') != std::string_view::npos || text.find(' ') != std::string_view::npos)
            return false;

        while (!text.empty())
        {
            if (pairs.size() >= kMaxPairs)
                return false;
            std::size_t comma = text.find(',');
            if (comma == 0)
                return false;
            std::string_view pair = comma == std::string_view::npos ? text : text.substr(0, comma);
            if (comma == std::string_view::npos)
                text = {};
            else if (comma + 1 >= text.size())
                return false;
            else
                text.remove_prefix(comma + 1);

            std::size_t eq = pair.find('=');
            if (eq == std::string_view::npos || eq == 0 || eq + 1 >= pair.size())
                return false;
            if (pair.find('=', eq + 1) != std::string_view::npos)
                return false;
            uint64_t spellId = 0;
            if (!ParseDecimal(pair.substr(0, eq), kMaxSpellIdDigits, 4294967295ull, spellId) || spellId == 0)
                return false;
            std::string_view bit = pair.substr(eq + 1);
            if (bit != "0" && bit != "1")
                return false;
            uint32_t const id = static_cast<uint32_t>(spellId);
            for (std::pair<uint32_t, bool> const& existing : pairs)
                if (existing.first == id)
                    return false;
            pairs.push_back(std::make_pair(id, bit == "1"));
        }
        return true;
    }

    inline ParseResult ParseAddonMessage(std::string_view raw)
    {
        ParseResult result;
        constexpr std::string_view kWirePrefix("NXCPAK\t");
        if (raw.size() < kWirePrefix.size() || raw.substr(0, kWirePrefix.size()) != kWirePrefix)
            return result;
        if (raw.size() > kMaxRawBytes)
        {
            result.Kind = ParseKind::Malformed;
            return result;
        }

        std::string_view payload = raw.substr(kWirePrefix.size());
        if (payload.empty())
        {
            result.Kind = ParseKind::Malformed;
            return result;
        }
        if (payload == "v1|clear")
        {
            result.Kind = ParseKind::Clear;
            return result;
        }
        if (payload.size() < 3 || payload.substr(0, 3) != "v1|")
        {
            result.Kind = ParseKind::Malformed;
            return result;
        }

        std::string_view body = payload.substr(3);
        std::size_t bar = body.find('|');
        uint64_t seq = 0;
        if (bar == std::string_view::npos || !ParseDecimal(body.substr(0, bar), 9, kMaxSeq, seq) || seq == 0)
        {
            result.Kind = ParseKind::Malformed;
            return result;
        }
        body.remove_prefix(bar + 1);
        std::size_t slash = body.find('/');
        bar = body.find('|');
        uint64_t index = 0;
        uint64_t total = 0;
        if (slash == std::string_view::npos || bar == std::string_view::npos || slash > bar)
        {
            result.Kind = ParseKind::Malformed;
            return result;
        }
        if (!ParseDecimal(body.substr(0, slash), 1, kMaxChunks, index) || index == 0
            || !ParseDecimal(body.substr(slash + 1, bar - slash - 1), 1, kMaxChunks, total) || total == 0
            || index > total)
        {
            result.Kind = ParseKind::Malformed;
            return result;
        }
        if (!ParsePairs(body.substr(bar + 1), result.Pairs))
        {
            result.Kind = ParseKind::Malformed;
            return result;
        }

        result.Kind = ParseKind::Chunk;
        result.Seq = static_cast<uint32_t>(seq);
        result.Index = static_cast<uint32_t>(index);
        result.Total = static_cast<uint32_t>(total);
        return result;
    }

    inline ChainChoice const* FindChoice(PreferenceSnapshot const& snapshot, uint32_t chainId)
    {
        for (ChainChoice const& choice : snapshot.Choices)
            if (choice.ChainId == chainId)
                return &choice;
        return nullptr;
    }

    inline void PushToggle(std::vector<PlannedToggle>& toggles, uint32_t spellId, bool enable)
    {
        if (spellId == 0)
            return;
        for (PlannedToggle const& toggle : toggles)
            if (toggle.SpellId == spellId)
                return;
        PlannedToggle toggle;
        toggle.SpellId = spellId;
        toggle.Enable = enable;
        toggles.push_back(toggle);
    }

    // A new generation applies listed chains onto spells the pet has now,
    // including Cower 1742 when that spell is present. The same generation
    // applies again only where DecideChains reports a rank replacement.
    // Unlisted spells and spells the pet does not have produce no toggle
    // and are not learned. A null snapshot produces no toggle and does not
    // call DecideChains.
    inline AddonPlan BuildAddonPlan(
        std::vector<SpellView> const& baseline,
        std::vector<SpellView> const& live,
        PreferenceSnapshot const* optIn,
        uint64_t publishedGeneration,
        uint64_t appliedGeneration,
        ExpensiveWork* work = nullptr)
    {
        AddonPlan plan;
        if (!optIn || !optIn->OptedIn)
            return plan;

        plan.OptedIn = true;
        bool const fresh = appliedGeneration != publishedGeneration;
        if (fresh)
        {
            for (SpellView const& spell : live)
            {
                if (!spell.Present || !spell.Autocastable)
                    continue;
                ChainChoice const* choice = FindChoice(*optIn, spell.ChainId);
                if (!choice)
                    continue;
                bool const isOn = spell.Active == ACT_ENABLED;
                if (isOn == choice->Enabled)
                    continue;
                PushToggle(plan.Toggles, spell.SpellId, choice->Enabled);
            }
            return plan;
        }

        std::vector<ChainOutcome> outcomes = DecideChains(baseline, live, true, true, true, work);
        plan.UsedDecide = true;
        for (ChainOutcome const& outcome : outcomes)
        {
            bool const wantRestore = outcome.Result == Outcome::RestoreEnabled
                || outcome.Result == Outcome::RestoreDisabled;
            if (!wantRestore)
                continue;
            ChainChoice const* choice = FindChoice(*optIn, outcome.ChainId);
            if (!choice)
                continue;
            SpellView const* slot = nullptr;
            for (SpellView const& spell : live)
                if (spell.SpellId == outcome.SuccessorSpellId)
                    slot = &spell;
            if (!slot || !slot->Present || !slot->Autocastable)
                continue;
            bool const isOn = slot->Active == ACT_ENABLED;
            if (isOn == choice->Enabled)
                continue;
            PushToggle(plan.Toggles, slot->SpellId, choice->Enabled);
        }
        return plan;
    }

    class OptInStore
    {
    public:
        IngestResult Accept(
            uint64_t guid,
            bool isHunter,
            std::string_view raw,
            uint64_t nowMs,
            SpellLookupFn lookup,
            void const* ctx)
        {
            ParseResult parsed = ParseAddonMessage(raw);
            if (parsed.Kind == ParseKind::NotOurs)
                return IngestResult::NotOurs;
            if (!isHunter)
                return IngestResult::IgnoredNotHunter;

            std::lock_guard<std::mutex> guard(mutex_);
            PlayerSlot& slot = slots_[guid];
            if (!Allow(slot, nowMs))
                return IngestResult::RateLimited;
            if (parsed.Kind == ParseKind::Malformed)
                return IngestResult::Malformed;
            if (parsed.Kind == ParseKind::Clear)
            {
                ClearSlot(slot);
                return IngestResult::Cleared;
            }
            return AcceptChunk(slot, parsed, lookup, ctx);
        }

        // Copies the immutable snapshot. The returned generation is 0 when
        // this guid has no slot. A cleared slot has a generation and a null
        // snapshot. The map thread reads the shared_ptr after this returns.
        uint64_t Read(uint64_t guid, std::shared_ptr<PreferenceSnapshot const>& out) const
        {
            std::lock_guard<std::mutex> guard(mutex_);
            auto itr = slots_.find(guid);
            if (itr == slots_.end())
            {
                out.reset();
                return 0;
            }
            out = itr->second.Published;
            return itr->second.Generation;
        }

        void OnLogin(uint64_t guid)
        {
            std::lock_guard<std::mutex> guard(mutex_);
            auto itr = slots_.find(guid);
            if (itr == slots_.end())
                return;
            itr->second.Tracking = false;
            itr->second.LastSeq = 0;
            itr->second.Partial.Reset();
        }

        void OnLogout(uint64_t guid)
        {
            std::lock_guard<std::mutex> guard(mutex_);
            slots_.erase(guid);
        }

        void ClearAll()
        {
            std::lock_guard<std::mutex> guard(mutex_);
            slots_.clear();
        }

    private:
        struct ChunkSlot
        {
            bool Present = false;
            std::vector<std::pair<uint32_t, bool>> Pairs;
        };

        struct PartialAssembly
        {
            uint32_t Seq = 0;
            uint32_t Total = 0;
            std::vector<ChunkSlot> Chunks;

            void Reset()
            {
                Seq = 0;
                Total = 0;
                Chunks.clear();
            }
        };

        struct PlayerSlot
        {
            bool Tracking = false;
            uint32_t LastSeq = 0;
            PartialAssembly Partial;
            uint64_t Generation = 0;
            std::shared_ptr<PreferenceSnapshot const> Published;
            bool RateStarted = false;
            uint64_t RateWindowStart = 0;
            uint32_t RateCount = 0;
        };

        static bool Allow(PlayerSlot& slot, uint64_t nowMs)
        {
            if (!slot.RateStarted || nowMs < slot.RateWindowStart
                || nowMs - slot.RateWindowStart >= kRateLimitWindowMs)
            {
                slot.RateStarted = true;
                slot.RateWindowStart = nowMs;
                slot.RateCount = 1;
                return true;
            }
            if (slot.RateCount >= kRateLimitCount)
                return false;
            ++slot.RateCount;
            return true;
        }

        static void ClearSlot(PlayerSlot& slot)
        {
            slot.Partial.Reset();
            slot.Tracking = false;
            slot.LastSeq = 0;
            ++slot.Generation;
            slot.Published.reset();
        }

        static bool SamePairs(
            std::vector<std::pair<uint32_t, bool>> const& left,
            std::vector<std::pair<uint32_t, bool>> const& right)
        {
            if (left.size() != right.size())
                return false;
            for (std::size_t i = 0; i < left.size(); ++i)
                if (left[i].first != right[i].first || left[i].second != right[i].second)
                    return false;
            return true;
        }

        static IngestResult AcceptChunk(
            PlayerSlot& slot,
            ParseResult const& parsed,
            SpellLookupFn lookup,
            void const* ctx)
        {
            uint32_t const seq = parsed.Seq;
            if (slot.Tracking && seq < slot.LastSeq)
                return IngestResult::StaleSeq;
            if (slot.Tracking && seq == slot.LastSeq && slot.Partial.Seq != seq)
                return IngestResult::StaleSeq;
            if (slot.Partial.Seq != 0 && seq != slot.Partial.Seq)
            {
                if (seq > slot.Partial.Seq)
                    slot.Partial.Reset();
                else
                    return IngestResult::StaleSeq;
            }

            if (slot.Partial.Seq == 0)
            {
                slot.Partial.Seq = seq;
                slot.Partial.Total = parsed.Total;
                slot.Partial.Chunks.assign(parsed.Total, ChunkSlot{});
            }
            else if (slot.Partial.Total != parsed.Total)
            {
                slot.Partial.Reset();
                return IngestResult::Malformed;
            }

            ChunkSlot& chunk = slot.Partial.Chunks[parsed.Index - 1];
            if (chunk.Present)
            {
                if (SamePairs(chunk.Pairs, parsed.Pairs))
                    return IngestResult::Partial;
                slot.Partial.Reset();
                return IngestResult::Malformed;
            }
            chunk.Present = true;
            chunk.Pairs = parsed.Pairs;

            for (ChunkSlot const& part : slot.Partial.Chunks)
                if (!part.Present)
                    return IngestResult::Partial;

            std::vector<std::pair<uint32_t, bool>> merged;
            for (ChunkSlot const& part : slot.Partial.Chunks)
            {
                for (std::pair<uint32_t, bool> const& pair : part.Pairs)
                {
                    if (merged.size() >= kMaxPairs)
                    {
                        slot.Partial.Reset();
                        return IngestResult::Malformed;
                    }
                    bool duplicate = false;
                    for (std::pair<uint32_t, bool> const& existing : merged)
                        if (existing.first == pair.first)
                            duplicate = true;
                    if (duplicate)
                    {
                        slot.Partial.Reset();
                        return IngestResult::Malformed;
                    }
                    merged.push_back(pair);
                }
            }

            auto snapshot = std::make_shared<PreferenceSnapshot>();
            snapshot->Seq = seq;
            snapshot->OptedIn = true;
            if (lookup)
            {
                for (std::pair<uint32_t, bool> const& pair : merged)
                {
                    SpellLookup looked = lookup(pair.first, ctx);
                    if (!looked.Autocastable || looked.ChainId == 0)
                        continue;
                    bool replaced = false;
                    for (ChainChoice& choice : snapshot->Choices)
                    {
                        if (choice.ChainId != looked.ChainId)
                            continue;
                        choice.SpellId = pair.first;
                        choice.Enabled = pair.second;
                        replaced = true;
                        break;
                    }
                    if (replaced)
                        continue;
                    ChainChoice choice;
                    choice.ChainId = looked.ChainId;
                    choice.SpellId = pair.first;
                    choice.Enabled = pair.second;
                    snapshot->Choices.push_back(choice);
                }
            }

            slot.Published = snapshot;
            ++slot.Generation;
            slot.Tracking = true;
            slot.LastSeq = seq;
            slot.Partial.Reset();
            return IngestResult::Published;
        }

        mutable std::mutex mutex_;
        std::unordered_map<uint64_t, PlayerSlot> slots_;
    };
}

#endif
