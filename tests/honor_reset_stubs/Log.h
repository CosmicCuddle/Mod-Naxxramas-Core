// P10 test stub: counts LOG_INFO lines.
#ifndef P10_STUB_LOG_H
#define P10_STUB_LOG_H
inline int StubLogInfoCount = 0;
#define LOG_INFO(filter, ...) (++StubLogInfoCount)
#endif
