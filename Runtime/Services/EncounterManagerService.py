import datetime                        as DateTime
import typing                          as Typing
import discord                         as Discord
import pydantic                        as Pydantic
import Runtime.Services.DebugService   as Debug
import Runtime.Services.PlatformClient as PlatformClient

COLOR_ENCOUNTER_ACTIVE: int = 0x0030A6
COLOR_MGT2E_ACTIVE    : int = 0x005E5E
COLOR_ENCOUNTER_ENDED : int = 0x595959

class CombatantEntry(Pydantic.BaseModel):
    model_config = Pydantic.ConfigDict(populate_by_name = True, arbitrary_types_allowed = True)

    ID                 : str
    Name               : str
    Initiative         : int
    CurrentHitPoints   : int
    MaxHitPoints       : int
    TemporaryHitPoints : int                                    = 0
    ArmorClass         : int                                    = 10
    ArmorProtection    : int                                    = 0
    Conditions         : list[str]                              = Pydantic.Field(default_factory = list)
    EntityType         : str                                    = "Character"
    ParentCharacterID  : Typing.Optional[str]                   = None
    IsMonster          : bool                                   = False
    ControllerDiscordID: Typing.Optional[str]                   = None
    CharacterID        : Typing.Optional[str]                   = None
    MonsterData        : Typing.Optional[dict[str, Typing.Any]] = None
    Characteristics    : Typing.Optional[dict[str, int]]        = None
    MaxCharacteristics : Typing.Optional[dict[str, int]]        = None
    VehicleStats       : Typing.Optional[dict[str, Typing.Any]] = None
    PassivePerception  : int                                    = 10
    InitiativeBonus    : int                                    = 0
    GroupName          : Typing.Optional[str]                   = None
    IsHidden           : bool                                   = False
    Note               : Typing.Optional[str]                   = None
    ThumbnailURL       : Typing.Optional[str]                   = None
    ActiveEffects      : list[dict[str, Typing.Any]]            = Pydantic.Field(default_factory = list)

    @property
    def Effects(self) -> list[dict[str, Typing.Any]]:
        return self.ActiveEffects

    @Effects.setter
    def Effects(self, Value: list[dict[str, Typing.Any]]) -> None:
        self.ActiveEffects = Value

    @Pydantic.model_validator(mode = "before")
    @classmethod
    def NormalizeEffectsField(cls, ValuesDictionary: Typing.Any) -> Typing.Any:
        if isinstance(ValuesDictionary, dict):
            if ("Effects" in ValuesDictionary) and ("ActiveEffects" not in ValuesDictionary):
                ValuesDictionary["ActiveEffects"] = ValuesDictionary["Effects"]

            RawEntityType: str = str(ValuesDictionary.get("EntityType", ""))
            if (not RawEntityType) and bool(ValuesDictionary.get("IsMonster", False)):
                ValuesDictionary["EntityType"] = "Other"

        return ValuesDictionary

class CombatEncounter(Pydantic.BaseModel):
    model_config = Pydantic.ConfigDict(populate_by_name = True, arbitrary_types_allowed = True)

    ChannelID           : str
    GuildID             : Typing.Optional[str]                   = None
    GameSystem          : str                                    = "DND5E"
    InitiativeMode      : str                                    = "Standard"
    RoundNumber         : int                                    = 1
    ActiveCombatantIndex: int                                    = 0
    Combatants          : list[CombatantEntry]                   = Pydantic.Field(default_factory = list)
    RemainingInRound    : list[str]                              = Pydantic.Field(default_factory = list)
    ActiveEffects       : list[dict[str, Typing.Any]]            = Pydantic.Field(default_factory = list)
    IsActive            : bool                                   = True
    CreatedAt           : DateTime.datetime                      = Pydantic.Field(default_factory = lambda: DateTime.datetime.now(DateTime.timezone.utc))

    @property
    def CurrentTurnIndex(self) -> int:
        return self.ActiveCombatantIndex

    @CurrentTurnIndex.setter
    def CurrentTurnIndex(self, Value: int) -> None:
        self.ActiveCombatantIndex = Value

    @Pydantic.model_validator(mode = "before")
    @classmethod
    def NormalizeTurnIndexField(cls, ValuesDictionary: Typing.Any) -> Typing.Any:
        if isinstance(ValuesDictionary, dict):
            if ("CurrentTurnIndex" in ValuesDictionary) and ("ActiveCombatantIndex" not in ValuesDictionary):
                ValuesDictionary["ActiveCombatantIndex"] = ValuesDictionary["CurrentTurnIndex"]

        return ValuesDictionary

    def SynchronizeGroupInitiatives(self) -> None:
        GroupInitiatives: dict[str, int] = dict()
        for Combatant in self.Combatants:
            if (Combatant.GroupName is not None):
                ExistingScore: int = GroupInitiatives.get(Combatant.GroupName, Combatant.Initiative)
                GroupInitiatives[Combatant.GroupName] = max(ExistingScore, Combatant.Initiative)

        for Combatant in self.Combatants:
            if (Combatant.GroupName is not None) and (Combatant.GroupName in GroupInitiatives):
                Combatant.Initiative = GroupInitiatives[Combatant.GroupName]

    def SortCombatants(self) -> None:
        if (self.InitiativeMode == "Popcorn"):
            return

        self.SynchronizeGroupInitiatives()
        self.Combatants.sort(key = lambda C: (C.Initiative, C.PassivePerception, C.InitiativeBonus), reverse = True)

    def GetActiveCombatant(self) -> Typing.Optional[CombatantEntry]:
        if not self.Combatants:
            return None

        SafeIndex: int = self.ActiveCombatantIndex % len(self.Combatants)
        return self.Combatants[SafeIndex]

    def GetRemainingCombatants(self) -> list[CombatantEntry]:
        if not self.RemainingInRound:
            return list(self.Combatants)

        RemainingSet: set[str] = set(self.RemainingInRound)
        return [Candidate for Candidate in self.Combatants if (Candidate.ID in RemainingSet)]

    def PassTurn(self, TargetID: str) -> tuple[Typing.Optional[CombatantEntry], int, bool]:
        if not self.Combatants:
            return (None, self.RoundNumber, False)

        TargetCombatant: Typing.Optional[CombatantEntry] = self.FindCombatant(TargetID)
        if (TargetCombatant is None):
            return (None, self.RoundNumber, False)

        RoundWrapped: bool = False
        if not self.RemainingInRound:
            self.RoundNumber     += 1
            self.RemainingInRound = [Candidate.ID for Candidate in self.Combatants]
            RoundWrapped          = True

        if TargetCombatant.ID not in self.RemainingInRound:
            return (None, self.RoundNumber, RoundWrapped)

        for Index, Candidate in enumerate(self.Combatants):
            if (Candidate.ID == TargetCombatant.ID):
                self.ActiveCombatantIndex = Index
                break

        self.RemainingInRound.remove(TargetCombatant.ID)
        return (TargetCombatant, self.RoundNumber, RoundWrapped)

    def AdvanceTurn(self) -> tuple[Typing.Optional[CombatantEntry], int]:
        if not self.Combatants:
            return (None, self.RoundNumber)

        if (self.InitiativeMode == "Popcorn"):
            RemainingList: list[CombatantEntry] = self.GetRemainingCombatants()
            if (len(RemainingList) > 0):
                NextEntry, RoundNum, _ = self.PassTurn(RemainingList[0].ID)
                return (NextEntry, RoundNum)

        self.ActiveCombatantIndex += 1
        if (self.ActiveCombatantIndex >= len(self.Combatants)):
            self.ActiveCombatantIndex = 0
            self.RoundNumber         += 1

        ActiveCombatant: CombatantEntry = self.Combatants[self.ActiveCombatantIndex]
        return (ActiveCombatant, self.RoundNumber)

    def PreviousTurn(self) -> tuple[Typing.Optional[CombatantEntry], int]:
        if not self.Combatants:
            return (None, self.RoundNumber)

        self.ActiveCombatantIndex -= 1
        if (self.ActiveCombatantIndex < 0):
            self.ActiveCombatantIndex = len(self.Combatants) - 1
            self.RoundNumber          = max(1, self.RoundNumber - 1)

        ActiveCombatant: CombatantEntry = self.Combatants[self.ActiveCombatantIndex]
        return (ActiveCombatant, self.RoundNumber)

    def AddCombatant(self, Entry: CombatantEntry) -> None:
        CurrentActive: Typing.Optional[CombatantEntry] = self.GetActiveCombatant()
        self.Combatants.append(Entry)
        if (self.InitiativeMode == "Popcorn"):
            if Entry.ID not in self.RemainingInRound:
                self.RemainingInRound.append(Entry.ID)

            return

        self.SortCombatants()
        if (CurrentActive is not None):
            for Index, Candidate in enumerate(self.Combatants):
                if (Candidate.ID == CurrentActive.ID):
                    self.ActiveCombatantIndex = Index
                    break

    def RemoveCombatant(self, TargetID: str) -> Typing.Optional[CombatantEntry]:
        CleanID       : str                             = TargetID.strip().lower()
        FoundIndex    : Typing.Optional[int]            = None
        FoundCombatant: Typing.Optional[CombatantEntry] = None

        if CleanID.isdigit():
            TargetIndex: int = int(CleanID) - 1
            if (0 <= TargetIndex < len(self.Combatants)):
                FoundIndex     = TargetIndex
                FoundCombatant = self.Combatants[TargetIndex]

        if (FoundCombatant is None):
            for Index, Combatant in enumerate(self.Combatants):
                if (Combatant.ID.lower() == CleanID) or (Combatant.Name.lower() == CleanID):
                    FoundIndex     = Index
                    FoundCombatant = Combatant
                    break

        if (FoundCombatant is None):
            for Index, Combatant in enumerate(self.Combatants):
                if CleanID in Combatant.Name.lower():
                    FoundIndex     = Index
                    FoundCombatant = Combatant
                    break

        if (FoundIndex is not None) and (FoundCombatant is not None):
            self.Combatants.pop(FoundIndex)
            if FoundCombatant.ID in self.RemainingInRound:
                self.RemainingInRound.remove(FoundCombatant.ID)

            if (self.ActiveCombatantIndex >= len(self.Combatants)):
                self.ActiveCombatantIndex = max(0, len(self.Combatants) - 1)

            return FoundCombatant

        return None

    def FindCombatant(self, TargetID: str) -> Typing.Optional[CombatantEntry]:
        CleanID: str = TargetID.strip().lower()
        if CleanID.isdigit():
            TargetIndex: int = int(CleanID) - 1
            if (0 <= TargetIndex < len(self.Combatants)):
                return self.Combatants[TargetIndex]

        for Combatant in self.Combatants:
            if (Combatant.ID.lower() == CleanID) or (Combatant.Name.lower() == CleanID):
                return Combatant

        for Combatant in self.Combatants:
            if CleanID in Combatant.Name.lower():
                return Combatant

        return None

    def FindCombatantsByController(self, DiscordUserID: str) -> list[CombatantEntry]:
        TargetUserStr: str = str(DiscordUserID).strip()
        return [Candidate for Candidate in self.Combatants if (Candidate.ControllerDiscordID == TargetUserStr)]

class EncounterManagerService:
    def __init__(self, PlatformClientInstance: Typing.Optional[PlatformClient.TallyPlatformClient] = None) -> None:
        self.EncountersByChannel: dict[str, CombatEncounter]                        = dict()
        self.PlatformClient     : Typing.Optional[PlatformClient.TallyPlatformClient] = PlatformClientInstance

    def CreateEncounter(self, ChannelID: int | str, GuildID: Typing.Optional[int | str] = None, GameSystem: str = "DND5E", InitiativeMode: str = "Standard") -> CombatEncounter:
        ChannelKey: str                  = str(ChannelID)
        GuildKey  : Typing.Optional[str] = str(GuildID) if (GuildID is not None) else None
        NewEncounter: Typing.Any = CombatEncounter(ChannelID = ChannelKey, GuildID = GuildKey, GameSystem = GameSystem, InitiativeMode = InitiativeMode)
        self.EncountersByChannel[ChannelKey] = NewEncounter
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Combat Encounter Created: ChannelID={ChannelKey}, System={GameSystem}, Mode={InitiativeMode}")
        return NewEncounter

    async def CreateEncounterAsync(self, ChannelID: int | str, GuildID: Typing.Optional[int | str] = None, GameSystem: str = "DND5E", InitiativeMode: str = "Standard") -> CombatEncounter:
        NewEncounter: CombatEncounter = self.CreateEncounter(ChannelID = ChannelID, GuildID = GuildID, GameSystem = GameSystem, InitiativeMode = InitiativeMode)
        await self.SaveEncounterAsync(ChannelID)
        return NewEncounter

    def GetEncounter(self, ChannelID: int | str) -> Typing.Optional[CombatEncounter]:
        ChannelKey: str = str(ChannelID)
        return self.EncountersByChannel.get(ChannelKey)

    async def GetOrLoadEncounterAsync(self, ChannelID: int | str) -> Typing.Optional[CombatEncounter]:
        ChannelKey: str = str(ChannelID)
        if ChannelKey in self.EncountersByChannel:
            return self.EncountersByChannel[ChannelKey]

        if (self.PlatformClient is not None):
            try:
                EncounterDictionary: Typing.Optional[dict[str, Typing.Any]] = await self.PlatformClient.FetchCombatEncounter(ChannelKey)
                if (EncounterDictionary is not None) and bool(EncounterDictionary.get("IsActive", True)):
                    CombatantsData  : list[dict[str, Typing.Any]] = EncounterDictionary.get("Combatants", [])
                    ParsedCombatants: list[CombatantEntry]        = []
                    for CombatantPayload in CombatantsData:
                        ParsedCombatants.append(CombatantEntry.model_validate(CombatantPayload))

                    LoadedEncounter: Typing.Any = CombatEncounter(ChannelID = str(EncounterDictionary.get("ChannelID", ChannelKey)), GuildID = EncounterDictionary.get("GuildID"), GameSystem = str(EncounterDictionary.get("GameSystem", "DND5E")), InitiativeMode = str(EncounterDictionary.get("InitiativeMode", "Standard")), RoundNumber = int(EncounterDictionary.get("RoundNumber", 1)), ActiveCombatantIndex = int(EncounterDictionary.get("ActiveCombatantIndex", 0)), Combatants = ParsedCombatants, RemainingInRound = list(EncounterDictionary.get("RemainingInRound", [])), ActiveEffects = EncounterDictionary.get("ActiveEffects", []), IsActive = bool(EncounterDictionary.get("IsActive", True)))
                    self.EncountersByChannel[ChannelKey] = LoadedEncounter
                    Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Loaded Combat Encounter from Platform: ChannelID={ChannelKey}")
                    return LoadedEncounter

            except Exception as LoadException:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Load Encounter from Platform: ChannelID={ChannelKey}, Error=\"{str(LoadException)}\"")

        return None

    async def SaveEncounterAsync(self, ChannelID: int | str) -> None:
        ChannelKey: str                              = str(ChannelID)
        Encounter : Typing.Optional[CombatEncounter] = self.EncountersByChannel.get(ChannelKey)
        if (Encounter is None):
            return

        if (self.PlatformClient is not None):
            try:
                PayloadDictionary: dict[str, Typing.Any] = {
                    "RoundNumber"         : Encounter.RoundNumber,
                    "ActiveCombatantIndex": Encounter.ActiveCombatantIndex,
                    "GameSystem"          : Encounter.GameSystem,
                    "InitiativeMode"      : Encounter.InitiativeMode,
                    "RemainingInRound"    : Encounter.RemainingInRound,
                    "Combatants"          : [Combatant.model_dump() for Combatant in Encounter.Combatants],
                    "ActiveEffects"       : Encounter.ActiveEffects,
                    "GuildID"             : Encounter.GuildID
                }
                await self.PlatformClient.SaveCombatEncounter(ChannelKey, PayloadDictionary)

            except Exception as SaveException:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Save Encounter to Platform: ChannelID={ChannelKey}, Error=\"{str(SaveException)}\"")

    def EndEncounter(self, ChannelID: int | str) -> Typing.Optional[CombatEncounter]:
        ChannelKey: str = str(ChannelID)
        if ChannelKey in self.EncountersByChannel:
            EndedEncounter: Typing.Any = self.EncountersByChannel.pop(ChannelKey)
            EndedEncounter.IsActive = False
            Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Combat Encounter Ended: ChannelID={ChannelKey}, TotalRounds={EndedEncounter.RoundNumber}")
            return EndedEncounter

        return None

    async def EndEncounterAsync(self, ChannelID: int | str) -> Typing.Optional[CombatEncounter]:
        ChannelKey    : str                              = str(ChannelID)
        EndedEncounter: Typing.Optional[CombatEncounter] = self.EndEncounter(ChannelKey)

        if (self.PlatformClient is not None):
            try:
                await self.PlatformClient.DeleteCombatEncounter(ChannelKey)

            except Exception as DeleteException:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Delete Encounter on Platform: ChannelID={ChannelKey}, Error=\"{str(DeleteException)}\"")

        return EndedEncounter

    def FormatMGT2EVitals(self, Combatant: CombatantEntry) -> str:
        if (Combatant.EntityType == "Vehicle") or (Combatant.VehicleStats is not None):
            StatsDictionary: dict[str, Typing.Any] = Combatant.VehicleStats or {}
            CurrentHull    : int                   = int(StatsDictionary.get("HullPoints", Combatant.CurrentHitPoints))
            MaxHull        : int                   = int(StatsDictionary.get("MaxHullPoints", Combatant.MaxHitPoints))
            return f"Hull {CurrentHull}/{MaxHull} | Armor {Combatant.ArmorProtection}"

        if (Combatant.Characteristics is not None):
            MaxDictionary: dict[str, int] = Combatant.MaxCharacteristics or Combatant.Characteristics
            CurEND       : int            = int(Combatant.Characteristics.get("Endurance", Combatant.CurrentHitPoints))
            MaxEND       : int            = int(MaxDictionary.get("Endurance", Combatant.MaxHitPoints))
            CurSTR       : int            = int(Combatant.Characteristics.get("Strength", 7))
            MaxSTR       : int            = int(MaxDictionary.get("Strength", CurSTR))
            CurDEX       : int            = int(Combatant.Characteristics.get("Dexterity", 7))
            MaxDEX       : int            = int(MaxDictionary.get("Dexterity", CurDEX))
            ZeroCount    : int            = sum(1 for CounterValue in (CurEND, CurSTR, CurDEX) if (CounterValue <= 0))
            TraumaStatus : str            = " 💀" if (ZeroCount >= 3) else (" ⚠️" if (ZeroCount >= 2) else "")
            return f"END {CurEND}/{MaxEND} • STR {CurSTR}/{MaxSTR} • DEX {CurDEX}/{MaxDEX} | Armor {Combatant.ArmorProtection}{TraumaStatus}"

        return f"END {Combatant.CurrentHitPoints}/{Combatant.MaxHitPoints} | Armor {Combatant.ArmorProtection}"

    def FormatEncounterEmbed(self, Encounter: CombatEncounter, ViewerDiscordID: Typing.Optional[str] = None, IsDungeonMaster: bool = False, CommandPrefix: Typing.Optional[str] = None) -> Discord.Embed:
        if not Encounter.IsActive:
            EndEmbed: Discord.Embed = Discord.Embed(title = "Combat Ended", description = f"Encounter concluded after **{Encounter.RoundNumber}** rounds.", color = COLOR_ENCOUNTER_ENDED)
            return EndEmbed

        EffectivePrefix: str  = CommandPrefix if (CommandPrefix is not None) else ("." if (Encounter.GameSystem == "MGT2E") else "!")
        IsPopcorn      : bool = (Encounter.InitiativeMode == "Popcorn")
        IsTraveller    : bool = (Encounter.GameSystem == "MGT2E")
        EmbedColor     : int  = COLOR_MGT2E_ACTIVE if IsTraveller else COLOR_ENCOUNTER_ACTIVE

        ActiveCombatant: Typing.Optional[CombatantEntry] = Encounter.GetActiveCombatant()
        ActiveName     : str                             = "None"
        if (ActiveCombatant is not None):
            if ActiveCombatant.IsHidden and (not IsDungeonMaster) and (ViewerDiscordID != ActiveCombatant.ControllerDiscordID):
                ActiveName = "Hidden Combatant"

            else:
                ActiveName = ActiveCombatant.Name

        ModeLabel     : str           = "Popcorn Initiative" if IsPopcorn else "Initiative Tracker"
        EncounterEmbed: Discord.Embed = Discord.Embed(title = f"{ModeLabel} — Round {Encounter.RoundNumber}", description = f"Current Turn: **{ActiveName}**", color = EmbedColor)
        if (ActiveCombatant is not None) and (ActiveCombatant.ThumbnailURL is not None):
            EncounterEmbed.set_thumbnail(url = ActiveCombatant.ThumbnailURL)

        if not Encounter.Combatants:
            AddHint: str = f"`{EffectivePrefix}init add <Name> <Score>`" if IsTraveller else f"`{EffectivePrefix}init mad <Monster>`"
            EncounterEmbed.add_field(name = "Combatants", value = f"No combatants in encounter.\nUse `{EffectivePrefix}init join` or {AddHint} to add participants.", inline = False)
            return EncounterEmbed

        RemainingSet  : set[str]  = set(Encounter.RemainingInRound)
        CombatantLines: list[str] = []
        for Index, Combatant in enumerate(Encounter.Combatants):
            IsCurrentTurn: bool = (Index == Encounter.ActiveCombatantIndex)
            Pointer      : str  = "➔ " if (IsCurrentTurn) else "   "
            CanSeeDetails: bool = (not Combatant.IsHidden) or IsDungeonMaster or (ViewerDiscordID == Combatant.ControllerDiscordID)
            EntityTag    : str  = f" ({Combatant.EntityType})" if (Combatant.EntityType in ("Companion", "Vehicle")) else ""

            if IsPopcorn:
                ActBadge  : str = "⏳" if ((Combatant.ID in RemainingSet) or (not Encounter.RemainingInRound)) else "✅"
                SlotPrefix: str = f"`{Pointer}{ActBadge}`"

            else:
                SlotPrefix = f"`{Pointer}[{Combatant.Initiative:>2}]`"

            if CanSeeDetails:
                ConditionBadge: str = f" [{", ".join(Combatant.Conditions)}]" if (bool(Combatant.Conditions)) else ""
                HiddenBadge   : str = " 👻" if (Combatant.IsHidden) else ""
                NoteBadge     : str = f" • *{Combatant.Note}*" if (Combatant.Note is not None) else ""

                if IsTraveller:
                    VitalsText: str = self.FormatMGT2EVitals(Combatant)

                else:
                    if (Combatant.EntityType == "Vehicle") and (Combatant.VehicleStats is not None):
                        CurHull   : int = int(Combatant.VehicleStats.get("HullPoints", Combatant.CurrentHitPoints))
                        MaxHull   : int = int(Combatant.VehicleStats.get("MaxHullPoints", Combatant.MaxHitPoints))
                        VitalsText      = f"{CurHull}/{MaxHull} Hull | AC {Combatant.ArmorClass}"

                    else:
                        TemporaryString: str = f" (+{Combatant.TemporaryHitPoints})" if (Combatant.TemporaryHitPoints > 0) else ""
                        VitalsText           = f"{Combatant.CurrentHitPoints}/{Combatant.MaxHitPoints}{TemporaryString} HP | AC {Combatant.ArmorClass}"

                LineText: str = f"{SlotPrefix} **{Combatant.Name}**{EntityTag}{HiddenBadge} — {VitalsText}{ConditionBadge}{NoteBadge}"

            else:
                HiddenVitals: str = "END ?/? | Armor ?" if IsTraveller else "?/? HP | AC ?"
                LineText          = f"`{Pointer}[??]` ❓ **Hidden Combatant** — {HiddenVitals}"

            CombatantLines.append(LineText)

        FieldHeading: str = "Combat Roster" if IsPopcorn else "Turn Order"
        FooterHint  : str = f"Use {EffectivePrefix}init pass <Target> or the dropdown below to pass the turn." if IsPopcorn else f"Use {EffectivePrefix}init next or the controls below to advance turns."
        EncounterEmbed.add_field(name = FieldHeading, value = "\n".join(CombatantLines)[:1020], inline = False)
        EncounterEmbed.set_footer(text = FooterHint)
        return EncounterEmbed
