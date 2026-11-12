import re                                                 as RegularExpressions
import typing                                             as Typing
import uuid                                               as UUIDLibrary
import discord                                            as Discord
import discord.ext.commands                               as Commands
import Runtime.Configuration.Config                       as Config
import Runtime.Services.DebugService                      as Debug
import Runtime.Services.DiceService                       as Dice
import Runtime.Services.PlatformClient                    as PlatformClient
import Runtime.Services.CharacterStateService             as CharacterState
import Runtime.Services.EncounterManagerService           as EncounterManager
import Runtime.Services.Compendium.SourceFilterService    as SourceFilter
import Runtime.Services.Automation.AutomationEngine       as AutomationEngine
import Runtime.Services.Automation.AutomationModels       as AutomationModels
import Runtime.Services.Automation.EffectContext          as EffectContext
import Runtime.Services.Automation.MonsterActionCompiler  as MonsterActionCompiler
import Runtime.Services.Automation.Effects.IEffectHandler as IEffectHandler
import Runtime.Services.Draconic.API.ArgumentParser       as ArgumentParser
import Runtime.Services.TargetResolverService             as TargetResolver
import Runtime.Application.Components.InitiativeControls  as InitiativeControls
import Runtime.Decorators.AuthorizationDecorators         as AuthorizationDecorators

COLOR_INITIATIVE_EMBED: int = 0x0030A6
COLOR_ERROR_EMBED     : int = 0xA60000

COUNT_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-n|--count)\s+(\d+)", RegularExpressions.IGNORECASE)

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance: Typing.Any = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)

def IsDungeonMasterOrAdmin(Context: Commands.Context) -> bool:
    return AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)

class InitiativeCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterState.CharacterStateService] = None, EncounterManagerInstance: Typing.Optional[EncounterManager.EncounterManagerService] = None, EncounterManager: Typing.Optional[EncounterManager.EncounterManagerService] = None, TargetResolverInstance: Typing.Optional[TargetResolver.TargetResolverService] = None) -> None:
        self.BotInstance     : Commands.Bot                                       = BotInstance
        self.StateService    : CharacterState.CharacterStateService               = StateService if (StateService is not None) else (getattr(BotInstance, "CharacterStateService", None) or CharacterState.CharacterStateService())
        self.PlatformClient  : PlatformClient.TallyPlatformClient                 = self.StateService.PlatformClient
        ResolvedManager      : Typing.Optional[EncounterManager.EncounterManagerService] = EncounterManagerInstance if (EncounterManagerInstance is not None) else (EncounterManager or getattr(BotInstance, "EncounterManager", None))
        self.EncounterManager: EncounterManager.EncounterManagerService     = ResolvedManager if (ResolvedManager is not None) else EncounterManager.EncounterManagerService(PlatformClientInstance = self.PlatformClient)
        if (self.EncounterManager.PlatformClient is None):
            self.EncounterManager.PlatformClient = self.PlatformClient

        self.TargetResolver  : TargetResolver.TargetResolverService               = TargetResolverInstance if (TargetResolverInstance is not None) else (getattr(BotInstance, "TargetResolverService", None) or TargetResolver.TargetResolverService(CharacterStateInstance = self.StateService))
        self.DiceRoller      : Dice.DiceRollerService                             = Dice.DiceRollerService()
        self.SourceFilter    : SourceFilter.SourceFilterService                   = SourceFilter.SourceFilterService()
        self.EffectHandler   : IEffectHandler.IEffectHandler                      = IEffectHandler.IEffectHandler(self.DiceRoller)

    async def AddMonstersInternal(self, Context: Commands.Context, ArgumentsText: str, UseHPVariance: bool = False) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active. Start one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}init begin`.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        CountNumber    : int                            = 1
        CountArg       : Typing.Optional[str]           = ParsedArguments.last("n") or ParsedArguments.last("count")
        if (CountArg is not None):
            if CountArg.strip().isdigit():
                CountNumber = max(1, min(int(CountArg.strip()), 50))

        elif (COUNT_PATTERN.search(ArgumentsText) is not None):
            CountMatch: Typing.Any = COUNT_PATTERN.search(ArgumentsText)
            if (CountMatch is not None):
                CountNumber = max(1, min(int(CountMatch.group(1)), 50))

        PositionalList: list[str] = list(ParsedArguments.PositionalArguments)
        CleanedQuery  : str       = " ".join(PositionalList).strip()
        if (not CleanedQuery) and (COUNT_PATTERN.search(ArgumentsText) is not None):
            CleanedQuery = COUNT_PATTERN.sub("", ArgumentsText).strip()

        if not CleanedQuery:
            await Context.send("Please specify a monster or combatant name to add.")
            return

        NameOverride : Typing.Optional[str] = ParsedArguments.last("name")
        HPArg        : Typing.Optional[str] = ParsedArguments.last("hp")
        MaxHPArg     : Typing.Optional[str] = ParsedArguments.last("maxhp")
        ACArg        : Typing.Optional[str] = ParsedArguments.last("ac")
        ControllerArg: Typing.Optional[str] = ParsedArguments.last("controller")
        PassiveArg   : Typing.Optional[str] = ParsedArguments.last("p")
        BonusArg     : Typing.Optional[str] = ParsedArguments.last("b")
        GroupArg     : Typing.Optional[str] = ParsedArguments.last("group")
        IsHidden     : bool                 = ("h" in ParsedArguments.OptionsDictionary)
        NoteText     : Typing.Optional[str] = ParsedArguments.last("note")
        ThumbURL     : Typing.Optional[str] = ParsedArguments.last("thumb")

        ControllerID: Typing.Optional[str] = None
        if (ControllerArg is not None):
            ControllerID = ControllerArg.strip().lstrip("<@!").rstrip(">")

        MonsterRecord    : Typing.Optional[dict] = await self.PlatformClient.FetchMonsterDetails(CleanedQuery)
        MonsterName      : str                   = NameOverride if (NameOverride is not None) else CleanedQuery
        ArmorClass       : int                   = 10
        AverageHP        : int                   = 10
        HPFormula        : str                   = ""
        DexterityModifier: int                   = 0
        MonsterSource    : str                   = "Custom"
        SourceTag        : str                   = "Custom"
        PassivePerception: int                   = 10

        if (MonsterRecord is not None):
            MonsterName             = NameOverride if (NameOverride is not None) else str(MonsterRecord.get("name", CleanedQuery))
            ACData           : list = MonsterRecord.get("ac", [10])
            ArmorClass              = int(ACData[0].get("ac") if (isinstance(ACData[0], dict)) else ACData[0]) if (ACData) else 10
            HPData           : dict = MonsterRecord.get("hp", {})
            AverageHP               = int(HPData.get("average", 10))
            HPFormula               = str(HPData.get("formula", ""))
            DEXScore         : int  = int(MonsterRecord.get("dex", 10))
            DexterityModifier       = (DEXScore - 10) // 2
            MonsterSource           = str(MonsterRecord.get("source", "MM"))
            SourceTag               = "2024" if (self.SourceFilter.IsSource2024(MonsterSource)) else f"Legacy ({MonsterSource})"
            PassivePerception       = int(MonsterRecord.get("passive", 10 + DexterityModifier))

        if (ACArg is not None):
            if ACArg.strip().isdigit():
                ArmorClass = int(ACArg.strip())

        if (PassiveArg is not None):
            if PassiveArg.strip().isdigit():
                PassivePerception = int(PassiveArg.strip())

        if (BonusArg is not None):
            try:
                DexterityModifier += int(BonusArg)

            except ValueError:
                BonusRoll: Typing.Any = self.DiceRoller.EvaluateRoll(BonusArg)
                DexterityModifier   += BonusRoll.Total

        ExistingBaseMatches: int = 0
        for ExistingCandidate in Encounter.Combatants:
            if ExistingCandidate.Name.startswith(MonsterName):
                ExistingBaseMatches += 1

        GroupSharedInitiative: Typing.Optional[int] = None
        if (GroupArg is not None):
            for GroupCandidate in Encounter.Combatants:
                if (GroupCandidate.GroupName == GroupArg):
                    GroupSharedInitiative = GroupCandidate.Initiative
                    break

        AddedCombatants: list[str] = []
        for MonsterOffset in range(CountNumber):
            if (CountNumber > 1) or (ExistingBaseMatches > 0):
                SequentialIndex: int = ExistingBaseMatches + MonsterOffset + 1
                DisplayName    : str = f"{MonsterName} {SequentialIndex}"

            else:
                DisplayName = MonsterName

            CombatantHP: int = AverageHP
            if (HPArg is not None):
                try:
                    CombatantHP = int(HPArg)

                except ValueError:
                    RolledHP   : Typing.Any = self.DiceRoller.EvaluateRoll(HPArg)
                    CombatantHP             = max(1, RolledHP.Total)

            elif UseHPVariance and HPFormula:
                RolledHP    = self.DiceRoller.EvaluateRoll(HPFormula)
                CombatantHP = max(1, RolledHP.Total)

            CombatantMaxHP: int = int(MaxHPArg) if (MaxHPArg is not None and MaxHPArg.isdigit()) else CombatantHP

            if (GroupSharedInitiative is not None):
                InitTotal: int = GroupSharedInitiative

            else:
                InitRoll : Typing.Any = self.DiceRoller.EvaluateRoll(f"1d20{"+" if (DexterityModifier >= 0) else ""}{DexterityModifier}")
                InitTotal             = InitRoll.Total
                if (GroupArg is not None):
                    GroupSharedInitiative = InitTotal

            NewMonster: Typing.Any = EncounterManager.CombatantEntry(ID = str(UUIDLibrary.uuid4()), Name = DisplayName, Initiative = InitTotal, CurrentHitPoints = CombatantHP, MaxHitPoints = CombatantMaxHP, TemporaryHitPoints = 0, ArmorClass = ArmorClass, Conditions = [], EntityType = "Other", IsMonster = True, ControllerDiscordID = ControllerID, CharacterID = None, MonsterData = MonsterRecord, PassivePerception = PassivePerception, InitiativeBonus = DexterityModifier, GroupName = GroupArg, IsHidden = IsHidden, Note = NoteText, ThumbnailURL = ThumbURL)
            Encounter.AddCombatant(NewMonster)
            AddedCombatants.append(f"**{DisplayName}** (Init: {InitTotal}, Source: {SourceTag})")

        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        HeadingText : str           = f"Monsters Added to Combat: {MonsterName}" if (CountNumber == 1) else f"Monsters Added to Combat: {CountNumber}x {MonsterName}"
        ConfirmEmbed: Discord.Embed = Discord.Embed(title = HeadingText, description = "\n".join(AddedCombatants), color = COLOR_INITIATIVE_EMBED)
        ConfirmEmbed.set_footer(text = f"5e.tools Bestiary • Source: {MonsterSource}")
        await Context.send(embed = ConfirmEmbed)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDungeonMasterOrAdmin(Context))
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @Commands.group(name = "init", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def InitiativeGroup(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            NoEncounterEmbed: Discord.Embed = Discord.Embed(title = "No Active Encounter", description = f"No combat encounter is running in this channel.\n\nStart one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}init begin`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoEncounterEmbed)
            return

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDungeonMasterOrAdmin(Context))
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "status", aliases = ["list"])
    @Commands.check(CheckDND5EPrefix)
    async def ShowEncounterStatus(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            NoEncounterEmbed: Discord.Embed = Discord.Embed(title = "No Active Encounter", description = f"No combat encounter is running in this channel.\n\nStart one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}init begin`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoEncounterEmbed)
            return

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDungeonMasterOrAdmin(Context))
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "begin", aliases = ["start"])
    @Commands.check(CheckDND5EPrefix)
    async def BeginEncounter(self, Context: Commands.Context, *, ArgumentsText: str = "") -> None:
        ExistingEncounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (ExistingEncounter is not None):
            await Context.send("A combat encounter is already active in this channel.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalLow  : list[str]                      = [P.strip().lower() for P in ParsedArguments.PositionalArguments]
        InitiativeMode : str                            = "Popcorn" if ("popcorn" in PositionalLow) else "Standard"

        RoundNumber: int                  = 1
        RoundArg   : Typing.Optional[str] = ParsedArguments.last("round")
        if (RoundArg is not None) and RoundArg.isdigit():
            RoundNumber = max(1, int(RoundArg))

        NewEncounter            : EncounterManager.CombatEncounter = await self.EncounterManager.CreateEncounterAsync(Context.channel.id, Context.guild.id if (Context.guild) else None, GameSystem = "DND5E", InitiativeMode = InitiativeMode)
        NewEncounter.RoundNumber                                   = RoundNumber
        if (RoundNumber > 1):
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(NewEncounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDungeonMasterOrAdmin(Context), CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "end", aliases = ["stop"])
    @Commands.check(CheckDND5EPrefix)
    async def EndEncounter(self, Context: Commands.Context) -> None:
        if not IsDungeonMasterOrAdmin(Context):
            await Context.send("You lack permission to end this combat encounter. Requires Dungeon Master or Macro Master role.")
            return

        EndedEncounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.EndEncounterAsync(Context.channel.id)
        if (EndedEncounter is None):
            await Context.send("No active combat encounter to end in this channel.")
            return

        EndEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(EndedEncounter)
        await Context.send(embed = EndEmbed)

    @InitiativeGroup.command(name = "join")
    @Commands.check(CheckDND5EPrefix)
    async def JoinEncounter(self, Context: Commands.Context, *, OptionalFlags: str = "") -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active. Start one with `{Context.prefix}init begin`.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(OptionalFlags)
        CompanionName  : Typing.Optional[str]           = ParsedArguments.last("comp") or ParsedArguments.last("companion") or ParsedArguments.last("vehicle")
        if (CompanionName is not None):
            ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, CompanionName)
            if (ActiveRecord is None):
                await Context.send(f"Could not find companion or vehicle matching `{CompanionName}`.")
                return

        else:
            ActiveRecord = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
            if (ActiveRecord is None):
                await Context.send("You do not have an active character selected.")
                return

        DetailData       : dict                 = ActiveRecord.get("DetailData", {})
        EntityType       : str                  = str(ActiveRecord.get("EntityType", "Character"))
        ParentCharacterID: Typing.Optional[str] = ActiveRecord.get("ParentCharacterID")
        DefaultName      : str                  = str(ActiveRecord.get("Name", "Hero"))
        CharacterName    : str                  = str(ParsedArguments.last("name", DefaultName))
        CharacterID      : str                  = str(ActiveRecord.get("ID", str(UUIDLibrary.uuid4())))
        InitBonus        : int                  = int(DetailData.get("InitiativeBonus", 0))

        BonusArg: Typing.Optional[str] = ParsedArguments.last("b")
        if (BonusArg is not None):
            try:
                InitBonus += int(BonusArg)

            except ValueError:
                BonusRoll: Typing.Any = self.DiceRoller.EvaluateRoll(BonusArg)
                InitBonus += BonusRoll.Total

        AdvantageState: int              = ParsedArguments.adv()
        DicePart      : str              = "2d20kh1" if (AdvantageState == 1) else ("2d20kl1" if (AdvantageState == -1) else "1d20")
        Formula       : str              = f"{DicePart}{"+" if (InitBonus >= 0) else ""}{InitBonus}"
        RollOutcome   : Dice.RollOutcome = self.DiceRoller.EvaluateRoll(Formula)

        HitPointsData    : dict = DetailData.get("HitPoints", {})
        CurrentHP        : int  = int(HitPointsData.get("CurrentHitPoints", 10))
        MaxHP            : int  = int(HitPointsData.get("MaxHitPoints", 10))
        TempHP           : int  = int(HitPointsData.get("TemporaryHitPoints", 0))
        ArmorClass       : int  = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", 10))
        PassivePerception: int  = int(DetailData.get("PassivePerception", 10))

        HPArg: Typing.Optional[str] = ParsedArguments.last("hp")
        if (HPArg is not None):
            try:
                CurrentHP = int(HPArg)
                MaxHP     = max(MaxHP, CurrentHP)

            except ValueError:
                HPRoll   : Typing.Any = self.DiceRoller.EvaluateRoll(HPArg)
                CurrentHP             = max(1, HPRoll.Total)
                MaxHP                 = max(MaxHP, CurrentHP)

        MaxHPArg: Typing.Optional[str] = ParsedArguments.last("maxhp")
        if (MaxHPArg is not None):
            if MaxHPArg.strip().isdigit():
                MaxHP = int(MaxHPArg.strip())

        ACArg: Typing.Optional[str] = ParsedArguments.last("ac")
        if (ACArg is not None):
            if ACArg.strip().isdigit():
                ArmorClass = int(ACArg.strip())

        PassiveArg: Typing.Optional[str] = ParsedArguments.last("p")
        if (PassiveArg is not None):
            if PassiveArg.strip().isdigit():
                PassivePerception = int(PassiveArg.strip())

        ControllerID : str                  = str(Context.author.id)
        ControllerArg: Typing.Optional[str] = ParsedArguments.last("controller")
        if (ControllerArg is not None):
            CleanController: str = ControllerArg.strip().lstrip("<@!").rstrip(">")
            if CleanController:
                ControllerID = CleanController

        GroupName : Typing.Optional[str] = ParsedArguments.last("group")
        IsHidden  : bool                 = ("h" in ParsedArguments.OptionsDictionary)
        NoteText  : Typing.Optional[str] = ParsedArguments.last("note")
        ThumbURL  : Typing.Optional[str] = ParsedArguments.last("thumb")
        RerollFlag: bool                 = ("reroll" in ParsedArguments.OptionsDictionary)

        InitiativeTotal: int = RollOutcome.Total
        if (GroupName is not None):
            for GroupCandidate in Encounter.Combatants:
                if (GroupCandidate.GroupName == GroupName):
                    InitiativeTotal = GroupCandidate.Initiative
                    break

        ExistingCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(CharacterName)
        if (ExistingCombatant is not None):
            if RerollFlag:
                ExistingCombatant.Initiative = InitiativeTotal

            ExistingCombatant.CurrentHitPoints    = CurrentHP
            ExistingCombatant.MaxHitPoints        = MaxHP
            ExistingCombatant.ArmorClass          = ArmorClass
            ExistingCombatant.PassivePerception   = PassivePerception
            ExistingCombatant.ControllerDiscordID = ControllerID
            if (GroupName is not None):
                ExistingCombatant.GroupName = GroupName

            if IsHidden:
                ExistingCombatant.IsHidden = True

            if (NoteText is not None):
                ExistingCombatant.Note = NoteText

            if (ThumbURL is not None):
                ExistingCombatant.ThumbnailURL = ThumbURL

            Encounter.SortCombatants()

        else:
            NewCombatant: Typing.Any = EncounterManager.CombatantEntry(ID = CharacterID, Name = CharacterName, Initiative = InitiativeTotal, CurrentHitPoints = CurrentHP, MaxHitPoints = MaxHP, TemporaryHitPoints = TempHP, ArmorClass = ArmorClass, EntityType = EntityType, ParentCharacterID = ParentCharacterID, IsMonster = False, ControllerDiscordID = ControllerID, CharacterID = CharacterID, PassivePerception = PassivePerception, InitiativeBonus = InitBonus, GroupName = GroupName, IsHidden = IsHidden, Note = NoteText, ThumbnailURL = ThumbURL)
            Encounter.AddCombatant(NewCombatant)

        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        ConfirmEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName} Joined Combat", description = f"Initiative Roll: {RollOutcome.Breakdown} = **{RollOutcome.Total}**", color = COLOR_INITIATIVE_EMBED)
        await Context.send(embed = ConfirmEmbed)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDungeonMasterOrAdmin(Context))
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "add")
    @Commands.check(CheckDND5EPrefix)
    async def AddMonsterToEncounter(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        await self.AddMonstersInternal(Context = Context, ArgumentsText = ArgumentsText, UseHPVariance = False)

    @InitiativeGroup.command(name = "madd")
    @Commands.check(CheckDND5EPrefix)
    async def MonsterAddWithVariance(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        await self.AddMonstersInternal(Context = Context, ArgumentsText = ArgumentsText, UseHPVariance = True)

    @InitiativeGroup.command(name = "addother", aliases = ["other"])
    @Commands.check(CheckDND5EPrefix)
    async def AddOtherEntityCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        if not IsDungeonMasterOrAdmin(Context):
            await Context.send("You lack permission to add Platform Other entities to combat. Requires Dungeon Master or Macro Master role.")
            return

        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active. Start one with `{Context.prefix}init begin`.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        QueryName      : str                            = " ".join(ParsedArguments.PositionalArguments).strip()
        if not QueryName:
            await Context.send(f"Usage: `{Context.prefix}init addother <Name> [-name Override] [-h] [-controller @User]`")
            return

        OtherEntities: list[dict[str, Typing.Any]]            = await self.PlatformClient.FetchCharactersByEntityType("Other", GameSystem = "DND5E")
        QueryLower   : str                                    = QueryName.lower()
        MatchedOther : Typing.Optional[dict[str, Typing.Any]] = None
        for Candidate in OtherEntities:
            if (str(Candidate.get("Name", "")).lower() == QueryLower) or (str(Candidate.get("ID", "")).lower() == QueryLower):
                MatchedOther = Candidate
                break

        if (MatchedOther is None):
            for Candidate in OtherEntities:
                if QueryLower in str(Candidate.get("Name", "")).lower():
                    MatchedOther = Candidate
                    break

        if (MatchedOther is None):
            await Context.send(f"Could not find Dungeons & Dragons `Other` entity matching `{QueryName}` on Platform.")
            return

        DetailData     : dict                 = MatchedOther.get("DetailData", {})
        EntityID       : str                  = str(MatchedOther.get("ID", str(UUIDLibrary.uuid4())))
        DisplayName    : str                  = str(ParsedArguments.last("name") or MatchedOther.get("Name", QueryName))
        HPBlock        : dict                 = DetailData.get("HitPoints", {})
        MaxHP          : int                  = int(HPBlock.get("MaxHitPoints", 10))
        CurrentHP      : int                  = int(HPBlock.get("CurrentHitPoints", MaxHP))
        ArmorClassValue: int                  = int(DetailData.get("ArmorClass", {}).get("TotalArmorClass", 10) if isinstance(DetailData.get("ArmorClass"), dict) else DetailData.get("ArmorClass", 10))
        InitBonus      : int                  = int(DetailData.get("InitiativeBonus", 0))
        InitRoll       : Dice.RollOutcome     = self.DiceRoller.EvaluateRoll(f"1d20{"+" if (InitBonus >= 0) else ""}{InitBonus}")
        ControllerArg  : Typing.Optional[str] = ParsedArguments.last("controller")
        ControllerID   : Typing.Optional[str] = ControllerArg.strip().lstrip("<@!").rstrip(">") if (ControllerArg is not None) else None
        IsHidden       : bool                 = ("h" in ParsedArguments.OptionsDictionary)

        NewEntry: Typing.Any = EncounterManager.CombatantEntry(ID = EntityID, Name = DisplayName, Initiative = InitRoll.Total, CurrentHitPoints = CurrentHP, MaxHitPoints = MaxHP, ArmorClass = ArmorClassValue, EntityType = "Other", IsMonster = True, ControllerDiscordID = ControllerID, CharacterID = EntityID, InitiativeBonus = InitBonus, IsHidden = IsHidden)
        Encounter.AddCombatant(NewEntry)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = True, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(content = f"Added **{DisplayName}** (Other) to combat (Init: {InitRoll.Total}).", embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "pass")
    @Commands.check(CheckDND5EPrefix)
    async def PassTurnCommand(self, Context: Commands.Context, *, TargetQuery: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        if (Encounter.InitiativeMode != "Popcorn"):
            await Context.send(f"This encounter uses Standard initiative. Use `{Context.prefix}init next` instead (or start with `{Context.prefix}init begin popcorn`).")
            return

        ActiveCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.GetActiveCombatant()
        CallerID       : str                                              = str(Context.author.id)
        if (ActiveCombatant is not None) and (ActiveCombatant.ControllerDiscordID is not None) and (ActiveCombatant.ControllerDiscordID != CallerID) and (not IsDungeonMasterOrAdmin(Context)):
            await Context.send(f"Only **{ActiveCombatant.Name}**'s controller or a DM may pass the turn.")
            return

        CleanTarget : str                                 = TargetQuery.strip()
        ResolvedList: list[TargetResolver.ResolvedTarget] = await self.TargetResolver.ResolveTargets([CleanTarget], GameSystem = "DND5E", ChannelID = Context.channel.id, Encounter = Encounter)
        TargetID    : str                                 = ResolvedList[0].Combatant.ID if (ResolvedList and ResolvedList[0].Combatant is not None) else CleanTarget

        NextCombatant, RoundNumber, RoundWrapped = Encounter.PassTurn(TargetID)
        if (NextCombatant is None):
            await Context.send(f"Could not pass turn to `{TargetQuery}` (not found or already acted this round).")
            return

        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = CallerID, IsDungeonMaster = IsDungeonMasterOrAdmin(Context), CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)

        MentionText: str = ""
        if (NextCombatant.ControllerDiscordID is not None):
            RoundNotice: str = f" (New Round {RoundNumber}!)" if RoundWrapped else ""
            MentionText      = f"<@{NextCombatant.ControllerDiscordID}>, it's **{NextCombatant.Name}**'s turn!{RoundNotice}"

        await Context.send(content = MentionText or None, embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "next", aliases = ["n"])
    @Commands.check(CheckDND5EPrefix)
    async def NextTurn(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        ActiveCombatant, RoundNumber = Encounter.AdvanceTurn()
        ExpiredAnnouncements: list[str] = self.EffectHandler.TickTurnEffects(Encounter)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDungeonMasterOrAdmin(Context))
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)

        MentionParts: list[str] = []
        if (ActiveCombatant is not None) and (ActiveCombatant.ControllerDiscordID is not None):
            MentionParts.append(f"<@{ActiveCombatant.ControllerDiscordID}>, it's your turn!")

        if ExpiredAnnouncements:
            MentionParts.extend(ExpiredAnnouncements)

        MentionText: str = "\n".join(MentionParts)
        await Context.send(content = MentionText or None, embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "prev", aliases = ["p"])
    @Commands.check(CheckDND5EPrefix)
    async def PreviousTurn(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Encounter.PreviousTurn()
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDungeonMasterOrAdmin(Context))
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "hp")
    @Commands.check(CheckDND5EPrefix)
    async def CombatantHitPoints(self, Context: Commands.Context, TargetID: str, AmountText: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        try:
            OldHP              : int       = Target.CurrentHitPoints
            DamageAnnouncements: list[str] = []
            if AmountText.startswith("+"):
                DeltaHP: int = int(AmountText[1:])
                Target.CurrentHitPoints = min(Target.MaxHitPoints, Target.CurrentHitPoints + DeltaHP)

            elif AmountText.startswith("-"):
                DamageAmount: int = int(AmountText[1:])
                DamageToHP  : int = DamageAmount
                if (Target.TemporaryHitPoints > 0):
                    Absorbed: int = min(Target.TemporaryHitPoints, DamageAmount)
                    Target.TemporaryHitPoints -= Absorbed
                    DamageToHP = DamageAmount - Absorbed
                    DamageAnnouncements.append(f"Temporary HP absorbed {Absorbed} damage.")

                Target.CurrentHitPoints = max(0, Target.CurrentHitPoints - DamageToHP)
                ConcNotice: Typing.Optional[str] = self.EffectHandler.HandleDamageConcentrationCheck(Target, DamageAmount, Encounter = Encounter, AutoRoll = False)
                if (ConcNotice is not None):
                    DamageAnnouncements.append(ConcNotice)

            else:
                Target.CurrentHitPoints = max(0, min(Target.MaxHitPoints, int(AmountText)))

            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            AnnounceString: str = f"\n{chr(10).join(DamageAnnouncements)}" if (DamageAnnouncements) else ""
            await Context.send(f"**{Target.Name}** HP: {OldHP} ➔ **{Target.CurrentHitPoints}/{Target.MaxHitPoints}**{AnnounceString}")

        except ValueError:
            await Context.send("Invalid HP amount. Example: `&init hp Goblin1 -5`")

    @InitiativeGroup.command(name = "thp")
    @Commands.check(CheckDND5EPrefix)
    async def CombatantTemporaryHitPoints(self, Context: Commands.Context, TargetID: str, AmountText: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        try:
            OldTHP: int = Target.TemporaryHitPoints
            if AmountText.startswith("+"):
                Target.TemporaryHitPoints += int(AmountText[1:])

            elif AmountText.startswith("-"):
                Target.TemporaryHitPoints = max(0, Target.TemporaryHitPoints - int(AmountText[1:]))

            else:
                Target.TemporaryHitPoints = max(0, int(AmountText))

            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"**{Target.Name}** Temp HP: {OldTHP} ➔ **+{Target.TemporaryHitPoints}**")

        except ValueError:
            await Context.send("Invalid Temp HP amount. Example: `&init thp Goblin1 5`")

    @InitiativeGroup.command(name = "maxhp")
    @Commands.check(CheckDND5EPrefix)
    async def CombatantMaxHitPoints(self, Context: Commands.Context, TargetID: str, AmountText: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        try:
            Target.MaxHitPoints     = max(1, int(AmountText))
            Target.CurrentHitPoints = min(Target.CurrentHitPoints, Target.MaxHitPoints)
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"**{Target.Name}** Max HP set to **{Target.MaxHitPoints}** (Current: {Target.CurrentHitPoints}/{Target.MaxHitPoints}).")

        except ValueError:
            await Context.send("Invalid Max HP amount. Example: `&init maxhp Goblin1 20`")

    @InitiativeGroup.command(name = "ac")
    @Commands.check(CheckDND5EPrefix)
    async def CombatantArmorClass(self, Context: Commands.Context, TargetID: str, AmountText: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        try:
            Target.ArmorClass = max(0, int(AmountText))
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"**{Target.Name}** AC set to **{Target.ArmorClass}**.")

        except ValueError:
            await Context.send("Invalid AC amount. Example: `&init ac Goblin1 16`")

    @InitiativeGroup.command(name = "round")
    @Commands.check(CheckDND5EPrefix)
    async def SetEncounterRound(self, Context: Commands.Context, RoundNumberText: str) -> None:
        if not IsDungeonMasterOrAdmin(Context):
            await Context.send("You lack permission to adjust the encounter round. Requires Dungeon Master or Macro Master role.")
            return

        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        try:
            Encounter.RoundNumber = max(1, int(RoundNumberText))
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"Encounter round set to **{Encounter.RoundNumber}**.")

        except ValueError:
            await Context.send("Invalid round number. Example: `&init round 3`")

    @InitiativeGroup.command(name = "note")
    @Commands.check(CheckDND5EPrefix)
    async def CombatantNote(self, Context: Commands.Context, TargetID: str, *, NoteText: str = "") -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        CleanNote: Typing.Optional[str] = NoteText.strip() if (NoteText.strip()) else None
        Target.Note                     = CleanNote
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        if (CleanNote is not None):
            await Context.send(f"Set note for **{Target.Name}**: *\"{CleanNote}\"*")

        else:
            await Context.send(f"Cleared note for **{Target.Name}**.")

    @InitiativeGroup.command(name = "reroll")
    @Commands.check(CheckDND5EPrefix)
    async def RerollInitiative(self, Context: Commands.Context, *, TargetID: str = "") -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        if TargetID.strip():
            Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
            if (Target is None):
                await Context.send(f"Could not find combatant `{TargetID}`.")
                return

            BonusValue: int = Target.InitiativeBonus
            RollResult: Dice.RollOutcome = self.DiceRoller.EvaluateRoll(f"1d20{"+" if (BonusValue >= 0) else ""}{BonusValue}")
            Target.Initiative = RollResult.Total
            Encounter.SortCombatants()
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"Rerolled initiative for **{Target.Name}**: {RollResult.Breakdown} = **{RollResult.Total}**")

        else:
            RerolledMessages: list[str] = []
            for Combatant in Encounter.Combatants:
                BonusValue = Combatant.InitiativeBonus
                RollResult = self.DiceRoller.EvaluateRoll(f"1d20{"+" if (BonusValue >= 0) else ""}{BonusValue}")
                Combatant.Initiative = RollResult.Total
                RerolledMessages.append(f"• **{Combatant.Name}**: {RollResult.Total}")

            Encounter.SortCombatants()
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send("Rerolled initiative for all combatants:\n" + "\n".join(RerolledMessages))

    @InitiativeGroup.group(name = "effect", aliases = ["e"], invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def EffectGroup(self, Context: Commands.Context, *, TargetID: str = "") -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        if TargetID.strip():
            Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
            if (Target is None):
                await Context.send(f"Could not find combatant `{TargetID}`.")
                return

            ActiveEffects: list[dict[str, Typing.Any]] = self.EffectHandler.GetCombatantActiveEffects(Target)
            if not ActiveEffects:
                await Context.send(f"**{Target.Name}** has no active effects.")
                return

            EffectLines: list[str] = []
            for Eff in ActiveEffects:
                DurText : str = f" ({Eff.get("DurationRounds")} rounds left)" if (Eff.get("DurationRounds") is not None) else " (Indefinite)"
                ConcText: str = " [Conc]" if (Eff.get("Concentration")) else ""
                EffectLines.append(f"• **{Eff.get("Name")}**{DurText}{ConcText}")

            await Context.send(f"Active effects on **{Target.Name}**:\n" + "\n".join(EffectLines))

        else:
            AllLines: list[str] = []
            for Combatant in Encounter.Combatants:
                ActiveEffects = self.EffectHandler.GetCombatantActiveEffects(Combatant)
                if ActiveEffects:
                    SummaryText: str = ", ".join([str(E.get("Name")) for E in ActiveEffects])
                    AllLines.append(f"• **{Combatant.Name}**: {SummaryText}")

            if not AllLines:
                await Context.send("No active effects on any combatant.")
                return

            await Context.send("Active effects in encounter:\n" + "\n".join(AllLines))

    @EffectGroup.command(name = "add")
    @Commands.check(CheckDND5EPrefix)
    async def AddEffectCommand(self, Context: Commands.Context, TargetID: str, EffectName: str, *, FlagsText: str = "") -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(FlagsText)
        DurationRounds : Typing.Optional[int]           = None
        DurationArg    : Typing.Optional[str]           = ParsedArguments.last("d") or ParsedArguments.last("dur")
        if (DurationArg is not None) and DurationArg.isdigit():
            DurationRounds = int(DurationArg)

        IsConc  : bool                 = ("conc" in ParsedArguments.OptionsDictionary)
        DescText: Typing.Optional[str] = ParsedArguments.last("desc")

        self.EffectHandler.AttachEffect(Combatant = Target, EffectName = EffectName, DurationRounds = DurationRounds, IsConcentration = IsConc, CasterName = str(Context.author.display_name), Description = DescText, Encounter = Encounter)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        DurationMessage     : str = f" for {DurationRounds} rounds" if (DurationRounds is not None) else ""
        ConcentrationMessage: str = " (Concentration)" if (IsConc) else ""
        await Context.send(f"Attached effect **{EffectName}** to **{Target.Name}**{DurationMessage}{ConcentrationMessage}.")

    @EffectGroup.command(name = "remove", aliases = ["rem", "delete"])
    @Commands.check(CheckDND5EPrefix)
    async def RemoveEffectCommand(self, Context: Commands.Context, TargetID: str, *, EffectName: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        Success: bool = self.EffectHandler.RemoveEffect(Target, EffectName, Encounter = Encounter)
        if Success:
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"Removed effect **{EffectName}** from **{Target.Name}**.")

        else:
            await Context.send(f"Could not find effect `{EffectName}` on **{Target.Name}**.")

    @InitiativeGroup.command(name = "opt", aliases = ["c", "condition"])
    @Commands.check(CheckDND5EPrefix)
    async def CombatantCondition(self, Context: Commands.Context, TargetID: str, *, ConditionName: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        NormalizedCondition: str = ConditionName.strip().title()
        if NormalizedCondition in Target.Conditions:
            Target.Conditions.remove(NormalizedCondition)
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"Removed condition **{NormalizedCondition}** from **{Target.Name}**.")

        else:
            Target.Conditions.append(NormalizedCondition)
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"Applied condition **{NormalizedCondition}** to **{Target.Name}**.")

    @InitiativeGroup.command(name = "remove", aliases = ["rem"])
    @Commands.check(CheckDND5EPrefix)
    async def RemoveCombatant(self, Context: Commands.Context, *, TargetID: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        TargetCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (TargetCombatant is not None) and (TargetCombatant.ControllerDiscordID is not None) and (TargetCombatant.ControllerDiscordID != str(Context.author.id)):
            if not IsDungeonMasterOrAdmin(Context):
                await Context.send("You lack permission to remove other players' combatants. Requires Dungeon Master or Macro Master role.")
                return

        Removed: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.RemoveCombatant(TargetID)
        if (Removed is not None):
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"Removed **{Removed.Name}** from combat.")

        else:
            await Context.send(f"Could not find combatant `{TargetID}`.")

    @InitiativeGroup.command(name = "attack", aliases = ["a"])
    @Commands.check(CheckDND5EPrefix)
    async def MonsterAttackCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active in this channel. Start one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}init begin`.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalList : list[str]                      = list(ParsedArguments.PositionalArguments)

        if not PositionalList:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}init a <Monster> <Attack> [-t <Target>] [flags]`")
            return

        MonsterQuery: str = PositionalList[0]
        ActionQuery : str = " ".join(PositionalList[1:]) if (len(PositionalList) > 1) else ""

        AttackerCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(MonsterQuery)
        if (AttackerCombatant is None) and (Encounter.ActiveCombatantIndex is not None) and (Encounter.ActiveCombatantIndex < len(Encounter.Combatants)):
            ActiveCombatant: Typing.Any = Encounter.Combatants[Encounter.ActiveCombatantIndex]
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
            MonsterData: Typing.Any = AttackerCombatant.MonsterData
            if (MonsterData is None):
                MonsterData = await self.PlatformClient.FetchMonsterDetails(AttackerCombatant.Name)
                if (MonsterData is not None):
                    AttackerCombatant.MonsterData = MonsterData

            if (MonsterData is not None):
                Compiler : Typing.Any = MonsterActionCompiler.MonsterActionCompiler()
                ActionDoc             = Compiler.FindAndCompileMonsterAction(MonsterData, ActionQuery)

        elif (AttackerCombatant.CharacterID is not None):
            try:
                PlatformActions: Typing.Any = await self.PlatformClient.FetchCharacterActions(AttackerCombatant.CharacterID)
                for ActionDictionary in PlatformActions:
                    CandidateName: Typing.Any = str(ActionDictionary.get("Name", "")).lower()
                    if (ActionQuery.lower() == CandidateName) or (ActionQuery.lower() in CandidateName):
                        ActionDoc = AutomationModels.ActionDocument.model_validate(ActionDictionary)
                        break

            except Exception as ActionFetchError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to fetch platform actions: {str(ActionFetchError)}")

        if (ActionDoc is None):
            await Context.send(f"Could not find action `{ActionQuery}` for **{AttackerCombatant.Name}**.")
            return

        TargetTokens   : list[str]                             = ParsedArguments.get("t") or []
        ResolvedTargets: list[TargetResolver.ResolvedTarget]   = await self.TargetResolver.ResolveTargets(TargetTokens, GameSystem = "DND5E", ChannelID = Context.channel.id, Encounter = Encounter) if TargetTokens else []
        TargetEntities : list[EncounterManager.CombatantEntry] = [R.Combatant for R in ResolvedTargets if (R.Combatant is not None)]

        AutoContext: Typing.Any = EffectContext.AutomationContext(Caster = AttackerCombatant, Targets = TargetEntities, Encounter = Encounter, Arguments = ParsedArguments)

        Engine: Typing.Any = AutomationEngine.AutomationEngine(self.DiceRoller)
        Result: Typing.Any = Engine.RunAutomation(ActionDoc, AutoContext)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

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
                SaveStatus : str = "Passed" if (TargetOutcome.SaveSucceeded) else "Failed"
                SaveSummary: str = f"• **Save:** {SaveStatus} ({TargetOutcome.SaveResultTotal} vs DC {TargetOutcome.SaveTargetDC})"
                DescriptionLines.append(SaveSummary)

            if (TargetOutcome.DamageDealt > 0):
                DamageTypeText: str = f" {TargetOutcome.DamageType}" if (TargetOutcome.DamageType) else ""
                DescriptionLines.append(f"• **Damage:** {TargetOutcome.DamageDealt}{DamageTypeText}")

            if TargetOutcome.ConditionsApplied:
                ConditionsText: Typing.Any = ", ".join(TargetOutcome.ConditionsApplied)
                DescriptionLines.append(f"• **Conditions Applied:** {ConditionsText}")

            if TargetOutcome.EffectsAttached:
                EffectsText: Typing.Any = ", ".join(TargetOutcome.EffectsAttached)
                DescriptionLines.append(f"• **Effects Applied:** {EffectsText}")

            for NarrativeMsg in TargetOutcome.NarrativeMessages:
                DescriptionLines.append(f"• {NarrativeMsg}")

            TargetEntity: Typing.Any = Encounter.FindCombatant(TargetOutcome.TargetName)
            if (TargetEntity is not None):
                DescriptionLines.append(f"• **HP:** {TargetEntity.CurrentHitPoints}/{TargetEntity.MaxHitPoints}")

            DescriptionLines.append("")

        for GlobalMessage in Result.GlobalNarrative:
            DescriptionLines.append(f"📢 {GlobalMessage}")

        ResultEmbed: Discord.Embed = Discord.Embed(title = f"{AttackerCombatant.Name}: {ActionDoc.Name}", description = "\n".join(DescriptionLines).strip() or "Action resolved.", color = COLOR_INITIATIVE_EMBED)
        await Context.send(embed = ResultEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(InitiativeCommands(BotInstance))
