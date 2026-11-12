import datetime                as DateTime
import typing                  as Typing
import discord                 as Discord
import pydantic                as Pydantic
import Services.DebugService   as Debug
import Services.PlatformClient as PlatformClient

COLOR_ENCOUNTER_ACTIVE: int = 0x0030A6
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
    Conditions         : list[str]                              = Pydantic.Field(default_factory = list)
    IsMonster          : bool                                   = False
    ControllerDiscordID: Typing.Optional[str]                   = None
    CharacterID        : Typing.Optional[str]                   = None
    MonsterData        : Typing.Optional[dict[str, Typing.Any]] = None
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

        return ValuesDictionary

class CombatEncounter(Pydantic.BaseModel):
    model_config = Pydantic.ConfigDict(populate_by_name = True, arbitrary_types_allowed = True)

    ChannelID           : str
    GuildID             : Typing.Optional[str]                   = None
    RoundNumber         : int                                    = 1
    ActiveCombatantIndex: int                                    = 0
    Combatants          : list[CombatantEntry]                   = Pydantic.Field(default_factory = list)
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
        self.SynchronizeGroupInitiatives()
        self.Combatants.sort(key = lambda C: (C.Initiative, C.PassivePerception, C.InitiativeBonus), reverse = True)

    def GetActiveCombatant(self) -> Typing.Optional[CombatantEntry]:
        if not self.Combatants:
            return None

        SafeIndex: int = self.ActiveCombatantIndex % len(self.Combatants)
        return self.Combatants[SafeIndex]

    def AdvanceTurn(self) -> tuple[Typing.Optional[CombatantEntry], int]:
        if not self.Combatants:
            return (None, self.RoundNumber)

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
        self.SortCombatants()
        if (CurrentActive is not None):
            for Index, Candidate in enumerate(self.Combatants):
                if (Candidate.ID == CurrentActive.ID):
                    self.ActiveCombatantIndex = Index
                    break

    def RemoveCombatant(self, TargetID: str) -> Typing.Optional[CombatantEntry]:
        CleanID: str                            = TargetID.strip().lower()
        FoundIndex     : Typing.Optional[int]           = None
        FoundCombatant : Typing.Optional[CombatantEntry] = None

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

class EncounterManagerService:
    def __init__(self, PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None) -> None:
        self.EncountersByChannel: dict[str, CombatEncounter]                        = dict()
        self.PlatformClient     : Typing.Optional[PlatformClient.MISPlatformClient] = PlatformClientInstance

    def CreateEncounter(self, ChannelID: int | str, GuildID: Typing.Optional[int | str] = None) -> CombatEncounter:
        ChannelKey: str                  = str(ChannelID)
        GuildKey  : Typing.Optional[str] = str(GuildID) if (GuildID is not None) else None
        NewEncounter                     = CombatEncounter(ChannelID = ChannelKey, GuildID = GuildKey)
        self.EncountersByChannel[ChannelKey] = NewEncounter
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Combat Encounter Created: ChannelID={ChannelKey}")
        return NewEncounter

    async def CreateEncounterAsync(self, ChannelID: int | str, GuildID: Typing.Optional[int | str] = None) -> CombatEncounter:
        NewEncounter: CombatEncounter = self.CreateEncounter(ChannelID = ChannelID, GuildID = GuildID)
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
                    CombatantsData: list[dict[str, Typing.Any]] = EncounterDictionary.get("Combatants", [])
                    ParsedCombatants: list[CombatantEntry]      = []
                    for CombatantPayload in CombatantsData:
                        ParsedCombatants.append(CombatantEntry.model_validate(CombatantPayload))

                    LoadedEncounter = CombatEncounter(ChannelID = str(EncounterDictionary.get("ChannelID", ChannelKey)), GuildID = EncounterDictionary.get("GuildID"), RoundNumber = int(EncounterDictionary.get("RoundNumber", 1)), ActiveCombatantIndex = int(EncounterDictionary.get("ActiveCombatantIndex", 0)), Combatants = ParsedCombatants, ActiveEffects = EncounterDictionary.get("ActiveEffects", []), IsActive = bool(EncounterDictionary.get("IsActive", True)))
                    self.EncountersByChannel[ChannelKey] = LoadedEncounter
                    Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Loaded Combat Encounter from Platform: ChannelID={ChannelKey}")
                    return LoadedEncounter

            except Exception as LoadException:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Load Encounter from Platform: ChannelID={ChannelKey}, Error=\"{str(LoadException)}\"")

        return None

    async def SaveEncounterAsync(self, ChannelID: int | str) -> None:
        ChannelKey: str                         = str(ChannelID)
        Encounter : Typing.Optional[CombatEncounter] = self.EncountersByChannel.get(ChannelKey)
        if (Encounter is None):
            return

        if (self.PlatformClient is not None):
            try:
                PayloadDictionary: dict[str, Typing.Any] = {
                    "RoundNumber"         : Encounter.RoundNumber,
                    "ActiveCombatantIndex": Encounter.ActiveCombatantIndex,
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
            EndedEncounter          = self.EncountersByChannel.pop(ChannelKey)
            EndedEncounter.IsActive = False
            Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Combat Encounter Ended: ChannelID={ChannelKey}, TotalRounds={EndedEncounter.RoundNumber}")
            return EndedEncounter

        return None

    async def EndEncounterAsync(self, ChannelID: int | str) -> Typing.Optional[CombatEncounter]:
        ChannelKey    : str                         = str(ChannelID)
        EndedEncounter: Typing.Optional[CombatEncounter] = self.EndEncounter(ChannelKey)

        if (self.PlatformClient is not None):
            try:
                await self.PlatformClient.DeleteCombatEncounter(ChannelKey)

            except Exception as DeleteException:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Delete Encounter on Platform: ChannelID={ChannelKey}, Error=\"{str(DeleteException)}\"")

        return EndedEncounter

    def FormatEncounterEmbed(self, Encounter: CombatEncounter, ViewerDiscordID: Typing.Optional[str] = None, IsDungeonMaster: bool = False) -> Discord.Embed:
        if not Encounter.IsActive:
            EndEmbed: Discord.Embed = Discord.Embed(title = "Combat Ended", description = f"Encounter concluded after **{Encounter.RoundNumber}** rounds.", color = COLOR_ENCOUNTER_ENDED)
            return EndEmbed

        ActiveCombatant: Typing.Optional[CombatantEntry] = Encounter.GetActiveCombatant()
        ActiveName     : str                            = "None"
        if (ActiveCombatant is not None):
            if ActiveCombatant.IsHidden and (not IsDungeonMaster) and (ViewerDiscordID != ActiveCombatant.ControllerDiscordID):
                ActiveName = "Hidden Combatant"

            else:
                ActiveName = ActiveCombatant.Name

        EncounterEmbed: Discord.Embed = Discord.Embed(title = f"Initiative Tracker — Round {Encounter.RoundNumber}", description = f"Current Turn: **{ActiveName}**", color = COLOR_ENCOUNTER_ACTIVE)
        if (ActiveCombatant is not None) and (ActiveCombatant.ThumbnailURL is not None):
            EncounterEmbed.set_thumbnail(url = ActiveCombatant.ThumbnailURL)

        if not Encounter.Combatants:
            EncounterEmbed.add_field(name = "Combatants", value = "No combatants in encounter.\nUse `&init join` or `&init add <Monster>` to add participants.", inline = False)
            return EncounterEmbed

        CombatantLines: list[str] = []
        for Index, Combatant in enumerate(Encounter.Combatants):
            IsCurrentTurn : bool = (Index == Encounter.ActiveCombatantIndex)
            Pointer       : str  = "➔ " if (IsCurrentTurn) else "   "
            CanSeeDetails : bool = (not Combatant.IsHidden) or IsDungeonMaster or (ViewerDiscordID == Combatant.ControllerDiscordID)

            if CanSeeDetails:
                TempString    : str = f" (+{Combatant.TemporaryHitPoints})" if (Combatant.TemporaryHitPoints > 0) else ""
                ConditionBadge: str = f" [{", ".join(Combatant.Conditions)}]" if (bool(Combatant.Conditions)) else ""
                HiddenBadge   : str = " 👻" if (Combatant.IsHidden) else ""
                NoteBadge     : str = f" • *{Combatant.Note}*" if (Combatant.Note is not None) else ""
                LineText      : str = f"`{Pointer}[{Combatant.Initiative:>2}]` **{Combatant.Name}**{HiddenBadge} — {Combatant.CurrentHitPoints}/{Combatant.MaxHitPoints}{TempString} HP | AC {Combatant.ArmorClass}{ConditionBadge}{NoteBadge}"

            else:
                LineText: str = f"`{Pointer}[??]` ❓ **Hidden Combatant** — ?/? HP | AC ?"

            CombatantLines.append(LineText)

        EncounterEmbed.add_field(name = "Turn Order", value = "\n".join(CombatantLines)[:1020], inline = False)
        EncounterEmbed.set_footer(text = "Use &init next or the controls below to advance turns.")
        return EncounterEmbed
