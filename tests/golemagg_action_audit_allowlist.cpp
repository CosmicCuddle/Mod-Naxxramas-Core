#include "GolemaggActionAuditAllowlist.h"

#include <cassert>
#include <iostream>

int main()
{
    using NaxxramasGolemaggActionAudit::IsAllowedBotName;

    // No broad audit when config is unset, wildcard or list-valued.
    assert(!IsAllowedBotName("Grau", ""));
    assert(!IsAllowedBotName("Grau", "  \t\r\n"));
    assert(!IsAllowedBotName("Grau", "*"));
    assert(!IsAllowedBotName("Grau", "all"));
    assert(!IsAllowedBotName("Grau", "Grau,Krugan"));
    assert(!IsAllowedBotName("Grau", "Krugan"));

    // Exact match; no prefix, substring or accidental multiple-bot access.
    assert(IsAllowedBotName("Grau", "Grau"));
    assert(IsAllowedBotName("Grau", " gRaU \t"));
    assert(!IsAllowedBotName("GrauAlt", "Grau"));
    assert(!IsAllowedBotName("Grau", "GrauAlt"));
    assert(!IsAllowedBotName("Grau", "Gra"));
    assert(!IsAllowedBotName("Krugan", "Grau"));

    // Names ending in r/t/n must not be trimmed as whitespace characters.
    assert(IsAllowedBotName("Arndor", "  Arndor  "));
    assert(IsAllowedBotName("Hettraz", "HeTtRaZ"));
    assert(IsAllowedBotName("Rukhan", "  Rukhan  "));
    assert(!IsAllowedBotName("Arndor", "Arndo"));

    std::cout << "PASS: one-bot Golemagg diagnostic opt-in is exact and default deny\n";
}
