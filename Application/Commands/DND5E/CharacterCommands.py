import typing                         as Typing
import discord                        as Discord
import discord.ext.commands           as Commands
import Configuration.Config           as Config
import Services.DebugService          as Debug
import Services.PlatformClient        as PlatformClient
import Services.CharacterStateService as CharacterState

COLOR_CHARACTER_EMBED: int = 0x0030A6
COLOR_ERROR_EMBED    : int = 0xA60000

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E5E)

class CharacterCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterState.CharacterStateService] = None) -> None:
        self.BotInstance   : Commands.Bot                        = BotInstance
        self.StateService  : CharacterState.CharacterStateService = StateService if (StateService is not None) else CharacterState.CharacterStateService()
        self.PlatformClient: PlatformClient.MISPlatformClient          = self.StateService.PlatformClient

    async def ExecuteListCharacters(self, Context: Commands.Context) -> None:
        FetchedList: list[dict] = await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        OwnedList  : list[dict] = [C for C in FetchedList if (C.get("GameSystem") == "DND5E")]
        if not OwnedList:
            NotFoundEmbed: Discord.Embed = Discord.Embed(title = "No Characters Found", description = "No Dungeons & Dragons characters linked to your Discord account were found on MIS.\n\nUse `&import <URL>` to import a character sheet from D&D Beyond or Dicecloud v1.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NotFoundEmbed)
            return

        ActiveID : Typing.Optional[str] = self.StateService.GetActiveCharacterID(Context.author.id, Context.channel.id)
        ListEmbed: Discord.Embed        = Discord.Embed(title = "Your MIS Characters", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E5E}character <Name>` to switch active characters.", color = COLOR_CHARACTER_EMBED)
        for CharacterItem in OwnedList:
            CharacterID     : str  = str(CharacterItem.get("ID", ""))
            CharacterName   : str  = str(CharacterItem.get("Name", "Unknown"))
            DetailData : dict = CharacterItem.get("DetailData", {})
            TotalLvl   : int  = int(DetailData.get("TotalLevel", 1))
            ClassesList: list = DetailData.get("Classes", [])
            ClassText  : str  = ", ".join(f"{C.get("ClassName", "")} {C.get("Level", "")}" for C in ClassesList) or "Level 1"
            IsActive   : bool = (CharacterID == ActiveID)
            Badge      : str  = " ⭐ *(Active)*" if (IsActive) else ""
            ListEmbed.add_field(name = f"{CharacterName}{Badge}", value = f"Level {TotalLvl} • {ClassText}\n`ID: {CharacterID}`", inline = False)

        ListEmbed.set_footer(text = "MIS-Bot • Dungeons & Dragons Character Management")
        await Context.send(embed = ListEmbed)

    async def ExecuteSelectCharacter(self, Context: Commands.Context, TargetQuery: str) -> None:
        QueryCleaned: str        = TargetQuery.strip().lower()
        FetchedList : list[dict] = await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        OwnedList   : list[dict] = [C for C in FetchedList if (C.get("GameSystem") == "DND5E")]
        MatchedCharacter : Typing.Optional[dict] = None

        for CharacterItem in OwnedList:
            CharacterID  : str = str(CharacterItem.get("ID", "")).lower()
            CharacterName: str = str(CharacterItem.get("Name", "")).lower()
            if (CharacterID == QueryCleaned) or (CharacterName == QueryCleaned):
                MatchedCharacter = CharacterItem
                break

        if (MatchedCharacter is None):
            for CharacterItem in OwnedList:
                CharacterName = str(CharacterItem.get("Name", "")).lower()
                if QueryCleaned in CharacterName:
                    MatchedCharacter = CharacterItem
                    break

        if (MatchedCharacter is not None):
            SelectedID  : str           = str(MatchedCharacter.get("ID", ""))
            SelectedName: str           = str(MatchedCharacter.get("Name", ""))
            self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, SelectedID)
            self.StateService.CharacterCache[SelectedID] = MatchedCharacter
            ConfirmEmbed: Discord.Embed = Discord.Embed(title = "Active Character Changed", description = f"Active character set to **{SelectedName}**.", color = COLOR_CHARACTER_EMBED)
            await Context.send(embed = ConfirmEmbed)
            return

        ErrorEmbed: Discord.Embed = Discord.Embed(title = "Character Selection Failed", description = f"No character matching `{TargetQuery}` was found among your owned characters.", color = COLOR_ERROR_EMBED)
        await Context.send(embed = ErrorEmbed)

    async def ExecuteRemoveCharacter(self, Context: Commands.Context) -> None:
        ContextKey: str = self.StateService.BuildContextKey(Context.author.id, Context.channel.id)
        if ContextKey in self.StateService.UserActiveCharacter:
            del self.StateService.UserActiveCharacter[ContextKey]

        UnsetEmbed: Discord.Embed = Discord.Embed(title = "Active Character Removed", description = "Active character selection cleared for this channel.", color = COLOR_CHARACTER_EMBED)
        await Context.send(embed = UnsetEmbed)

    async def ExecuteStatusCharacter(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nUse `{Context.prefix}character list` to see your characters.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        CharacterName     : str  = str(ActiveRecord.get("Name", "Hero"))
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        HitPointsData: dict = DetailData.get("HitPoints", {})
        CurrentHP    : int  = int(HitPointsData.get("CurrentHitPoints", 10))
        MaxHP        : int  = int(HitPointsData.get("MaxHitPoints", 10))
        TempHP       : int  = int(HitPointsData.get("TemporaryHitPoints", 0))
        ArmorClass   : int  = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", 10))
        TotalLevel   : int  = int(DetailData.get("TotalLevel", 1))

        Pct       : float = max(0.0, min(1.0, CurrentHP / MaxHP)) if (MaxHP > 0) else 0.0
        FilledBars: int   = int(round(Pct * 10))
        EmptyBars : int   = 10 - FilledBars
        BarString : str   = f"`[{"█" * FilledBars}{"░" * EmptyBars}]` **{CurrentHP} / {MaxHP}**"
        if (TempHP > 0):
            BarString += f" *(+{TempHP} Temp)*"

        StatusEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName} — Resource & Status Overview", description = f"Level {TotalLevel} • Armor Class **{ArmorClass}**", color = COLOR_CHARACTER_EMBED)
        StatusEmbed.add_field(name = "Hit Points", value = BarString, inline = False)

        PoolList    : list[dict[str, Typing.Any]] = self.StateService.GetHitDicePool(DetailData)
        TotalAvailHD: int                         = sum(int(P.get("Available", 0)) for P in PoolList)
        TotalPoolHD : int                         = sum(int(P.get("Total", 0)) for P in PoolList)
        HDStrings   : list[str]                   = [f"d{P.get("HitDie")}: {P.get("Available")}/{P.get("Total")}" for P in PoolList]
        if HDStrings:
            StatusEmbed.add_field(name = "Hit Dice", value = f"{", ".join(HDStrings)}\n*({TotalAvailHD}/{TotalPoolHD} available)*", inline = True)

        SuccessCount, FailureCount = self.StateService.GetDeathSaves(DetailData)
        if (CurrentHP == 0) or (SuccessCount > 0) or (FailureCount > 0):
            SuccessPips, FailurePips = self.StateService.FormatDeathSavePips(SuccessCount, FailureCount)
            StateLabel               = "💀 Dead" if (FailureCount >= 3) else ("🩺 Stable" if (SuccessCount >= 3) else "⚠️ Dying")
            StatusEmbed.add_field(name = "Death Saves", value = f"Successes: `[{SuccessPips}]`\nFailures:  `[{FailurePips}]` • **{StateLabel}**", inline = True)

        else:
            StatusEmbed.add_field(name = "Death Saves", value = "Healthy *(Conscious)*", inline = True)

        Spellcasting: dict      = DetailData.get("Spellcasting", {})
        SlotEntries : list      = Spellcasting.get("SpellSlots", [])
        SlotStrings : list[str] = []
        for SlotItem in SlotEntries:
            LevelNum  : int = int(SlotItem.get("Level", 0))
            TotalSlots: int = int(SlotItem.get("TotalSlots", 0))
            UsedSlots : int = int(SlotItem.get("UsedSlots", 0))
            AvailSlots: int = max(0, TotalSlots - UsedSlots)
            if (TotalSlots > 0):
                SlotStrings.append(f"**L{LevelNum}:** {AvailSlots}/{TotalSlots}")

        if SlotStrings:
            StatusEmbed.add_field(name = "Spell Slots", value = " • ".join(SlotStrings), inline = False)

        CustomCounters: list = DetailData.get("CustomCounters", [])
        if CustomCounters:
            CounterStrings: list[str] = [f"**{C.get("Name")}**: {C.get("CurrentValue", 0)}/{C.get("MaxValue", 0)}" for C in CustomCounters[:6]]
            StatusEmbed.add_field(name = "Custom Counters", value = " | ".join(CounterStrings), inline = False)

        ConcentrationData = DetailData.get("Concentration")
        if ConcentrationData:
            SpellName: str = str(ConcentrationData.get("SpellName", "Spell"))
            StatusEmbed.add_field(name = "Concentration", value = f"Concentrating on **{SpellName}**", inline = True)

        ActiveConditions: list[str] = DetailData.get("Conditions", [])
        if ActiveConditions:
            StatusEmbed.add_field(name = "Active Conditions", value = ", ".join(f"*{C}*" for C in ActiveConditions), inline = True)

        StatusEmbed.set_footer(text = f"MIS-Bot • Character Status ({Context.prefix}character status)")
        await Context.send(embed = StatusEmbed)

    @Commands.group(name = "character", aliases = ["char"], invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def CharacterGroup(self, Context: Commands.Context, *, TargetArgument: Typing.Optional[str] = None) -> None:
        if (TargetArgument is None):
            ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
            if (ActiveRecord is not None):
                await self.ExecuteStatusCharacter(Context)
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

        elif (FirstKeyword == "status"):
            await self.ExecuteStatusCharacter(Context)
            return

        elif FirstKeyword in ("sheet", "full"):
            ActiveRecord = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
            if (ActiveRecord is not None):
                SheetEmbed: Discord.Embed = self.StateService.FormatSheetEmbed(ActiveRecord)
                await Context.send(embed = SheetEmbed)
                return

            await self.ExecuteListCharacters(Context)
            return

        await self.ExecuteSelectCharacter(Context, TargetQuery = CleanedArgument)

    @CharacterGroup.command(name = "sheet", aliases = ["full"])
    @Commands.check(CheckDND5EPrefix)
    async def SheetCharacter(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is not None):
            SheetEmbed: Discord.Embed = self.StateService.FormatSheetEmbed(ActiveRecord)
            await Context.send(embed = SheetEmbed)
            return

        await self.ExecuteListCharacters(Context)

    @CharacterGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListCharacters(self, Context: Commands.Context) -> None:
        await self.ExecuteListCharacters(Context)

    @CharacterGroup.command(name = "select", aliases = ["switch", "set"])
    @Commands.check(CheckDND5EPrefix)
    async def SelectCharacter(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        await self.ExecuteSelectCharacter(Context, TargetQuery = TargetQuery)

    @CharacterGroup.command(name = "delete", aliases = ["remove", "unset"])
    @Commands.check(CheckDND5EPrefix)
    async def RemoveCharacter(self, Context: Commands.Context) -> None:
        await self.ExecuteRemoveCharacter(Context)

    @CharacterGroup.command(name = "status")
    @Commands.check(CheckDND5EPrefix)
    async def StatusCharacter(self, Context: Commands.Context) -> None:
        await self.ExecuteStatusCharacter(Context)

    @Commands.command(name = "import")
    @Commands.check(CheckDND5EPrefix)
    async def ImportCommand(self, Context: Commands.Context, SheetURL: str) -> None:
        CleanedURL: str = SheetURL.strip()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Character Import Initiated: URL=\"{CleanedURL}\", DiscordID={Context.author.id}")

        try:
            ImportResult : dict[str, Typing.Any] = await self.PlatformClient.ImportCharacter(ImportURL = CleanedURL, DiscordID = str(Context.author.id))
            CharacterID  : str                   = str(ImportResult.get("ID", ""))
            CharacterName: str                   = str(ImportResult.get("Name", "Imported Character"))
            DetailData   : dict                  = ImportResult.get("DetailData", {})
            TotalLevel   : int                   = int(DetailData.get("TotalLevel", 1))
            ClassesList  : list                  = DetailData.get("Classes", [])
            ClassText    : str                   = ", ".join(f"{C.get("ClassName", "")} {C.get("Level", "")}" for C in ClassesList) or "Level 1"
            HitPoints    : dict                  = DetailData.get("HitPoints", {})
            MaxHP        : int                   = int(HitPoints.get("MaxHitPoints", 10))
            ArmorClass   : int                   = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", 10))

            self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, CharacterID)
            self.StateService.CharacterCache[CharacterID] = ImportResult

            SuccessEmbed: Discord.Embed = Discord.Embed(title = f"Character Successfully Imported: {CharacterName}", description = f"Imported from `{CleanedURL}`\nAutomatically set as your active character in this channel.", color = COLOR_CHARACTER_EMBED)
            SuccessEmbed.add_field(name = "Class & Level", value = f"Level {TotalLevel} • {ClassText}", inline = True)
            SuccessEmbed.add_field(name = "Vitals", value = f"HP: **{MaxHP}** | AC: **{ArmorClass}**", inline = True)
            SuccessEmbed.add_field(name = "Character ID", value = f"`{CharacterID}`", inline = False)
            SuccessEmbed.set_footer(text = "MIS-Bot • Dungeons & Dragons Character Import Engine")
            await Context.send(embed = SuccessEmbed)

        except Exception as ImportError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Character Import Failed: {str(ImportError)}")
            ErrorEmbed: Discord.Embed = Discord.Embed(title = "Character Import Failed", description = f"Could not import character from `{CleanedURL}`.\n\n**Error:** {str(ImportError)}\n\n*Supported sources: D&D Beyond (`dndbeyond.com/characters/...`) and Dicecloud v1.*", color = COLOR_ERROR_EMBED)
            await Context.send(embed = ErrorEmbed)

    @Commands.group(name = "csettings", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def CharacterSettingsGroup(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nUse `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}character list` to see your characters.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        CharacterName    : str  = str(ActiveRecord.get("Name", "Hero"))
        DetailData  : dict = ActiveRecord.get("DetailData", {})
        Variables   : dict = DetailData.get("Variables", {})

        RuleSetPref : str  = str(Variables.get("csetting_rule", "2024"))
        DicePref    : str  = str(Variables.get("csetting_dice", "verbose"))
        CounterStyle: str  = str(Variables.get("csetting_counter_display", "number"))

        SettingsEmbed: Discord.Embed = Discord.Embed(title = f"Settings for {CharacterName}", description = "Per-character preferences stored on the Platform.", color = COLOR_CHARACTER_EMBED)
        SettingsEmbed.add_field(name = "Ruleset Preference", value = f"`{RuleSetPref}` (`2024` or `legacy`)", inline = True)
        SettingsEmbed.add_field(name = "Dice Display", value = f"`{DicePref}` (`verbose` or `compact`)", inline = True)
        SettingsEmbed.add_field(name = "Counter Shape", value = f"`{CounterStyle}` (`number`, `circle`, `square`, `hex`, `star`)", inline = True)
        SettingsEmbed.set_footer(text = f"Use {Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}csettings <rule|dice|counter_display> <value> to modify.")
        await Context.send(embed = SettingsEmbed)

    @CharacterSettingsGroup.command(name = "rule")
    @Commands.check(CheckDND5EPrefix)
    async def SetRulePreference(self, Context: Commands.Context, PreferenceValue: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("No active character selected.")
            return

        CleanedValue: str = PreferenceValue.strip().lower()
        if CleanedValue not in ("2024", "legacy"):
            await Context.send("Invalid ruleset preference. Valid values are `2024` or `legacy`.")
            return

        CharacterID: str = str(ActiveRecord.get("ID", ""))
        await self.PlatformClient.SetCharacterVariables(CharacterID, {"csetting_rule": CleanedValue})
        ActiveRecord.setdefault("DetailData", {}).setdefault("Variables", {})["csetting_rule"] = CleanedValue
        await Context.send(f"Ruleset preference for **{ActiveRecord.get("Name")}** updated to `{CleanedValue}`.")

    @CharacterSettingsGroup.command(name = "dice")
    @Commands.check(CheckDND5EPrefix)
    async def SetDicePreference(self, Context: Commands.Context, PreferenceValue: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("No active character selected.")
            return

        CleanedValue: str = PreferenceValue.strip().lower()
        if CleanedValue not in ("compact", "verbose"):
            await Context.send("Invalid dice preference. Valid values are `compact` or `verbose`.")
            return

        CharacterID: str = str(ActiveRecord.get("ID", ""))
        await self.PlatformClient.SetCharacterVariables(CharacterID, {"csetting_dice": CleanedValue})
        ActiveRecord.setdefault("DetailData", {}).setdefault("Variables", {})["csetting_dice"] = CleanedValue
        await Context.send(f"Dice display preference for **{ActiveRecord.get("Name")}** updated to `{CleanedValue}`.")

    @CharacterSettingsGroup.command(name = "counter_display", aliases = ["counter", "cc"])
    @Commands.check(CheckDND5EPrefix)
    async def SetCounterDisplayPreference(self, Context: Commands.Context, StyleValue: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("No active character selected.")
            return

        CleanedValue: str = StyleValue.strip().lower()
        if CleanedValue not in ("number", "circle", "square", "hex", "star"):
            await Context.send("Invalid counter shape. Valid shapes are `number`, `circle`, `square`, `hex`, or `star`.")
            return

        CharacterID: str = str(ActiveRecord.get("ID", ""))
        await self.PlatformClient.SetCharacterVariables(CharacterID, {"csetting_counter_display": CleanedValue})
        ActiveRecord.setdefault("DetailData", {}).setdefault("Variables", {})["csetting_counter_display"] = CleanedValue
        await Context.send(f"Counter display shape for **{ActiveRecord.get("Name")}** updated to `{CleanedValue}`.")

    @Commands.command(name = "sheet")
    @Commands.check(CheckDND5EPrefix)
    async def SheetCommand(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nUse `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}character list` to see your characters.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        SheetEmbed: Discord.Embed = self.StateService.FormatSheetEmbed(ActiveRecord)
        await Context.send(embed = SheetEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(CharacterCommands(BotInstance))
