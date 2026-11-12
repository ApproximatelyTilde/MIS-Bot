import Runtime.Services.Compendium.SourceFilterService as SourceFilter

class TestCompendiumSourceFilter:
    def TestNormalizeSource(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        assert (FilterService.NormalizeSource(" xphb ") == "XPHB")
        assert (FilterService.NormalizeSource("phb") == "PHB")

    def TestIsSource2024(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        assert (FilterService.IsSource2024("XPHB") is True)
        assert (FilterService.IsSource2024("XDMG") is True)
        assert (FilterService.IsSource2024("XMM") is True)
        assert (FilterService.IsSource2024("XGE") is False)
        assert (FilterService.IsSource2024("PHB") is False)
        assert (FilterService.IsSource2024("DMG") is False)

    def TestIsLegacySourceAndCoreLegacy(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        assert (FilterService.IsLegacySource("PHB") is True)
        assert (FilterService.IsLegacySource("XPHB") is False)
        assert (FilterService.IsCoreLegacySource("PHB") is True)
        assert (FilterService.IsCoreLegacySource("DMG") is True)
        assert (FilterService.IsCoreLegacySource("MM") is True)
        assert (FilterService.IsCoreLegacySource("VGM") is False)

    def TestGetModernEquivalentSource(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        assert (FilterService.GetModernEquivalentSource("PHB") == "XPHB")
        assert (FilterService.GetModernEquivalentSource("DMG") == "XDMG")
        assert (FilterService.GetModernEquivalentSource("MM") == "XMM")
        assert (FilterService.GetModernEquivalentSource("TCE") is None)

    def TestGetSourceDisplayName(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        assert (FilterService.GetSourceDisplayName("XPHB") == "Player's Handbook (2024)")
        assert (FilterService.GetSourceDisplayName("PHB") == "Player's Handbook (2014)")
        assert (FilterService.GetSourceDisplayName("CUSTOM") == "CUSTOM")

    def TestShouldShowLegacyNudge(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        assert (FilterService.ShouldShowLegacyNudge("PHB", "Standard") is True)
        assert (FilterService.ShouldShowLegacyNudge("XPHB", "Standard") is False)
        assert (FilterService.ShouldShowLegacyNudge("PHB", "LegacyOnly") is False)

    def TestGenerateLegacyNudgeWarning(self) -> None:
        FilterService    : SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        WarningWithModern: str                              = FilterService.GenerateLegacyNudgeWarning("PHB", "Fireball", "Spell")
        assert ("2014 Core Rules" in WarningWithModern)
        assert ("XPHB" in WarningWithModern)

        WarningWithoutModern: str = FilterService.GenerateLegacyNudgeWarning("VGM", "Tabaxi", "Race")
        assert ("legacy material" in WarningWithoutModern)

    def TestPrioritizeRecords(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        RecordPHB: dict[str, str] = {
            "name"  : "Invisibility",
            "source": "PHB"
        }
        RecordXPHB: dict[str, str] = {
            "name"  : "Invisibility",
            "source": "XPHB"
        }
        RecordTCE: dict[str, str] = {
            "name"  : "Invisibility",
            "source": "TCE"
        }

        PrioritizedList: list[dict[str, str]] = FilterService.PrioritizeRecords([RecordPHB, RecordXPHB, RecordTCE])
        assert (PrioritizedList[0]["source"] == "XPHB")
        assert (PrioritizedList[1]["source"] == "TCE")
        assert (PrioritizedList[2]["source"] == "PHB")

    def TestSelectPreferredRecord(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        RecordLegacy : dict[str, str] = {
            "name"  : "Shield",
            "source": "PHB"
        }
        RecordModern : dict[str, str] = {
            "name"  : "Shield",
            "source": "XPHB"
        }

        PreferredRecord: dict[str, str] = FilterService.SelectPreferredRecord([RecordLegacy, RecordModern])
        assert (PreferredRecord is not None)
        assert (PreferredRecord["source"] == "XPHB")

        assert (FilterService.SelectPreferredRecord([]) is None)

    def TestPrioritizeCandidateNames(self) -> None:
        FilterService: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()
        NamesList    : list[str]                        = ["Fireball (2014)", "Fireball (2024)", "Fireball (Homebrew)"]
        SortedNames  : list[str]                        = FilterService.PrioritizeCandidateNames(NamesList)
        assert (SortedNames[0] == "Fireball (2024)")
        assert (SortedNames[1] == "Fireball (Homebrew)")
        assert (SortedNames[2] == "Fireball (2014)")
