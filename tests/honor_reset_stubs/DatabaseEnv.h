// P10 test stub: the CharacterDatabase surface HonorReset.cpp uses
// (8daffda: Query -> QueryResult, (*result)[0].Get<uint64>(), DirectExecute
// with a format string or a prepared statement, CHAR_UPD_ALL_HONOR_POINTS).
#ifndef P10_STUB_DATABASE_ENV_H
#define P10_STUB_DATABASE_ENV_H
#include "Define.h"
#include <memory>
#include <string>
#include <vector>

enum CharacterDatabaseStatements { CHAR_UPD_ALL_HONOR_POINTS = 1 };

struct StubField
{
    uint64 value = 0;
    template <typename T> T Get() const { return static_cast<T>(value); }
};

struct StubResultSet
{
    StubField fields[1];
    StubField const& operator[](int i) const { return fields[i]; }
};

using QueryResult = std::shared_ptr<StubResultSet>;
struct StubPrepared { CharacterDatabaseStatements id; };

struct StubCharacterDatabase
{
    bool hasRow = false;
    uint64 lastReset = 0;
    std::vector<std::string> executed;
    int honorResets = 0;

    QueryResult Query(char const*)
    {
        if (!hasRow)
            return nullptr;
        auto r = std::make_shared<StubResultSet>();
        r->fields[0].value = lastReset;
        return r;
    }
    StubPrepared* GetPreparedStatement(CharacterDatabaseStatements id)
    {
        static StubPrepared p;
        p.id = id;
        return &p;
    }
    void DirectExecute(StubPrepared* p)
    {
        if (p && p->id == CHAR_UPD_ALL_HONOR_POINTS)
            ++honorResets;
    }
    template <typename... Args>
    void DirectExecute(char const* sql, uint64 value, Args&&...)
    {
        executed.push_back(sql);
        hasRow = true;
        lastReset = value;
    }
};

inline StubCharacterDatabase CharacterDatabase;
#endif
