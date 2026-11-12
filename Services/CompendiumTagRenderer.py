import re                    as RegularExpressions
import typing                as Typing
import discord               as Discord
import Services.DebugService as Debug

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

class CompendiumTagRenderer:
    def RenderTags(self, RawText: str) -> str:
        def ReplaceTagMatch(TagMatch: RegularExpressions.Match) -> str:
            TagName    : str = TagMatch.group(1).lower()
            TagContent : str = TagMatch.group(2)
            Splitted   : list[str] = TagContent.split("|")
            PrimaryText: str = Splitted[0].strip()

            if TagName in ("b", "bold"):
                return f"**{PrimaryText}**"

            elif TagName in ("i", "italic"):
                return f"*{PrimaryText}*"

            elif TagName in ("strike", "s"):
                return f"~~{PrimaryText}~~"

            elif TagName in ("code", "kbd"):
                return f"`{PrimaryText}`"

            elif TagName in ("spell", "creature", "item", "skill", "action", "feat", "race", "background", "class"):
                return f"**{PrimaryText.title()}**"

            elif TagName in ("condition", "disease", "sense"):
                return f"*{PrimaryText.title()}*"

            elif (TagName == "chance"):
                return f"{PrimaryText}%"

            elif (TagName == "recharge"):
                RechargeVal: str = PrimaryText if (len(PrimaryText) > 0) else "6"
                return f"(Recharge {RechargeVal}-6)"

            return PrimaryText

        return TAG_REPLACE_PATTERN.sub(ReplaceTagMatch, RawText)

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
                EntryTitle: str = str(EntriesData.get("name", ""))
                SubContent: str = self.RenderEntries(EntriesData.get("entries", []))
                return f"**{EntryTitle}**\n{SubContent}"

            elif (EntryType == "list"):
                ItemsList: list[str] = [f"• {self.RenderEntries(Item)}" for Item in EntriesData.get("items", [])]
                return "\n".join(ItemsList)

            elif (EntryType == "inset"):
                InsetText: str = self.RenderEntries(EntriesData.get("entries", []))
                return f"> {InsetText}"

            elif (EntryType == "table"):
                CaptionText: str = str(EntriesData.get("caption", ""))
                RowsList   : list[str] = []
                for RowItem in EntriesData.get("rows", []):
                    RowString: str = " | ".join(str(Cell) for Cell in RowItem)
                    RowsList.append(f"• {RowString}")

                TableFormatted: str = "\n".join(RowsList)
                return f"**{CaptionText}**\n{TableFormatted}" if CaptionText else TableFormatted

            elif "entries" in EntriesData:
                return self.RenderEntries(EntriesData.get("entries"))

        return ""

    def FormatSpellEmbed(self, SpellData: Typing.Dict[str, Typing.Any]) -> Discord.Embed:
        SpellName     : str = str(SpellData.get("name", "Unknown Spell"))
        SpellLevel    : int = int(SpellData.get("level", 0))
        SchoolCode    : str = str(SpellData.get("school", "V")).upper()
        SchoolName    : str = SPELL_SCHOOL_MAPPING.get(SchoolCode, "Evocation")
        SourceText    : str = str(SpellData.get("source", "PHB"))

        LevelHeader   : str = f"{SchoolName} cantrip" if (SpellLevel == 0) else f"{SpellLevel}-level {SchoolName}"
        SpellEmbed    : Discord.Embed = Discord.Embed(title = SpellName, description = f"*{LevelHeader}*", color = COLOR_COMPENDIUM_EMBED)

        TimeEntries   : list[Typing.Dict[str, Typing.Any]] = SpellData.get("time", [])
        CastingTime   : str = f"{TimeEntries[0].get('number', 1)} {TimeEntries[0].get('unit', 'action')}" if TimeEntries else "1 action"
        SpellEmbed.add_field(name = "Casting Time", value = CastingTime, inline = True)

        RangeData     : Typing.Dict[str, Typing.Any] = SpellData.get("range", {})
        DistanceData  : Typing.Dict[str, Typing.Any] = RangeData.get("distance", {})
        RangeString   : str = f"{DistanceData.get('amount', '')} {DistanceData.get('type', '')}".strip() or str(RangeData.get("type", "Self"))
        SpellEmbed.add_field(name = "Range", value = RangeString, inline = True)

        ComponentsData: Typing.Dict[str, Typing.Any] = SpellData.get("components", {})
        CompParts     : list[str] = []
        if ComponentsData.get("v"):
            CompParts.append("V")

        if ComponentsData.get("s"):
            CompParts.append("S")

        if ComponentsData.get("m"):
            MaterialText: str = str(ComponentsData.get("m", ""))
            CompParts.append(f"M ({MaterialText})" if (MaterialText != "True") else "M")

        SpellEmbed.add_field(name = "Components", value = ", ".join(CompParts) or "None", inline = True)

        DurationList  : list[Typing.Dict[str, Typing.Any]] = SpellData.get("duration", [])
        DurationText  : str = "Instantaneous"
        if DurationList:
            FirstDur: Typing.Dict[str, Typing.Any] = DurationList[0]
            if (FirstDur.get("type") == "timed"):
                DurationAmount = FirstDur.get("duration", {})
                ConcPrefix     = "Concentration, up to " if FirstDur.get("concentration") else ""
                DurationText   = f"{ConcPrefix}{DurationAmount.get('amount', 1)} {DurationAmount.get('type', 'minute')}"

            elif (FirstDur.get("type") == "instant"):
                DurationText = "Instantaneous"

        SpellEmbed.add_field(name = "Duration", value = DurationText, inline = True)

        DescriptionText: str = self.RenderEntries(SpellData.get("entries", []))
        if (len(DescriptionText) > 1024):
            SpellEmbed.add_field(name = "Description", value = DescriptionText[:1020] + "…", inline = False)

        else:
            SpellEmbed.add_field(name = "Description", value = DescriptionText, inline = False)

        HigherLevelsData = SpellData.get("entriesHigherLevel")
        if HigherLevelsData:
            HigherText: str = self.RenderEntries(HigherLevelsData)
            SpellEmbed.add_field(name = "At Higher Levels", value = HigherText[:1020], inline = False)

        SpellEmbed.set_footer(text = f"5eTools • Source: {SourceText}")
        return SpellEmbed

    def FormatMonsterEmbed(self, MonsterData: Typing.Dict[str, Typing.Any]) -> Discord.Embed:
        MonsterName : str = str(MonsterData.get("name", "Unknown Creature"))
        SizeCodes   : list[str] = MonsterData.get("size", ["M"])
        SizeName    : str = SIZE_MAPPING.get(SizeCodes[0], "Medium") if SizeCodes else "Medium"
        TypeData    : Typing.Any = MonsterData.get("type", "beast")
        TypeName    : str = TypeData.get("type", "beast") if isinstance(TypeData, dict) else str(TypeData)
        SourceText  : str = str(MonsterData.get("source", "MM"))

        Subtitle    : str = f"{SizeName} {TypeName}"
        MonsterEmbed: Discord.Embed = Discord.Embed(title = MonsterName, description = f"*{Subtitle}*", color = COLOR_COMPENDIUM_EMBED)

        ACData      : list[Typing.Any] = MonsterData.get("ac", [10])
        ACValue     : str = str(ACData[0].get("ac") if isinstance(ACData[0], dict) else ACData[0]) if ACData else "10"
        MonsterEmbed.add_field(name = "Armor Class", value = ACValue, inline = True)

        HPData      : Typing.Dict[str, Typing.Any] = MonsterData.get("hp", {})
        HPValue     : str = f"{HPData.get('average', 10)} ({HPData.get('formula', '')})" if HPData else "10"
        MonsterEmbed.add_field(name = "Hit Points", value = HPValue, inline = True)

        CRData      : Typing.Any = MonsterData.get("cr", "0")
        CRValue     : str = str(CRData.get("cr") if isinstance(CRData, dict) else CRData)
        MonsterEmbed.add_field(name = "Challenge", value = CRValue, inline = True)

        STRScore    : int = int(MonsterData.get("str", 10))
        DEXScore    : int = int(MonsterData.get("dex", 10))
        CONScore    : int = int(MonsterData.get("con", 10))
        INTScore    : int = int(MonsterData.get("int", 10))
        WISScore    : int = int(MonsterData.get("wis", 10))
        CHAScore    : int = int(MonsterData.get("cha", 10))

        def FormatMod(ScoreValue: int) -> str:
            Modifier: int = (ScoreValue - 10) // 2
            return f"{ScoreValue} ({'+' if (Modifier >= 0) else ''}{Modifier})"

        AbilityBlock: str = f"**STR** {FormatMod(STRScore)} | **DEX** {FormatMod(DEXScore)} | **CON** {FormatMod(CONScore)}\n**INT** {FormatMod(INTScore)} | **WIS** {FormatMod(WISScore)} | **CHA** {FormatMod(CHAScore)}"
        MonsterEmbed.add_field(name = "Ability Scores", value = AbilityBlock, inline = False)

        TraitsList  : list[Typing.Dict[str, Typing.Any]] = MonsterData.get("trait", [])
        if TraitsList:
            TraitStrings: list[str] = [f"**{T.get('name')}**: {self.RenderEntries(T.get('entries', []))}" for T in TraitsList[:4]]
            MonsterEmbed.add_field(name = "Traits", value = "\n\n".join(TraitStrings)[:1020], inline = False)

        ActionsList : list[Typing.Dict[str, Typing.Any]] = MonsterData.get("action", [])
        if ActionsList:
            ActionStrings: list[str] = [f"**{A.get('name')}**: {self.RenderEntries(A.get('entries', []))}" for A in ActionsList[:5]]
            MonsterEmbed.add_field(name = "Actions", value = "\n\n".join(ActionStrings)[:1020], inline = False)

        MonsterEmbed.set_footer(text = f"5eTools • Source: {SourceText}")
        return MonsterEmbed

    def FormatItemEmbed(self, ItemData: Typing.Dict[str, Typing.Any]) -> Discord.Embed:
        ItemName    : str = str(ItemData.get("name", "Unknown Item"))
        RarityText  : str = str(ItemData.get("rarity", "common")).capitalize()
        SourceText  : str = str(ItemData.get("source", "DMG"))
        ItemEmbed   : Discord.Embed = Discord.Embed(title = ItemName, description = f"*{RarityText}*", color = COLOR_COMPENDIUM_EMBED)

        WeightValue = ItemData.get("weight")
        if (WeightValue is not None):
            ItemEmbed.add_field(name = "Weight", value = f"{WeightValue} lbs", inline = True)

        ValueAmount = ItemData.get("value")
        if (ValueAmount is not None):
            ItemEmbed.add_field(name = "Value", value = f"{ValueAmount} cp", inline = True)

        DescText    : str = self.RenderEntries(ItemData.get("entries", []))
        if DescText:
            ItemEmbed.add_field(name = "Description", value = DescText[:1020], inline = False)

        ItemEmbed.set_footer(text = f"5eTools • Source: {SourceText}")
        return ItemEmbed

