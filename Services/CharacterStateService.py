import typing                           as Typing
import discord                          as Discord
import Services.DebugService            as Debug
import Services.PlatformClient          as PlatformClient

SKILL_ABILITY_MAPPING: dict[str, str] = {
    "athletics"        : "Strength",
    "acrobatics"       : "Dexterity",
    "sleight of hand"  : "Dexterity",
    "stealth"          : "Dexterity",
    "arcana"           : "Intelligence",
    "history"          : "Intelligence",
    "investigation"    : "Intelligence",
    "nature"           : "Intelligence",
    "religion"         : "Intelligence",
    "animal handling"  : "Wisdom",
    "insight"          : "Wisdom",
    "medicine"         : "Wisdom",
    "perception"       : "Wisdom",
    "survival"         : "Wisdom",
    "deception"        : "Charisma",
    "intimidation"     : "Charisma",
    "performance"      : "Charisma",
    "persuasion"       : "Charisma"
}

SKILL_ALIASES: dict[str, str] = {
    "ath" : "athletics",
    "acro": "acrobatics",
    "soh" : "sleight of hand",
    "sleight": "sleight of hand",
    "ste" : "stealth",
    "arc" : "arcana",
    "hist": "history",
    "inv" : "investigation",
    "nat" : "nature",
    "rel" : "religion",
    "ani" : "animal handling",
    "animal": "animal handling",
    "ins" : "insight",
    "med" : "medicine",
    "perc": "perception",
    "sur" : "survival",
    "dec" : "deception",
    "intimidate": "intimidation",
    "intim": "intimidation",
    "perf": "performance",
    "pers": "persuasion"
}

ABILITY_ALIASES: dict[str, str] = {
    "str": "Strength",
    "strength": "Strength",
    "dex": "Dexterity",
    "dexterity": "Dexterity",
    "con": "Constitution",
    "constitution": "Constitution",
    "int": "Intelligence",
    "intelligence": "Intelligence",
    "wis": "Wisdom",
    "wisdom": "Wisdom",
    "cha": "Charisma",
    "charisma": "Charisma"
}

class CharacterStateService:
    def __init__(self, PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None) -> None:
        self.PlatformClient     : PlatformClient.MISPlatformClient = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.MISPlatformClient()
        self.UserActiveCharacter: dict[str, str]                   = {}
        self.CharacterCache     : dict[str, dict[str, Typing.Any]] = {}

    def BuildContextKey(self, DiscordUserID: int | str, ChannelID: int | str) -> str:
        return f"{DiscordUserID}:{ChannelID}"

    def SetActiveCharacter(self, DiscordUserID: int | str, ChannelID: int | str, CharacterID: str) -> None:
        ContextKey: str = self.BuildContextKey(DiscordUserID, ChannelID)
        self.UserActiveCharacter[ContextKey] = str(CharacterID).strip()
        self.UserActiveCharacter[str(DiscordUserID)] = str(CharacterID).strip()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Active Character Set: UserID={DiscordUserID}, CharID={CharacterID}")

    def GetActiveCharacterID(self, DiscordUserID: int | str, ChannelID: int | str) -> Typing.Optional[str]:
        ContextKey: str = self.BuildContextKey(DiscordUserID, ChannelID)
        if ContextKey in self.UserActiveCharacter:
            return self.UserActiveCharacter[ContextKey]

        return self.UserActiveCharacter.get(str(DiscordUserID))

    async def ResolveActiveCharacter(self, DiscordUserID: int | str, ChannelID: int | str) -> Typing.Optional[dict[str, Typing.Any]]:
        ActiveID: Typing.Optional[str] = self.GetActiveCharacterID(DiscordUserID, ChannelID)
        if (ActiveID is not None) and (ActiveID in self.CharacterCache):
            return self.CharacterCache[ActiveID]

        OwnedCharacters: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchCharactersByDiscordID(str(DiscordUserID))
        for CharRecord in OwnedCharacters:
            CharID: str = str(CharRecord.get("ID", ""))
            if CharID:
                self.CharacterCache[CharID] = CharRecord

        if (ActiveID is not None) and (ActiveID in self.CharacterCache):
            return self.CharacterCache[ActiveID]

        if (len(OwnedCharacters) == 1):
            SingleID: str = str(OwnedCharacters[0].get("ID", ""))
            self.SetActiveCharacter(DiscordUserID, ChannelID, SingleID)
            return OwnedCharacters[0]

        return None

    def GetAbilityModifier(self, DetailData: dict[str, Typing.Any], AbilityQuery: str) -> tuple[str, int, int]:
        ResolvedAbility: Typing.Optional[str] = ABILITY_ALIASES.get(AbilityQuery.strip().lower())
        if (ResolvedAbility is None):
            ResolvedAbility = "Strength"

        AbilityScores: dict[str, Typing.Any] = DetailData.get("AbilityScores", {})
        AbilityData  : dict[str, Typing.Any] = AbilityScores.get(ResolvedAbility, {})
        ScoreValue   : int                   = int(AbilityData.get("TotalScore", 10))
        Modifier     : int                   = int(AbilityData.get("Modifier", (ScoreValue - 10) // 2))
        return (ResolvedAbility, ScoreValue, Modifier)

    def GetSavingThrowModifier(self, DetailData: dict[str, Typing.Any], AbilityQuery: str) -> tuple[str, int, bool]:
        AbilityName, _, BaseModifier = self.GetAbilityModifier(DetailData, AbilityQuery)
        ProfBonus   : int            = int(DetailData.get("ProficiencyBonus", 2))
        SavesList   : list[dict]     = DetailData.get("SavingThrowProficiencies", [])
        IsProficient: bool           = False
        BonusMod    : int            = 0

        for SaveEntry in SavesList:
            if (str(SaveEntry.get("AbilityName", "")).lower() == AbilityName.lower()):
                IsProficient = bool(SaveEntry.get("IsProficient", False))
                BonusMod     = int(SaveEntry.get("BonusModifier", 0))
                break

        TotalSaveModifier: int = BaseModifier + (ProfBonus if IsProficient else 0) + BonusMod
        return (AbilityName, TotalSaveModifier, IsProficient)

    def GetSkillModifier(self, DetailData: dict[str, Typing.Any], SkillQuery: str) -> tuple[str, str, int, str]:
        QueryNormalized: str                  = SkillQuery.strip().lower()
        ResolvedSkill  : str                  = SKILL_ALIASES.get(QueryNormalized, QueryNormalized)
        AssociatedAbil : str                  = SKILL_ABILITY_MAPPING.get(ResolvedSkill, "Wisdom")
        _, _, AbilityMod                      = self.GetAbilityModifier(DetailData, AssociatedAbil)
        ProfBonus      : int                  = int(DetailData.get("ProficiencyBonus", 2))
        SkillsList     : list[dict]           = DetailData.get("SkillProficiencies", [])
        TierName       : str                  = "None"
        BonusMod       : int                  = 0

        for SkillEntry in SkillsList:
            if (str(SkillEntry.get("SkillName", "")).lower() == ResolvedSkill):
                TierName = str(SkillEntry.get("ProficiencyTier", "None"))
                BonusMod = int(SkillEntry.get("BonusModifier", 0))
                break

        Multiplier: float = 0.0
        if (TierName == "Proficient"):
            Multiplier = 1.0

        elif (TierName == "Expertise"):
            Multiplier = 2.0

        elif (TierName == "HalfProficient"):
            Multiplier = 0.5

        TotalSkillModifier: int = AbilityMod + int(ProfBonus * Multiplier) + BonusMod
        CleanSkillTitle   : str = ResolvedSkill.title()
        return (CleanSkillTitle, AssociatedAbil, TotalSkillModifier, TierName)

    def ModifyHitPoints(self, DetailData: dict[str, Typing.Any], DeltaHP: int, IsTemp: bool = False) -> tuple[int, int, int]:
        HitPointsData: dict[str, Typing.Any] = DetailData.get("HitPoints", {})
        CurrentHP    : int                   = int(HitPointsData.get("CurrentHitPoints", 10))
        MaxHP        : int                   = int(HitPointsData.get("MaxHitPoints", 10))
        TempHP       : int                   = int(HitPointsData.get("TemporaryHitPoints", 0))

        if IsTemp:
            TempHP = max(0, DeltaHP)
            HitPointsData["TemporaryHitPoints"] = TempHP
            return (CurrentHP, CurrentHP, TempHP)

        if (DeltaHP < 0):
            DamageRemaining: int = abs(DeltaHP)
            if (TempHP > 0):
                AbsorbedDamage = min(TempHP, DamageRemaining)
                TempHP         -= AbsorbedDamage
                DamageRemaining -= AbsorbedDamage

            NewCurrentHP = max(0, CurrentHP - DamageRemaining)

        else:
            NewCurrentHP = min(MaxHP, CurrentHP + DeltaHP)

        HitPointsData["CurrentHitPoints"]   = NewCurrentHP
        HitPointsData["TemporaryHitPoints"] = TempHP
        return (CurrentHP, NewCurrentHP, TempHP)

    def ModifySpellSlot(self, DetailData: dict[str, Typing.Any], SlotLevel: int, DeltaUsed: int) -> tuple[int, int]:
        Spellcasting: dict[str, Typing.Any] = DetailData.get("Spellcasting", {})
        SpellSlots  : list[dict]            = Spellcasting.get("SpellSlots", [])

        for SlotEntry in SpellSlots:
            if (int(SlotEntry.get("Level", 0)) == SlotLevel):
                TotalSlots    : int = int(SlotEntry.get("TotalSlots", 0))
                UsedSlots     : int = int(SlotEntry.get("UsedSlots", 0))
                NewUsed       : int = max(0, min(TotalSlots, UsedSlots + DeltaUsed))
                SlotEntry["UsedSlots"]      = NewUsed
                SlotEntry["AvailableSlots"] = max(0, TotalSlots - NewUsed)
                return (SlotEntry["AvailableSlots"], TotalSlots)

        return (0, 0)

    def ApplyRest(self, DetailData: dict[str, Typing.Any], RestType: str) -> dict[str, Typing.Any]:
        HitPointsData: dict[str, Typing.Any] = DetailData.get("HitPoints", {})
        MaxHP        : int                   = int(HitPointsData.get("MaxHitPoints", 10))
        Spellcasting : dict[str, Typing.Any] = DetailData.get("Spellcasting", {})

        if (RestType.lower() == "long"):
            HitPointsData["CurrentHitPoints"]   = MaxHP
            HitPointsData["TemporaryHitPoints"] = 0
            for SlotEntry in Spellcasting.get("SpellSlots", []):
                SlotEntry["UsedSlots"]      = 0
                SlotEntry["AvailableSlots"] = int(SlotEntry.get("TotalSlots", 0))

            ClassesList: list[dict] = DetailData.get("Classes", [])
            for ClassEntry in ClassesList:
                TotalHD: int = int(ClassEntry.get("HitDiceTotal", 1))
                UsedHD : int = int(ClassEntry.get("HitDiceUsed", 0))
                RecovHD: int = max(1, TotalHD // 2)
                ClassEntry["HitDiceUsed"] = max(0, UsedHD - RecovHD)

            return {"RestType": "Long", "HP": MaxHP, "SlotsReset": True}

        else:
            PactMagic: Typing.Optional[dict] = Spellcasting.get("PactMagic")
            if (PactMagic is not None):
                PactMagic["UsedSlots"]      = 0
                PactMagic["AvailableSlots"] = int(PactMagic.get("TotalSlots", 0))

            return {"RestType": "Short", "PactSlotsReset": True}

    def FormatSheetEmbed(self, CharacterRecord: dict[str, Typing.Any]) -> Discord.Embed:
        CharName     : str  = str(CharacterRecord.get("Name", "Hero"))
        DetailData   : dict = CharacterRecord.get("DetailData", {})
        SpeciesData  : dict = DetailData.get("Species", {})
        SpeciesName  : str  = str(SpeciesData.get("SpeciesName", "Unknown Species"))
        TotalLevel   : int  = int(DetailData.get("TotalLevel", 1))
        ClassesList  : list = DetailData.get("Classes", [])
        ClassDesc    : str  = ", ".join(f"{C.get('ClassName', '')} {C.get('Level', '')}" for C in ClassesList) or "Adventurer 1"

        SheetEmbed: Discord.Embed = Discord.Embed(title = CharName, description = f"Level {TotalLevel} • {SpeciesName} • {ClassDesc}", color = 0x0030A6)

        HitPointsData: dict = DetailData.get("HitPoints", {})
        CurrentHP    : int  = int(HitPointsData.get("CurrentHitPoints", 10))
        MaxHP        : int  = int(HitPointsData.get("MaxHitPoints", 10))
        TempHP       : int  = int(HitPointsData.get("TemporaryHitPoints", 0))
        HPString     : str  = f"{CurrentHP}/{MaxHP}" if (TempHP == 0) else f"{CurrentHP}/{MaxHP} (+{TempHP} temp)"
        SheetEmbed.add_field(name = "Hit Points", value = HPString, inline = True)

        ArmorClassData: dict = DetailData.get("ArmorClass", {})
        TotalAC       : int  = int(ArmorClassData.get("TotalArmorClass", 10))
        SheetEmbed.add_field(name = "Armor Class", value = str(TotalAC), inline = True)

        ProfBonus: int = int(DetailData.get("ProficiencyBonus", 2))
        SheetEmbed.add_field(name = "Proficiency", value = f"+{ProfBonus}", inline = True)

        AbilityScores: dict      = DetailData.get("AbilityScores", {})
        ScoreStrings : list[str] = []
        for Abil in ("Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"):
            AbilEntry: dict = AbilityScores.get(Abil, {})
            Score    : int  = int(AbilEntry.get("TotalScore", 10))
            Mod      : int  = int(AbilEntry.get("Modifier", (Score - 10) // 2))
            ScoreStrings.append(f"**{Abil[:3].upper()}**: {Score} ({'+' if Mod >= 0 else ''}{Mod})")

        SheetEmbed.add_field(name = "Ability Scores", value = " | ".join(ScoreStrings[:3]) + "\n" + " | ".join(ScoreStrings[3:]), inline = False)

        PassivePerception: int = int(DetailData.get("PassivePerception", 10))
        InitiativeBonus  : int = int(DetailData.get("InitiativeBonus", 0))
        SpeedData        : dict = DetailData.get("Speed", {})
        WalkingSpeed     : int  = int(SpeedData.get("WalkingSpeedFeet", 30))
        StatsLine        : str  = f"**Passive Perception:** {PassivePerception} | **Initiative:** {'+' if InitiativeBonus >= 0 else ''}{InitiativeBonus} | **Speed:** {WalkingSpeed} ft"
        SheetEmbed.add_field(name = "Exploration & Senses", value = StatsLine, inline = False)

        Spellcasting: dict      = DetailData.get("Spellcasting", {})
        SpellSlots  : list[dict] = Spellcasting.get("SpellSlots", [])
        if SpellSlots:
            SlotStrings: list[str] = []
            for Slot in SpellSlots:
                Lvl: int = int(Slot.get("Level", 1))
                Tot: int = int(Slot.get("TotalSlots", 0))
                Avail: int = int(Slot.get("AvailableSlots", Tot))
                if (Tot > 0):
                    SlotStrings.append(f"**L{Lvl}:** {Avail}/{Tot}")

            if SlotStrings:
                SheetEmbed.add_field(name = "Spell Slots", value = " • ".join(SlotStrings), inline = False)

        SheetEmbed.set_footer(text = f"Character ID: {CharacterRecord.get('ID')} • MIS Platform")
        return SheetEmbed

