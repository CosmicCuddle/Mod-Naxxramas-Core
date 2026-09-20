/*
 * Naxxramas Core
 *
 * Custom gameplay systems, class changes, racial changes
 * and server-specific modifications.
 */

// Warrior
void AddWarriorRendFlurryScripts();
void AddWarriorImprovedRendScripts();

// Racials
void AddOrcBloodFuryScripts();
void AddTrollBerserkingScripts();
void AddBloodElfArcaneTorrentScripts();

void Addmod_naxxramas_coreScripts()
{
    AddWarriorRendFlurryScripts();
    AddWarriorImprovedRendScripts();

    AddOrcBloodFuryScripts();
    AddTrollBerserkingScripts();
    AddBloodElfArcaneTorrentScripts();
}