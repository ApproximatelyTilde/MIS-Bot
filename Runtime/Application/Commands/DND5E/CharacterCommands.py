import re                                                as RegularExpressions
import typing                                            as Typing
import uuid                                              as UUIDLibrary
import discord                                           as Discord
import discord.ext.commands                              as Commands
import Runtime.Configuration.Config                      as Config
import Runtime.Services.DebugService                     as Debug
import Runtime.Services.PlatformClient                   as PlatformClient
import Runtime.Services.CharacterStateService            as CharacterState
import Runtime.Services.EncounterManagerService          as EncounterManager
import Runtime.Services.DiceService                      as Dice
import Runtime.Services.Draconic.API.ArgumentParser      as ArgumentParser
import Runtime.Application.Components.InitiativeControls as InitiativeControls
import Runtime.Decorators.AuthorizationDecorators        as AuthorizationDecorators

USER_MENTION_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"^<@!?(\d+)>$")

COLOR_CHARACTER_EMBED: int                        = 0x0030A6
COLOR_ERROR_EMBED    : int                        = 0xA60000
DC1_URL_PATTERN      : RegularExpressions.Pattern = RegularExpressions.compile(r"^(?:https?:\/\/)?v1\.dicecloud\.com\/character\/([a-zA-Z0-9_-]+)(?:[\/?#].*)?$", RegularExpressions.IGNORECASE)
DC2_URL_PATTERN      : RegularExpressions.Pattern = RegularExpressions.compile(r"^(?:https?:\/\/)?(?!v1\.)(?:(?:beta|app|www)\.)?dicecloud\.com\/character\/([a-zA-Z0-9_-]+)(?:[\/?#].*)?$", RegularExpressions.IGNORECASE)
DDB_URL_PATTERN      : RegularExpressions.Pattern = RegularExpressions.compile(r"^(?:https?:\/\/)?(?:(?:www\.)?dndbeyond\.com\/(?:characters\/|sheet-pdfs\/.*_)|ddb\.ac\/characters\/|character-service\.dndbeyond\.com\/character\/v\d+\/character\/)([0-9]+)(?:[\/?#].*)?$", RegularExpressions.IGNORECASE)

def DetectPlatformName(SheetURL: str) -> Typing.Optional[str]:
    CleanedURL: str = SheetURL.strip()
    if (DC1_URL_PATTERN.search(CleanedURL) is not None):
        return "Dicecloud v1"

    if (DC2_URL_PATTERN.search(CleanedURL) is not None):
        return "Dicecloud v2"

    if (DDB_URL_PATTERN.search(CleanedURL) is not None):
        return "D&D Beyond"

    return None

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance: Typing.Any = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)

class CharacterCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterState.CharacterStateService] = None, EncounterManagerInstance: Typing.Optional[EncounterManager.EncounterManagerService] = None) -> None:
        self.BotInstance     : Commands.Bot                                  = BotInstance
        self.StateService    : CharacterState.CharacterStateService          = StateService if (StateService is not None) else (getattr(BotInstance, "CharacterStateService", None) or CharacterState.CharacterStateService())
        self.PlatformClient  : PlatformClient.TallyPlatformClient            = self.StateService.PlatformClient
        self.EncounterManager: EncounterManager.EncounterManagerService = EncounterManagerInstance if (EncounterManagerInstance is not None) else (getattr(BotInstance, "EncounterManager", None) or EncounterManager.EncounterManagerService(PlatformClientInstance = self.PlatformClient))
        self.DiceRoller      : Dice.DiceRollerService                        = Dice.DiceRollerService()

    async def ExecuteListCharacters(self, Context: Commands.Context) -> None:
        FetchedList: list[dict] = await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        OwnedList  : list[dict] = [C for C in FetchedList if (C.get("GameSystem") == "DND5E") and (str(C.get("EntityType", "Character")) == "Character")]
        if not OwnedList:
            NotFoundEmbed: Discord.Embed = Discord.Embed(title = "No Characters Found", description = f"No Dungeons & Dragons characters linked to your Discord account were found on zibell.\n\nUse `{Context.prefix}import <URL>` to import a character sheet, or `{Context.prefix}comp list` for companions/vehicles.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NotFoundEmbed)
            return

        ActiveID : Typing.Optional[str] = self.StateService.GetActiveCharacterID(Context.author.id, Context.channel.id)
        ListEmbed: Discord.Embed        = Discord.Embed(title = "Your zibell Characters", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}character <Name>` to switch active characters.", color = COLOR_CHARACTER_EMBED)
        for CharacterItem in OwnedList:
            CharacterID  : str  = str(CharacterItem.get("ID", ""))
            CharacterName: str  = str(CharacterItem.get("Name", "Unknown"))
            DetailData   : dict = CharacterItem.get("DetailData", {})
            TotalLevel   : int  = int(DetailData.get("TotalLevel", 1))
            ClassesList  : list = DetailData.get("Classes", [])
            ClassText    : str  = ", ".join(f"{C.get("ClassName", "")} {C.get("Level", "")}" for C in ClassesList) or "Level 1"
            IsActive     : bool = (CharacterID == ActiveID)
            Badge        : str  = " ⭐ *(Active)*" if (IsActive) else ""
            ListEmbed.add_field(name = f"{CharacterName}{Badge}", value = f"Level {TotalLevel} • {ClassText}\n`ID: {CharacterID}`", inline = False)

        ListEmbed.set_footer(text = "Tally │ Dungeons & Dragons Character Management")
        await Context.send(embed = ListEmbed)

    async def ExecuteSelectCharacter(self, Context: Commands.Context, TargetQuery: str) -> None:
        QueryCleaned    : str                   = TargetQuery.strip().lower()
        FetchedList     : list[dict]            = await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        OwnedList       : list[dict]            = [C for C in FetchedList if (C.get("GameSystem") == "DND5E")]
        MatchedCharacter: Typing.Optional[dict] = None

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
            SelectedID  : str = str(MatchedCharacter.get("ID", ""))
            SelectedName: str = str(MatchedCharacter.get("Name", ""))
            self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, SelectedID)
            self.StateService.CharacterCache[SelectedID] = MatchedCharacter
            ConfirmEmbed: Discord.Embed = Discord.Embed(title = "Active Character Changed", description = f"Active character set to **{SelectedName}**.", color = COLOR_CHARACTER_EMBED)
            await Context.send(embed = ConfirmEmbed)
            return

        ErrorEmbed: Discord.Embed = Discord.Embed(title = "Character Selection Failed", description = f"No character matching `{TargetQuery}` was found among your owned characters.", color = COLOR_ERROR_EMBED)
        await Context.send(embed = ErrorEmbed)

    async def ExecuteRemoveCharacter(self, Context: Commands.Context) -> None:
        self.StateService.ClearActiveCharacter(Context.author.id, Context.channel.id)

        UnsetEmbed: Discord.Embed = Discord.Embed(title = "Active Character Removed", description = "Active character selection cleared for this channel.", color = COLOR_CHARACTER_EMBED)
        await Context.send(embed = UnsetEmbed)

    async def ExecuteStatusCharacter(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nUse `{Context.prefix}character list` to see your characters.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        CharacterName: str  = str(ActiveRecord.get("Name", "Hero"))
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
            StateLabel: Typing.Any = "💀 Dead" if (FailureCount >= 3) else ("🩺 Stable" if (SuccessCount >= 3) else "⚠️ Dying")
            StatusEmbed.add_field(name = "Death Saves", value = f"Successes: `[{SuccessPips}]`\nFailures:  `[{FailurePips}]` • **{StateLabel}**", inline = True)

        else:
            StatusEmbed.add_field(name = "Death Saves", value = "Healthy *(Conscious)*", inline = True)

        Spellcasting: dict      = DetailData.get("Spellcasting", {})
        SlotEntries : list      = Spellcasting.get("SpellSlots", [])
        SlotStrings : list[str] = []
        for SlotItem in SlotEntries:
            LevelNumber: int = int(SlotItem.get("Level", 0))
            TotalSlots : int = int(SlotItem.get("TotalSlots", 0))
            UsedSlots  : int = int(SlotItem.get("UsedSlots", 0))
            AvailSlots : int = max(0, TotalSlots - UsedSlots)
            if (TotalSlots > 0):
                SlotStrings.append(f"**L{LevelNumber}:** {AvailSlots}/{TotalSlots}")

        if SlotStrings:
            StatusEmbed.add_field(name = "Spell Slots", value = " • ".join(SlotStrings), inline = False)

        CustomCounters: list = DetailData.get("CustomCounters", [])
        if CustomCounters:
            CounterStrings: list[str] = [f"**{C.get("Name")}**: {C.get("CurrentValue", 0)}/{C.get("MaxValue", 0)}" for C in CustomCounters[:6]]
            StatusEmbed.add_field(name = "Custom Counters", value = " | ".join(CounterStrings), inline = False)

        ConcentrationData: Typing.Any = DetailData.get("Concentration")
        if ConcentrationData:
            SpellName: str = str(ConcentrationData.get("SpellName", "Spell"))
            StatusEmbed.add_field(name = "Concentration", value = f"Concentrating on **{SpellName}**", inline = True)

        ActiveConditions: list[str] = DetailData.get("Conditions", [])
        if ActiveConditions:
            StatusEmbed.add_field(name = "Active Conditions", value = ", ".join(f"*{C}*" for C in ActiveConditions), inline = True)

        StatusEmbed.set_footer(text = f"Tally │ Character Status ({Context.prefix}character status)")
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
        CleanedURL    : str                  = SheetURL.strip()
        DetectedSource: Typing.Optional[str] = DetectPlatformName(CleanedURL)
        PlatformLabel : str                  = DetectedSource if (DetectedSource is not None) else "Character"
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"{PlatformLabel} Import Initiated: URL=\"{CleanedURL}\", DiscordID={Context.author.id}")

        try:
            ImportResult  : dict[str, Typing.Any] = await self.PlatformClient.ImportCharacter(ImportURL = CleanedURL, DiscordID = str(Context.author.id))
            CharacterID   : str                   = str(ImportResult.get("ID", ""))
            CharacterName : str                   = str(ImportResult.get("Name", "Imported Character"))
            DetailData    : dict                  = ImportResult.get("DetailData", {})
            TotalLevel    : int                   = int(DetailData.get("TotalLevel", 1))
            ClassesList   : list                  = DetailData.get("Classes", [])
            ClassText     : str                   = ", ".join(f"{C.get("ClassName", "")} {C.get("Level", "")}" for C in ClassesList) or "Level 1"
            HitPoints     : dict                  = DetailData.get("HitPoints", {})
            MaxHP         : int                   = int(HitPoints.get("MaxHitPoints", 10))
            ArmorClass    : int                   = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", 10))
            OriginalSource: str                   = str(DetailData.get("OriginalSource", "") or ImportResult.get("ImportSource", ""))
            ResolvedSource: str                   = "Dicecloud v1" if (OriginalSource == "DC1") else ("Dicecloud v2" if (OriginalSource == "DC2") else ("D&D Beyond" if (OriginalSource == "DDB") else PlatformLabel))

            self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, CharacterID)
            self.StateService.CharacterCache[CharacterID] = ImportResult

            SuccessTitle      : str           = (f"{ResolvedSource} Character Successfully Imported: {CharacterName}" if (ResolvedSource != "Character") else f"Character Successfully Imported: {CharacterName}")
            SuccessDescription: str           = (f"Imported from {ResolvedSource} (`{CleanedURL}`)\nAutomatically set as your active character in this channel." if (ResolvedSource != "Character") else f"Imported from `{CleanedURL}`\nAutomatically set as your active character in this channel.")
            SuccessFooter     : str           = (f"Tally │ Dungeons & Dragons Character Import Engine │ {ResolvedSource}" if (ResolvedSource != "Character") else "Tally │ Dungeons & Dragons Character Import Engine")
            SuccessEmbed      : Discord.Embed = Discord.Embed(title = SuccessTitle, description = SuccessDescription, color = COLOR_CHARACTER_EMBED)
            SuccessEmbed.add_field(name = "Class & Level", value = f"Level {TotalLevel} • {ClassText}", inline = True)
            SuccessEmbed.add_field(name = "Vitals", value = f"HP: **{MaxHP}** | AC: **{ArmorClass}**", inline = True)
            if (ResolvedSource != "Character"):
                SuccessEmbed.add_field(name = "Source Platform", value = ResolvedSource, inline = True)

            SuccessEmbed.add_field(name = "Character ID", value = f"`{CharacterID}`", inline = False)
            SuccessEmbed.set_footer(text = SuccessFooter)
            await Context.send(embed = SuccessEmbed)

        except Exception as ImportError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"{PlatformLabel} Import Failed: {str(ImportError)}")
            if (DetectedSource == "Dicecloud v1"):
                ErrorTitle      : str = "Dicecloud v1 Import Failed"
                ErrorDescription: str = f"Could not import character from Dicecloud v1 (`{CleanedURL}`).\n\n**Error:** {str(ImportError)}\n\n*Verify that your Dicecloud v1 sheet is shared and publicly accessible.*"

            elif (DetectedSource == "Dicecloud v2"):
                ErrorTitle      : str = "Dicecloud v2 Import Failed"
                ErrorDescription: str = f"Could not import character from Dicecloud v2 (`{CleanedURL}`).\n\n**Error:** {str(ImportError)}\n\n*Verify that your Dicecloud v2 sheet is accessible and that credentials are configured.*"

            elif (DetectedSource == "D&D Beyond"):
                ErrorTitle      : str = "D&D Beyond Import Failed"
                ErrorDescription: str = f"Could not import character from D&D Beyond (`{CleanedURL}`).\n\n**Error:** {str(ImportError)}\n\n*Verify that your D&D Beyond sheet is set to Public (not Private).*"

            else:
                ErrorTitle      : str = "Character Import Failed"
                ErrorDescription: str = f"Could not import character from `{CleanedURL}`.\n\n**Error:** {str(ImportError)}\n\n*Supported sources: D&D Beyond (`dndbeyond.com/characters/...`), Dicecloud v1 (`v1.dicecloud.com/character/...`), and Dicecloud v2 (`dicecloud.com/character/...`).*"

            ErrorEmbed: Discord.Embed = Discord.Embed(title = ErrorTitle, description = ErrorDescription, color = COLOR_ERROR_EMBED)
            ErrorEmbed.set_footer(text = (f"Tally │ Dungeons & Dragons Character Import Engine │ {DetectedSource}" if (DetectedSource is not None) else "Tally │ Dungeons & Dragons Character Import Engine"))
            await Context.send(embed = ErrorEmbed)

    @Commands.group(name = "csettings", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def CharacterSettingsGroup(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nUse `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}character list` to see your characters.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        CharacterName: str  = str(ActiveRecord.get("Name", "Hero"))
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        Variables    : dict = DetailData.get("Variables", {})

        RuleSetPref : str = str(Variables.get("csetting_rule", "2024"))
        DicePref    : str = str(Variables.get("csetting_dice", "verbose"))
        CounterStyle: str = str(Variables.get("csetting_counter_display", "number"))

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

    @Commands.group(name = "companion", aliases = ["comp", "vehicle", "ship"], invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def CompanionGroup(self, Context: Commands.Context) -> None:
        await self.ListCompanions(Context)

    @CompanionGroup.command(name = "list", aliases = ["ls"])
    @Commands.check(CheckDND5EPrefix)
    async def ListCompanions(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        LinkedList  : list[dict[str, Typing.Any]]            = []
        if (ActiveRecord is not None):
            ActiveID: str = str(ActiveRecord.get("ID", ""))
            if ActiveID:
                try:
                    LinkedList = await self.PlatformClient.FetchCharacterCompanions(ActiveID)

                except Exception as FetchError:
                    Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"FetchCharacterCompanions Error: {str(FetchError)}")

        OwnedList: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        SeenIDs  : set[str]                    = {str(C.get("ID", "")) for C in LinkedList}
        Combined : list[dict[str, Typing.Any]] = list(LinkedList)
        for Rec in OwnedList:
            RecordSystem: str = str(Rec.get("GameSystem", ""))
            RecordType  : str = str(Rec.get("EntityType", "Character"))
            RecordID    : str = str(Rec.get("ID", ""))
            if (RecordSystem == "DND5E") and (RecordType in ("Companion", "Vehicle")) and (RecordID not in SeenIDs):
                Combined.append(Rec)
                SeenIDs.add(RecordID)

        if not Combined:
            await Context.send("No companions or vehicles found linked to your character or account on the Platform.")
            return

        ListEmbed: Discord.Embed = Discord.Embed(title = "Dungeons & Dragons Companions & Vehicles", description = f"Use `{Context.prefix}comp select <Name>` or `{Context.prefix}comp join <Name>`.", color = COLOR_CHARACTER_EMBED)
        for Entry in Combined[:20]:
            EntryName : str  = str(Entry.get("Name", "Entity"))
            EntryType : str  = str(Entry.get("EntityType", "Companion"))
            EntryID   : str  = str(Entry.get("ID", ""))
            DetailData: dict = Entry.get("DetailData", {})
            if (EntryType == "Vehicle"):
                HullValue      : int = int(DetailData.get("HullPoints", DetailData.get("HitPoints", {}).get("CurrentHitPoints", 50)))
                ArmorClassValue: int = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", DetailData.get("ArmorClass", 15)) if isinstance(DetailData.get("ArmorClass"), dict) else DetailData.get("ArmorClass", 15))
                DetailText     : str = f"Hull: {HullValue} | AC: {ArmorClassValue}"

            else:
                HPBlock        : dict = DetailData.get("HitPoints", {})
                CurHP          : int  = int(HPBlock.get("CurrentHitPoints", 10))
                MaxHP          : int  = int(HPBlock.get("MaxHitPoints", CurHP))
                ArmorClassValue       = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", DetailData.get("ArmorClass", 10)) if isinstance(DetailData.get("ArmorClass"), dict) else DetailData.get("ArmorClass", 10))
                DetailText            = f"HP: {CurHP}/{MaxHP} | AC: {ArmorClassValue}"

            ListEmbed.add_field(name = f"{EntryName} [{EntryType}]", value = f"{DetailText}\n`ID: {EntryID}`", inline = False)

        await Context.send(embed = ListEmbed)

    @CompanionGroup.command(name = "select", aliases = ["switch"])
    @Commands.check(CheckDND5EPrefix)
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
        await Context.send(embed = Discord.Embed(title = f"Active {EntityType} Selected", description = f"Active entity in this channel set to **{EntityName}** ({EntityType}).", color = COLOR_CHARACTER_EMBED))

    @CompanionGroup.command(name = "sheet", aliases = ["view"])
    @Commands.check(CheckDND5EPrefix)
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
    @Commands.check(CheckDND5EPrefix)
    async def CompanionJoinCombat(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat active. Start one with `{Context.prefix}init begin`.")
            return

        Matched: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, TargetQuery)
        if (Matched is None):
            await Context.send(f"Could not find companion or vehicle matching `{TargetQuery}`.")
            return

        DetailData     : dict                                   = Matched.get("DetailData", {})
        EntityID       : str                                    = str(Matched.get("ID", str(UUIDLibrary.uuid4())))
        EntityName     : str                                    = str(Matched.get("Name", TargetQuery))
        EntityType     : str                                    = str(Matched.get("EntityType", "Companion"))
        InitBonus      : int                                    = int(DetailData.get("InitiativeBonus", 0))
        RollOutcome    : Dice.RollOutcome                       = self.DiceRoller.EvaluateRoll(f"1d20{"+" if (InitBonus >= 0) else ""}{InitBonus}")
        HPBlock        : dict                                   = DetailData.get("HitPoints", {})
        CurrentHP      : int                                    = int(HPBlock.get("CurrentHitPoints", DetailData.get("HullPoints", 10)))
        MaxHP          : int                                    = int(HPBlock.get("MaxHitPoints", DetailData.get("MaxHullPoints", CurrentHP)))
        ArmorClassValue: int                                    = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", DetailData.get("ArmorClass", 10)) if isinstance(DetailData.get("ArmorClass"), dict) else DetailData.get("ArmorClass", 10))
        VehicleStats   : Typing.Optional[dict[str, Typing.Any]] = dict(DetailData) if (EntityType == "Vehicle") else None

        NewCombatant: Typing.Any = EncounterManager.CombatantEntry(ID = EntityID, Name = EntityName, Initiative = RollOutcome.Total, CurrentHitPoints = CurrentHP, MaxHitPoints = MaxHP, ArmorClass = ArmorClassValue, EntityType = EntityType, ParentCharacterID = Matched.get("ParentCharacterID"), IsMonster = False, ControllerDiscordID = str(Context.author.id), CharacterID = EntityID, InitiativeBonus = InitBonus, VehicleStats = VehicleStats)
        Encounter.AddCombatant(NewCombatant)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context), CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(content = f"**{EntityName}** ({EntityType}) joined combat (Init: {RollOutcome.Total})!", embed = StatusEmbed, view = ControlsView)

    @CompanionGroup.command(name = "link")
    @Commands.check(CheckDND5EPrefix)
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
            FetchedList   : list[dict[str, Typing.Any]]            = await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
            ParentLow     : str                                    = ParentQuery.strip().lower()
            for Candidate in FetchedList:
                if (Candidate.get("GameSystem") == "DND5E") and (str(Candidate.get("EntityType", "Character")) == "Character"):
                    if (ParentLow in str(Candidate.get("Name", "")).lower()) or (str(Candidate.get("ID", "")).lower() == ParentLow):
                        ParentRecord = Candidate
                        break

        else:
            CompanionQuery = " ".join(PositionalList).strip()
            ParentRecord   = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)

        if (ParentRecord is None) or (str(ParentRecord.get("EntityType", "Character")) != "Character"):
            await Context.send("You must select or specify a primary `Character` as the link parent.")
            return

        Matched: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, CompanionQuery)
        if (Matched is None):
            await Context.send(f"Could not find companion or vehicle matching `{CompanionQuery}`.")
            return

        ParentID   : str = str(ParentRecord.get("ID", ""))
        CompanionID: str = str(Matched.get("ID", ""))
        try:
            UpdatedRecord: dict[str, Typing.Any] = await self.PlatformClient.LinkOrCreateCompanion(ParentID, CompanionID = CompanionID, EntityType = str(Matched.get("EntityType", "Companion")))
            self.StateService.CharacterCache[CompanionID] = UpdatedRecord
            await Context.send(f"Linked **{UpdatedRecord.get("Name", CompanionQuery)}** ({UpdatedRecord.get("EntityType", "Companion")}) to **{ParentRecord.get("Name", "Character")}**.")

        except Exception as LinkError:
            await Context.send(f"Failed to link companion: {str(LinkError)}")

    @CompanionGroup.command(name = "transfer")
    @Commands.check(CheckDND5EPrefix)
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
                PoolList: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchCharactersByEntityType(EntityCategory, GameSystem = "DND5E")
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
            UpdatedRecord: Typing.Any = await self.PlatformClient.TransferCharacterEntity(EntityID, {"ParentCharacterID": None})
            self.StateService.CharacterCache[EntityID] = UpdatedRecord
            await Context.send(f"Unlinked **{EntityName}** from its parent character.")
            return

        if (MentionMatch is not None):
            TargetDiscordID: str                  = MentionMatch.group(1)
            TargetOwnerID  : Typing.Optional[str] = await self.PlatformClient.ResolvePlatformUserIDByDiscordID(TargetDiscordID)
            if (TargetOwnerID is None):
                await Context.send("Target user does not have a linked account with characters on the Platform.")
                return

            TargetCharacter  : Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(TargetDiscordID, Context.channel.id)
            NewParentID : Typing.Optional[str]                   = str(TargetCharacter.get("ID")) if (TargetCharacter is not None) else None
            UpdatedRecord                                        = await self.PlatformClient.TransferCharacterEntity(EntityID, {"OwnerID": TargetOwnerID, "ParentCharacterID": NewParentID})
            self.StateService.CharacterCache[EntityID]           = UpdatedRecord
            if (TargetCharacter is not None):
                await Context.send(f"Transferred **{EntityName}** to **{TargetCharacter.get("Name")}**.")

            else:
                await Context.send(f"Transferred ownership of **{EntityName}** to <@{TargetDiscordID}>.")

            return

        IsDM         : bool                                   = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        CandidatePool: list[dict[str, Typing.Any]]            = await self.PlatformClient.FetchCharactersByEntityType("Character", GameSystem = "DND5E") if IsDM else await self.PlatformClient.FetchCharactersByDiscordID(str(Context.author.id))
        TargetParent : Typing.Optional[dict[str, Typing.Any]] = None
        for Candidate in CandidatePool:
            if (Candidate.get("GameSystem") == "DND5E") and (str(Candidate.get("EntityType", "Character")) == "Character"):
                if (DestLower in str(Candidate.get("Name", "")).lower()) or (str(Candidate.get("ID", "")).lower() == DestLower):
                    TargetParent = Candidate
                    break

        if (TargetParent is None):
            await Context.send(f"Could not find target Character matching `{DestinationText}`.")
            return

        TransferPayload: dict[str, Typing.Any] = {
            "ParentCharacterID": str(TargetParent.get("ID"))
        }
        if (TargetParent.get("OwnerID") is not None) and (TargetParent.get("OwnerID") != Matched.get("OwnerID")):
            TransferPayload["OwnerID"] = str(TargetParent.get("OwnerID"))

        UpdatedRecord = await self.PlatformClient.TransferCharacterEntity(EntityID, TransferPayload)
        self.StateService.CharacterCache[EntityID] = UpdatedRecord
        await Context.send(f"Transferred **{EntityName}** to **{TargetParent.get("Name", DestinationText)}**.")

    @Commands.group(name = "other", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def OtherEntityGroup(self, Context: Commands.Context) -> None:
        await self.ListOtherEntities(Context)

    @OtherEntityGroup.command(name = "list", aliases = ["ls"])
    @Commands.check(CheckDND5EPrefix)
    async def ListOtherEntities(self, Context: Commands.Context, *, FilterQuery: str = "") -> None:
        if not AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context):
            await Context.send("You lack permission to view Platform Other entities. Requires Dungeon Master or Macro Master role.")
            return

        OthersList: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchCharactersByEntityType("Other", GameSystem = "DND5E")
        if FilterQuery.strip():
            QueryLow  : str = FilterQuery.strip().lower()
            OthersList      = [O for O in OthersList if (QueryLow in str(O.get("Name", "")).lower())]

        if not OthersList:
            await Context.send("No Dungeons & Dragons `Other` entities found on the Platform.")
            return

        ListEmbed: Discord.Embed = Discord.Embed(title = f"Platform Other Entities ({len(OthersList)})", description = f"Spawn in combat with `{Context.prefix}init addother <Name>` or select with `{Context.prefix}other select <Name>`.", color = COLOR_CHARACTER_EMBED)
        for Entry in OthersList[:20]:
            ListEmbed.add_field(name = str(Entry.get("Name", "Entity")), value = f"`ID: {Entry.get("ID", "")}`", inline = True)

        await Context.send(embed = ListEmbed)

    @OtherEntityGroup.command(name = "select", aliases = ["switch"])
    @Commands.check(CheckDND5EPrefix)
    async def SelectOtherEntity(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        if not AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context):
            await Context.send("You lack permission to select Platform Other entities. Requires Dungeon Master or Macro Master role.")
            return

        OthersList: list[dict[str, Typing.Any]]            = await self.PlatformClient.FetchCharactersByEntityType("Other", GameSystem = "DND5E")
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
            await Context.send(f"Could not find Dungeons & Dragons `Other` entity matching `{TargetQuery}`.")
            return

        EntityID  : str = str(Matched.get("ID", ""))
        EntityName: str = str(Matched.get("Name", TargetQuery))
        self.StateService.SetActiveCharacter(Context.author.id, Context.channel.id, EntityID)
        self.StateService.CharacterCache[EntityID] = Matched
        await Context.send(embed = Discord.Embed(title = "Active Entity Changed", description = f"Active Dungeons & Dragons entity set to **{EntityName}** (Other).", color = COLOR_CHARACTER_EMBED))

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(CharacterCommands(BotInstance))
