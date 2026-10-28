// B09 test stub: fixed-width aliases the real AzerothCore Define.h provides.
#ifndef B09_STUB_DEFINE_H
#define B09_STUB_DEFINE_H
#include <cstdint>
using int32 = std::int32_t;
using uint8 = std::uint8_t;
using uint16 = std::uint16_t;
using uint32 = std::uint32_t;
using uint64 = std::uint64_t;
#endif
