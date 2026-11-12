import re     as RegularExpressions
import typing as Typing

MODERN_2024_CORE_SOURCES: list[str] = [
    "XPHB",
    "XDMG",
    "XMM"
]

LEGACY_2014_CORE_SOURCES: list[str] = [
    "PHB",
    "DMG",
    "MM"
]

MODERN_EQUIVALENT_MAPPING: dict[str, str] = {
    "PHB": "XPHB",
    "DMG": "XDMG",
    "MM" : "XMM"
}

SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "XPHB": "Player's Handbook (2024)",
    "XDMG": "Dungeon Master's Guide (2024)",
    "XMM" : "Monster Manual (2025)",
    "PHB" : "Player's Handbook (2014)",
    "DMG" : "Dungeon Master's Guide (2014)",
    "MM"  : "Monster Manual (2014)",
    "VGM" : "Volo's Guide to Monsters",
    "MTF" : "Mordenkainen's Tome of Foes",
    "SCAG": "Sword Coast Adventurer's Guide",
    "XGE" : "Xanathar's Guide to Everything",
    "TCE" : "Tasha's Cauldron of Everything",
    "MPMM": "Mordenkainen Presents: Monsters of the Multiverse",
    "FTD" : "Fizban's Treasury of Dragons",
    "BGG" : "Bigby Presents: Glory of the Giants"
}

class SourceFilterService:
    def NormalizeSource(self, SourceCode: str) -> str:
        return SourceCode.strip().upper()

    def IsSource2024(self, SourceCode: str) -> bool:
        Normalized: str = self.NormalizeSource(SourceCode)
        if (Normalized == "XGE"):
            return False

        elif (Normalized in MODERN_2024_CORE_SOURCES):
            return True

        elif Normalized.startswith("X"):
            return True

        return False

    def IsLegacySource(self, SourceCode: str) -> bool:
        return not self.IsSource2024(SourceCode)

    def IsCoreLegacySource(self, SourceCode: str) -> bool:
        Normalized: str = self.NormalizeSource(SourceCode)
        return (Normalized in LEGACY_2014_CORE_SOURCES)

    def GetModernEquivalentSource(self, SourceCode: str) -> Typing.Optional[str]:
        Normalized: str = self.NormalizeSource(SourceCode)
        return MODERN_EQUIVALENT_MAPPING.get(Normalized)

    def GetSourceDisplayName(self, SourceCode: str) -> str:
        Normalized: str = self.NormalizeSource(SourceCode)
        return SOURCE_DISPLAY_NAMES.get(Normalized, Normalized)

    def ShouldShowLegacyNudge(self, SourceCode: str, RuleSetEnforcementMode: str = "Standard") -> bool:
        if (RuleSetEnforcementMode == "LegacyOnly"):
            return False

        return self.IsLegacySource(SourceCode)

    def GenerateLegacyNudgeWarning(self, SourceCode: str, EntryName: str = "", EntityCategory: str = "Content") -> Typing.Optional[str]:
        Normalized      : str                   = self.NormalizeSource(SourceCode)
        ModernEquivalent: Typing.Optional[str] = self.GetModernEquivalentSource(Normalized)
        DisplayName     : str                   = self.GetSourceDisplayName(Normalized)

        if (ModernEquivalent is not None):
            ModernDisplay: str = self.GetSourceDisplayName(ModernEquivalent)
            return f"This entry is from the 2014 Core Rules (`{Normalized}` - {DisplayName}). A revised 2024 version (`{ModernEquivalent}` - {ModernDisplay}) is available. Consider using the 2024 version for compatibility with this server."

        return f"This entry is sourced from legacy material (`{Normalized}` - {DisplayName}). D&D 2024 content is recommended for this server."

    def GetSourceRank(self, SourceCode: str) -> int:
        Normalized: str = self.NormalizeSource(SourceCode)
        if (Normalized == "XGE"):
            return 3

        elif (Normalized in MODERN_2024_CORE_SOURCES):
            return 0

        elif Normalized.startswith("X"):
            return 1

        elif Normalized in ("MPMM", "FTD", "BGG", "TCE"):
            return 2

        elif Normalized in ("SCAG", "VGM", "MTF", "ERLW", "EGW"):
            return 3

        elif (Normalized in LEGACY_2014_CORE_SOURCES):
            return 4

        return 5

    def PrioritizeRecords(self, RecordsList: list[dict[str, Typing.Any]]) -> list[dict[str, Typing.Any]]:
        def ExtractSortKey(Record: dict[str, Typing.Any]) -> int:
            SourceValue: str = str(Record.get("source", ""))
            return self.GetSourceRank(SourceValue)

        return sorted(RecordsList, key = ExtractSortKey)

    def SelectPreferredRecord(self, RecordsList: list[dict[str, Typing.Any]]) -> Typing.Optional[dict[str, Typing.Any]]:
        if not RecordsList:
            return None

        PrioritizedList: list[dict[str, Typing.Any]] = self.PrioritizeRecords(RecordsList)
        return PrioritizedList[0]

    def PrioritizeCandidateNames(self, CandidateNames: list[str]) -> list[str]:
        def ExtractNameRank(NameString: str) -> int:
            LowerName: str = NameString.lower()
            if ("(2024)" in LowerName) or ("xphb" in LowerName) or ("xdmg" in LowerName) or ("xmm" in LowerName):
                return 0

            elif ("(2014)" in LowerName) or ("phb" in LowerName) or ("dmg" in LowerName) or ("mm" in LowerName):
                return 2

            return 1

        return sorted(CandidateNames, key = ExtractNameRank)

GLOBAL_SOURCE_FILTER: SourceFilterService = SourceFilterService()
