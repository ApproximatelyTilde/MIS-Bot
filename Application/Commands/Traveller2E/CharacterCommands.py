import typing                         as Typing
import discord                        as Discord
import discord.ext.commands          as Commands
import Configuration.Config           as Config
import Services.DebugService          as Debug
import Services.TravellerStateService as TravellerStateService

COLOR_TRAVELLER_EMBED: int = 0x005E5E
COLOR_ERROR_EMBED    : int = 0xA60000

def CheckTravellerPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER)

class TravellerCharacterCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[TravellerStateService.TravellerStateService] = None) -> None:
        self.BotInstance  : Commands.Bot                                = BotInstance
        self.StateService : TravellerStateService.TravellerStateService = StateService if (StateService is not None) else TravellerStateService.TravellerStateService()

    @Commands.group(name = "trav_character", aliases = ["trav_char"], invoke_without_command = True)
    @Commands.check(CheckTravellerPrefix)
    async def CharacterGroup(self, Context: Commands.Context) -> None:
        await self.ListCharacters(Context)

    @CharacterGroup.command(name = "list")
    @Commands.check(CheckTravellerPrefix)
    async def ListCharacters(self, Context: Commands.Context) -> None:
        MatchedList: list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        TravellerCharacters: list[dict[str, Typing.Any]] = [C for C in MatchedList if C.get("GameSystem") == "Traveller2ndEdition"]

        if not TravellerCharacters:
            NoCharsEmbed: Discord.Embed = Discord.Embed(title = "No Traveller Characters", description = "No Traveller 2nd Edition characters linked to your Discord account on MIS Platform.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharsEmbed)
            return

        ListEmbed: Discord.Embed = Discord.Embed(title = f"Traveller Characters ({len(TravellerCharacters)})", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}character select <Name|ID>` to switch your active character.", color = COLOR_TRAVELLER_EMBED)

        for CharacterRecord in TravellerCharacters:
            SummaryData: dict   = CharacterRecord.get("SummaryData", {})
            CharName   : str    = str(CharacterRecord.get("Name", "Unnamed"))
            CharID     : str    = str(CharacterRecord.get("ID", "Unknown"))
            Career     : str    = str(SummaryData.get("Career", "Citizen"))
            Terms      : int    = int(SummaryData.get("Terms", 1))
            Age        : int    = int(SummaryData.get("Age", 22))
            Homeworld  : str    = str(SummaryData.get("Homeworld", "Core"))
            ListEmbed.add_field(name = CharName, value = f"**Career:** {Career} (Terms: {Terms}, Age: {Age})\n**Homeworld:** {Homeworld}\n`ID: {CharID}`", inline = False)

        ListEmbed.set_footer(text = "MIS-Bot • Traveller 2E Subsystem")
        await Context.send(embed = ListEmbed)

    @CharacterGroup.command(name = "select", aliases = ["switch", "set"])
    @Commands.check(CheckTravellerPrefix)
    async def SelectCharacter(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        MatchedList: list[dict[str, Typing.Any]] = await self.StateService.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        TravellerCharacters: list[dict[str, Typing.Any]] = [C for C in MatchedList if C.get("GameSystem") == "Traveller2ndEdition"]

        QueryLower    : str                                  = TargetQuery.strip().lower()
        SelectedRecord: Typing.Optional[dict[str, Typing.Any]] = None

        for Candidate in TravellerCharacters:
            CandidateID  : str = str(Candidate.get("ID", "")).lower()
            CandidateName: str = str(Candidate.get("Name", "")).lower()
            if (CandidateID == QueryLower) or (CandidateName == QueryLower):
                SelectedRecord = Candidate
                break

        if (SelectedRecord is None):
            for Candidate in TravellerCharacters:
                CandidateName = str(Candidate.get("Name", "")).lower()
                if QueryLower in CandidateName:
                    SelectedRecord = Candidate
                    break

        if (SelectedRecord is None):
            await Context.send(f"Could not find Traveller character matching `{TargetQuery}`.")
            return

        CharID  : str = str(SelectedRecord.get("ID"))
        CharName: str = str(SelectedRecord.get("Name"))
        self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, CharID)
        self.StateService.CharacterCache[CharID] = SelectedRecord

        ConfirmEmbed: Discord.Embed = Discord.Embed(title = "Active Character Changed", description = f"Active Traveller character set to **{CharName}**.", color = COLOR_TRAVELLER_EMBED)
        await Context.send(embed = ConfirmEmbed)

    @Commands.command(name = "trav_sheet")
    @Commands.check(CheckTravellerPrefix)
    async def SheetCommand(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active Traveller character selected.\n\nSelect one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        SummaryData    : dict = ActiveRecord.get("SummaryData", {})
        DetailData     : dict = ActiveRecord.get("DetailData", {})
        Characteristics: dict = DetailData.get("Characteristics", {})
        Skills         : dict = DetailData.get("Skills", {})
        InventoryList  : list = DetailData.get("Inventory", [])
        CurrencyDict   : dict = DetailData.get("Currency", {})

        CharName : str = str(ActiveRecord.get("Name", "Traveller"))
        Career   : str = str(SummaryData.get("Career", "Citizen"))
        Terms    : int = int(SummaryData.get("Terms", 1))
        Age      : int = int(SummaryData.get("Age", 22))
        Homeworld: str = str(SummaryData.get("Homeworld", "Core"))
        Title    : str = str(SummaryData.get("Title", "Citizen"))
        Credits  : int = int(CurrencyDict.get("Credits", 0))

        SheetEmbed: Discord.Embed = Discord.Embed(title = f"{CharName} — {Title}", description = f"**Career:** {Career} | **Terms:** {Terms} | **Age:** {Age}\n**Homeworld:** {Homeworld} | **Credits:** Cr {Credits:,}", color = COLOR_TRAVELLER_EMBED)

        AttrLines: list[str] = []
        for ShortCode, FullName in [("STR", "Strength"), ("DEX", "Dexterity"), ("END", "Endurance"), ("INT", "Intelligence"), ("EDU", "Education"), ("SOC", "SocialStanding")]:
            ScoreValue: int = int(Characteristics.get(FullName, 7))
            ModValue  : int = self.StateService.CalculateCharacteristicModifier(ScoreValue)
            AttrLines.append(f"**{ShortCode}**: {ScoreValue:>2} (`{'+' if ModValue >= 0 else ''}{ModValue}`)")

        SheetEmbed.add_field(name = "Characteristics", value = " • ".join(AttrLines[:3]) + "\n" + " • ".join(AttrLines[3:]), inline = False)

        TrainedSkills: list[str] = [f"**{SkillKey}**: {SkillVal}" for SkillKey, SkillVal in sorted(Skills.items()) if (SkillVal >= 0)]
        SkillsText   : str       = ", ".join(TrainedSkills) if TrainedSkills else "No trained skills."
        SheetEmbed.add_field(name = f"Trained Skills ({len(TrainedSkills)})", value = SkillsText[:1020], inline = False)

        InvText: str = "\n".join(f"• {Item}" for Item in InventoryList) if InventoryList else "Empty inventory."
        SheetEmbed.add_field(name = "Inventory", value = InvText[:1020], inline = False)

        SheetEmbed.set_footer(text = f"MIS-Bot • MGT2E Character Sheet")
        await Context.send(embed = SheetEmbed)

    @Commands.command(name = "trav_inv", aliases = ["trav_inventory"])
    @Commands.check(CheckTravellerPrefix)
    async def InventoryCommand(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Traveller character selected.")
            return

        CharName     : str  = str(ActiveRecord.get("Name", "Traveller"))
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        InventoryList: list = DetailData.get("Inventory", [])
        Credits      : int  = int(DetailData.get("Currency", {}).get("Credits", 0))

        InvEmbed: Discord.Embed = Discord.Embed(title = f"{CharName}'s Inventory", description = f"**Current Wealth:** Cr {Credits:,}", color = COLOR_TRAVELLER_EMBED)
        ItemsText: str          = "\n".join(f"• {Item}" for Item in InventoryList) if InventoryList else "No items in inventory."
        InvEmbed.add_field(name = f"Possessions ({len(InventoryList)})", value = ItemsText[:1020], inline = False)
        InvEmbed.set_footer(text = "MIS-Bot • Traveller 2E Inventory")
        await Context.send(embed = InvEmbed)

    @Commands.command(name = "trav_credits")
    @Commands.check(CheckTravellerPrefix)
    async def CreditsCommand(self, Context: Commands.Context, DeltaText: str) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Traveller character selected.")
            return

        DetailData  : dict = ActiveRecord.get("DetailData", {})
        CurrencyDict: dict = DetailData.setdefault("Currency", {})
        CurrentCr   : int  = int(CurrencyDict.get("Credits", 0))

        CleanDelta: str = DeltaText.strip()
        try:
            if CleanDelta.startswith("+"):
                NewCr = CurrentCr + int(CleanDelta[1:])

            elif CleanDelta.startswith("-"):
                NewCr = max(0, CurrentCr - int(CleanDelta[1:]))

            else:
                NewCr = max(0, int(CleanDelta))

            CurrencyDict["Credits"] = NewCr
            await Context.send(f"**{ActiveRecord.get('Name')}** Credits: Cr {CurrentCr:,} ➔ **Cr {NewCr:,}**")

        except ValueError:
            await Context.send("Invalid credits amount. Example: `!credits +500` or `!credits -120`")

async def setup(BotInstance: Commands.Bot) -> None:
    StateServiceInstance: Typing.Optional[TravellerStateService.TravellerStateService] = getattr(BotInstance, "TravellerStateService", None)
    await BotInstance.add_cog(TravellerCharacterCommands(BotInstance, StateService = StateServiceInstance))
