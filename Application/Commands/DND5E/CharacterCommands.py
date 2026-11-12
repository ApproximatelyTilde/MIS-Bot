import typing                             as Typing
import discord                            as Discord
import discord.ext.commands               as Commands
import Configuration.Config               as Config
import Services.DebugService              as Debug
import Services.PlatformClient            as PlatformClient
import Services.CharacterStateService     as CharacterStateService

COLOR_CHARACTER_EMBED: int = 0x0030A6
COLOR_ERROR_EMBED    : int = 0xA60000

def CheckDNDPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND)

class CharacterCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterStateService.CharacterStateService] = None) -> None:
        self.BotInstance     : Commands.Bot                                 = BotInstance
        self.StateService    : CharacterStateService.CharacterStateService  = StateService if (StateService is not None) else CharacterStateService.CharacterStateService()
        self.PlatformClient  : PlatformClient.MISPlatformClient             = self.StateService.PlatformClient

    @Commands.group(name = "character", aliases = ["char"], invoke_without_command = True)
    @Commands.check(CheckDNDPrefix)
    async def CharacterGroup(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is not None):
            SheetEmbed: Discord.Embed = self.StateService.FormatSheetEmbed(ActiveRecord)
            await Context.send(embed = SheetEmbed)
            return

        await self.ListCharacters(Context)

    @CharacterGroup.command(name = "list")
    @Commands.check(CheckDNDPrefix)
    async def ListCharacters(self, Context: Commands.Context) -> None:
        OwnedList: list[dict] = await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        if not OwnedList:
            NotFoundEmbed: Discord.Embed = Discord.Embed(title = "No Characters Found", description = "No D&D 5E characters linked to your Discord account were found on MIS.\n\nCreate a character on the platform desktop to begin.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NotFoundEmbed)
            return

        ActiveID    : Typing.Optional[str] = self.StateService.GetActiveCharacterID(Context.author.id, Context.channel.id)
        ListEmbed   : Discord.Embed        = Discord.Embed(title = "Your MIS Characters", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}character select <Name|ID>` to switch active characters.", color = COLOR_CHARACTER_EMBED)
        for CharItem in OwnedList:
            CharID     : str  = str(CharItem.get("ID", ""))
            CharName   : str  = str(CharItem.get("Name", "Unknown"))
            DetailData : dict = CharItem.get("DetailData", {})
            TotalLvl   : int  = int(DetailData.get("TotalLevel", 1))
            ClassesList: list = DetailData.get("Classes", [])
            ClassText  : str  = ", ".join(f"{C.get('ClassName', '')} {C.get('Level', '')}" for C in ClassesList) or "Level 1"
            IsActive   : bool = (CharID == ActiveID)
            Badge      : str  = " ⭐ *(Active)*" if IsActive else ""
            ListEmbed.add_field(name = f"{CharName}{Badge}", value = f"Level {TotalLvl} • {ClassText}\n`ID: {CharID}`", inline = False)

        ListEmbed.set_footer(text = f"MIS-Bot • Character Management")
        await Context.send(embed = ListEmbed)

    @CharacterGroup.command(name = "select")
    @Commands.check(CheckDNDPrefix)
    async def SelectCharacter(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        QueryCleaned: str        = TargetQuery.strip().lower()
        OwnedList   : list[dict] = await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        MatchedChar : Typing.Optional[dict] = None

        for CharItem in OwnedList:
            CharID  : str = str(CharItem.get("ID", "")).lower()
            CharName: str = str(CharItem.get("Name", "")).lower()
            if (CharID == QueryCleaned) or (CharName == QueryCleaned):
                MatchedChar = CharItem
                break

        if (MatchedChar is None):
            for CharItem in OwnedList:
                CharName = str(CharItem.get("Name", "")).lower()
                if QueryCleaned in CharName:
                    MatchedChar = CharItem
                    break

        if (MatchedChar is not None):
            SelectedID  : str           = str(MatchedChar.get("ID", ""))
            SelectedName: str           = str(MatchedChar.get("Name", ""))
            self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, SelectedID)
            self.StateService.CharacterCache[SelectedID] = MatchedChar
            ConfirmEmbed: Discord.Embed = Discord.Embed(title = "Active Character Changed", description = f"Active character set to **{SelectedName}**.", color = COLOR_CHARACTER_EMBED)
            await Context.send(embed = ConfirmEmbed)
            return

        ErrorEmbed: Discord.Embed = Discord.Embed(title = "Character Selection Failed", description = f"No character matching `{TargetQuery}` was found among your owned characters.", color = COLOR_ERROR_EMBED)
        await Context.send(embed = ErrorEmbed)

    @Commands.command(name = "sheet")
    @Commands.check(CheckDNDPrefix)
    async def SheetCommand(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nUse `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}character list` to see your characters.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        SheetEmbed: Discord.Embed = self.StateService.FormatSheetEmbed(ActiveRecord)
        await Context.send(embed = SheetEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(CharacterCommands(BotInstance))

