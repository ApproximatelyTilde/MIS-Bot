import random                  as RandomLibrary
import re                      as RegularExpressions
import typing                  as Typing
import discord                 as Discord
import pydantic                as Pydantic
import Configuration.Config    as Config
import Services.DebugService   as Debug
import Services.PlatformClient as PlatformClient

DEFAULT_DIFFICULTY_AVERAGE: int = 8
COLOR_MGT2E_EMBED         : int = 0x005E5E
COLOR_SUCCESS_EMBED       : int = 0x005E00
COLOR_FAILURE_EMBED       : int = 0xA60000

CHARACTERISTIC_LOOKUP: dict[str, str] = {
    "str": "Strength",
    "dex": "Dexterity",
    "end": "Endurance",
    "int": "Intelligence",
    "edu": "Education",
    "soc": "SocialStanding",
    "strength": "Strength",
    "dexterity": "Dexterity",
    "endurance": "Endurance",
    "intelligence": "Intelligence",
    "education": "Education",
    "socialstanding": "SocialStanding",
    "social": "SocialStanding"
}

SKILL_DEFAULT_CHARACTERISTICS: dict[str, str] = {
    "admin"              : "Education",
    "advocate"           : "SocialStanding",
    "animals"            : "Intelligence",
    "art"                : "SocialStanding",
    "astrogation"        : "Education",
    "athletics"          : "Dexterity",
    "broker"             : "SocialStanding",
    "carouse"            : "SocialStanding",
    "deception"          : "SocialStanding",
    "diplomat"           : "SocialStanding",
    "drive"              : "Dexterity",
    "electronics"        : "Education",
    "engineer"           : "Education",
    "explosives"         : "Education",
    "flyer"              : "Dexterity",
    "gambler"            : "Intelligence",
    "gun combat"         : "Dexterity",
    "guncombat"          : "Dexterity",
    "gunner"             : "Dexterity",
    "heavy weapons"      : "Endurance",
    "heavyweapons"       : "Endurance",
    "investigate"        : "Intelligence",
    "jack of all trades" : "Education",
    "jackofalltrades"    : "Education",
    "language"           : "Education",
    "leadership"         : "SocialStanding",
    "mechanic"           : "Education",
    "medic"              : "Education",
    "melee"              : "Strength",
    "navigation"         : "Education",
    "persuade"           : "SocialStanding",
    "pilot"              : "Dexterity",
    "recon"              : "Intelligence",
    "science"            : "Education",
    "seafarer"           : "Dexterity",
    "stealth"            : "Dexterity",
    "steward"            : "SocialStanding",
    "streetwise"         : "Intelligence",
    "survival"           : "Endurance",
    "tactics"            : "Intelligence",
    "vacc suit"          : "Endurance",
    "vaccsuit"           : "Endurance"
}

class MGT2ERollOutcome(Pydantic.BaseModel):
    RawFormula          : str
    DiceRolls           : list[int]
    KeptRolls           : list[int]
    BaseTotal           : int
    ModifierTotal       : int
    Total               : int
    TargetDifficulty    : int
    Effect              : int
    IsSuccess           : bool
    IsExceptionalSuccess: bool
    IsExceptionalFailure: bool
    OutcomeDescription  : str
    BreakdownString     : str

class MGT2EStateService:
    def __init__(self, PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None) -> None:
        self.PlatformClient     : PlatformClient.MISPlatformClient = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.MISPlatformClient()
        self.ActiveCharacterMap : dict[str, str]                   = dict()
        self.CharacterCache     : dict[str, dict[str, Typing.Any]] = dict()

    def CalculateCharacteristicModifier(self, ScoreValue: int) -> int:
        if (ScoreValue <= 0):
            return -3

        if (ScoreValue <= 2):
            return -2

        if (ScoreValue <= 5):
            return -1

        if (ScoreValue <= 8):
            return 0

        if (ScoreValue <= 11):
            return 1

        if (ScoreValue <= 14):
            return 2

        return 3

    def NormalizeCharacteristicName(self, RawName: str) -> str:
        CleanKey: str = RawName.strip().lower()
        return CHARACTERISTIC_LOOKUP.get(CleanKey, RawName.title())

    def GetDefaultCharacteristicForSkill(self, SkillName: str) -> str:
        CleanName: str = SkillName.strip().lower()
        if ("(" in CleanName):
            CleanName = CleanName.split("(", 1)[0].strip()

        return SKILL_DEFAULT_CHARACTERISTICS.get(CleanName, "Education")

    def IsSkillTrained(self, SkillsDictionary: dict[str, int], TargetSkill: str) -> bool:
        NormalizedTarget: str = TargetSkill.strip().lower()
        if (NormalizedTarget == "jack of all trades") or (NormalizedTarget == "jackofalltrades"):
            return False

        for SkillKey, SkillValue in SkillsDictionary.items():
            NormalizedKey: str = SkillKey.strip().lower()
            if (NormalizedKey == NormalizedTarget) and (SkillValue >= 0):
                return True

        if ("(" in TargetSkill):
            GroupName: str = TargetSkill.split("(", 1)[0].strip().lower()
            for SkillKey, SkillValue in SkillsDictionary.items():
                NormalizedKey = SkillKey.strip().lower()
                if (NormalizedKey.startswith(GroupName) or (NormalizedKey == GroupName)) and (SkillValue >= 0):
                    return True

        else:
            for SkillKey, SkillValue in SkillsDictionary.items():
                NormalizedKey = SkillKey.strip().lower()
                if NormalizedKey.startswith(f"{NormalizedTarget} (") and (SkillValue >= 0):
                    return True

        return False

    def GetSkillModifier(self, SkillsDictionary: dict[str, int], TargetSkill: str) -> int:
        NormalizedTarget: str = TargetSkill.strip().lower()
        for SkillKey, SkillValue in SkillsDictionary.items():
            if (SkillKey.strip().lower() == NormalizedTarget):
                return SkillValue

        if self.IsSkillTrained(SkillsDictionary, TargetSkill):
            return 0

        JackOfAllTradesLevel: int = 0
        for SkillKey, SkillValue in SkillsDictionary.items():
            if (SkillKey.strip().lower() in ("jack of all trades", "jackofalltrades")):
                JackOfAllTradesLevel = max(0, SkillValue)
                break

        UntrainedPenalty: int = -3 + JackOfAllTradesLevel
        return min(0, UntrainedPenalty)

    def EvaluateRoll(self, Modifier: int = 0, NetBoons: int = 0, TargetDifficulty: int = DEFAULT_DIFFICULTY_AVERAGE, LabelText: str = "") -> MGT2ERollOutcome:
        DiceCount: int = 3 if (NetBoons != 0) else 2
        Rolls    : list[int] = [RandomLibrary.randint(1, 6) for _ in range(DiceCount)]

        if (NetBoons > 0):
            SortedRolls: list[int] = sorted(Rolls, reverse = True)
            KeptRolls  : list[int] = SortedRolls[:2]
            FormulaTag : str       = "3d6 (Boon)"

        elif (NetBoons < 0):
            SortedRolls = sorted(Rolls)
            KeptRolls   = SortedRolls[:2]
            FormulaTag  = "3d6 (Bane)"

        else:
            KeptRolls  = Rolls[:]
            FormulaTag = "2d6"

        BaseTotal: int            = sum(KeptRolls)
        Total    : int            = BaseTotal + Modifier
        Effect   : int            = Total - TargetDifficulty
        IsSuccess: bool           = (Total >= TargetDifficulty)
        IsExceptionalSuccess: bool = (Effect >= 6)
        IsExceptionalFailure: bool = (Effect <= -6)

        if IsExceptionalSuccess:
            OutcomeDescription: str = f"Exceptional Success (Effect +{Effect})"

        elif IsExceptionalFailure:
            OutcomeDescription = f"Exceptional Failure (Effect {Effect})"

        elif IsSuccess:
            OutcomeDescription = f"Success (Effect +{Effect})" if (Effect > 0) else "Marginal Success (Effect 0)"

        else:
            OutcomeDescription = f"Failure (Effect {Effect})"

        ModifierString: str = f" {"+" if (Modifier >= 0) else "-"} {abs(Modifier)}" if (Modifier != 0) else ""
        Breakdown     : str = f"[{", ".join(str(R) for R in Rolls)}] ➔ Kept [{KeptRolls[0]}, {KeptRolls[1]}]{ModifierString} = **{Total}** vs Diff {TargetDifficulty}"

        return MGT2ERollOutcome(RawFormula = FormulaTag, DiceRolls = Rolls, KeptRolls = KeptRolls, BaseTotal = BaseTotal, ModifierTotal = Modifier, Total = Total, TargetDifficulty = TargetDifficulty, Effect = Effect, IsSuccess = IsSuccess, IsExceptionalSuccess = IsExceptionalSuccess, IsExceptionalFailure = IsExceptionalFailure, OutcomeDescription = OutcomeDescription, BreakdownString = Breakdown)

    def ApplyPhysicalDamage(self, Characteristics: dict[str, int], DamageAmount: int, TargetAttribute: Typing.Optional[str] = None) -> tuple[dict[str, int], str]:
        RemainingDamage: int           = max(0, DamageAmount)
        Updated        : dict[str, int] = dict(Characteristics)
        DamageLog      : list[str]     = []

        CurrentEND: int = Updated.get("Endurance", 10)
        AbsorbedEND: int = min(CurrentEND, RemainingDamage)
        Updated["Endurance"] = CurrentEND - AbsorbedEND
        RemainingDamage      -= AbsorbedEND
        DamageLog.append(f"**END**: {CurrentEND} ➔ **{Updated["Endurance"]}** (-{AbsorbedEND})")

        SecondAttribute: str = self.NormalizeCharacteristicName(TargetAttribute) if (TargetAttribute is not None) else "Strength"
        if (SecondAttribute not in ("Strength", "Dexterity")):
            SecondAttribute = "Strength"

        ThirdAttribute: str = "Dexterity" if (SecondAttribute == "Strength") else "Strength"

        if (RemainingDamage > 0):
            CurrentSecond: int  = Updated.get(SecondAttribute, 10)
            AbsorbedSecond: int = min(CurrentSecond, RemainingDamage)
            Updated[SecondAttribute] = CurrentSecond - AbsorbedSecond
            RemainingDamage         -= AbsorbedSecond
            DamageLog.append(f"**{SecondAttribute[:3].upper()}**: {CurrentSecond} ➔ **{Updated[SecondAttribute]}** (-{AbsorbedSecond})")

        if (RemainingDamage > 0):
            CurrentThird: int  = Updated.get(ThirdAttribute, 10)
            AbsorbedThird: int = min(CurrentThird, RemainingDamage)
            Updated[ThirdAttribute] = CurrentThird - AbsorbedThird
            RemainingDamage        -= AbsorbedThird
            DamageLog.append(f"**{ThirdAttribute[:3].upper()}**: {CurrentThird} ➔ **{Updated[ThirdAttribute]}** (-{AbsorbedThird})")

        PhysicalZeros: int = sum(1 for Attr in ("Endurance", "Strength", "Dexterity") if Updated.get(Attr, 0) <= 0)
        StatusAlert  : str = ""
        if (PhysicalZeros >= 3):
            StatusAlert = "\n\n💀 **CRITICAL TRAUMA: DEAD / DYING** (All 3 physical characteristics reduced to 0!)"

        elif (PhysicalZeros >= 2):
            StatusAlert = "\n\n⚠️ **UNCONSCIOUS** (Two physical characteristics reduced to 0!)"

        SummaryText: str = "\n".join(DamageLog) + StatusAlert
        return (Updated, SummaryText)

    def ApplyPhysicalHealing(self, Characteristics: dict[str, int], MaxCharacteristics: dict[str, int], HealAmount: int, TargetAttribute: Typing.Optional[str] = None) -> tuple[dict[str, int], str]:
        RemainingHeal: int           = max(0, HealAmount)
        Updated      : dict[str, int] = dict(Characteristics)
        HealLog      : list[str]     = []

        TargetOrder: list[str] = [self.NormalizeCharacteristicName(TargetAttribute)] if (TargetAttribute is not None) else ["Endurance", "Strength", "Dexterity"]
        for Attr in ("Endurance", "Strength", "Dexterity"):
            if Attr not in TargetOrder:
                TargetOrder.append(Attr)

        for Attr in TargetOrder:
            if (RemainingHeal <= 0):
                break

            CurrentVal: int = Updated.get(Attr, 0)
            MaxVal    : int = MaxCharacteristics.get(Attr, 10)
            Missing   : int = max(0, MaxVal - CurrentVal)
            if (Missing > 0):
                HealedVal: int = min(Missing, RemainingHeal)
                Updated[Attr]  = CurrentVal + HealedVal
                RemainingHeal -= HealedVal
                HealLog.append(f"**{Attr[:3].upper()}**: {CurrentVal} ➔ **{Updated[Attr]}** (+{HealedVal})")

        SummaryText: str = "\n".join(HealLog) if (bool(HealLog)) else "All physical characteristics are already at maximum."
        return (Updated, SummaryText)

    def BuildContextKey(self, DiscordUserID: int | str, ChannelID: int | str) -> str:
        return f"{DiscordUserID}:{ChannelID}"

    def SetActiveCharacter(self, DiscordUserID: int | str, ChannelID: int | str, CharacterID: str) -> None:
        ContextKey: str = self.BuildContextKey(DiscordUserID, ChannelID)
        self.ActiveCharacterMap[ContextKey] = CharacterID
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Active MGT2E Character Set: UserID={DiscordUserID}, CharacterID={CharacterID}")

    def GetActiveCharacterID(self, DiscordUserID: int | str, ChannelID: int | str) -> Typing.Optional[str]:
        ContextKey: str = self.BuildContextKey(DiscordUserID, ChannelID)
        return self.ActiveCharacterMap.get(ContextKey)

    def FormatSheetEmbed(self, CharacterRecord: dict[str, Typing.Any]) -> Discord.Embed:
        SummaryData    : dict = CharacterRecord.get("SummaryData", {})
        DetailData     : dict = CharacterRecord.get("DetailData", {})
        Characteristics: dict = DetailData.get("Characteristics", {})
        Skills         : dict = DetailData.get("Skills", {})
        InventoryList  : list = DetailData.get("Inventory", [])
        CurrencyDictionary   : dict = DetailData.get("Currency", {})

        CharacterName : str = str(CharacterRecord.get("Name", "Traveller"))
        Career   : str = str(SummaryData.get("Career", "Citizen"))
        Terms    : int = int(SummaryData.get("Terms", 1))
        Age      : int = int(SummaryData.get("Age", 22))
        Homeworld: str = str(SummaryData.get("Homeworld", "Core"))
        Title    : str = str(SummaryData.get("Title", "Citizen"))
        Credits  : int = int(CurrencyDictionary.get("Credits", 0))

        SheetEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName} — {Title}", description = f"**Career:** {Career} | **Terms:** {Terms} | **Age:** {Age}\n**Homeworld:** {Homeworld} | **Credits:** Cr {Credits:,}", color = COLOR_MGT2E_EMBED)

        AttrLines: list[str] = []
        for ShortCode, FullName in [("STR", "Strength"), ("DEX", "Dexterity"), ("END", "Endurance"), ("INT", "Intelligence"), ("EDU", "Education"), ("SOC", "SocialStanding")]:
            ScoreValue: int = int(Characteristics.get(FullName, 7))
            ModifierValue  : int = self.CalculateCharacteristicModifier(ScoreValue)
            AttrLines.append(f"**{ShortCode}**: {ScoreValue:>2} (`{"+" if (ModifierValue >= 0) else ""}{ModifierValue}`)")

        SheetEmbed.add_field(name = "Characteristics", value = " • ".join(AttrLines[:3]) + "\n" + " • ".join(AttrLines[3:]), inline = False)

        TrainedSkills: list[str] = [f"**{SkillKey}**: {SkillVal}" for SkillKey, SkillVal in sorted(Skills.items()) if (SkillVal >= 0)]
        SkillsText   : str       = ", ".join(TrainedSkills) if (bool(TrainedSkills)) else "No trained skills."
        SheetEmbed.add_field(name = f"Trained Skills ({len(TrainedSkills)})", value = SkillsText[:1020], inline = False)

        InventoryText: str = "\n".join(f"• {Item}" for Item in InventoryList) if (bool(InventoryList)) else "Empty inventory."
        SheetEmbed.add_field(name = "Inventory", value = InventoryText[:1020], inline = False)

        SheetEmbed.set_footer(text = "MIS-Bot • Mongoose Traveller Character Sheet")
        return SheetEmbed

    async def ResolveActiveCharacter(self, DiscordUserID: int | str, ChannelID: int | str) -> Typing.Optional[dict[str, Typing.Any]]:
        ContextKey: str = self.BuildContextKey(DiscordUserID, ChannelID)
        ActiveCharacterID: Typing.Optional[str] = self.ActiveCharacterMap.get(ContextKey)

        if (ActiveCharacterID is not None) and (ActiveCharacterID in self.CharacterCache):
            return self.CharacterCache[ActiveCharacterID]

        MatchedList    : list[dict[str, Typing.Any]] = await self.PlatformClient.FetchCharactersByDiscordID(str(DiscordUserID))
        MGT2ECharacters: list[dict[str, Typing.Any]] = [C for C in MatchedList if (C.get("GameSystem") == "MGT2E")]

        if not MGT2ECharacters:
            return None

        SelectedRecord: dict[str, Typing.Any] = MGT2ECharacters[0]
        if (ActiveCharacterID is not None):
            for Candidate in MGT2ECharacters:
                if (Candidate.get("ID") == ActiveCharacterID):
                    SelectedRecord = Candidate
                    break

        CharacterID: str = str(SelectedRecord.get("ID"))
        self.CharacterCache[CharacterID] = SelectedRecord
        self.ActiveCharacterMap[ContextKey] = CharacterID
        return SelectedRecord
