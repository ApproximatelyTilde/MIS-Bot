import re                                                as RegularExpressions
import typing                                            as Typing
import uuid                                              as UUIDLibrary
import discord                                           as Discord
import discord.ext.commands                              as Commands
import Runtime.Services.DebugService                     as Debug
import Runtime.Services.MGT2EStateService                as MGT2EState
import Runtime.Services.EncounterManagerService          as EncounterManager
import Runtime.Services.Draconic.API.ArgumentParser      as ArgumentParser
import Runtime.Application.Components.InitiativeControls as InitiativeControls
import Runtime.Decorators.AuthorizationDecorators        as AuthorizationDecorators

COLOR_MGT2E_EMBED   : int                        = 0x005E5E
COLOR_ERROR_EMBED   : int                        = 0xA60000
USER_MENTION_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"^<@!?(\d+)>$")

class MGT2ECharacterCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[MGT2EState.MGT2EStateService] = None, EncounterManager: Typing.Optional[EncounterManager.EncounterManagerService] = None) -> None:
        self.BotInstance     : Commands.Bot                                  = BotInstance
        self.StateService    : MGT2EState.MGT2EStateService                  = StateService if (StateService is not None) else (getattr(BotInstance, "MGT2EStateService", None) or MGT2EState.MGT2EStateService())
        self.EncounterManager: EncounterManager.EncounterManagerService = EncounterManager if (EncounterManager is not None) else (getattr(BotInstance, "EncounterManager", None) or EncounterManager.EncounterManagerService(PlatformClientInstance = self.StateService.PlatformClient))

    async def ExecuteListCharacters(self, Context: Commands.Context) -> None:
        MatchedList    : list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        MGT2ECharacters: list[dict[str, Typing.Any]] = [C for C in MatchedList if (C.get("GameSystem") == "MGT2E") and (str(C.get("EntityType", "Character")) == "Character")]

        if not MGT2ECharacters:
            NoCharactersEmbed: Discord.Embed = Discord.Embed(title = "No Mongoose Traveller Characters", description = f"No Mongoose Traveller characters linked to your Discord account on zibell Platform.\n\nUse `{Context.prefix}comp list` for companions/vehicles.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharactersEmbed)
            return

        ListEmbed: Discord.Embed = Discord.Embed(title = f"Mongoose Traveller Characters ({len(MGT2ECharacters)})", description = f"Use `{Context.prefix}character <Name>` to switch your active character.", color = COLOR_MGT2E_EMBED)

        for CharacterRecord in MGT2ECharacters:
            SummaryData  : dict = CharacterRecord.get("SummaryData", {})
            CharacterName: str  = str(CharacterRecord.get("Name", "Unnamed"))
            CharacterID  : str  = str(CharacterRecord.get("ID", "Unknown"))
            EntityType   : str  = str(CharacterRecord.get("EntityType", "Character"))
            TypeTag      : str  = f" [{EntityType}]" if (EntityType != "Character") else ""
            Career       : str  = str(SummaryData.get("Career", "Citizen"))
            Terms        : int  = int(SummaryData.get("Terms", 1))
            Age          : int  = int(SummaryData.get("Age", 22))
            Homeworld    : str  = str(SummaryData.get("Homeworld", "Core"))
            ListEmbed.add_field(name = f"{CharacterName}{TypeTag}", value = f"**Career:** {Career} (Terms: {Terms}, Age: {Age})\n**Homeworld:** {Homeworld}\n`ID: {CharacterID}`", inline = False)

        ListEmbed.set_footer(text = "Tally │ Mongoose Traveller Subsystem")
        await Context.send(embed = ListEmbed)

    async def ExecuteSelectCharacter(self, Context: Commands.Context, TargetQuery: str) -> None:
        MatchedList    : list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        MGT2ECharacters: list[dict[str, Typing.Any]] = [C for C in MatchedList if (C.get("GameSystem") == "MGT2E")]

        QueryLower    : str                                    = TargetQuery.strip().lower()
        SelectedRecord: Typing.Optional[dict[str, Typing.Any]] = None

        for Candidate in MGT2ECharacters:
            CandidateID  : str = str(Candidate.get("ID", "")).lower()
            CandidateName: str = str(Candidate.get("Name", "")).lower()
            if (CandidateID == QueryLower) or (CandidateName == QueryLower):
                SelectedRecord = Candidate
                break

        if (SelectedRecord is None):
            for Candidate in MGT2ECharacters:
                CandidateName = str(Candidate.get("Name", "")).lower()
                if QueryLower in CandidateName:
                    SelectedRecord = Candidate
                    break

        if (SelectedRecord is None):
            await Context.send(f"Could not find Mongoose Traveller character matching `{TargetQuery}`.")
            return

        CharacterID  : str = str(SelectedRecord.get("ID"))
        CharacterName: str = str(SelectedRecord.get("Name"))
        self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, CharacterID)
        self.StateService.CharacterCache[CharacterID] = SelectedRecord

        ConfirmEmbed: Discord.Embed = Discord.Embed(title = "Active Character Changed", description = f"Active Mongoose Traveller character set to **{CharacterName}**.", color = COLOR_MGT2E_EMBED)
        await Context.send(embed = ConfirmEmbed)

    async def ExecuteRemoveCharacter(self, Context: Commands.Context) -> None:
        self.StateService.ClearActiveCharacter(Context.author.id, Context.channel.id)

        UnsetEmbed: Discord.Embed = Discord.Embed(title = "Active Character Removed", description = "Active Mongoose Traveller character selection cleared for this channel.", color = COLOR_MGT2E_EMBED)
        await Context.send(embed = UnsetEmbed)

    @Commands.group(name = "character", aliases = ["char"], invoke_without_command = True)
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CharacterGroup(self, Context: Commands.Context, *, TargetArgument: Typing.Optional[str] = None) -> None:
        if (TargetArgument is None):
            ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
            if (ActiveRecord is not None):
                SheetEmbed: Discord.Embed = self.StateService.FormatSheetEmbed(ActiveRecord)
                await Context.send(embed = SheetEmbed)
                return

            await self.ExecuteListCharacters(Context)
            return

        CleanedArgument: str       = TargetArgument.strip()
        TokensList     : list[str] = CleanedArgument.split()
        FirstKeyword   : str       = TokensList[0].lower()

        if (FirstKeyword == "list"):
            await self.ExecuteListCharacters(Context)
            return

        elif FirstKeyword in ("select", "switch", "set"):
            RemainingQuery: str = CleanedArgument[len(FirstKeyword):].strip()
            await self.ExecuteSelectCharacter(Context, TargetQuery = RemainingQuery)
            return

        elif FirstKeyword in ("delete", "remove", "unset"):
            await self.ExecuteRemoveCharacter(Context)
            return

        await self.ExecuteSelectCharacter(Context, TargetQuery = CleanedArgument)

    @CharacterGroup.command(name = "list")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def ListCharacters(self, Context: Commands.Context) -> None:
        await self.ExecuteListCharacters(Context)

    @CharacterGroup.command(name = "select", aliases = ["switch", "set"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def SelectCharacter(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        await self.ExecuteSelectCharacter(Context, TargetQuery = TargetQuery)

    @CharacterGroup.command(name = "delete", aliases = ["remove", "unset"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def RemoveCharacter(self, Context: Commands.Context) -> None:
        await self.ExecuteRemoveCharacter(Context)

    @Commands.command(name = "import")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def ImportCommand(self, Context: Commands.Context, SheetURL: str) -> None:
        CleanedURL: str = SheetURL.strip()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Mongoose Traveller Character Import Initiated: URL=\"{CleanedURL}\", DiscordID={Context.author.id}")

        try:
            ImportResult : dict[str, Typing.Any] = await self.StateService.PlatformClient.ImportCharacter(ImportURL = CleanedURL, DiscordID = str(Context.author.id))
            CharacterID  : str                   = str(ImportResult.get("ID", ""))
            CharacterName: str                   = str(ImportResult.get("Name", "Imported Character"))
            SummaryData  : dict                  = ImportResult.get("SummaryData", {})
            CareerText   : str                   = str(SummaryData.get("Career", "Traveller"))

            self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, CharacterID)
            self.StateService.CharacterCache[CharacterID] = ImportResult

            SuccessEmbed: Discord.Embed = Discord.Embed(title = f"Mongoose Traveller Character Imported: {CharacterName}", description = f"Imported from `{CleanedURL}`\nSet as active Mongoose Traveller character in this channel.", color = COLOR_MGT2E_EMBED)
            SuccessEmbed.add_field(name = "Career", value = CareerText, inline = True)
            SuccessEmbed.add_field(name = "Character ID", value = f"`{CharacterID}`", inline = False)
            SuccessEmbed.set_footer(text = "Tally │ Mongoose Traveller Subsystem")
            await Context.send(embed = SuccessEmbed)

        except Exception as ImportError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Mongoose Traveller Character Import Failed: {str(ImportError)}")
            ErrorEmbed: Discord.Embed = Discord.Embed(title = "Character Import Failed", description = f"Could not import Mongoose Traveller character from `{CleanedURL}`.\n\n**Error:** {str(ImportError)}", color = COLOR_ERROR_EMBED)
            await Context.send(embed = ErrorEmbed)

    @Commands.command(name = "sheet")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def SheetCommand(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active Mongoose Traveller character selected.\n\nSelect one with `{Context.prefix}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        SheetEmbed: Discord.Embed = self.StateService.FormatSheetEmbed(ActiveRecord)
        await Context.send(embed = SheetEmbed)

    @Commands.command(name = "inv", aliases = ["inventory"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def InventoryCommand(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Mongoose Traveller character selected.")
            return

        CharacterName: str  = str(ActiveRecord.get("Name", "Traveller"))
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        InventoryList: list = DetailData.get("Inventory", [])
        Credits      : int  = int(DetailData.get("Currency", {}).get("Credits", 0))

        InventoryEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}'s Inventory", description = f"**Current Wealth:** Cr {Credits:,}", color = COLOR_MGT2E_EMBED)
        ItemsText     : str           = "\n".join(f"• {Item}" for Item in InventoryList) if (bool(InventoryList)) else "No items in inventory."
        InventoryEmbed.add_field(name = f"Possessions ({len(InventoryList)})", value = ItemsText[:1020], inline = False)
        InventoryEmbed.set_footer(text = "Tally │ Mongoose Traveller Inventory")
        await Context.send(embed = InventoryEmbed)

    @Commands.command(name = "credits")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CreditsCommand(self, Context: Commands.Context, DeltaText: str) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Mongoose Traveller character selected.")
            return

        DetailData        : dict = ActiveRecord.get("DetailData", {})
        CurrencyDictionary: dict = DetailData.setdefault("Currency", {})
        CurrentCr         : int  = int(CurrencyDictionary.get("Credits", 0))

        CleanDelta: str = DeltaText.strip()
        try:
            if CleanDelta.startswith("+"):
                NewCredits: Typing.Any = CurrentCr + int(CleanDelta[1:])

            elif CleanDelta.startswith("-"):
                NewCredits = max(0, CurrentCr - int(CleanDelta[1:]))

            else:
                NewCredits = max(0, int(CleanDelta))

            CurrencyDictionary["Credits"] = NewCredits
            await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
            await Context.send(f"**{ActiveRecord.get("Name")}** Credits: Cr {CurrentCr:,} ➔ **Cr {NewCredits:,}**")

        except ValueError:
            await Context.send(f"Invalid credits amount. Example: `{Context.prefix}credits +500` or `{Context.prefix}credits -120`")

    @Commands.group(name = "companion", aliases = ["comp", "vehicle", "ship"], invoke_without_command = True)
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CompanionGroup(self, Context: Commands.Context) -> None:
        await self.ListCompanions(Context)

    @CompanionGroup.command(name = "list", aliases = ["ls"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def ListCompanions(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        LinkedList  : list[dict[str, Typing.Any]]            = []
        if (ActiveRecord is not None):
            ActiveID: str = str(ActiveRecord.get("ID", ""))
            if ActiveID:
                try:
                    LinkedList = await self.StateService.PlatformClient.FetchCharacterCompanions(ActiveID)

                except Exception as FetchError:
                    Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"FetchCharacterCompanions Error: {str(FetchError)}")

        OwnedList: list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        SeenIDs  : set[str]                    = {str(C.get("ID", "")) for C in LinkedList}
        Combined : list[dict[str, Typing.Any]] = list(LinkedList)
        for Rec in OwnedList:
            RecordSystem: str = str(Rec.get("GameSystem", ""))
            RecordType  : str = str(Rec.get("EntityType", "Character"))
            RecordID    : str = str(Rec.get("ID", ""))
            if (RecordSystem == "MGT2E") and (RecordType in ("Companion", "Vehicle")) and (RecordID not in SeenIDs):
                Combined.append(Rec)
                SeenIDs.add(RecordID)

        if not Combined:
            await Context.send("No companions, drones, or vehicles found linked to your character or account on the Platform.")
            return

        ListEmbed: Discord.Embed = Discord.Embed(title = "Mongoose Traveller Companions & Vehicles", description = f"Use `{Context.prefix}comp select <Name>` or `{Context.prefix}comp join <Name>`.", color = COLOR_MGT2E_EMBED)
        for Entry in Combined[:20]:
            EntryName : str  = str(Entry.get("Name", "Entity"))
            EntryType : str  = str(Entry.get("EntityType", "Companion"))
            EntryID   : str  = str(Entry.get("ID", ""))
            DetailData: dict = Entry.get("DetailData", {})
            if (EntryType == "Vehicle"):
                CurrentHull: int        = int(DetailData.get("HullPoints", 20))
                MaximumHull: int        = int(DetailData.get("MaxHullPoints", CurrentHull))
                ArmorValue : Typing.Any = DetailData.get("Armor", 0)
                DetailText : str        = f"Hull: {CurrentHull}/{MaximumHull} | Armor: {ArmorValue}"

            else:
                Chars         : dict = DetailData.get("Characteristics", {})
                EnduranceValue: int  = int(Chars.get("Endurance", 7))
                DetailText           = f"END: {EnduranceValue}"

            ListEmbed.add_field(name = f"{EntryName} [{EntryType}]", value = f"{DetailText}\n`ID: {EntryID}`", inline = False)

        await Context.send(embed = ListEmbed)

    @CompanionGroup.command(name = "select", aliases = ["switch"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def SelectCompanion(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        Matched: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, TargetQuery)
        if (Matched is None):
            await Context.send(f"Could not find companion or vehicle matching `{TargetQuery}`.")
            return

        EntityID  : str = str(Matched.get("ID", ""))
        EntityName: str = str(Matched.get("Name", TargetQuery))
        EntityType: str = str(Matched.get("EntityType", "Companion"))
        self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, EntityID)
        self.StateService.CharacterCache[EntityID] = Matched
        await Context.send(embed = Discord.Embed(title = f"Active {EntityType} Selected", description = f"Active Mongoose Traveller entity in this channel set to **{EntityName}** ({EntityType}).", color = COLOR_MGT2E_EMBED))

    @CompanionGroup.command(name = "sheet", aliases = ["view"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CompanionSheet(self, Context: Commands.Context, *, TargetQuery: str = "") -> None:
        if TargetQuery.strip():
            Record: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, TargetQuery)

        else:
            Record = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)

        if (Record is None):
            await Context.send("No companion or vehicle found matching that query.")
            return

        await Context.send(embed = self.StateService.FormatSheetEmbed(Record))

    @CompanionGroup.command(name = "join")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CompanionJoinCombat(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat active. Start one with `{Context.prefix}init begin`.")
            return

        Matched: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, TargetQuery)
        if (Matched is None):
            await Context.send(f"Could not find companion or vehicle matching `{TargetQuery}`.")
            return

        DetailData        : dict                                   = Matched.get("DetailData", {})
        EntityID          : str                                    = str(Matched.get("ID", str(UUIDLibrary.uuid4())))
        EntityName        : str                                    = str(Matched.get("Name", TargetQuery))
        EntityType        : str                                    = str(Matched.get("EntityType", "Companion"))
        Characteristics   : dict[str, int]                         = dict(DetailData.get("Characteristics", {}))
        MaxCharacteristics: dict[str, int]                         = dict(DetailData.get("MaxCharacteristics", Characteristics))
        ArmorData         : Typing.Any                             = DetailData.get("Armor", {})
        ArmorProtection   : int                                    = int(ArmorData.get("Protection", 0)) if isinstance(ArmorData, dict) else int(ArmorData or 0)
        DEXDM             : int                                    = self.StateService.CalculateCharacteristicModifier(int(Characteristics.get("Dexterity", 7)))
        Roll              : MGT2EState.MGT2ERollOutcome            = self.StateService.EvaluateRoll(Modifier = DEXDM)
        ENDScore          : int                                    = int(Characteristics.get("Endurance", 10))
        MaxENDScore       : int                                    = int(MaxCharacteristics.get("Endurance", ENDScore))
        VehicleStats      : Typing.Optional[dict[str, Typing.Any]] = None
        if (EntityType == "Vehicle"):
            CurrentHull : int = int(DetailData.get("HullPoints", 20))
            MaximumHull : int = int(DetailData.get("MaxHullPoints", CurrentHull))
            ENDScore          = CurrentHull
            MaxENDScore       = MaximumHull
            VehicleStats      = dict(DetailData)

        NewCombatant: Typing.Any = EncounterManager.CombatantEntry(ID = EntityID, Name = EntityName, Initiative = Roll.Total, CurrentHitPoints = ENDScore, MaxHitPoints = MaxENDScore, ArmorClass = 8, ArmorProtection = ArmorProtection, EntityType = EntityType, ParentCharacterID = Matched.get("ParentCharacterID"), IsMonster = False, ControllerDiscordID = str(Context.author.id), CharacterID = EntityID, Characteristics = Characteristics, MaxCharacteristics = MaxCharacteristics, VehicleStats = VehicleStats, InitiativeBonus = DEXDM)
        Encounter.AddCombatant(NewCombatant)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context), CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(content = f"**{EntityName}** ({EntityType}) joined combat ({Roll.Total})!", embed = StatusEmbed, view = ControlsView)

    @CompanionGroup.command(name = "link")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def LinkCompanion(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalList : list[str]                      = list(ParsedArguments.PositionalArguments)
        if not PositionalList:
            await Context.send(f"Usage: `{Context.prefix}comp link <Companion|Vehicle> [-to <ParentCharacter>]`")
            return

        ParentQuery: Typing.Optional[str] = ParsedArguments.last("to")
        if (ParentQuery is not None):
            CompanionQuery: str                                    = " ".join(PositionalList).strip()
            ParentRecord  : Typing.Optional[dict[str, Typing.Any]] = None
            FetchedList   : list[dict[str, Typing.Any]]            = await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
            ParentLow     : str                                    = ParentQuery.strip().lower()
            for Candidate in FetchedList:
                if (Candidate.get("GameSystem") == "MGT2E") and (str(Candidate.get("EntityType", "Character")) == "Character"):
                    if (ParentLow in str(Candidate.get("Name", "")).lower()) or (str(Candidate.get("ID", "")).lower() == ParentLow):
                        ParentRecord = Candidate
                        break

        else:
            CompanionQuery = " ".join(PositionalList).strip()
            ParentRecord   = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)

        if (ParentRecord is None) or (str(ParentRecord.get("EntityType", "Character")) != "Character"):
            await Context.send("You must select or specify a primary Mongoose Traveller `Character` as the link parent.")
            return

        Matched: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, CompanionQuery)
        if (Matched is None):
            await Context.send(f"Could not find companion or vehicle matching `{CompanionQuery}`.")
            return

        ParentID   : str = str(ParentRecord.get("ID", ""))
        CompanionID: str = str(Matched.get("ID", ""))
        try:
            UpdatedRecord: dict[str, Typing.Any] = await self.StateService.PlatformClient.LinkOrCreateCompanion(ParentID, CompanionID = CompanionID, EntityType = str(Matched.get("EntityType", "Companion")))
            self.StateService.CharacterCache[CompanionID] = UpdatedRecord
            await Context.send(f"Linked **{UpdatedRecord.get("Name", CompanionQuery)}** ({UpdatedRecord.get("EntityType", "Companion")}) to **{ParentRecord.get("Name", "Traveller")}**.")

        except Exception as LinkError:
            await Context.send(f"Failed to link companion: {str(LinkError)}")

    @CompanionGroup.command(name = "transfer")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def TransferCompanion(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalList : list[str]                      = list(ParsedArguments.PositionalArguments)
        ToFlag         : Typing.Optional[str]           = ParsedArguments.last("to")

        if (ToFlag is not None) and PositionalList:
            CompanionQuery : Typing.Any = " ".join(PositionalList).strip()
            DestinationText: Typing.Any = ToFlag.strip()

        elif (len(PositionalList) >= 2):
            CompanionQuery  = " ".join(PositionalList[:-1]).strip()
            DestinationText = PositionalList[-1].strip()

        else:
            await Context.send(f"Usage: `{Context.prefix}comp transfer <Companion|Vehicle> <@User|ParentCharacter|unlink>`")
            return

        Matched: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, CompanionQuery)
        if (Matched is None) and AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context):
            for EntityCategory in ("Companion", "Vehicle"):
                PoolList: list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByEntityType(EntityCategory, GameSystem = "MGT2E")
                for Item in PoolList:
                    if CompanionQuery.lower() in str(Item.get("Name", "")).lower():
                        Matched = Item
                        break

                if (Matched is not None):
                    break

        if (Matched is None):
            await Context.send(f"Could not find companion or vehicle matching `{CompanionQuery}`.")
            return

        EntityID    : str        = str(Matched.get("ID", ""))
        EntityName  : str        = str(Matched.get("Name", CompanionQuery))
        DestLower   : str        = DestinationText.lower()
        MentionMatch: Typing.Any = USER_MENTION_PATTERN.match(DestinationText)

        if (DestLower in ("unlink", "none", "clear")):
            UpdatedRecord: Typing.Any = await self.StateService.PlatformClient.TransferCharacterEntity(EntityID, {"ParentCharacterID": None})
            self.StateService.CharacterCache[EntityID] = UpdatedRecord
            await Context.send(f"Unlinked **{EntityName}** from its parent character.")
            return

        if (MentionMatch is not None):
            TargetDiscordID: str                  = MentionMatch.group(1)
            TargetOwnerID  : Typing.Optional[str] = await self.StateService.PlatformClient.ResolvePlatformUserIDByDiscordID(TargetDiscordID)
            if (TargetOwnerID is None):
                await Context.send("Target user does not have a linked account with characters on the Platform.")
                return

            TargetCharacter : Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(TargetDiscordID, Context.channel.id)
            NewParentID: Typing.Optional[str]                   = str(TargetCharacter.get("ID")) if (TargetCharacter is not None) else None
            UpdatedRecord                                       = await self.StateService.PlatformClient.TransferCharacterEntity(EntityID, {"OwnerID": TargetOwnerID, "ParentCharacterID": NewParentID})
            self.StateService.CharacterCache[EntityID]          = UpdatedRecord
            if (TargetCharacter is not None):
                await Context.send(f"Transferred **{EntityName}** to **{TargetCharacter.get("Name")}**.")

            else:
                await Context.send(f"Transferred ownership of **{EntityName}** to <@{TargetDiscordID}>.")

            return

        IsDM         : bool                                   = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        CandidatePool: list[dict[str, Typing.Any]]            = await self.StateService.PlatformClient.FetchCharactersByEntityType("Character", GameSystem = "MGT2E") if IsDM else await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        TargetParent : Typing.Optional[dict[str, Typing.Any]] = None
        for Candidate in CandidatePool:
            if (Candidate.get("GameSystem") == "MGT2E") and (str(Candidate.get("EntityType", "Character")) == "Character"):
                if (DestLower in str(Candidate.get("Name", "")).lower()) or (str(Candidate.get("ID", "")).lower() == DestLower):
                    TargetParent = Candidate
                    break

        if (TargetParent is None):
            await Context.send(f"Could not find target Mongoose Traveller Character matching `{DestinationText}`.")
            return

        TransferPayload: dict[str, Typing.Any] = {
            "ParentCharacterID": str(TargetParent.get("ID"))
        }
        if (TargetParent.get("OwnerID") is not None) and (TargetParent.get("OwnerID") != Matched.get("OwnerID")):
            TransferPayload["OwnerID"] = str(TargetParent.get("OwnerID"))

        UpdatedRecord = await self.StateService.PlatformClient.TransferCharacterEntity(EntityID, TransferPayload)
        self.StateService.CharacterCache[EntityID] = UpdatedRecord
        await Context.send(f"Transferred **{EntityName}** to **{TargetParent.get("Name", DestinationText)}**.")

    @Commands.group(name = "other", invoke_without_command = True)
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def OtherEntityGroup(self, Context: Commands.Context) -> None:
        await self.ListOtherEntities(Context)

    @OtherEntityGroup.command(name = "list", aliases = ["ls"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def ListOtherEntities(self, Context: Commands.Context, *, FilterQuery: str = "") -> None:
        if not AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context):
            await Context.send("You lack permission to view Platform Other entities. Requires Dungeon Master or Macro Master role.")
            return

        OthersList: list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByEntityType("Other", GameSystem = "MGT2E")
        if FilterQuery.strip():
            QueryLow  : str = FilterQuery.strip().lower()
            OthersList      = [O for O in OthersList if (QueryLow in str(O.get("Name", "")).lower())]

        if not OthersList:
            await Context.send("No Mongoose Traveller `Other` entities found on the Platform.")
            return

        ListEmbed: Discord.Embed = Discord.Embed(title = f"Mongoose Traveller Other Entities ({len(OthersList)})", description = f"Spawn in combat with `{Context.prefix}init addother <Name>` or select with `{Context.prefix}other select <Name>`.", color = COLOR_MGT2E_EMBED)
        for Entry in OthersList[:20]:
            ListEmbed.add_field(name = str(Entry.get("Name", "Entity")), value = f"`ID: {Entry.get("ID", "")}`", inline = True)

        await Context.send(embed = ListEmbed)

    @OtherEntityGroup.command(name = "select", aliases = ["switch"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def SelectOtherEntity(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        if not AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context):
            await Context.send("You lack permission to select Platform Other entities. Requires Dungeon Master or Macro Master role.")
            return

        OthersList: list[dict[str, Typing.Any]]            = await self.StateService.PlatformClient.FetchCharactersByEntityType("Other", GameSystem = "MGT2E")
        QueryLower: str                                    = TargetQuery.strip().lower()
        Matched   : Typing.Optional[dict[str, Typing.Any]] = None
        for Entry in OthersList:
            if (str(Entry.get("Name", "")).lower() == QueryLower) or (str(Entry.get("ID", "")).lower() == QueryLower):
                Matched = Entry
                break

        if (Matched is None):
            for Entry in OthersList:
                if QueryLower in str(Entry.get("Name", "")).lower():
                    Matched = Entry
                    break

        if (Matched is None):
            await Context.send(f"Could not find Mongoose Traveller `Other` entity matching `{TargetQuery}`.")
            return

        EntityID  : str = str(Matched.get("ID", ""))
        EntityName: str = str(Matched.get("Name", TargetQuery))
        self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, EntityID)
        self.StateService.CharacterCache[EntityID] = Matched
        await Context.send(embed = Discord.Embed(title = "Active Entity Changed", description = f"Active Mongoose Traveller entity set to **{EntityName}** (Other).", color = COLOR_MGT2E_EMBED))

async def setup(BotInstance: Commands.Bot) -> None:
    StateServiceInstance: Typing.Optional[MGT2EState.MGT2EStateService] = getattr(BotInstance, "MGT2EStateService", None)
    await BotInstance.add_cog(MGT2ECharacterCommands(BotInstance, StateService = StateServiceInstance))
