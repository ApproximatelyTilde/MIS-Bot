import typing                  as Typing
import discord                 as Discord
import Services.DebugService   as Debug
import Services.PlatformClient as PlatformClient
import Services.DiceService    as Dice

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
    def __init__(self, PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None, DiceRollerInstance: Typing.Optional[Dice.DiceRollerService] = None) -> None:
        self.PlatformClient     : PlatformClient.MISPlatformClient = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.MISPlatformClient()
        self.DiceRoller         : Dice.DiceRollerService           = DiceRollerInstance if (DiceRollerInstance is not None) else Dice.DiceRollerService()
        self.UserActiveCharacter: dict[str, str]                   = dict()
        self.CharacterCache     : dict[str, dict[str, Typing.Any]] = dict()

    def BuildContextKey(self, DiscordUserID: int | str, ChannelID: int | str) -> str:
        return f"{DiscordUserID}:{ChannelID}"

    def SetActiveCharacter(self, DiscordUserID: int | str, ChannelID: int | str, CharacterID: str) -> None:
        ContextKey: str = self.BuildContextKey(DiscordUserID, ChannelID)
        self.UserActiveCharacter[ContextKey] = str(CharacterID).strip()
        self.UserActiveCharacter[str(DiscordUserID)] = str(CharacterID).strip()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Active Character Set: UserID={DiscordUserID}, CharacterID={CharacterID}")

    def GetActiveCharacterID(self, DiscordUserID: int | str, ChannelID: int | str) -> Typing.Optional[str]:
        ContextKey: str = self.BuildContextKey(DiscordUserID, ChannelID)
        if ContextKey in self.UserActiveCharacter:
            return self.UserActiveCharacter[ContextKey]

        return self.UserActiveCharacter.get(str(DiscordUserID))

    async def ResolveActiveCharacter(self, DiscordUserID: int | str, ChannelID: int | str) -> Typing.Optional[dict[str, Typing.Any]]:
        ActiveID: Typing.Optional[str] = self.GetActiveCharacterID(DiscordUserID, ChannelID)
        if (ActiveID is not None) and (ActiveID in self.CharacterCache):
            return self.CharacterCache[ActiveID]

        FetchedCharacters: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchCharactersByDiscordID(str(DiscordUserID))
        OwnedCharacters  : list[dict[str, Typing.Any]] = [C for C in FetchedCharacters if (C.get("GameSystem") == "DND5E")]
        for CharacterRecord in OwnedCharacters:
            CharacterID: str = str(CharacterRecord.get("ID", ""))
            if CharacterID:
                self.CharacterCache[CharacterID] = CharacterRecord

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
        BonusModifier    : int            = 0

        for SaveEntry in SavesList:
            if (str(SaveEntry.get("AbilityName", "")).lower() == AbilityName.lower()):
                IsProficient = bool(SaveEntry.get("IsProficient", False))
                BonusModifier     = int(SaveEntry.get("BonusModifier", 0))
                break

        TotalSaveModifier: int = BaseModifier + (ProfBonus if (IsProficient) else 0) + BonusModifier
        return (AbilityName, TotalSaveModifier, IsProficient)

    def HasJackOfAllTrades(self, DetailData: dict[str, Typing.Any]) -> bool:
        ClassesList: list[dict[str, Typing.Any]] = DetailData.get("Classes", [])
        for ClassItem in ClassesList:
            ClassName : str = str(ClassItem.get("ClassName", "")).lower()
            ClassLevel: int = int(ClassItem.get("Level", 0))
            if (ClassName == "bard") and (ClassLevel >= 2):
                return True

        FeaturesList: list[dict[str, Typing.Any]] = DetailData.get("Features", [])
        for FeatureItem in FeaturesList:
            FeatureName: str = str(FeatureItem.get("FeatureName", FeatureItem.get("Name", ""))).lower()
            if "jack of all trades" in FeatureName:
                return True

        return False

    def GetSkillModifier(self, DetailData: dict[str, Typing.Any], SkillQuery: str) -> tuple[str, str, int, str]:
        QueryNormalized: str                  = SkillQuery.strip().lower()
        ResolvedSkill  : str                  = SKILL_ALIASES.get(QueryNormalized, QueryNormalized)
        AssociatedAbil : str                  = SKILL_ABILITY_MAPPING.get(ResolvedSkill, "Wisdom")
        _, _, AbilityModifier                      = self.GetAbilityModifier(DetailData, AssociatedAbil)
        ProfBonus      : int                  = int(DetailData.get("ProficiencyBonus", 2))
        SkillsList     : list[dict]           = DetailData.get("SkillProficiencies", [])
        TierName       : str                  = "None"
        BonusModifier       : int                  = 0

        for SkillEntry in SkillsList:
            if (str(SkillEntry.get("SkillName", "")).lower() == ResolvedSkill):
                TierName = str(SkillEntry.get("ProficiencyTier", "None"))
                BonusModifier = int(SkillEntry.get("BonusModifier", 0))
                break

        Multiplier: float = 0.0
        if (TierName == "Proficient"):
            Multiplier = 1.0

        elif (TierName == "Expertise"):
            Multiplier = 2.0

        elif (TierName == "HalfProficient"):
            Multiplier = 0.5

        elif (TierName == "None") and self.HasJackOfAllTrades(DetailData):
            Multiplier = 0.5
            TierName   = "Jack of All Trades"

        TotalSkillModifier: int = AbilityModifier + int(ProfBonus * Multiplier) + BonusModifier
        CleanSkillTitle   : str = ResolvedSkill.title()
        return (CleanSkillTitle, AssociatedAbil, TotalSkillModifier, TierName)

    def CalculatePassiveScore(self, DetailData: dict[str, Typing.Any], QueryName: str, AdvantageState: int = 0, SituationalBonus: int = 0) -> tuple[str, int, str]:
        QueryNormalized: str = QueryName.strip().lower()
        AdvantageBonus : int = AdvantageState * 5
        TotalBonus     : int = AdvantageBonus + SituationalBonus

        if QueryNormalized in ABILITY_ALIASES:
            AbilityName, _, AbilityModifier = self.GetAbilityModifier(DetailData, QueryNormalized)
            JackBonus     : int       = 0
            BreakdownParts: list[str] = [f"Base (10)", f"Modifier ({"+" if (AbilityModifier >= 0) else ""}{AbilityModifier})"]
            if self.HasJackOfAllTrades(DetailData):
                ProfBonus: int = int(DetailData.get("ProficiencyBonus", 2))
                JackBonus      = ProfBonus // 2
                BreakdownParts.append(f"Jack of All Trades (+{JackBonus})")

            if (AdvantageState == 1):
                BreakdownParts.append("Advantage (+5)")

            elif (AdvantageState == -1):
                BreakdownParts.append("Disadvantage (-5)")

            if (SituationalBonus != 0):
                BreakdownParts.append(f"Bonus ({"+" if (SituationalBonus >= 0) else ""}{SituationalBonus})")

            FinalPassiveScore: int = 10 + AbilityModifier + JackBonus + TotalBonus
            BreakdownString  : str = " + ".join(BreakdownParts) + f" = **{FinalPassiveScore}**"
            return (AbilityName, FinalPassiveScore, BreakdownString)

        SkillTitle, AssocAbil, SkillModifier, TierName = self.GetSkillModifier(DetailData, QueryNormalized)
        BreakdownParts                            = [f"Base (10)", f"Modifier ({"+" if (SkillModifier >= 0) else ""}{SkillModifier})"]
        if (TierName != "None"):
            BreakdownParts.append(f"Tier ({TierName})")

        if (AdvantageState == 1):
            BreakdownParts.append("Advantage (+5)")

        elif (AdvantageState == -1):
            BreakdownParts.append("Disadvantage (-5)")

        if (SituationalBonus != 0):
            BreakdownParts.append(f"Bonus ({"+" if (SituationalBonus >= 0) else ""}{SituationalBonus})")

        FinalPassiveScore = 10 + SkillModifier + TotalBonus
        BreakdownString   = " + ".join(BreakdownParts) + f" = **{FinalPassiveScore}**"
        return (SkillTitle, FinalPassiveScore, BreakdownString)

    def GetAllPassiveScores(self, DetailData: dict[str, Typing.Any]) -> dict[str, int]:
        PassiveResults: dict[str, int] = dict()
        for SkillKey in SKILL_ABILITY_MAPPING.keys():
            SkillTitle, _, SkillModifier, _ = self.GetSkillModifier(DetailData, SkillKey)
            PassiveResults[SkillTitle] = 10 + SkillModifier

        return PassiveResults

    def ModifyHitPoints(self, DetailData: dict[str, Typing.Any], DeltaHP: int, IsTemp: bool = False, IsCriticalDamage: bool = False) -> tuple[int, int, int]:
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

            OldHP        = CurrentHP
            NewCurrentHP = max(0, CurrentHP - DamageRemaining)

            if (OldHP == 0) and (DamageRemaining > 0):
                DeathSaves: dict[str, int] = DetailData.setdefault("DeathSaves", {"SuccessCount": 0, "FailureCount": 0})
                FailuresAdded: int = 2 if (IsCriticalDamage) else 1
                DeathSaves["FailureCount"] = min(3, int(DeathSaves.get("FailureCount", 0)) + FailuresAdded)

        else:
            OldHP        = CurrentHP
            NewCurrentHP = min(MaxHP, CurrentHP + DeltaHP)
            if (OldHP == 0) and (NewCurrentHP > 0):
                DetailData["DeathSaves"] = {
                    "SuccessCount": 0,
                    "FailureCount": 0
                }

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
            DetailData["DeathSaves"]            = {
                "SuccessCount": 0,
                "FailureCount": 0
            }
            for SlotEntry in Spellcasting.get("SpellSlots", []):
                SlotEntry["UsedSlots"]      = 0
                SlotEntry["AvailableSlots"] = int(SlotEntry.get("TotalSlots", 0))

            ClassesList: list[dict] = DetailData.get("Classes", [])
            for ClassEntry in ClassesList:
                TotalHD: int = int(ClassEntry.get("HitDiceTotal", 1))
                UsedHD : int = int(ClassEntry.get("HitDiceUsed", 0))
                RecovHD: int = max(1, TotalHD // 2)
                ClassEntry["HitDiceUsed"] = max(0, UsedHD - RecovHD)

            return {
                "RestType"  : "Long",
                "HP"        : MaxHP,
                "SlotsReset": True
            }

        else:
            PactMagic: Typing.Optional[dict] = Spellcasting.get("PactMagic")
            if (PactMagic is not None):
                PactMagic["UsedSlots"]      = 0
                PactMagic["AvailableSlots"] = int(PactMagic.get("TotalSlots", 0))

            return {
                "RestType"      : "Short",
                "PactSlotsReset": True
            }

    def GetHitDicePool(self, DetailData: dict[str, Typing.Any]) -> list[dict[str, Typing.Any]]:
        ClassesList: list[dict[str, Typing.Any]] = DetailData.get("Classes", [])
        PoolList   : list[dict[str, Typing.Any]] = []

        if ClassesList:
            for ClassEntry in ClassesList:
                ClassName: str = str(ClassEntry.get("ClassName", "Adventurer"))
                LevelVal : int = int(ClassEntry.get("Level", 1))
                DieFace  : int = int(ClassEntry.get("HitDie", 8))
                TotalHD  : int = int(ClassEntry.get("HitDiceTotal", LevelVal))
                if (TotalHD <= 0):
                    TotalHD = LevelVal
                    ClassEntry["HitDiceTotal"] = TotalHD

                UsedHD : int = int(ClassEntry.get("HitDiceUsed", 0))
                AvailHD: int = max(0, TotalHD - UsedHD)
                PoolList.append({
                    "ClassName": ClassName,
                    "HitDie"   : DieFace,
                    "Total"    : TotalHD,
                    "Used"     : UsedHD,
                    "Available": AvailHD
                })

        else:
            TotalLevel: int = int(DetailData.get("TotalLevel", 1))
            PoolList.append({
                "ClassName": "Adventurer",
                "HitDie"   : 8,
                "Total"    : TotalLevel,
                "Used"     : 0,
                "Available": TotalLevel
            })

        return PoolList

    def SpendHitDice(self, DetailData: dict[str, Typing.Any], Count: int = 1, DieType: Typing.Optional[str] = None) -> tuple[int, int, list[dict[str, Typing.Any]], int, int]:
        ClassesList: list[dict[str, Typing.Any]] = DetailData.get("Classes", [])
        if not ClassesList:
            TotalLevel: int = int(DetailData.get("TotalLevel", 1))
            ClassesList     = [{"ClassName": "Adventurer", "Level": TotalLevel, "HitDie": 8, "HitDiceTotal": TotalLevel, "HitDiceUsed": 0}]
            DetailData["Classes"] = ClassesList

        TargetDieFace: Typing.Optional[int] = None
        if (DieType is not None):
            CleanDieStr: str = DieType.strip().lower()
            if CleanDieStr.startswith("d"):
                CleanDieStr = CleanDieStr[1:]

            try:
                TargetDieFace = int(CleanDieStr)

            except ValueError:
                TargetDieFace = None

        RemainingToSpend: int                         = Count
        RollsDetails    : list[dict[str, Typing.Any]] = []
        TotalHealed     : int                         = 0
        _, _, ConstitutionModifier                                  = self.GetAbilityModifier(DetailData, "Constitution")

        for ClassEntry in ClassesList:
            if (RemainingToSpend <= 0):
                break

            DieFace: int = int(ClassEntry.get("HitDie", 8))
            if (TargetDieFace is not None) and (DieFace != TargetDieFace):
                continue

            LevelVal: int = int(ClassEntry.get("Level", 1))
            TotalHD : int = int(ClassEntry.get("HitDiceTotal", LevelVal))
            if (TotalHD <= 0):
                TotalHD = LevelVal
                ClassEntry["HitDiceTotal"] = TotalHD

            UsedHD : int = int(ClassEntry.get("HitDiceUsed", 0))
            AvailHD: int = max(0, TotalHD - UsedHD)

            SpendFromThis: int = min(RemainingToSpend, AvailHD)
            for _ in range(SpendFromThis):
                RollOutcome = self.DiceRoller.EvaluateRoll(f"1d{DieFace}")
                SingleRoll  : int = RollOutcome.Total
                EffectiveVal: int = max(0, SingleRoll + ConstitutionModifier)
                TotalHealed += EffectiveVal
                RollsDetails.append({
                    "Die"   : DieFace,
                    "Roll"  : SingleRoll,
                    "ConstitutionModifier": ConstitutionModifier,
                    "Total" : EffectiveVal
                })

            ClassEntry["HitDiceUsed"] = UsedHD + SpendFromThis
            RemainingToSpend -= SpendFromThis

        HitPointsData: dict[str, Typing.Any] = DetailData.get("HitPoints", {})
        OldHP        : int                   = int(HitPointsData.get("CurrentHitPoints", 10))
        MaxHP        : int                   = int(HitPointsData.get("MaxHitPoints", 10))
        NewHP        : int                   = min(MaxHP, OldHP + TotalHealed)
        HitPointsData["CurrentHitPoints"]    = NewHP

        if (OldHP == 0) and (NewHP > 0):
            DetailData["DeathSaves"] = {
                "SuccessCount": 0,
                "FailureCount": 0
            }

        return (TotalHealed, OldHP, RollsDetails, NewHP, MaxHP)

    def ResetHitDice(self, DetailData: dict[str, Typing.Any]) -> None:
        ClassesList: list[dict[str, Typing.Any]] = DetailData.get("Classes", [])
        for ClassEntry in ClassesList:
            ClassEntry["HitDiceUsed"] = 0

    def SetHitDice(self, DetailData: dict[str, Typing.Any], CurrentVal: int, MaxVal: int, DieType: Typing.Optional[str] = None) -> None:
        ClassesList: list[dict[str, Typing.Any]] = DetailData.get("Classes", [])
        if not ClassesList:
            ClassesList = [{"ClassName": "Adventurer", "Level": MaxVal, "HitDie": 8, "HitDiceTotal": MaxVal, "HitDiceUsed": max(0, MaxVal - CurrentVal)}]
            DetailData["Classes"] = ClassesList
            return

        TargetDieFace: Typing.Optional[int] = None
        if (DieType is not None):
            CleanDieStr: str = DieType.strip().lower()
            if CleanDieStr.startswith("d"):
                CleanDieStr = CleanDieStr[1:]

            try:
                TargetDieFace = int(CleanDieStr)

            except ValueError:
                TargetDieFace = None

        TargetClass: dict[str, Typing.Any] = ClassesList[0]
        if (TargetDieFace is not None):
            for ClassEntry in ClassesList:
                if (int(ClassEntry.get("HitDie", 8)) == TargetDieFace):
                    TargetClass = ClassEntry
                    break

        TargetClass["HitDiceTotal"] = max(1, MaxVal)
        TargetClass["HitDiceUsed"]  = max(0, TargetClass["HitDiceTotal"] - CurrentVal)

    def GetDeathSaves(self, DetailData: dict[str, Typing.Any]) -> tuple[int, int]:
        DeathSavesData: dict[str, Typing.Any] = DetailData.setdefault("DeathSaves", {"SuccessCount": 0, "FailureCount": 0})
        SuccessCount  : int                   = int(DeathSavesData.get("SuccessCount", 0))
        FailureCount  : int                   = int(DeathSavesData.get("FailureCount", 0))
        return (SuccessCount, FailureCount)

    def FormatDeathSavePips(self, SuccessCount: int, FailureCount: int) -> tuple[str, str]:
        SuccessPips: str = " ".join("●" if (Index < SuccessCount) else "○" for Index in range(3))
        FailurePips: str = " ".join("●" if (Index < FailureCount) else "○" for Index in range(3))
        return (SuccessPips, FailurePips)

    def ModifyDeathSaves(self, DetailData: dict[str, Typing.Any], DeltaSuccess: int = 0, DeltaFailure: int = 0, Reset: bool = False) -> tuple[int, int]:
        if Reset:
            DetailData["DeathSaves"] = {
                "SuccessCount": 0,
                "FailureCount": 0
            }
            return (0, 0)

        DeathSavesData: dict[str, Typing.Any] = DetailData.setdefault("DeathSaves", {"SuccessCount": 0, "FailureCount": 0})
        SuccessCount  : int                   = max(0, min(3, int(DeathSavesData.get("SuccessCount", 0)) + DeltaSuccess))
        FailureCount  : int                   = max(0, min(3, int(DeathSavesData.get("FailureCount", 0)) + DeltaFailure))
        DeathSavesData["SuccessCount"]        = SuccessCount
        DeathSavesData["FailureCount"]        = FailureCount
        return (SuccessCount, FailureCount)

    def RollDeathSave(self, DetailData: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        DeathSavesData: dict[str, Typing.Any] = DetailData.setdefault("DeathSaves", {"SuccessCount": 0, "FailureCount": 0})
        SuccessCount  : int                   = int(DeathSavesData.get("SuccessCount", 0))
        FailureCount  : int                   = int(DeathSavesData.get("FailureCount", 0))

        RollOutcome  = self.DiceRoller.EvaluateRoll("1d20")
        RollValue    : int  = RollOutcome.Total
        StatusMessage: str  = "Dying"
        IsNat20      : bool = (RollValue == 20)
        IsNat1       : bool = (RollValue == 1)

        if IsNat20:
            SuccessCount = 0
            FailureCount = 0
            DeathSavesData["SuccessCount"] = 0
            DeathSavesData["FailureCount"] = 0
            HitPointsData = DetailData.setdefault("HitPoints", {})
            HitPointsData["CurrentHitPoints"] = max(1, int(HitPointsData.get("CurrentHitPoints", 0)) + 1)
            StatusMessage = "Critical Success! Regained 1 HP and regained consciousness!"

        elif IsNat1:
            FailureCount = min(3, FailureCount + 2)
            DeathSavesData["FailureCount"] = FailureCount
            StatusMessage = "Dead!" if (FailureCount >= 3) else "Critical Failure! 2 failures recorded."

        elif (RollValue >= 10):
            SuccessCount = min(3, SuccessCount + 1)
            DeathSavesData["SuccessCount"] = SuccessCount
            StatusMessage = "Stable!" if (SuccessCount >= 3) else "Success!"

        else:
            FailureCount = min(3, FailureCount + 1)
            DeathSavesData["FailureCount"] = FailureCount
            StatusMessage = "Dead!" if (FailureCount >= 3) else "Failure!"

        SuccessPips, FailurePips = self.FormatDeathSavePips(SuccessCount, FailureCount)
        return {
            "RollValue"        : RollValue,
            "IsNatural20"      : IsNat20,
            "IsNatural1"       : IsNat1,
            "SuccessCount"     : SuccessCount,
            "FailureCount"     : FailureCount,
            "SuccessPips"      : SuccessPips,
            "FailurePips"      : FailurePips,
            "StatusMessage"    : StatusMessage,
            "IsStable"         : (SuccessCount >= 3),
            "IsDead"           : (FailureCount >= 3),
            "RegainedConscious": IsNat20
        }

    def FormatSheetEmbed(self, CharacterRecord: dict[str, Typing.Any]) -> Discord.Embed:
        CharacterName     : str  = str(CharacterRecord.get("Name", "Hero"))
        DetailData   : dict = CharacterRecord.get("DetailData", {})
        SpeciesData  : dict = DetailData.get("Species", {})
        SpeciesName  : str  = str(SpeciesData.get("SpeciesName", "Unknown Species"))
        TotalLevel   : int  = int(DetailData.get("TotalLevel", 1))
        ClassesList  : list = DetailData.get("Classes", [])
        ClassDesc    : str  = ", ".join(f"{C.get("ClassName", "")} {C.get("Level", "")}" for C in ClassesList) or "Adventurer 1"

        SheetEmbed: Discord.Embed = Discord.Embed(title = CharacterName, description = f"Level {TotalLevel} • {SpeciesName} • {ClassDesc}", color = 0x0030A6)

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
            ModifierItem      : int  = int(AbilEntry.get("Modifier", (Score - 10) // 2))
            ScoreStrings.append(f"**{Abil[:3].upper()}**: {Score} ({"+" if (ModifierItem >= 0) else ""}{ModifierItem})")

        SheetEmbed.add_field(name = "Ability Scores", value = " | ".join(ScoreStrings[:3]) + "\n" + " | ".join(ScoreStrings[3:]), inline = False)

        PassivePerception: int = int(DetailData.get("PassivePerception", 10))
        InitiativeBonus  : int = int(DetailData.get("InitiativeBonus", 0))
        SpeedData        : dict = DetailData.get("Speed", {})
        WalkingSpeed     : int  = int(SpeedData.get("WalkingSpeedFeet", 30))
        StatsLine        : str  = f"**Passive Perception:** {PassivePerception} | **Initiative:** {"+" if (InitiativeBonus >= 0) else ""}{InitiativeBonus} | **Speed:** {WalkingSpeed} ft"
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

        SheetEmbed.set_footer(text = f"Character ID: {CharacterRecord.get("ID")} • MIS Platform")
        return SheetEmbed

