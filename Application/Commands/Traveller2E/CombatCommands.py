import re                                       as RegularExpressions
import typing                                   as Typing
import uuid                                     as UUIDLibrary
import discord                                  as Discord
import discord.ext.commands                     as Commands
import Configuration.Config                     as Config
import Services.DebugService                    as Debug
import Services.TravellerStateService           as TravellerStateService
import Services.EncounterManagerService         as EncounterManagerService
import Application.Components.InitiativeControls as InitiativeControls

COLOR_TRAVELLER_COMBAT: int = 0x005E5E
COLOR_DAMAGE_EMBED    : int = 0xA60000
COLOR_HEAL_EMBED      : int = 0x005E00

ATTR_FLAG_PATTERN     : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-attr|-a|--attribute)\s+([a-zA-Z]+)", RegularExpressions.IGNORECASE)

def CheckTravellerPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER)

class TravellerCombatCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[TravellerStateService.TravellerStateService] = None, EncounterManager: Typing.Optional[EncounterManagerService.EncounterManagerService] = None) -> None:
        self.BotInstance     : Commands.Bot                                       = BotInstance
        self.StateService    : TravellerStateService.TravellerStateService        = StateService if (StateService is not None) else TravellerStateService.TravellerStateService()
        self.EncounterManager: EncounterManagerService.EncounterManagerService    = EncounterManager if (EncounterManager is not None) else EncounterManagerService.EncounterManagerService()

    @Commands.command(name = "trav_damage", aliases = ["trav_dmg", "trav_wound"])
    @Commands.check(CheckTravellerPrefix)
    async def DamageCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Traveller character selected.")
            return

        WorkingText: str                 = ArgumentsText.strip()
        TargetAttr : Typing.Optional[str] = None
        AttrMatch                         = ATTR_FLAG_PATTERN.search(WorkingText)
        if (AttrMatch is not None):
            TargetAttr  = AttrMatch.group(1).strip()
            WorkingText = ATTR_FLAG_PATTERN.sub("", WorkingText).strip()

        try:
            DamageAmount: int = int(WorkingText.split()[0])

        except (ValueError, IndexError):
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}damage <amount> [-attr <STAT>]`")
            return

        DetailData     : dict           = ActiveRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.setdefault("Characteristics", {})
        CharName       : str            = str(ActiveRecord.get("Name", "Hero"))

        UpdatedCharacteristics, SummaryLog = self.StateService.ApplyPhysicalDamage(Characteristics, DamageAmount, TargetAttr)
        DetailData["Characteristics"]       = UpdatedCharacteristics

        DamageEmbed: Discord.Embed = Discord.Embed(title = f"{CharName} took {DamageAmount} Damage", description = SummaryLog, color = COLOR_DAMAGE_EMBED)
        DamageEmbed.set_footer(text = "MIS-Bot • Physical Characteristic Trauma")
        await Context.send(embed = DamageEmbed)

    @Commands.command(name = "trav_heal")
    @Commands.check(CheckTravellerPrefix)
    async def HealCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Traveller character selected.")
            return

        Tokens: list[str] = ArgumentsText.strip().split()
        if not Tokens:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}heal <amount> [STAT]`")
            return

        try:
            HealAmount: int = int(Tokens[0])

        except ValueError:
            await Context.send("Invalid healing amount.")
            return

        TargetStat: Typing.Optional[str] = Tokens[1] if (len(Tokens) > 1) else None
        DetailData     : dict           = ActiveRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.setdefault("Characteristics", {})
        MaxCharacteristics: dict[str, int] = DetailData.setdefault("MaxCharacteristics", dict(Characteristics))
        CharName       : str            = str(ActiveRecord.get("Name", "Hero"))

        UpdatedCharacteristics, SummaryLog = self.StateService.ApplyPhysicalHealing(Characteristics, MaxCharacteristics, HealAmount, TargetStat)
        DetailData["Characteristics"]       = UpdatedCharacteristics

        HealEmbed: Discord.Embed = Discord.Embed(title = f"{CharName} Healed {HealAmount} Points", description = SummaryLog, color = COLOR_HEAL_EMBED)
        HealEmbed.set_footer(text = "MIS-Bot • Physical Recovery")
        await Context.send(embed = HealEmbed)

    @Commands.command(name = "trav_stat")
    @Commands.check(CheckTravellerPrefix)
    async def StatCommand(self, Context: Commands.Context, StatName: str, ValueText: str) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Traveller character selected.")
            return

        FullStatName: str               = self.StateService.NormalizeCharacteristicName(StatName)
        DetailData  : dict              = ActiveRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.setdefault("Characteristics", {})
        CurrentVal  : int               = Characteristics.get(FullStatName, 7)
        CleanText   : str               = ValueText.strip()

        try:
            if CleanText.startswith("+"):
                NewVal = CurrentVal + int(CleanText[1:])

            elif CleanText.startswith("-"):
                NewVal = max(0, CurrentVal - int(CleanText[1:]))

            else:
                NewVal = max(0, int(CleanText))

            Characteristics[FullStatName] = NewVal
            NewDM: int                    = self.StateService.CalculateCharacteristicModifier(NewVal)
            await Context.send(f"**{ActiveRecord.get('Name')}** {FullStatName}: {CurrentVal} ➔ **{NewVal}** (DM: `{'+' if NewDM >= 0 else ''}{NewDM}`)")

        except ValueError:
            await Context.send("Invalid stat value. Example: `!stat STR +1` or `!stat END 10`")

    @Commands.group(name = "trav_init", invoke_without_command = True)
    @Commands.check(CheckTravellerPrefix)
    async def InitiativeGroup(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active in this channel.\nStart one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}init begin`.")
            return

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "begin", aliases = ["start"])
    @Commands.check(CheckTravellerPrefix)
    async def BeginEncounter(self, Context: Commands.Context) -> None:
        Existing: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Existing is not None):
            await Context.send("A combat encounter is already running in this channel.")
            return

        NewEncounter: EncounterManagerService.CombatEncounter   = self.EncounterManager.CreateEncounter(Context.channel.id, Context.guild.id if Context.guild else None)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(NewEncounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "end", aliases = ["stop"])
    @Commands.check(CheckTravellerPrefix)
    async def EndEncounter(self, Context: Commands.Context) -> None:
        Ended: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.EndEncounter(Context.channel.id)
        if (Ended is None):
            await Context.send("No active combat encounter to end.")
            return

        EndEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Ended)
        await Context.send(embed = EndEmbed)

    @InitiativeGroup.command(name = "join")
    @Commands.check(CheckTravellerPrefix)
    async def JoinEncounter(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat active. Start one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}init begin`.")
            return

        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Traveller character selected.")
            return

        DetailData     : dict           = ActiveRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.get("Characteristics", {})
        CharName       : str            = str(ActiveRecord.get("Name", "Traveller"))
        CharID         : str            = str(ActiveRecord.get("ID", str(UUIDLibrary.uuid4())))

        DEXScore: int                              = int(Characteristics.get("Dexterity", 7))
        DEXMod  : int                              = self.StateService.CalculateCharacteristicModifier(DEXScore)
        Roll    : TravellerStateService.TravellerRollOutcome = self.StateService.EvaluateRoll(Modifier = DEXMod)

        ENDScore: int = int(Characteristics.get("Endurance", 10))

        ExistingCombatant: Typing.Optional[EncounterManagerService.CombatantEntry] = Encounter.FindCombatant(CharName)
        if (ExistingCombatant is not None):
            ExistingCombatant.Initiative       = Roll.Total
            ExistingCombatant.CurrentHitPoints = ENDScore
            ExistingCombatant.MaxHitPoints     = ENDScore
            Encounter.SortCombatants()

        else:
            NewCombatant = EncounterManagerService.CombatantEntry(
                ID                  = CharID,
                Name                = CharName,
                Initiative          = Roll.Total,
                CurrentHitPoints    = ENDScore,
                MaxHitPoints        = ENDScore,
                ArmorClass          = 8,
                IsMonster           = False,
                ControllerDiscordID = str(Context.author.id),
                CharacterID         = CharID
            )
            Encounter.AddCombatant(NewCombatant)

        ConfirmEmbed: Discord.Embed = Discord.Embed(title = f"{CharName} Joined Combat", description = f"Initiative Roll: {Roll.BreakdownString}", color = COLOR_TRAVELLER_COMBAT)
        await Context.send(embed = ConfirmEmbed)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "add")
    @Commands.check(CheckTravellerPrefix)
    async def AddCombatant(self, Context: Commands.Context, Name: str, InitiativeScore: int, EndurancePoints: int = 10) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send("No combat encounter running in this channel.")
            return

        NewEntry = EncounterManagerService.CombatantEntry(
            ID               = str(UUIDLibrary.uuid4()),
            Name             = Name,
            Initiative       = InitiativeScore,
            CurrentHitPoints = EndurancePoints,
            MaxHitPoints     = EndurancePoints,
            ArmorClass       = 8,
            IsMonster        = True
        )
        Encounter.AddCombatant(NewEntry)
        await Context.send(f"Added **{Name}** (Init: {InitiativeScore}, END: {EndurancePoints}) to combat.")

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "next", aliases = ["n"])
    @Commands.check(CheckTravellerPrefix)
    async def NextTurn(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        ActiveCombatant, _ = Encounter.AdvanceTurn()
        StatusEmbed : Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)

        MentionText: str = ""
        if (ActiveCombatant is not None) and (ActiveCombatant.ControllerDiscordID is not None):
            MentionText = f"<@{ActiveCombatant.ControllerDiscordID}>, it's your turn!"

        await Context.send(content = MentionText or None, embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "prev", aliases = ["p"])
    @Commands.check(CheckTravellerPrefix)
    async def PreviousTurn(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Encounter.PreviousTurn()
        StatusEmbed : Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

async def setup(BotInstance: Commands.Bot) -> None:
    StateServiceInstance: Typing.Optional[TravellerStateService.TravellerStateService] = getattr(BotInstance, "TravellerStateService", None)
    EncounterMgrInstance: Typing.Optional[EncounterManagerService.EncounterManagerService] = getattr(BotInstance, "EncounterManager", None)
    await BotInstance.add_cog(TravellerCombatCommands(BotInstance, StateService = StateServiceInstance, EncounterManager = EncounterMgrInstance))
