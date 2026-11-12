import re                                              as RegularExpressions
import typing                                          as Typing
import discord                                         as Discord
import Runtime.Services.Compendium.SourceFilterService as SourceFilter

COLOR_COMPENDIUM_EMBED: int = 0x0030A6

TAG_REPLACE_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"\{@([a-zA-Z0-9]+)\s+([^}]+)\}")

SPELL_SCHOOL_MAPPING: dict[str, str] = {
    "A": "Abjuration",
    "C": "Conjuration",
    "D": "Divination",
    "E": "Enchantment",
    "I": "Illusion",
    "N": "Necromancy",
    "T": "Transmutation",
    "V": "Evocation"
}

SIZE_MAPPING: dict[str, str] = {
    "T": "Tiny",
    "S": "Small",
    "M": "Medium",
    "L": "Large",
    "H": "Huge",
    "G": "Gargantuan"
}

ALIGNMENT_MAPPING: dict[str, str] = {
    "L": "Lawful",
    "N": "Neutral",
    "C": "Chaotic",
    "G": "Good",
    "E": "Evil",
    "U": "Unaligned",
    "A": "Any Alignment"
}

TAGS_BOLD        : frozenset[str] = frozenset({"b", "bold"})
TAGS_ITALIC      : frozenset[str] = frozenset({"i", "italic"})
TAGS_STRIKE      : frozenset[str] = frozenset({"strike", "s"})
TAGS_CODE        : frozenset[str] = frozenset({"code", "kbd", "dice", "damage", "scaledamage", "d20"})
TAGS_TITLE_BOLD  : frozenset[str] = frozenset({"spell", "creature", "item", "skill", "action", "feat", "race", "background", "class", "subclass", "variantrule", "table", "optfeature"})
TAGS_TITLE_ITALIC: frozenset[str] = frozenset({"condition", "disease", "sense", "status"})

def FormatTagMatch(TagMatch: RegularExpressions.Match) -> str:
    TagName    : str       = TagMatch.group(1).lower()
    TagContent : str       = TagMatch.group(2)
    Splitted   : list[str] = TagContent.split("|")
    PrimaryText: str       = Splitted[0].strip()

    if (TagName in TAGS_BOLD):
        return f"**{PrimaryText}**"

    elif (TagName in TAGS_ITALIC):
        return f"*{PrimaryText}*"

    elif (TagName in TAGS_STRIKE):
        return f"~~{PrimaryText}~~"

    elif (TagName in TAGS_CODE):
        return f"`{PrimaryText}`"

    elif (TagName in TAGS_TITLE_BOLD):
        return f"**{PrimaryText.title()}**"

    elif (TagName in TAGS_TITLE_ITALIC):
        return f"*{PrimaryText.title()}*"

    elif (TagName == "chance"):
        return f"{PrimaryText}%"

    elif (TagName == "recharge"):
        RechargeValue: str = PrimaryText if (len(PrimaryText) > 0) else "6"
        return f"(Recharge {RechargeValue}-6)"

    return PrimaryText

class CompendiumTagRenderer:
    def __init__(self) -> None:
        self.SourceFilter: SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()

    def RenderTags(self, RawText: str) -> str:
        return TAG_REPLACE_PATTERN.sub(FormatTagMatch, RawText)

    def RenderEntries(self, EntriesData: Typing.Any) -> str:
        if isinstance(EntriesData, str):
            return self.RenderTags(EntriesData)

        elif isinstance(EntriesData, list):
            RenderedBlocks: list[str] = []
            for SubEntry in EntriesData:
                BlockText: str = self.RenderEntries(SubEntry)
                if (len(BlockText) > 0):
                    RenderedBlocks.append(BlockText)

            return "\n\n".join(RenderedBlocks)

        elif isinstance(EntriesData, dict):
            EntryType: str = str(EntriesData.get("type", "")).lower()
            if (EntryType == "entries"):
                EntryTitle: str = str(EntriesData.get("name", "")).strip()
                SubContent: str = self.RenderEntries(EntriesData.get("entries", []))
                return f"**{EntryTitle}**\n{SubContent}" if (len(EntryTitle) > 0) else SubContent

            elif (EntryType == "list"):
                ItemsList: list[str] = [f"• {self.RenderEntries(Item)}" for Item in EntriesData.get("items", [])]
                return "\n".join(ItemsList)

            elif (EntryType in ("item", "itemsub")) or ("entry" in EntriesData):
                ItemName  : str = str(EntriesData.get("name", "")).strip()
                SubContent: str = self.RenderEntries(EntriesData.get("entry", EntriesData.get("entries", "")))
                return f"**{ItemName}** {SubContent}".strip() if (len(ItemName) > 0) else SubContent

            elif (EntryType == "inset"):
                InsetText: str = self.RenderEntries(EntriesData.get("entries", []))
                return f"> {InsetText}"

            elif (EntryType == "table") or (("colLabels" in EntriesData) and ("rows" in EntriesData)):
                CaptionText: str       = str(EntriesData.get("caption", ""))
                ColLabels  : list[str] = [str(C) for C in EntriesData.get("colLabels", [])]
                RowsList   : list[str] = []
                if ColLabels:
                    RowsList.append(" | ".join(ColLabels))
                    RowsList.append(" | ".join(["---"] * len(ColLabels)))

                for RowItem in EntriesData.get("rows", []):
                    RowString: str = " | ".join(str(self.RenderEntries(Cell)) for Cell in RowItem)
                    RowsList.append(RowString)

                TableFormatted: str = "\n".join(RowsList)
                return f"**{CaptionText}**\n{TableFormatted}" if (len(CaptionText) > 0) else TableFormatted

            elif "entries" in EntriesData:
                return self.RenderEntries(EntriesData.get("entries"))

        return ""

    def FormatSpellEmbed(self, SpellData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        SpellName : str = str(SpellData.get("name", "Unknown Spell"))
        SpellLevel: int = int(SpellData.get("level", 0))
        SchoolCode: str = str(SpellData.get("school", "V")).upper()
        SchoolName: str = SPELL_SCHOOL_MAPPING.get(SchoolCode, "Evocation")
        SourceText: str = str(SpellData.get("source", "PHB"))

        LevelHeader: str           = f"{SchoolName} cantrip" if (SpellLevel == 0) else f"{SpellLevel}-level {SchoolName}"
        SpellEmbed : Discord.Embed = Discord.Embed(title = SpellName, description = f"*{LevelHeader}*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, SpellName, "Spell")
            if (WarningNotice is not None):
                SpellEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        TimeEntries: list[dict[str, Typing.Any]] = SpellData.get("time", [])
        CastingTime: str                         = f"{TimeEntries[0].get("number", 1)} {TimeEntries[0].get("unit", "action")}" if (TimeEntries) else "1 action"
        SpellEmbed.add_field(name = "Casting Time", value = CastingTime, inline = True)

        RangeData   : dict[str, Typing.Any] = SpellData.get("range", {})
        DistanceData: dict[str, Typing.Any] = RangeData.get("distance", {})
        RangeString : str                   = f"{DistanceData.get("amount", "")} {DistanceData.get("type", "")}".strip() or str(RangeData.get("type", "Self"))
        SpellEmbed.add_field(name = "Range", value = RangeString, inline = True)

        ComponentsData: dict[str, Typing.Any] = SpellData.get("components", {})
        CompParts     : list[str]             = []
        if ComponentsData.get("v"):
            CompParts.append("V")

        if ComponentsData.get("s"):
            CompParts.append("S")

        if ComponentsData.get("m"):
            MaterialText: str = str(ComponentsData.get("m", ""))
            CompParts.append(f"M ({MaterialText})" if (MaterialText != "True") else "M")

        SpellEmbed.add_field(name = "Components", value = ", ".join(CompParts) or "None", inline = True)

        DurationList: list[dict[str, Typing.Any]] = SpellData.get("duration", [])
        DurationText: str                         = "Instantaneous"
        if DurationList:
            FirstDur: dict[str, Typing.Any] = DurationList[0]
            if (FirstDur.get("type") == "timed"):
                DurationAmount     : Typing.Any = FirstDur.get("duration", {})
                ConcentrationPrefix: Typing.Any = "Concentration, up to " if (FirstDur.get("concentration")) else ""
                DurationText                    = f"{ConcentrationPrefix}{DurationAmount.get("amount", 1)} {DurationAmount.get("type", "minute")}"

            elif (FirstDur.get("type") == "instant"):
                DurationText = "Instantaneous"

        SpellEmbed.add_field(name = "Duration", value = DurationText, inline = True)

        DescriptionText: str = self.RenderEntries(SpellData.get("entries", []))
        if (len(DescriptionText) > 1024):
            SpellEmbed.add_field(name = "Description", value = DescriptionText[:1020] + "…", inline = False)

        else:
            SpellEmbed.add_field(name = "Description", value = DescriptionText, inline = False)

        HigherLevelsData: Typing.Any = SpellData.get("entriesHigherLevel")
        if HigherLevelsData:
            HigherText: str = self.RenderEntries(HigherLevelsData)
            SpellEmbed.add_field(name = "At Higher Levels", value = HigherText[:1020], inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            SpellEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            SpellEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            SpellEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return SpellEmbed

    def FormatMonsterEmbed(self, MonsterData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        MonsterName: str        = str(MonsterData.get("name", "Unknown Creature"))
        SizeCodes  : list[str]  = MonsterData.get("size", ["M"])
        SizeName   : str        = SIZE_MAPPING.get(SizeCodes[0], "Medium") if (SizeCodes) else "Medium"
        TypeData   : Typing.Any = MonsterData.get("type", "beast")
        TypeName   : str        = TypeData.get("type", "beast") if (isinstance(TypeData, dict)) else str(TypeData)
        SourceText : str        = str(MonsterData.get("source", "MM"))

        Subtitle    : str           = f"{SizeName} {TypeName}"
        MonsterEmbed: Discord.Embed = Discord.Embed(title = MonsterName, description = f"*{Subtitle}*", color = COLOR_COMPENDIUM_EMBED)

        if (RuleSetEnforcementMode == "Strict2024") and self.SourceFilter.IsLegacySource(SourceText):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, MonsterName, "Monster")
            if (WarningNotice is not None):
                MonsterEmbed.add_field(name = "⚠️ Legacy Monster Notice", value = WarningNotice, inline = False)

        ACData : list[Typing.Any] = MonsterData.get("ac", [10])
        ACValue: str              = str(ACData[0].get("ac") if (isinstance(ACData[0], dict)) else ACData[0]) if (ACData) else "10"
        MonsterEmbed.add_field(name = "Armor Class", value = ACValue, inline = True)

        HPData : dict[str, Typing.Any] = MonsterData.get("hp", {})
        HPValue: str                   = f"{HPData.get("average", 10)} ({HPData.get("formula", "")})" if (HPData) else "10"
        MonsterEmbed.add_field(name = "Hit Points", value = HPValue, inline = True)

        CRData : Typing.Any = MonsterData.get("cr", "0")
        CRValue: str        = str(CRData.get("cr") if (isinstance(CRData, dict)) else CRData)
        MonsterEmbed.add_field(name = "Challenge", value = CRValue, inline = True)

        STRScore: int = int(MonsterData.get("str", 10))
        DEXScore: int = int(MonsterData.get("dex", 10))
        CONScore: int = int(MonsterData.get("con", 10))
        INTScore: int = int(MonsterData.get("int", 10))
        WISScore: int = int(MonsterData.get("wis", 10))
        CHAScore: int = int(MonsterData.get("cha", 10))

        def FormatModifier(ScoreValue: int) -> str:
            Modifier: int = (ScoreValue - 10) // 2
            return f"{ScoreValue} ({"+" if (Modifier >= 0) else ""}{Modifier})"

        AbilityBlock: str = f"**STR** {FormatModifier(STRScore)} | **DEX** {FormatModifier(DEXScore)} | **CON** {FormatModifier(CONScore)}\n**INT** {FormatModifier(INTScore)} | **WIS** {FormatModifier(WISScore)} | **CHA** {FormatModifier(CHAScore)}"
        MonsterEmbed.add_field(name = "Ability Scores", value = AbilityBlock, inline = False)

        TraitsList  : list[dict[str, Typing.Any]] = MonsterData.get("trait", [])
        if TraitsList:
            TraitStrings: list[str] = [f"**{T.get("name")}**: {self.RenderEntries(T.get("entries", []))}" for T in TraitsList[:4]]
            MonsterEmbed.add_field(name = "Traits", value = "\n\n".join(TraitStrings)[:1020], inline = False)

        ActionsList : list[dict[str, Typing.Any]] = MonsterData.get("action", [])
        if ActionsList:
            ActionStrings: list[str] = [f"**{A.get("name")}**: {self.RenderEntries(A.get("entries", []))}" for A in ActionsList[:5]]
            MonsterEmbed.add_field(name = "Actions", value = "\n\n".join(ActionStrings)[:1020], inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            MonsterEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024/2025)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            MonsterEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            MonsterEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return MonsterEmbed

    def FormatItemEmbed(self, ItemData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        ItemName  : str           = str(ItemData.get("name", "Unknown Item"))
        RarityText: str           = str(ItemData.get("rarity", "common")).capitalize()
        SourceText: str           = str(ItemData.get("source", "DMG"))
        ItemEmbed : Discord.Embed = Discord.Embed(title = ItemName, description = f"*{RarityText}*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, ItemName, "Item")
            if (WarningNotice is not None):
                ItemEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        WeightValue: Typing.Any = ItemData.get("weight")
        if (WeightValue is not None):
            ItemEmbed.add_field(name = "Weight", value = f"{WeightValue} lbs", inline = True)

        ValueAmount: Typing.Any = ItemData.get("value")
        if (ValueAmount is not None):
            ItemEmbed.add_field(name = "Value", value = f"{ValueAmount} cp", inline = True)

        DescText    : str = self.RenderEntries(ItemData.get("entries", []))
        if DescText:
            ItemEmbed.add_field(name = "Description", value = DescText[:1020], inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            ItemEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            ItemEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            ItemEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return ItemEmbed

    def FormatFeatureEmbed(self, FeatureData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        FeatureName : str = str(FeatureData.get("name", "Unknown Feat"))
        SourceText  : str = str(FeatureData.get("source", "PHB"))
        CategoryCode: str = str(FeatureData.get("category", "")).upper()
        CategoryMap : dict[str, str] = {
            "O": "Origin Feat",
            "G": "General Feat",
            "F": "Fighting Style Feat",
            "E": "Epic Boon Feat"
        }
        CategoryName: str           = CategoryMap.get(CategoryCode, "Feat")
        FeatureEmbed: Discord.Embed = Discord.Embed(title = FeatureName, description = f"*{CategoryName}*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, FeatureName, "Feat")
            if (WarningNotice is not None):
                FeatureEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        PrerequisitesList: list[dict[str, Typing.Any]] = FeatureData.get("prerequisite", [])
        if PrerequisitesList:
            PrereqStrings: list[str] = []
            for PrereqItem in PrerequisitesList:
                if "level" in PrereqItem:
                    PrereqStrings.append(f"Level {PrereqItem["level"]}+")

                if "ability" in PrereqItem:
                    AbilityParts: list[str] = []
                    for AbilMap in PrereqItem["ability"]:
                        for AbilKey, ScoreValue in AbilMap.items():
                            AbilityParts.append(f"{AbilKey.upper()} {ScoreValue}+")

                    PrereqStrings.append(" or ".join(AbilityParts))

                if "feature" in PrereqItem:
                    PrereqStrings.extend(str(F) for F in PrereqItem["feature"])

                if "otherSummary" in PrereqItem:
                    SummaryData: Typing.Any = PrereqItem["otherSummary"]
                    if isinstance(SummaryData, dict):
                        PrereqStrings.append(str(SummaryData.get("entrySummary", SummaryData.get("entry", "Special"))))

                    else:
                        PrereqStrings.append(str(SummaryData))

            PrereqCombined: str = ", ".join(PrereqStrings) if (PrereqStrings) else "None"
            FeatureEmbed.add_field(name = "Prerequisites", value = PrereqCombined, inline = False)

        DescriptionText: str = self.RenderEntries(FeatureData.get("entries", []))
        if DescriptionText:
            if (len(DescriptionText) > 1024):
                FeatureEmbed.add_field(name = "Description & Benefits", value = DescriptionText[:1020] + "…", inline = False)

            else:
                FeatureEmbed.add_field(name = "Description & Benefits", value = DescriptionText, inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            FeatureEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            FeatureEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            FeatureEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return FeatureEmbed

    def FormatOptionEmbed(self, OptionData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        OptionName    : str           = str(OptionData.get("name", "Unknown Option"))
        SourceText    : str           = str(OptionData.get("source", "PHB"))
        FeatureType   : Typing.Any    = OptionData.get("featureType", OptionData.get("OptionCategory", "Option"))
        FeatureTypeStr: str           = ", ".join(FeatureType) if (isinstance(FeatureType, list)) else str(FeatureType)
        OptionEmbed   : Discord.Embed = Discord.Embed(title = OptionName, description = f"*{FeatureTypeStr}*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, OptionName, "Option")
            if (WarningNotice is not None):
                OptionEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        PrereqsData: Typing.Any = OptionData.get("prerequisite")
        if PrereqsData:
            PrereqText: str = self.RenderEntries(PrereqsData)
            OptionEmbed.add_field(name = "Prerequisites", value = PrereqText[:1020], inline = False)

        DescriptionText: str = self.RenderEntries(OptionData.get("entries", []))
        if DescriptionText:
            OptionEmbed.add_field(name = "Details", value = DescriptionText[:1020], inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            OptionEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            OptionEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            OptionEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return OptionEmbed

    def FormatRuleEmbed(self, RuleData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        RuleName  : str           = str(RuleData.get("name", "Unknown Rule"))
        SourceText: str           = str(RuleData.get("source", "XPHB"))
        RuleType  : str           = str(RuleData.get("RuleType", RuleData.get("ruleType", "Rule")))
        RuleEmbed : Discord.Embed = Discord.Embed(title = RuleName, description = f"*{RuleType}*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, RuleName, "Rule")
            if (WarningNotice is not None):
                RuleEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        if ("colLabels" in RuleData) and ("rows" in RuleData):
            ColLabels : list[str]              = [str(C) for C in RuleData.get("colLabels", [])]
            RowsList  : list[list[Typing.Any]] = RuleData.get("rows", [])
            TableLines: list[str]              = []
            if ColLabels:
                TableLines.append(" | ".join(ColLabels))
                TableLines.append(" | ".join(["---"] * len(ColLabels)))

            for Row in RowsList:
                RenderedCells: list[str] = [self.RenderEntries(Cell) for Cell in Row]
                TableLines.append(" | ".join(RenderedCells))

            TableBody: str = "\n".join(TableLines)
            if (len(TableBody) > 1024):
                TableBody = TableBody[:1020] + "…"

            RuleEmbed.add_field(name = "Table Data", value = TableBody, inline = False)

        EntriesData: Typing.Any = RuleData.get("entries")
        if EntriesData:
            DescriptionText: str = self.RenderEntries(EntriesData)
            if (len(DescriptionText) > 1024):
                RuleEmbed.add_field(name = "Rule Glossary Text", value = DescriptionText[:1020] + "…", inline = False)

            else:
                RuleEmbed.add_field(name = "Rule Glossary Text", value = DescriptionText, inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            RuleEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            RuleEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            RuleEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return RuleEmbed

    def FormatClassEmbed(self, ClassData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        ClassName : str                   = str(ClassData.get("name", "Unknown Class"))
        SourceText: str                   = str(ClassData.get("source", "PHB"))
        HDData    : dict[str, Typing.Any] = ClassData.get("hd", {})
        HDFaces   : int                   = int(HDData.get("faces", 8))
        ClassEmbed: Discord.Embed         = Discord.Embed(title = ClassName, description = f"*Hit Die: 1d{HDFaces}*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, ClassName, "Class")
            if (WarningNotice is not None):
                ClassEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        PrimaryAbilList: list[dict[str, Typing.Any]] = ClassData.get("primaryAbility", [])
        if PrimaryAbilList:
            AbilOptions: list[str] = []
            for OptionDictionary in PrimaryAbilList:
                AbilOptions.append("/".join(K.upper() for K in OptionDictionary.keys()))

            ClassEmbed.add_field(name = "Primary Ability", value = ", ".join(AbilOptions), inline = True)

        SavesList: list[str] = [S.upper() for S in ClassData.get("proficiency", [])]
        if SavesList:
            ClassEmbed.add_field(name = "Saving Throws", value = ", ".join(SavesList), inline = True)

        StartingProfs: dict[str, Typing.Any] = ClassData.get("startingProficiencies", {})
        ArmorList    : list[str]             = StartingProfs.get("armor", [])
        if ArmorList:
            ClassEmbed.add_field(name = "Armor Training", value = ", ".join(str(A).title() for A in ArmorList), inline = True)

        WeaponList: list[str] = StartingProfs.get("weapons", [])
        if WeaponList:
            ClassEmbed.add_field(name = "Weapon Training", value = ", ".join(str(W).title() for W in WeaponList), inline = True)

        SubclassesList: list[str] = ClassData.get("AvailableSubclasses", [])
        if SubclassesList:
            ClassEmbed.add_field(name = "Subclasses", value = ", ".join(SubclassesList[:8]), inline = False)

        FeaturesList: list[dict[str, Typing.Any]] = ClassData.get("classFeatures", [])
        if FeaturesList:
            FeatureNames: list[str] = []
            for FeatureRef in FeaturesList[:6]:
                FeatureStr: str = str(FeatureRef if (isinstance(FeatureRef, str)) else FeatureRef.get("classFeature", ""))
                BaseName  : str = FeatureStr.split("|")[0]
                if BaseName and (BaseName not in FeatureNames):
                    FeatureNames.append(BaseName)

            if FeatureNames:
                ClassEmbed.add_field(name = "Core Features", value = ", ".join(FeatureNames), inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            ClassEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            ClassEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            ClassEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return ClassEmbed

    def FormatSubclassEmbed(self, SubclassData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        SubclassName : str           = str(SubclassData.get("name", "Unknown Subclass"))
        ClassName    : str           = str(SubclassData.get("className", SubclassData.get("class", "Unknown Class")))
        SourceText   : str           = str(SubclassData.get("source", "PHB"))
        SubclassEmbed: Discord.Embed = Discord.Embed(title = f"{SubclassName} ({ClassName})", description = f"*{ClassName} Subclass*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, SubclassName, "Subclass")
            if (WarningNotice is not None):
                SubclassEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        SpellAbilityValue: Typing.Optional[str] = SubclassData.get("spellcastingAbility")
        if SpellAbilityValue:
            SubclassEmbed.add_field(name = "Spellcasting Ability", value = str(SpellAbilityValue).upper(), inline = True)

        CasterProgressionValue: Typing.Optional[str] = SubclassData.get("casterProgression")
        if CasterProgressionValue:
            ProgressionTitle: str = f"{CasterProgressionValue} Caster" if ("/" in str(CasterProgressionValue)) else str(CasterProgressionValue).capitalize()
            SubclassEmbed.add_field(name = "Caster Progression", value = ProgressionTitle, inline = True)

        FeaturesList: list[Typing.Any] = SubclassData.get("subclassFeatures", [])
        if FeaturesList:
            FeatureNames: list[str] = []
            for FeatureReference in FeaturesList:
                FeatureString: str = str(FeatureReference if isinstance(FeatureReference, str) else FeatureReference.get("subclassFeature", ""))
                BaseName     : str = FeatureString.split("|")[0].strip()
                if BaseName and (BaseName not in FeatureNames):
                    FeatureNames.append(BaseName)

            if FeatureNames:
                SubclassEmbed.add_field(name = "Subclass Features", value = ", ".join(FeatureNames[:12]), inline = False)

        TableGroupsList: list[dict[str, Typing.Any]] = SubclassData.get("subclassTableGroups", [])
        for TableGroup in TableGroupsList:
            GroupTitle: str = str(TableGroup.get("title", TableGroup.get("caption", "Progression Table")))
            if ("colLabels" in TableGroup) and ("rows" in TableGroup):
                ColLabels : list[str]              = [str(ColumnItem) for ColumnItem in TableGroup.get("colLabels", [])]
                RowsList  : list[list[Typing.Any]] = TableGroup.get("rows", [])
                TableLines: list[str]              = []
                if ColLabels:
                    TableLines.append(" | ".join(ColLabels))
                    TableLines.append(" | ".join(["---"] * len(ColLabels)))

                for RowItem in RowsList:
                    RenderedCells: list[str] = [self.RenderEntries(CellItem) for CellItem in RowItem]
                    TableLines.append(" | ".join(RenderedCells))

                TableBody: str = "\n".join(TableLines)
                if (len(TableBody) > 1024):
                    TableBody = TableBody[:1020] + "…"

                SubclassEmbed.add_field(name = GroupTitle, value = TableBody, inline = False)

        EntriesData: Typing.Any = SubclassData.get("entries")
        if EntriesData:
            DescriptionText: str = self.RenderEntries(EntriesData)
            if (len(DescriptionText) > 1024):
                SubclassEmbed.add_field(name = "Description & Overview", value = DescriptionText[:1020] + "…", inline = False)

            else:
                SubclassEmbed.add_field(name = "Description & Overview", value = DescriptionText, inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            SubclassEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            SubclassEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            SubclassEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return SubclassEmbed

    def FormatBackgroundEmbed(self, BackgroundData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        BackgroundName: str           = str(BackgroundData.get("name", "Unknown Background"))
        SourceText    : str           = str(BackgroundData.get("source", "PHB"))
        BgEmbed       : Discord.Embed = Discord.Embed(title = BackgroundName, description = "*Character Background*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, BackgroundName, "Background")
            if (WarningNotice is not None):
                BgEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        FeaturesList: list[dict[str, Typing.Any]] = BackgroundData.get("feats", [])
        if FeaturesList:
            FeatureNames: list[str] = []
            for FMap in FeaturesList:
                for FKey in FMap.keys():
                    FeatureNames.append(FKey.split("|")[0].title())

            BgEmbed.add_field(name = "Origin Feat", value = ", ".join(FeatureNames), inline = True)

        SkillsList: list[dict[str, Typing.Any]] = BackgroundData.get("skillProficiencies", [])
        if SkillsList:
            SkillNames: list[str] = []
            for SMap in SkillsList:
                SkillNames.extend(K.title() for K in SMap.keys() if (K != "choose"))

            if SkillNames:
                BgEmbed.add_field(name = "Skill Proficiencies", value = ", ".join(SkillNames), inline = True)

        ToolsList: list[dict[str, Typing.Any]] = BackgroundData.get("toolProficiencies", [])
        if ToolsList:
            ToolNames: list[str] = []
            for TMap in ToolsList:
                ToolNames.extend(K.title() for K in TMap.keys() if (K != "choose"))

            if ToolNames:
                BgEmbed.add_field(name = "Tool Proficiencies", value = ", ".join(ToolNames), inline = True)

        EntriesData: Typing.Any = BackgroundData.get("entries")
        if EntriesData:
            DescriptionText: str = self.RenderEntries(EntriesData)
            BgEmbed.add_field(name = "Details & Equipment", value = DescriptionText[:1020], inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            BgEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            BgEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            BgEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return BgEmbed

    def FormatSpeciesEmbed(self, SpeciesData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        SpeciesName : str           = str(SpeciesData.get("name", "Unknown Species"))
        SourceText  : str           = str(SpeciesData.get("source", "PHB"))
        SizeCodes   : list[str]     = SpeciesData.get("size", ["M"])
        SizeName    : str           = SIZE_MAPPING.get(SizeCodes[0], "Medium") if (SizeCodes) else "Medium"
        SpeedValue  : Typing.Any    = SpeciesData.get("speed", 30)
        SpeedStr    : str           = f"{SpeedValue} ft" if (isinstance(SpeedValue, (int, str))) else f"{SpeedValue.get("walk", 30)} ft"
        Subtitle    : str           = f"Size: {SizeName} | Speed: {SpeedStr}"
        SpeciesEmbed: Discord.Embed = Discord.Embed(title = SpeciesName, description = f"*{Subtitle}*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, SpeciesName, "Species")
            if (WarningNotice is not None):
                SpeciesEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        DarkvisionValue: Typing.Any = SpeciesData.get("darkvision")
        if DarkvisionValue:
            SpeciesEmbed.add_field(name = "Darkvision", value = f"{DarkvisionValue} ft", inline = True)

        EntriesData: Typing.Any = SpeciesData.get("entries")
        if EntriesData:
            DescriptionText: str = self.RenderEntries(EntriesData)
            SpeciesEmbed.add_field(name = "Traits & Features", value = DescriptionText[:1020], inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            SpeciesEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            SpeciesEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            SpeciesEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return SpeciesEmbed

    def FormatConditionEmbed(self, ConditionData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        ConditionName: str           = str(ConditionData.get("name", "Unknown Condition"))
        SourceText   : str           = str(ConditionData.get("source", "PHB"))
        KindName     : str           = str(ConditionData.get("ConditionKind", "Condition"))
        CondEmbed    : Discord.Embed = Discord.Embed(title = ConditionName, description = f"*{KindName}*", color = COLOR_COMPENDIUM_EMBED)

        if self.SourceFilter.ShouldShowLegacyNudge(SourceText, RuleSetEnforcementMode):
            WarningNotice: Typing.Optional[str] = self.SourceFilter.GenerateLegacyNudgeWarning(SourceText, ConditionName, "Condition")
            if (WarningNotice is not None):
                CondEmbed.add_field(name = "⚠️ Legacy 2014 Content Notice", value = WarningNotice, inline = False)

        EntriesData: Typing.Any = ConditionData.get("entries")
        if EntriesData:
            DescriptionText: str = self.RenderEntries(EntriesData)
            CondEmbed.add_field(name = "Effects & Rules", value = DescriptionText[:1020], inline = False)

        if self.SourceFilter.IsSource2024(SourceText):
            CondEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (D&D 2024)")

        elif self.SourceFilter.IsCoreLegacySource(SourceText):
            CondEmbed.set_footer(text = f"5e.tools • Source: {SourceText} (Legacy 2014)")

        else:
            CondEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")

        return CondEmbed

    def FormatDeityEmbed(self, DeityData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        DeityName : str           = str(DeityData.get("name", "Unknown Deity"))
        SourceText: str           = str(DeityData.get("source", "PHB"))
        Pantheon  : str           = str(DeityData.get("pantheon", "Pantheon"))
        AlignList : list[str]     = DeityData.get("alignment", ["N"])
        AlignStr  : str           = "".join(str(A) for A in AlignList)
        Subtitle  : str           = f"{Pantheon} | Alignment: {AlignStr}"
        DeityEmbed: Discord.Embed = Discord.Embed(title = DeityName, description = f"*{Subtitle}*", color = COLOR_COMPENDIUM_EMBED)

        DomainsList: list[str] = DeityData.get("domains", [])
        if DomainsList:
            DeityEmbed.add_field(name = "Domains", value = ", ".join(DomainsList), inline = True)

        ProvinceText: str = str(DeityData.get("province", ""))
        if ProvinceText:
            DeityEmbed.add_field(name = "Province", value = ProvinceText, inline = True)

        SymbolText: str = str(DeityData.get("symbol", ""))
        if SymbolText:
            DeityEmbed.add_field(name = "Holy Symbol", value = SymbolText, inline = True)

        EntriesData: Typing.Any = DeityData.get("entries")
        if EntriesData:
            DescriptionText: str = self.RenderEntries(EntriesData)
            DeityEmbed.add_field(name = "Lore & Description", value = DescriptionText[:1020], inline = False)

        DeityEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")
        return DeityEmbed

    def FormatVehicleEmbed(self, VehicleData: dict[str, Typing.Any], RuleSetEnforcementMode: str = "Standard") -> Discord.Embed:
        VehicleName : str           = str(VehicleData.get("name", "Unknown Vehicle"))
        SourceText  : str           = str(VehicleData.get("source", "DMG"))
        VehicleType : str           = str(VehicleData.get("vehicleType", "Vehicle")).capitalize()
        SizeCodes   : list[str]     = VehicleData.get("size", ["G"])
        SizeName    : str           = SIZE_MAPPING.get(SizeCodes[0], "Gargantuan") if (SizeCodes) else "Gargantuan"
        VehicleEmbed: Discord.Embed = Discord.Embed(title = VehicleName, description = f"*{SizeName} {VehicleType}*", color = COLOR_COMPENDIUM_EMBED)

        ArmorClassValue: Typing.Any = VehicleData.get("ac")
        if (ArmorClassValue is not None):
            VehicleEmbed.add_field(name = "Armor Class", value = str(ArmorClassValue), inline = True)

        HitPointsValue: Typing.Any = VehicleData.get("hp")
        if (HitPointsValue is not None):
            HPStr: str = f"{HitPointsValue.get("average", 100)} ({HitPointsValue.get("formula", "")})" if (isinstance(HitPointsValue, dict)) else str(HitPointsValue)
            VehicleEmbed.add_field(name = "Hit Points", value = HPStr, inline = True)

        SpeedValue: Typing.Any = VehicleData.get("speed")
        if (SpeedValue is not None):
            SpeedStr: str = str(SpeedValue)
            if isinstance(SpeedValue, dict):
                SpeedParts: list[str] = [f"{K}: {V} ft" for K, V in SpeedValue.items()]
                SpeedStr              = ", ".join(SpeedParts)

            VehicleEmbed.add_field(name = "Speed", value = SpeedStr, inline = True)

        CrewValue      : Typing.Any = VehicleData.get("capCrew")
        PassengersValue: Typing.Any = VehicleData.get("capPassenger")
        if (CrewValue is not None) or (PassengersValue is not None):
            CrewText: str = f"Crew: {CrewValue or 0} | Passengers: {PassengersValue or 0}"
            VehicleEmbed.add_field(name = "Capacity", value = CrewText, inline = True)

        EntriesData: Typing.Any = VehicleData.get("entries")
        if EntriesData:
            DescriptionText: str = self.RenderEntries(EntriesData)
            VehicleEmbed.add_field(name = "Description & Features", value = DescriptionText[:1020], inline = False)

        VehicleEmbed.set_footer(text = f"5e.tools • Source: {SourceText}")
        return VehicleEmbed

