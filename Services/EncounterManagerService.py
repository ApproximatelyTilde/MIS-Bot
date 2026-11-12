import datetime                           as DateTime
import typing                             as Typing
import discord                            as Discord
import pydantic                           as Pydantic
import Services.DebugService              as Debug

COLOR_ENCOUNTER_ACTIVE: int = 0x0030A6
COLOR_ENCOUNTER_ENDED : int = 0x595959

class CombatantEntry(Pydantic.BaseModel):
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

class CombatEncounter(Pydantic.BaseModel):
    ChannelID       : str
    GuildID         : Typing.Optional[str] = None
    RoundNumber     : int                  = 1
    CurrentTurnIndex: int                  = 0
    Combatants      : list[CombatantEntry] = Pydantic.Field(default_factory = list)
    IsActive        : bool                 = True
    CreatedAt       : DateTime.datetime    = Pydantic.Field(default_factory = lambda: DateTime.datetime.now(DateTime.timezone.utc))

    def SortCombatants(self) -> None:
        self.Combatants.sort(key = lambda C: C.Initiative, reverse = True)

    def GetActiveCombatant(self) -> Typing.Optional[CombatantEntry]:
        if not self.Combatants:
            return None

        SafeIndex: int = self.CurrentTurnIndex % len(self.Combatants)
        return self.Combatants[SafeIndex]

    def AdvanceTurn(self) -> tuple[Typing.Optional[CombatantEntry], int]:
        if not self.Combatants:
            return (None, self.RoundNumber)

        self.CurrentTurnIndex += 1
        if (self.CurrentTurnIndex >= len(self.Combatants)):
            self.CurrentTurnIndex = 0
            self.RoundNumber     += 1

        ActiveCombatant: CombatantEntry = self.Combatants[self.CurrentTurnIndex]
        return (ActiveCombatant, self.RoundNumber)

    def PreviousTurn(self) -> tuple[Typing.Optional[CombatantEntry], int]:
        if not self.Combatants:
            return (None, self.RoundNumber)

        self.CurrentTurnIndex -= 1
        if (self.CurrentTurnIndex < 0):
            self.CurrentTurnIndex = len(self.Combatants) - 1
            self.RoundNumber      = max(1, self.RoundNumber - 1)

        ActiveCombatant: CombatantEntry = self.Combatants[self.CurrentTurnIndex]
        return (ActiveCombatant, self.RoundNumber)

    def AddCombatant(self, Entry: CombatantEntry) -> None:
        CurrentActive: Typing.Optional[CombatantEntry] = self.GetActiveCombatant()
        self.Combatants.append(Entry)
        self.SortCombatants()
        if (CurrentActive is not None):
            for Index, Candidate in enumerate(self.Combatants):
                if (Candidate.ID == CurrentActive.ID):
                    self.CurrentTurnIndex = Index
                    break

    def RemoveCombatant(self, TargetIdentifier: str) -> Typing.Optional[CombatantEntry]:
        CleanIdentifier: str                     = TargetIdentifier.strip().lower()
        FoundIndex     : Typing.Optional[int]    = None
        FoundCombatant : Typing.Optional[CombatantEntry] = None

        if CleanIdentifier.isdigit():
            TargetIndex: int = int(CleanIdentifier) - 1
            if (0 <= TargetIndex < len(self.Combatants)):
                FoundIndex     = TargetIndex
                FoundCombatant = self.Combatants[TargetIndex]

        if (FoundCombatant is None):
            for Index, Combatant in enumerate(self.Combatants):
                if (Combatant.ID.lower() == CleanIdentifier) or (Combatant.Name.lower() == CleanIdentifier):
                    FoundIndex     = Index
                    FoundCombatant = Combatant
                    break

        if (FoundCombatant is None):
            for Index, Combatant in enumerate(self.Combatants):
                if CleanIdentifier in Combatant.Name.lower():
                    FoundIndex     = Index
                    FoundCombatant = Combatant
                    break

        if (FoundIndex is not None) and (FoundCombatant is not None):
            self.Combatants.pop(FoundIndex)
            if (self.CurrentTurnIndex >= len(self.Combatants)):
                self.CurrentTurnIndex = max(0, len(self.Combatants) - 1)

            return FoundCombatant

        return None

    def FindCombatant(self, TargetIdentifier: str) -> Typing.Optional[CombatantEntry]:
        CleanIdentifier: str = TargetIdentifier.strip().lower()
        if CleanIdentifier.isdigit():
            TargetIndex: int = int(CleanIdentifier) - 1
            if (0 <= TargetIndex < len(self.Combatants)):
                return self.Combatants[TargetIndex]

        for Combatant in self.Combatants:
            if (Combatant.ID.lower() == CleanIdentifier) or (Combatant.Name.lower() == CleanIdentifier):
                return Combatant

        for Combatant in self.Combatants:
            if CleanIdentifier in Combatant.Name.lower():
                return Combatant

        return None

class EncounterManagerService:
    def __init__(self) -> None:
        self.EncountersByChannel: dict[str, CombatEncounter] = {}

    def CreateEncounter(self, ChannelID: int | str, GuildID: Typing.Optional[int | str] = None) -> CombatEncounter:
        ChannelKey: str         = str(ChannelID)
        GuildKey  : Typing.Optional[str] = str(GuildID) if (GuildID is not None) else None
        NewEncounter            = CombatEncounter(ChannelID = ChannelKey, GuildID = GuildKey)
        self.EncountersByChannel[ChannelKey] = NewEncounter
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Combat Encounter Created: ChannelID={ChannelKey}")
        return NewEncounter

    def GetEncounter(self, ChannelID: int | str) -> Typing.Optional[CombatEncounter]:
        ChannelKey: str = str(ChannelID)
        return self.EncountersByChannel.get(ChannelKey)

    def EndEncounter(self, ChannelID: int | str) -> Typing.Optional[CombatEncounter]:
        ChannelKey: str = str(ChannelID)
        if ChannelKey in self.EncountersByChannel:
            EndedEncounter          = self.EncountersByChannel.pop(ChannelKey)
            EndedEncounter.IsActive = False
            Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Combat Encounter Ended: ChannelID={ChannelKey}, TotalRounds={EndedEncounter.RoundNumber}")
            return EndedEncounter

        return None

    def FormatEncounterEmbed(self, Encounter: CombatEncounter) -> Discord.Embed:
        if not Encounter.IsActive:
            EndEmbed: Discord.Embed = Discord.Embed(title = "Combat Ended", description = f"Encounter concluded after **{Encounter.RoundNumber}** rounds.", color = COLOR_ENCOUNTER_ENDED)
            return EndEmbed

        ActiveCombatant: Typing.Optional[CombatantEntry] = Encounter.GetActiveCombatant()
        ActiveName     : str                            = ActiveCombatant.Name if (ActiveCombatant is not None) else "None"
        EncounterEmbed : Discord.Embed                  = Discord.Embed(title = f"Initiative Tracker — Round {Encounter.RoundNumber}", description = f"Current Turn: **{ActiveName}**", color = COLOR_ENCOUNTER_ACTIVE)

        if not Encounter.Combatants:
            EncounterEmbed.add_field(name = "Combatants", value = "No combatants in encounter.\nUse `&init join` or `&init add <Monster>` to add participants.", inline = False)
            return EncounterEmbed

        CombatantLines: list[str] = []
        for Index, Combatant in enumerate(Encounter.Combatants):
            IsCurrentTurn : bool      = (Index == Encounter.CurrentTurnIndex)
            Pointer       : str       = "➔ " if IsCurrentTurn else "   "
            TempString    : str       = f" (+{Combatant.TemporaryHitPoints})" if (Combatant.TemporaryHitPoints > 0) else ""
            ConditionBadge: str       = f" [{', '.join(Combatant.Conditions)}]" if Combatant.Conditions else ""
            LineText      : str       = f"`{Pointer}[{Combatant.Initiative:>2}]` **{Combatant.Name}** — {Combatant.CurrentHitPoints}/{Combatant.MaxHitPoints}{TempString} HP | AC {Combatant.ArmorClass}{ConditionBadge}"
            CombatantLines.append(LineText)

        EncounterEmbed.add_field(name = "Turn Order", value = "\n".join(CombatantLines)[:1020], inline = False)
        EncounterEmbed.set_footer(text = "Use &init next or the controls below to advance turns.")
        return EncounterEmbed

