// B09 test stub: records each LOG_ERROR / LOG_INFO with its format string.
#ifndef B09_STUB_LOG_H
#define B09_STUB_LOG_H
#include <string>
#include <vector>

struct StubLogLine
{
    std::string level;
    std::string text;
};

inline std::vector<StubLogLine>& StubLogLines()
{
    static std::vector<StubLogLine> lines;
    return lines;
}

template <typename... Args>
inline void StubLogRecord(char const* level, char const* /*filter*/, char const* text, Args&&...)
{
    StubLogLines().push_back({level, text});
}

#define LOG_ERROR(filter, ...) StubLogRecord("ERROR", filter, __VA_ARGS__)
#define LOG_INFO(filter, ...) StubLogRecord("INFO", filter, __VA_ARGS__)
#endif
