import re                                       as RegularExpressions
import typing                                   as Typing
import uuid                                     as UUIDLibrary
import pydantic                                 as Pydantic
import Runtime.Services.CharacterStateService   as CharacterState
import Runtime.Services.MGT2EStateService       as MGT2EState
import Runtime.Services.EncounterManagerService as EncounterManager

USER_MENTION_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"^<@!?(\d+)>$")

class ResolvedTarget(Pydantic.BaseModel):
    model_config = Pydantic.ConfigDict(arbitrary_types_allowed = True)

    RawToken           : str
    DisplayName        : str
    Combatant          : Typing.Optional[EncounterManager.CombatantEntry] = None
    CharacterRecord    : Typing.Optional[dict[str, Typing.Any]]           = None
    MentionedUserID    : Typing.Optional[str]                             = None
    ControllerDiscordID: Typing.Optional[str]                             = None
    IsSynthetic        : bool                                             = False
    SystemMismatch     : bool                                             = False
    ErrorMessage       : Typing.Optional[str]                             = None

class TargetResolverService:
    def __init__(self, CharacterStateInstance: Typing.Optional[CharacterState.CharacterStateService] = None, MGT2EStateInstance: Typing.Optional[MGT2EState.MGT2EStateService] = None, ActiveSystemByContext: Typing.Optional[dict[str, str]] = None) -> None:
        self.CharacterState       : CharacterState.CharacterStateService = CharacterStateInstance if (CharacterStateInstance is not None) else CharacterState.CharacterStateService()
        self.MGT2EState           : MGT2EState.MGT2EStateService         = MGT2EStateInstance if (MGT2EStateInstance is not None) else MGT2EState.MGT2EStateService()
        self.ActiveSystemByContext: dict[str, str]                       = ActiveSystemByContext if (ActiveSystemByContext is not None) else self.CharacterState.ActiveSystemByContext

    def ExtractMentionedUserID(self, RawToken: str) -> Typing.Optional[str]:
        MatchObject: Typing.Any = USER_MENTION_PATTERN.match(RawToken.strip())
        if (MatchObject is not None):
            return MatchObject.group(1)

        return None

    async def ValidateSystemGuard(self, DiscordUserID: int | str, ChannelID: int | str, ExpectedSystem: str) -> tuple[bool, Typing.Optional[dict[str, Typing.Any]], Typing.Optional[str]]:
        ContextKey  : str                  = f"{DiscordUserID}:{ChannelID}"
        ActiveSystem: Typing.Optional[str] = self.ActiveSystemByContext.get(ContextKey) or self.ActiveSystemByContext.get(str(DiscordUserID))

        if (ExpectedSystem == "MGT2E"):
            if (ActiveSystem == "DND5E"):
                DNDRecord  : Typing.Optional[dict[str, Typing.Any]] = await self.CharacterState.ResolveActiveCharacter(DiscordUserID, ChannelID)
                ActiveTitle: str                                    = str(DNDRecord.get("Name", "Dungeons & Dragons Character")) if (DNDRecord is not None) else "Dungeons & Dragons Character"
                return (False, None, f"You currently have a Dungeons & Dragons entity (`{ActiveTitle}`) active. Switch to a Mongoose Traveller entity first with `.char select <Name>`.")

            MGT2ERecord: Typing.Optional[dict[str, Typing.Any]] = await self.MGT2EState.ResolveActiveCharacter(DiscordUserID, ChannelID)
            if (MGT2ERecord is None):
                DNDCheck: Typing.Optional[dict[str, Typing.Any]] = await self.CharacterState.ResolveActiveCharacter(DiscordUserID, ChannelID)
                if (DNDCheck is not None):
                    return (False, None, f"This Mongoose Traveller action cannot use your Dungeons & Dragons character (`{DNDCheck.get("Name", "Hero")}`). Select or import a Mongoose Traveller character with `.char select <Name>`.")

                return (False, None, "You do not have an active Mongoose Traveller character selected. Select one with `.char select <Name>`.")

            return (True, MGT2ERecord, None)

        if (ActiveSystem == "MGT2E"):
            MGT2ERecord = await self.MGT2EState.ResolveActiveCharacter(DiscordUserID, ChannelID)
            ActiveTitle = str(MGT2ERecord.get("Name", "Mongoose Traveller Character")) if (MGT2ERecord is not None) else "Mongoose Traveller Character"
            return (False, None, f"You currently have a Mongoose Traveller entity (`{ActiveTitle}`) active. Switch to a Dungeons & Dragons entity first with `!char select <Name>`.")

        DNDRecord = await self.CharacterState.ResolveActiveCharacter(DiscordUserID, ChannelID)
        if (DNDRecord is None):
            MGT2ECheck: Typing.Optional[dict[str, Typing.Any]] = await self.MGT2EState.ResolveActiveCharacter(DiscordUserID, ChannelID)
            if (MGT2ECheck is not None):
                return (False, None, f"This Dungeons & Dragons action cannot use your Mongoose Traveller character (`{MGT2ECheck.get("Name", "Traveller")}`). Select a Dungeons & Dragons character with `!char select <Name>`.")

            return (False, None, "You do not have an active Dungeons & Dragons character selected. Select one with `!char select <Name>`.")

        return (True, DNDRecord, None)

    def BuildSyntheticCombatantFromRecord(self, CharacterRecord: dict[str, Typing.Any], GameSystem: str, ControllerDiscordID: Typing.Optional[str] = None) -> EncounterManager.CombatantEntry:
        DetailData   : dict[str, Typing.Any] = CharacterRecord.get("DetailData", {})
        CharacterID  : str                   = str(CharacterRecord.get("ID", str(UUIDLibrary.uuid4())))
        CharacterName: str                   = str(CharacterRecord.get("Name", "Target"))
        EntityType   : str                   = str(CharacterRecord.get("EntityType", "Character"))

        if (GameSystem == "MGT2E"):
            Characteristics   : dict[str, int]                         = dict(DetailData.get("Characteristics", {}))
            MaxCharacteristics: dict[str, int]                         = dict(DetailData.get("MaxCharacteristics", Characteristics))
            ENDScore          : int                                    = int(Characteristics.get("Endurance", 7))
            MaxENDScore       : int                                    = int(MaxCharacteristics.get("Endurance", ENDScore))
            ArmorData         : Typing.Any                             = DetailData.get("Armor", {})
            ArmorProtection   : int                                    = int(ArmorData.get("Protection", 0)) if isinstance(ArmorData, dict) else int(ArmorData or 0)
            VehicleStats      : Typing.Optional[dict[str, Typing.Any]] = None
            if (EntityType == "Vehicle"):
                CurrentHull : int = int(DetailData.get("HullPoints", 20))
                MaximumHull : int = int(DetailData.get("MaxHullPoints", CurrentHull))
                ENDScore          = CurrentHull
                MaxENDScore       = MaximumHull
                VehicleStats      = dict(DetailData)

            return EncounterManager.CombatantEntry(ID = CharacterID, Name = CharacterName, Initiative = 0, CurrentHitPoints = ENDScore, MaxHitPoints = MaxENDScore, ArmorClass = 8, ArmorProtection = ArmorProtection, EntityType = EntityType, ParentCharacterID = CharacterRecord.get("ParentCharacterID"), IsMonster = (EntityType == "Other"), ControllerDiscordID = ControllerDiscordID, CharacterID = CharacterID, Characteristics = Characteristics, MaxCharacteristics = MaxCharacteristics, VehicleStats = VehicleStats)

        HitPointsData    : dict[str, Typing.Any]                  = DetailData.get("HitPoints", {})
        CurrentHP        : int                                    = int(HitPointsData.get("CurrentHitPoints", DetailData.get("HullPoints", 10)))
        MaxHP            : int                                    = int(HitPointsData.get("MaxHitPoints", DetailData.get("MaxHullPoints", CurrentHP)))
        TempHP           : int                                    = int(HitPointsData.get("TemporaryHitPoints", 0))
        ArmorClassValue  : int                                    = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", DetailData.get("ArmorClass", 10)) if isinstance(DetailData.get("ArmorClass"), dict) else DetailData.get("ArmorClass", 10))
        PassivePerception: int                                    = int(DetailData.get("PassivePerception", 10))
        InitBonus        : int                                    = int(DetailData.get("InitiativeBonus", 0))
        VehicleStatsDND  : Typing.Optional[dict[str, Typing.Any]] = dict(DetailData) if (EntityType == "Vehicle") else None

        return EncounterManager.CombatantEntry(ID = CharacterID, Name = CharacterName, Initiative = 0, CurrentHitPoints = CurrentHP, MaxHitPoints = MaxHP, TemporaryHitPoints = TempHP, ArmorClass = ArmorClassValue, EntityType = EntityType, ParentCharacterID = CharacterRecord.get("ParentCharacterID"), IsMonster = (EntityType == "Other"), ControllerDiscordID = ControllerDiscordID, CharacterID = CharacterID, PassivePerception = PassivePerception, InitiativeBonus = InitBonus, VehicleStats = VehicleStatsDND)

    async def ResolveSingleTarget(self, TargetToken: str, GameSystem: str, ChannelID: int | str, Encounter: Typing.Optional[EncounterManager.CombatEncounter] = None) -> Typing.Optional[ResolvedTarget]:
        CleanToken     : str                  = TargetToken.strip()
        MentionedUserID: Typing.Optional[str] = self.ExtractMentionedUserID(CleanToken)

        if (MentionedUserID is not None):
            StateService: Typing.Any = self.MGT2EState if (GameSystem == "MGT2E") else self.CharacterState
            IsAllowed, ActiveRecord, ErrorMsg = await self.ValidateSystemGuard(MentionedUserID, ChannelID, GameSystem)

            if (Encounter is not None):
                ControlledList  : list[EncounterManager.CombatantEntry]            = Encounter.FindCombatantsByController(MentionedUserID)
                MatchedCombatant: Typing.Optional[EncounterManager.CombatantEntry] = None
                if ControlledList:
                    if (ActiveRecord is not None):
                        ActiveID: str = str(ActiveRecord.get("ID", ""))
                        for Candidate in ControlledList:
                            if (Candidate.CharacterID == ActiveID) or (Candidate.ID == ActiveID):
                                MatchedCombatant = Candidate
                                break

                    if (MatchedCombatant is None):
                        MatchedCombatant = ControlledList[0]

                    return ResolvedTarget(RawToken = CleanToken, DisplayName = MatchedCombatant.Name, Combatant = MatchedCombatant, CharacterRecord = ActiveRecord, MentionedUserID = MentionedUserID, ControllerDiscordID = MentionedUserID, IsSynthetic = False, SystemMismatch = (not IsAllowed), ErrorMessage = ErrorMsg)

                if (ActiveRecord is not None):
                    ByName: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(str(ActiveRecord.get("Name", "")))
                    if (ByName is not None):
                        return ResolvedTarget(RawToken = CleanToken, DisplayName = ByName.Name, Combatant = ByName, CharacterRecord = ActiveRecord, MentionedUserID = MentionedUserID, ControllerDiscordID = ByName.ControllerDiscordID or MentionedUserID, IsSynthetic = False)

            if (not IsAllowed) or (ActiveRecord is None):
                return ResolvedTarget(RawToken = CleanToken, DisplayName = f"User {MentionedUserID}", MentionedUserID = MentionedUserID, ControllerDiscordID = MentionedUserID, IsSynthetic = True, SystemMismatch = True, ErrorMessage = ErrorMsg)

            SyntheticCombatant: EncounterManager.CombatantEntry = self.BuildSyntheticCombatantFromRecord(ActiveRecord, GameSystem = GameSystem, ControllerDiscordID = MentionedUserID)
            return ResolvedTarget(RawToken = CleanToken, DisplayName = str(ActiveRecord.get("Name", "Target")), Combatant = SyntheticCombatant, CharacterRecord = ActiveRecord, MentionedUserID = MentionedUserID, ControllerDiscordID = MentionedUserID, IsSynthetic = True)

        if (Encounter is not None):
            FoundCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(CleanToken)
            if (FoundCombatant is not None):
                LinkedRecord: Typing.Optional[dict[str, Typing.Any]] = None
                if (FoundCombatant.CharacterID is not None):
                    StateService = self.MGT2EState if (GameSystem == "MGT2E") else self.CharacterState
                    LinkedRecord = await StateService.ResolveEntityByID(FoundCombatant.CharacterID, FoundCombatant.ControllerDiscordID)

                return ResolvedTarget(RawToken = CleanToken, DisplayName = FoundCombatant.Name, Combatant = FoundCombatant, CharacterRecord = LinkedRecord, ControllerDiscordID = FoundCombatant.ControllerDiscordID, IsSynthetic = False)

        return None

    async def ResolveTargets(self, TargetTokens: list[str], GameSystem: str, ChannelID: int | str, Encounter: Typing.Optional[EncounterManager.CombatEncounter] = None) -> list[ResolvedTarget]:
        ResolvedList: list[ResolvedTarget] = []
        for Token in TargetTokens:
            if not Token.strip():
                continue

            Result: Typing.Any = await self.ResolveSingleTarget(Token, GameSystem = GameSystem, ChannelID = ChannelID, Encounter = Encounter)
            if (Result is not None):
                ResolvedList.append(Result)

        return ResolvedList
