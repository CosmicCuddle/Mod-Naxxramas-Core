// F14 P5 test stub: PlayerbotAIConfig.h L107 (Enabled) and L533 (macro).
#ifndef F14_STUB_PLAYERBOT_AI_CONFIG_H
#define F14_STUB_PLAYERBOT_AI_CONFIG_H
struct PlayerbotAIConfig
{
    bool Enabled = true;
    static PlayerbotAIConfig& Instance()
    {
        static PlayerbotAIConfig config;
        return config;
    }
};
#define sPlayerbotAIConfig PlayerbotAIConfig::Instance()
#endif
