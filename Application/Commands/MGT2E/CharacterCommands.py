import typing                             as Typing
import discord                            as Discord
import discord.ext.commands               as Commands
import Configuration.Config               as Config
import Services.DebugService              as Debug
import Services.MGT2EStateService         as MGT2EState
import Decorators.AuthorizationDecorators as AuthorizationDecorators

COLOR_MGT2E_EMBED: int = 0x005E5E
COLOR_ERROR_EMBED: int = 0xA60000

class MGT2ECharacterCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[MGT2EState.MGT2EStateService] = None) -> None:
        self.BotInstance : Commands.Bot                 = BotInstance
        self.StateService: MGT2EState.MGT2EStateService = StateService if (StateService is not None) else MGT2EState.MGT2EStateService()

    async def ExecuteListCharacters(self, Context: Commands.Context) -> None:
        MatchedList    : list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        MGT2ECharacters: list[dict[str, Typing.Any]] = [C for C in MatchedList if (C.get("GameSystem") == "MGT2E")]

        if not MGT2ECharacters:
            NoCharactersEmbed: Discord.Embed = Discord.Embed(title = "No Mongoose Traveller Characters", description = "No Mongoose Traveller characters linked to your Discord account on MIS Platform.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharactersEmbed)
            return

        ListEmbed: Discord.Embed = Discord.Embed(title = f"Mongoose Traveller Characters ({len(MGT2ECharacters)})", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E}character <Name>` to switch your active character.", color = COLOR_MGT2E_EMBED)

        for CharacterRecord in MGT2ECharacters:
            SummaryData: dict = CharacterRecord.get("SummaryData", {})
            CharacterName   : str  = str(CharacterRecord.get("Name", "Unnamed"))
            CharacterID     : str  = str(CharacterRecord.get("ID", "Unknown"))
            Career     : str  = str(SummaryData.get("Career", "Citizen"))
            Terms      : int  = int(SummaryData.get("Terms", 1))
            Age        : int  = int(SummaryData.get("Age", 22))
            Homeworld  : str  = str(SummaryData.get("Homeworld", "Core"))
            ListEmbed.add_field(name = CharacterName, value = f"**Career:** {Career} (Terms: {Terms}, Age: {Age})\n**Homeworld:** {Homeworld}\n`ID: {CharacterID}`", inline = False)

        ListEmbed.set_footer(text = "MIS-Bot • Mongoose Traveller Subsystem")
        await Context.send(embed = ListEmbed)

    async def ExecuteSelectCharacter(self, Context: Commands.Context, TargetQuery: str) -> None:
        MatchedList    : list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        MGT2ECharacters: list[dict[str, Typing.Any]] = [C for C in MatchedList if (C.get("GameSystem") == "MGT2E")]

        QueryLower    : str                                  = TargetQuery.strip().lower()
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
        ContextKey: str = self.StateService.BuildContextKey(Context.author.id, Context.channel.id)
        if ContextKey in self.StateService.ActiveCharacterMap:
            del self.StateService.ActiveCharacterMap[ContextKey]

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
            ImportResult: dict[str, Typing.Any] = await self.StateService.PlatformClient.ImportCharacter(ImportURL = CleanedURL, DiscordID = str(Context.author.id))
            CharacterID : str                   = str(ImportResult.get("ID", ""))
            CharacterName: str                  = str(ImportResult.get("Name", "Imported Character"))
            SummaryData : dict                  = ImportResult.get("SummaryData", {})
            CareerText  : str                   = str(SummaryData.get("Career", "Traveller"))

            self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, CharacterID)
            self.StateService.CharacterCache[CharacterID] = ImportResult

            SuccessEmbed: Discord.Embed = Discord.Embed(title = f"Mongoose Traveller Character Imported: {CharacterName}", description = f"Imported from `{CleanedURL}`\nSet as active Mongoose Traveller character in this channel.", color = COLOR_MGT2E_EMBED)
            SuccessEmbed.add_field(name = "Career", value = CareerText, inline = True)
            SuccessEmbed.add_field(name = "Character ID", value = f"`{CharacterID}`", inline = False)
            SuccessEmbed.set_footer(text = "MIS-Bot • Mongoose Traveller Subsystem")
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
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active Mongoose Traveller character selected.\n\nSelect one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E}character select <Name>`.", color = COLOR_ERROR_EMBED)
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

        CharacterName     : str  = str(ActiveRecord.get("Name", "Traveller"))
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        InventoryList: list = DetailData.get("Inventory", [])
        Credits      : int  = int(DetailData.get("Currency", {}).get("Credits", 0))

        InventoryEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}'s Inventory", description = f"**Current Wealth:** Cr {Credits:,}", color = COLOR_MGT2E_EMBED)
        ItemsText: str          = "\n".join(f"• {Item}" for Item in InventoryList) if (bool(InventoryList)) else "No items in inventory."
        InventoryEmbed.add_field(name = f"Possessions ({len(InventoryList)})", value = ItemsText[:1020], inline = False)
        InventoryEmbed.set_footer(text = "MIS-Bot • Mongoose Traveller Inventory")
        await Context.send(embed = InventoryEmbed)

    @Commands.command(name = "credits")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CreditsCommand(self, Context: Commands.Context, DeltaText: str) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Mongoose Traveller character selected.")
            return

        DetailData  : dict = ActiveRecord.get("DetailData", {})
        CurrencyDictionary: dict = DetailData.setdefault("Currency", {})
        CurrentCr   : int  = int(CurrencyDictionary.get("Credits", 0))

        CleanDelta: str = DeltaText.strip()
        try:
            if CleanDelta.startswith("+"):
                NewCr = CurrentCr + int(CleanDelta[1:])

            elif CleanDelta.startswith("-"):
                NewCr = max(0, CurrentCr - int(CleanDelta[1:]))

            else:
                NewCr = max(0, int(CleanDelta))

            CurrencyDictionary["Credits"] = NewCr
            await Context.send(f"**{ActiveRecord.get("Name")}** Credits: Cr {CurrentCr:,} ➔ **Cr {NewCr:,}**")

        except ValueError:
            await Context.send(f"Invalid credits amount. Example: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E}credits +500` or `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E}credits -120`")

async def setup(BotInstance: Commands.Bot) -> None:
    StateServiceInstance: Typing.Optional[MGT2EState.MGT2EStateService] = getattr(BotInstance, "MGT2EStateService", None)
    await BotInstance.add_cog(MGT2ECharacterCommands(BotInstance, StateService = StateServiceInstance))
