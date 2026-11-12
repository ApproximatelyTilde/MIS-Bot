import re                                       as RegularExpressions
import typing                                   as Typing
import uuid                                     as UUIDLibrary
import discord                                  as Discord
import discord.ext.commands                     as Commands
import Configuration.Config                     as Config
import Services.DebugService                    as Debug
import Services.DiceService                     as DiceService
import Services.PlatformClient                  as PlatformClient
import Services.CharacterStateService           as CharacterStateService
import Services.EncounterManagerService         as EncounterManagerService
import Services.Automation.AutomationEngine      as AutomationEngine
import Services.Automation.AutomationModels      as AutomationModels
import Services.Automation.EffectContext         as EffectContext
import Services.Automation.MonsterActionCompiler as MonsterActionCompiler
import Services.Draconic.API.ArgumentParser      as ArgumentParser
import Application.Components.InitiativeControls as InitiativeControls

COLOR_INITIATIVE_EMBED: int = 0x0030A6
COLOR_ERROR_EMBED     : int = 0xA60000

COUNT_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-n|--count)\s+(\d+)", RegularExpressions.IGNORECASE)

def CheckDNDPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND)

class InitiativeCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterStateService.CharacterStateService] = None, EncounterManager: Typing.Optional[EncounterManagerService.EncounterManagerService] = None) -> None:
        self.BotInstance     : Commands.Bot                                       = BotInstance
        self.StateService    : CharacterStateService.CharacterStateService        = StateService if (StateService is not None) else CharacterStateService.CharacterStateService()
        self.EncounterManager: EncounterManagerService.EncounterManagerService    = EncounterManager if (EncounterManager is not None) else EncounterManagerService.EncounterManagerService()
        self.DiceRoller      : DiceService.DiceRollerService                     = DiceService.DiceRollerService()
        self.PlatformClient  : PlatformClient.MISPlatformClient                   = self.StateService.PlatformClient

    @Commands.group(name = "init", invoke_without_command = True)
    @Commands.check(CheckDNDPrefix)
    async def InitiativeGroup(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            NoEncounterEmbed: Discord.Embed = Discord.Embed(title = "No Active Encounter", description = f"No combat encounter is running in this channel.\n\nStart one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}init begin`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoEncounterEmbed)
            return

        StatusEmbed: Discord.Embed                    = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "begin", aliases = ["start"])
    @Commands.check(CheckDNDPrefix)
    async def BeginEncounter(self, Context: Commands.Context) -> None:
        ExistingEncounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (ExistingEncounter is not None):
            await Context.send("A combat encounter is already active in this channel.")
            return

        NewEncounter: EncounterManagerService.CombatEncounter   = self.EncounterManager.CreateEncounter(Context.channel.id, Context.guild.id if Context.guild else None)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(NewEncounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "end", aliases = ["stop"])
    @Commands.check(CheckDNDPrefix)
    async def EndEncounter(self, Context: Commands.Context) -> None:
        EndedEncounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.EndEncounter(Context.channel.id)
        if (EndedEncounter is None):
            await Context.send("No active combat encounter to end in this channel.")
            return

        EndEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(EndedEncounter)
        await Context.send(embed = EndEmbed)

    @InitiativeGroup.command(name = "join")
    @Commands.check(CheckDNDPrefix)
    async def JoinEncounter(self, Context: Commands.Context, *, OptionalFlags: str = "") -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active. Start one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}init begin`.")
            return

        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active character selected.")
            return

        DetailData : dict = ActiveRecord.get("DetailData", {})
        CharName   : str  = str(ActiveRecord.get("Name", "Hero"))
        CharID     : str  = str(ActiveRecord.get("ID", str(UUIDLibrary.uuid4())))
        InitBonus  : int  = int(DetailData.get("InitiativeBonus", 0))

        Formula    : str                     = f"1d20{'+' if InitBonus >= 0 else ''}{InitBonus} {OptionalFlags}".strip()
        RollOutcome: DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(Formula)

        HitPointsData: dict = DetailData.get("HitPoints", {})
        CurrentHP    : int  = int(HitPointsData.get("CurrentHitPoints", 10))
        MaxHP        : int  = int(HitPointsData.get("MaxHitPoints", 10))
        TempHP       : int  = int(HitPointsData.get("TemporaryHitPoints", 0))
        ArmorClass   : int  = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", 10))

        ExistingCombatant: Typing.Optional[EncounterManagerService.CombatantEntry] = Encounter.FindCombatant(CharName)
        if (ExistingCombatant is not None):
            ExistingCombatant.Initiative       = RollOutcome.Total
            ExistingCombatant.CurrentHitPoints = CurrentHP
            ExistingCombatant.MaxHitPoints     = MaxHP
            ExistingCombatant.ArmorClass       = ArmorClass
            Encounter.SortCombatants()

        else:
            NewCombatant = EncounterManagerService.CombatantEntry(
                ID                  = CharID,
                Name                = CharName,
                Initiative          = RollOutcome.Total,
                CurrentHitPoints    = CurrentHP,
                MaxHitPoints        = MaxHP,
                TemporaryHitPoints  = TempHP,
                ArmorClass          = ArmorClass,
                IsMonster           = False,
                ControllerDiscordID = str(Context.author.id),
                CharacterID         = CharID
            )
            Encounter.AddCombatant(NewCombatant)

        ConfirmEmbed: Discord.Embed = Discord.Embed(title = f"{CharName} Joined Combat", description = f"Initiative Roll: {RollOutcome.Breakdown} = **{RollOutcome.Total}**", color = COLOR_INITIATIVE_EMBED)
        await Context.send(embed = ConfirmEmbed)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "add")
    @Commands.check(CheckDNDPrefix)
    async def AddMonsterToEncounter(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active. Start one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}init begin`.")
            return

        CountNumber : int = 1
        CleanedText : str = ArgumentsText.strip()
        CountMatch        = COUNT_PATTERN.search(CleanedText)
        if (CountMatch is not None):
            CountNumber = max(1, min(int(CountMatch.group(1)), 20))
            CleanedText = COUNT_PATTERN.sub("", CleanedText).strip()

        MonsterRecord: Typing.Optional[dict] = await self.PlatformClient.FetchMonsterDetails(CleanedText)
        if (MonsterRecord is None):
            await Context.send(f"Could not find monster `{CleanedText}` in 5eTools bestiary.")
            return

        MonsterName : str            = str(MonsterRecord.get("name", CleanedText))
        ACData      : list           = MonsterRecord.get("ac", [10])
        ArmorClass  : int            = int(ACData[0].get("ac") if isinstance(ACData[0], dict) else ACData[0]) if ACData else 10
        HPData      : dict           = MonsterRecord.get("hp", {})
        AverageHP   : int            = int(HPData.get("average", 10))
        DEXScore    : int            = int(MonsterRecord.get("dex", 10))
        DEXMod      : int            = (DEXScore - 10) // 2

        AddedCombatants: list[str] = []
        for MonsterIndex in range(1, CountNumber + 1):
            DisplayName: str                 = f"{MonsterName} {MonsterIndex}" if (CountNumber > 1) else MonsterName
            InitRoll   : DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(f"1d20{'+' if DEXMod >= 0 else ''}{DEXMod}")
            NewMonster = EncounterManagerService.CombatantEntry(
                ID                 = str(UUIDLibrary.uuid4()),
                Name               = DisplayName,
                Initiative         = InitRoll.Total,
                CurrentHitPoints   = AverageHP,
                MaxHitPoints       = AverageHP,
                ArmorClass         = ArmorClass,
                IsMonster          = True,
                MonsterData        = MonsterRecord
            )
            Encounter.AddCombatant(NewMonster)
            AddedCombatants.append(f"**{DisplayName}** (Init: {InitRoll.Total})")

        ConfirmEmbed: Discord.Embed = Discord.Embed(title = f"Monsters Added to Combat", description = "\n".join(AddedCombatants), color = COLOR_INITIATIVE_EMBED)
        await Context.send(embed = ConfirmEmbed)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "next", aliases = ["n"])
    @Commands.check(CheckDNDPrefix)
    async def NextTurn(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        ActiveCombatant, RoundNumber = Encounter.AdvanceTurn()
        StatusEmbed : Discord.Embed  = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)

        MentionText: str = ""
        if (ActiveCombatant is not None) and (ActiveCombatant.ControllerDiscordID is not None):
            MentionText = f"<@{ActiveCombatant.ControllerDiscordID}>, it's your turn!"

        await Context.send(content = MentionText or None, embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "prev", aliases = ["p"])
    @Commands.check(CheckDNDPrefix)
    async def PreviousTurn(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Encounter.PreviousTurn()
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "hp")
    @Commands.check(CheckDNDPrefix)
    async def CombatantHitPoints(self, Context: Commands.Context, TargetIdentifier: str, AmountText: str) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManagerService.CombatantEntry] = Encounter.FindCombatant(TargetIdentifier)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetIdentifier}`.")
            return

        try:
            OldHP: int = Target.CurrentHitPoints
            if AmountText.startswith("+"):
                DeltaHP: int = int(AmountText[1:])
                Target.CurrentHitPoints = min(Target.MaxHitPoints, Target.CurrentHitPoints + DeltaHP)

            elif AmountText.startswith("-"):
                DeltaHP = int(AmountText[1:])
                Target.CurrentHitPoints = max(0, Target.CurrentHitPoints - DeltaHP)

            else:
                Target.CurrentHitPoints = max(0, min(Target.MaxHitPoints, int(AmountText)))

            await Context.send(f"**{Target.Name}** HP: {OldHP} ➔ **{Target.CurrentHitPoints}/{Target.MaxHitPoints}**")

        except ValueError:
            await Context.send("Invalid HP amount. Example: `&init hp Goblin1 -5`")

    @InitiativeGroup.command(name = "opt", aliases = ["c", "condition"])
    @Commands.check(CheckDNDPrefix)
    async def CombatantCondition(self, Context: Commands.Context, TargetIdentifier: str, *, ConditionName: str) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManagerService.CombatantEntry] = Encounter.FindCombatant(TargetIdentifier)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetIdentifier}`.")
            return

        NormalizedCondition: str = ConditionName.strip().title()
        if NormalizedCondition in Target.Conditions:
            Target.Conditions.remove(NormalizedCondition)
            await Context.send(f"Removed condition **{NormalizedCondition}** from **{Target.Name}**.")

        else:
            Target.Conditions.append(NormalizedCondition)
            await Context.send(f"Applied condition **{NormalizedCondition}** to **{Target.Name}**.")

    @InitiativeGroup.command(name = "remove", aliases = ["rem"])
    @Commands.check(CheckDNDPrefix)
    async def RemoveCombatant(self, Context: Commands.Context, *, TargetIdentifier: str) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Removed: Typing.Optional[EncounterManagerService.CombatantEntry] = Encounter.RemoveCombatant(TargetIdentifier)
        if (Removed is not None):
            await Context.send(f"Removed **{Removed.Name}** from combat.")

        else:
            await Context.send(f"Could not find combatant `{TargetIdentifier}`.")

    @InitiativeGroup.command(name = "attack", aliases = ["a"])
    @Commands.check(CheckDNDPrefix)
    async def MonsterAttackCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active in this channel. Start one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}init begin`.")
            return

        ParsedArgs    : ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalList: list[str]                      = list(ParsedArgs.PositionalArguments)

        if not PositionalList:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}init a <Monster> <Attack> [-t <Target>] [flags]`")
            return

        MonsterQuery: str = PositionalList[0]
        ActionQuery : str = " ".join(PositionalList[1:]) if (len(PositionalList) > 1) else ""

        AttackerCombatant: Typing.Optional[EncounterManagerService.CombatantEntry] = Encounter.FindCombatant(MonsterQuery)
        if (AttackerCombatant is None) and (Encounter.ActiveCombatantIndex is not None) and (Encounter.ActiveCombatantIndex < len(Encounter.Combatants)):
            ActiveCombatant = Encounter.Combatants[Encounter.ActiveCombatantIndex]
            if (ActionQuery == ""):
                AttackerCombatant = ActiveCombatant
                ActionQuery       = MonsterQuery

        if (AttackerCombatant is None):
            await Context.send(f"Could not find combatant `{MonsterQuery}` in the active encounter.")
            return

        if not ActionQuery:
            await Context.send(f"Please specify an action for **{AttackerCombatant.Name}** to use.")
            return

        ActionDoc: Typing.Optional[AutomationModels.ActionDocument] = None

        if AttackerCombatant.IsMonster:
            MonsterData = AttackerCombatant.MonsterData
            if (MonsterData is None):
                MonsterData = await self.PlatformClient.FetchMonsterDetails(AttackerCombatant.Name)
                if (MonsterData is not None):
                    AttackerCombatant.MonsterData = MonsterData

            if (MonsterData is not None):
                Compiler  = MonsterActionCompiler.MonsterActionCompiler()
                ActionDoc = Compiler.FindAndCompileMonsterAction(MonsterData, ActionQuery)

        elif (AttackerCombatant.CharacterID is not None):
            try:
                PlatformActions = await self.PlatformClient.FetchCharacterActions(AttackerCombatant.CharacterID)
                for ActionDict in PlatformActions:
                    CandidateName = str(ActionDict.get("Name", "")).lower()
                    if (ActionQuery.lower() == CandidateName) or (ActionQuery.lower() in CandidateName):
                        ActionDoc = AutomationModels.ActionDocument.model_validate(ActionDict)
                        break

            except Exception:
                pass

        if (ActionDoc is None):
            await Context.send(f"Could not find action `{ActionQuery}` for **{AttackerCombatant.Name}**.")
            return

        TargetEntities : list[EncounterManagerService.CombatantEntry] = []
        TargetNamesList: list[str]                                    = ParsedArgs.get("t")
        for TName in TargetNamesList:
            MatchedTarget = Encounter.FindCombatant(TName)
            if (MatchedTarget is not None):
                TargetEntities.append(MatchedTarget)

        AutoContext = EffectContext.AutomationContext(
            Caster    = AttackerCombatant,
            Targets   = TargetEntities,
            Encounter = Encounter,
            Arguments = ParsedArgs
        )

        Engine = AutomationEngine.AutomationEngine(self.DiceRoller)
        Result = Engine.RunAutomation(ActionDoc, AutoContext)

        DescriptionLines: list[str] = []
        if ActionDoc.Phrase:
            DescriptionLines.append(f"*{ActionDoc.Phrase}*\n")

        for TargetOutcome in Result.TargetOutcomes:
            TargetHeader: str = f"🎯 **Target: {TargetOutcome.TargetName}**"
            DescriptionLines.append(TargetHeader)

            if (TargetOutcome.HitStatus is not None):
                AttackSummary: str = f"• **Attack:** {TargetOutcome.HitStatus} ({TargetOutcome.AttackTotal} vs AC {TargetOutcome.TargetArmorClass})"
                DescriptionLines.append(AttackSummary)

            if (TargetOutcome.SaveResultTotal is not None):
                SaveStatus : str = "Passed" if TargetOutcome.SaveSucceeded else "Failed"
                SaveSummary: str = f"• **Save:** {SaveStatus} ({TargetOutcome.SaveResultTotal} vs DC {TargetOutcome.SaveTargetDC})"
                DescriptionLines.append(SaveSummary)

            if (TargetOutcome.DamageDealt > 0):
                DamageTypeText: str = f" {TargetOutcome.DamageType}" if TargetOutcome.DamageType else ""
                DescriptionLines.append(f"• **Damage:** {TargetOutcome.DamageDealt}{DamageTypeText}")

            if TargetOutcome.ConditionsApplied:
                CondsText = ", ".join(TargetOutcome.ConditionsApplied)
                DescriptionLines.append(f"• **Conditions Applied:** {CondsText}")

            if TargetOutcome.EffectsAttached:
                EffectsText = ", ".join(TargetOutcome.EffectsAttached)
                DescriptionLines.append(f"• **Effects Applied:** {EffectsText}")

            for NarrativeMsg in TargetOutcome.NarrativeMessages:
                DescriptionLines.append(f"• {NarrativeMsg}")

            TargetEntity = Encounter.FindCombatant(TargetOutcome.TargetName)
            if (TargetEntity is not None):
                DescriptionLines.append(f"• **HP:** {TargetEntity.CurrentHitPoints}/{TargetEntity.MaxHitPoints}")

            DescriptionLines.append("")

        for GlobalMsg in Result.GlobalNarrative:
            DescriptionLines.append(f"📢 {GlobalMsg}")

        ResultEmbed = Discord.Embed(
            title       = f"{AttackerCombatant.Name}: {ActionDoc.Name}",
            description = "\n".join(DescriptionLines).strip() or "Action resolved.",
            color       = COLOR_INITIATIVE_EMBED
        )
        await Context.send(embed = ResultEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(InitiativeCommands(BotInstance))

