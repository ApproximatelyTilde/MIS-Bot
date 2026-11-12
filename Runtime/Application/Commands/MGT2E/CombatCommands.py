import re                                                 as RegularExpressions
import typing                                             as Typing
import uuid                                               as UUIDLibrary
import discord                                            as Discord
import discord.ext.commands                               as Commands
import Runtime.Services.MGT2EStateService                 as MGT2EState
import Runtime.Services.EncounterManagerService           as EncounterManager
import Runtime.Services.TargetResolverService             as TargetResolver
import Runtime.Services.Draconic.API.ArgumentParser       as ArgumentParser
import Runtime.Services.Automation.Effects.IEffectHandler as IEffectHandler
import Runtime.Services.DiceService                       as Dice
import Runtime.Application.Components.InitiativeControls  as InitiativeControls
import Runtime.Decorators.AuthorizationDecorators         as AuthorizationDecorators

COLOR_MGT2E_COMBAT: int = 0x005E5E
COLOR_DAMAGE_EMBED: int = 0xA60000
COLOR_HEAL_EMBED  : int = 0x005E00

ATTR_FLAG_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-attr|-a|--attribute)\s+([a-zA-Z]+)", RegularExpressions.IGNORECASE)

class MGT2ECombatCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[MGT2EState.MGT2EStateService] = None, EncounterManagerInstance: Typing.Optional[EncounterManager.EncounterManagerService] = None, TargetResolverInstance: Typing.Optional[TargetResolver.TargetResolverService] = None) -> None:
        self.BotInstance     : Commands.Bot                             = BotInstance
        self.StateService    : MGT2EState.MGT2EStateService             = StateService if (StateService is not None) else (getattr(BotInstance, "MGT2EStateService", None) or MGT2EState.MGT2EStateService())
        self.EncounterManager: EncounterManager.EncounterManagerService = EncounterManagerInstance if (EncounterManagerInstance is not None) else (getattr(BotInstance, "EncounterManager", None) or EncounterManager.EncounterManagerService(PlatformClientInstance = self.StateService.PlatformClient))
        if (self.EncounterManager.PlatformClient is None):
            self.EncounterManager.PlatformClient = self.StateService.PlatformClient

        self.TargetResolver  : TargetResolver.TargetResolverService          = TargetResolverInstance if (TargetResolverInstance is not None) else (getattr(BotInstance, "TargetResolverService", None) or TargetResolver.TargetResolverService(MGT2EStateInstance = self.StateService))
        self.DiceRoller      : Dice.DiceRollerService                        = Dice.DiceRollerService()
        self.EffectHandler   : IEffectHandler.IEffectHandler                 = IEffectHandler.IEffectHandler(self.DiceRoller)

    def SyncCharacterToEncounterCombatant(self, Encounter: Typing.Optional[EncounterManager.CombatEncounter], CharacterID: str, Characteristics: dict[str, int]) -> Typing.Optional[EncounterManager.CombatantEntry]:
        if (Encounter is None):
            return None

        for Combatant in Encounter.Combatants:
            if (Combatant.CharacterID == CharacterID) or (Combatant.ID == CharacterID):
                Combatant.Characteristics  = dict(Characteristics)
                Combatant.CurrentHitPoints = int(Characteristics.get("Endurance", Combatant.CurrentHitPoints))
                return Combatant

        return None

    @Commands.command(name = "damage", aliases = ["dmg", "wound"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def DamageCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ParsedArguments: ArgumentParser.ParsedArguments                    = ArgumentParser.ParsedArguments(ArgumentsText)
        Encounter      : Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        TargetTokens   : list[str]                                         = ParsedArguments.get("t") or []
        AttrArg        : Typing.Optional[str]                              = ParsedArguments.last("attr") or ParsedArguments.last("a") or ParsedArguments.last("attribute")
        PositionalList : list[str]                                         = list(ParsedArguments.PositionalArguments)

        WorkingText: str                  = ArgumentsText.strip()
        TargetAttr : Typing.Optional[str] = AttrArg
        if (TargetAttr is None):
            AttrMatch: Typing.Any = ATTR_FLAG_PATTERN.search(WorkingText)
            if (AttrMatch is not None):
                TargetAttr = AttrMatch.group(1).strip()

        try:
            DamageAmount: int = int(PositionalList[0]) if PositionalList else int(ATTR_FLAG_PATTERN.sub("", WorkingText).strip().split()[0])

        except (ValueError, IndexError):
            await Context.send(f"Usage: `{Context.prefix}damage <amount> [-attr <STAT>] [-t <target>]`")
            return

        if TargetTokens:
            ResolvedList: list[TargetResolver.ResolvedTarget] = await self.TargetResolver.ResolveTargets(TargetTokens, GameSystem = "MGT2E", ChannelID = Context.channel.id, Encounter = Encounter)
            if not ResolvedList:
                await Context.send(f"Could not resolve target `{", ".join(TargetTokens)}`.")
                return

            SummaryBlocks: list[str] = []
            for ResolvedTarget in ResolvedList:
                if ResolvedTarget.SystemMismatch and (ResolvedTarget.MentionedUserID is not None):
                    await Context.send(ResolvedTarget.ErrorMessage or "Target user does not have an active Mongoose Traveller character.")
                    return

                TargetCombatant: Typing.Optional[EncounterManager.CombatantEntry] = ResolvedTarget.Combatant
                TargetRecord   : Typing.Optional[dict[str, Typing.Any]]           = ResolvedTarget.CharacterRecord
                RawDamage      : int                                              = DamageAmount

                if (TargetCombatant is not None) and (TargetCombatant.ArmorProtection > 0):
                    RawDamage = max(0, DamageAmount - TargetCombatant.ArmorProtection)

                if (TargetRecord is not None):
                    DetailData     : dict           = TargetRecord.get("DetailData", {})
                    Characteristics: dict[str, int] = DetailData.setdefault("Characteristics", {})
                    UpdatedChars, SummaryLog        = self.StateService.ApplyPhysicalDamage(Characteristics, RawDamage, TargetAttr)
                    DetailData["Characteristics"]   = UpdatedChars
                    await self.StateService.SaveStateToPlatformAsync(TargetRecord)
                    if (TargetCombatant is not None) and (not ResolvedTarget.IsSynthetic):
                        TargetCombatant.Characteristics  = dict(UpdatedChars)
                        TargetCombatant.CurrentHitPoints = int(UpdatedChars.get("Endurance", TargetCombatant.CurrentHitPoints))

                elif (TargetCombatant is not None):
                    CharsMap: dict[str, int] = TargetCombatant.Characteristics if (TargetCombatant.Characteristics is not None) else {"Endurance": TargetCombatant.CurrentHitPoints, "Strength": 7, "Dexterity": 7}
                    if (TargetCombatant.MaxCharacteristics is None):
                        TargetCombatant.MaxCharacteristics = dict(CharsMap)

                    UpdatedChars, SummaryLog         = self.StateService.ApplyPhysicalDamage(CharsMap, RawDamage, TargetAttr)
                    TargetCombatant.Characteristics  = UpdatedChars
                    TargetCombatant.CurrentHitPoints = int(UpdatedChars.get("Endurance", TargetCombatant.CurrentHitPoints))

                else:
                    continue

                ArmorNote: str = f" *(Armor absorbed {min(DamageAmount, TargetCombatant.ArmorProtection)})*" if ((TargetCombatant is not None) and (TargetCombatant.ArmorProtection > 0)) else ""
                SummaryBlocks.append(f"**{ResolvedTarget.DisplayName}**{ArmorNote}\n{SummaryLog}")

            if (Encounter is not None):
                await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

            DamageEmbed: Discord.Embed = Discord.Embed(title = f"Physical Trauma ({DamageAmount} Raw Damage)", description = "\n\n".join(SummaryBlocks), color = COLOR_DAMAGE_EMBED)
            DamageEmbed.set_footer(text = "Tally │ Physical Characteristic Trauma")
            await Context.send(embed = DamageEmbed)
            return

        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Mongoose Traveller character selected.")
            return

        DetailData           = ActiveRecord.get("DetailData", {})
        Characteristics      = DetailData.setdefault("Characteristics", {})
        CharacterName  : str = str(ActiveRecord.get("Name", "Traveller"))
        CharacterID    : str = str(ActiveRecord.get("ID", ""))

        UpdatedCharacteristics, SummaryLog = self.StateService.ApplyPhysicalDamage(Characteristics, DamageAmount, TargetAttr)
        DetailData["Characteristics"]      = UpdatedCharacteristics
        await self.StateService.SaveStateToPlatformAsync(ActiveRecord)

        SyncedCombatant: Typing.Optional[EncounterManager.CombatantEntry] = self.SyncCharacterToEncounterCombatant(Encounter, CharacterID, UpdatedCharacteristics)
        if (SyncedCombatant is not None):
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        DamageEmbed = Discord.Embed(title = f"{CharacterName} took {DamageAmount} Damage", description = SummaryLog, color = COLOR_DAMAGE_EMBED)
        DamageEmbed.set_footer(text = "Tally │ Physical Characteristic Trauma")
        await Context.send(embed = DamageEmbed)

    @Commands.command(name = "heal")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def HealCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalList : list[str]                      = list(ParsedArguments.PositionalArguments)
        if not PositionalList:
            await Context.send(f"Usage: `{Context.prefix}heal <amount> [STAT] [-t <target>]`")
            return

        try:
            HealAmount: int = int(PositionalList[0])

        except ValueError:
            await Context.send("Invalid healing amount.")
            return

        TargetStat  : Typing.Optional[str]                              = PositionalList[1] if (len(PositionalList) > 1) else None
        Encounter   : Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        TargetTokens: list[str]                                         = ParsedArguments.get("t") or []

        if TargetTokens:
            ResolvedList: list[TargetResolver.ResolvedTarget] = await self.TargetResolver.ResolveTargets(TargetTokens, GameSystem = "MGT2E", ChannelID = Context.channel.id, Encounter = Encounter)
            if not ResolvedList:
                await Context.send(f"Could not resolve target `{", ".join(TargetTokens)}`.")
                return

            HealBlocks: list[str] = []
            for ResolvedTarget in ResolvedList:
                if ResolvedTarget.SystemMismatch and (ResolvedTarget.MentionedUserID is not None):
                    await Context.send(ResolvedTarget.ErrorMessage or "Target user does not have an active Mongoose Traveller character.")
                    return

                TargetCombatant: Typing.Any = ResolvedTarget.Combatant
                TargetRecord   : Typing.Any = ResolvedTarget.CharacterRecord
                if (TargetRecord is not None):
                    DetailData        : dict           = TargetRecord.get("DetailData", {})
                    Characteristics   : dict[str, int] = DetailData.setdefault("Characteristics", {})
                    MaxCharacteristics: dict[str, int] = DetailData.setdefault("MaxCharacteristics", dict(Characteristics))
                    UpdatedChars, SummaryLog           = self.StateService.ApplyPhysicalHealing(Characteristics, MaxCharacteristics, HealAmount, TargetStat)
                    DetailData["Characteristics"]      = UpdatedChars
                    await self.StateService.SaveStateToPlatformAsync(TargetRecord)
                    if (TargetCombatant is not None) and (not ResolvedTarget.IsSynthetic):
                        TargetCombatant.Characteristics  = dict(UpdatedChars)
                        TargetCombatant.CurrentHitPoints = int(UpdatedChars.get("Endurance", TargetCombatant.CurrentHitPoints))

                elif (TargetCombatant is not None):
                    CharsMap: dict[str, int] = TargetCombatant.Characteristics if (TargetCombatant.Characteristics is not None) else {"Endurance": TargetCombatant.CurrentHitPoints, "Strength": 7, "Dexterity": 7}
                    MaxMap  : dict[str, int] = TargetCombatant.MaxCharacteristics if (TargetCombatant.MaxCharacteristics is not None) else {"Endurance": TargetCombatant.MaxHitPoints, "Strength": 7, "Dexterity": 7}
                    UpdatedChars, SummaryLog         = self.StateService.ApplyPhysicalHealing(CharsMap, MaxMap, HealAmount, TargetStat)
                    TargetCombatant.Characteristics  = UpdatedChars
                    TargetCombatant.CurrentHitPoints = int(UpdatedChars.get("Endurance", TargetCombatant.CurrentHitPoints))

                else:
                    continue

                HealBlocks.append(f"**{ResolvedTarget.DisplayName}**\n{SummaryLog}")

            if (Encounter is not None):
                await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

            HealEmbed: Discord.Embed = Discord.Embed(title = f"Healed {HealAmount} Points", description = "\n\n".join(HealBlocks), color = COLOR_HEAL_EMBED)
            HealEmbed.set_footer(text = "Tally │ Physical Recovery")
            await Context.send(embed = HealEmbed)
            return

        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Mongoose Traveller character selected.")
            return

        DetailData              = ActiveRecord.get("DetailData", {})
        Characteristics         = DetailData.setdefault("Characteristics", {})
        MaxCharacteristics      = DetailData.setdefault("MaxCharacteristics", dict(Characteristics))
        CharacterName     : str = str(ActiveRecord.get("Name", "Traveller"))
        CharacterID       : str = str(ActiveRecord.get("ID", ""))

        UpdatedCharacteristics, SummaryLog = self.StateService.ApplyPhysicalHealing(Characteristics, MaxCharacteristics, HealAmount, TargetStat)
        DetailData["Characteristics"]      = UpdatedCharacteristics
        await self.StateService.SaveStateToPlatformAsync(ActiveRecord)

        SyncedCombatant: Typing.Optional[EncounterManager.CombatantEntry] = self.SyncCharacterToEncounterCombatant(Encounter, CharacterID, UpdatedCharacteristics)
        if (SyncedCombatant is not None):
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        HealEmbed = Discord.Embed(title = f"{CharacterName} Healed {HealAmount} Points", description = SummaryLog, color = COLOR_HEAL_EMBED)
        HealEmbed.set_footer(text = "Tally │ Physical Recovery")
        await Context.send(embed = HealEmbed)

    @Commands.command(name = "stat")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def StatCommand(self, Context: Commands.Context, StatName: str, ValueText: str) -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active Mongoose Traveller character selected.")
            return

        FullStatName   : str            = self.StateService.NormalizeCharacteristicName(StatName)
        DetailData     : dict           = ActiveRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.setdefault("Characteristics", {})
        CurrentValue   : int            = Characteristics.get(FullStatName, 7)
        CleanText      : str            = ValueText.strip()
        CharacterID    : str            = str(ActiveRecord.get("ID", ""))

        try:
            if CleanText.startswith("+"):
                NewValue: Typing.Any = CurrentValue + int(CleanText[1:])

            elif CleanText.startswith("-"):
                NewValue = max(0, CurrentValue - int(CleanText[1:]))

            else:
                NewValue = max(0, int(CleanText))

            Characteristics[FullStatName] = NewValue
            await self.StateService.SaveStateToPlatformAsync(ActiveRecord)

            Encounter      : Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
            SyncedCombatant: Typing.Optional[EncounterManager.CombatantEntry]  = self.SyncCharacterToEncounterCombatant(Encounter, CharacterID, Characteristics)
            if (SyncedCombatant is not None):
                await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

            NewDM: int = self.StateService.CalculateCharacteristicModifier(NewValue)
            await Context.send(f"**{ActiveRecord.get("Name")}** {FullStatName}: {CurrentValue} ➔ **{NewValue}** (DM: `{"+" if (NewDM >= 0) else ""}{NewDM}`)")

        except ValueError:
            await Context.send(f"Invalid stat value. Example: `{Context.prefix}stat STR +1` or `{Context.prefix}stat END 10`")

    @Commands.group(name = "init", invoke_without_command = True)
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def InitiativeGroup(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat encounter active in this channel.\nStart one with `{Context.prefix}init begin`.")
            return

        IsDM        : bool                                      = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDM, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "status", aliases = ["list"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def ShowEncounterStatus(self, Context: Commands.Context) -> None:
        await self.InitiativeGroup(Context)

    @InitiativeGroup.command(name = "begin", aliases = ["start"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def BeginEncounter(self, Context: Commands.Context, *, ArgumentsText: str = "") -> None:
        Existing: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Existing is not None):
            await Context.send("A combat encounter is already running in this channel.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalLow  : list[str]                      = [P.strip().lower() for P in ParsedArguments.PositionalArguments]
        InitiativeMode : str                            = "Popcorn" if ("popcorn" in PositionalLow) else "Standard"

        RoundNumber: int                  = 1
        RoundArg   : Typing.Optional[str] = ParsedArguments.last("round")
        if (RoundArg is not None) and RoundArg.isdigit():
            RoundNumber = max(1, int(RoundArg))

        NewEncounter            : EncounterManager.CombatEncounter = await self.EncounterManager.CreateEncounterAsync(Context.channel.id, Context.guild.id if (Context.guild) else None, GameSystem = "MGT2E", InitiativeMode = InitiativeMode)
        NewEncounter.RoundNumber                                         = RoundNumber
        if (RoundNumber > 1):
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        IsDM        : bool                                      = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(NewEncounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDM, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "end", aliases = ["stop"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def EndEncounter(self, Context: Commands.Context) -> None:
        Ended: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.EndEncounterAsync(Context.channel.id)
        if (Ended is None):
            await Context.send("No active combat encounter to end.")
            return

        EndEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Ended, CommandPrefix = Context.prefix)
        await Context.send(embed = EndEmbed)

    @InitiativeGroup.command(name = "join")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def JoinEncounter(self, Context: Commands.Context, *, OptionalFlags: str = "") -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat active. Start one with `{Context.prefix}init begin`.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(OptionalFlags)
        CompanionName  : Typing.Optional[str]           = ParsedArguments.last("comp") or ParsedArguments.last("companion") or ParsedArguments.last("vehicle")
        if (CompanionName is not None):
            ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveCompanionOrVehicle(Context.author.id, Context.channel.id, CompanionName)
            if (ActiveRecord is None):
                await Context.send(f"Could not find companion or vehicle matching `{CompanionName}`.")
                return

        else:
            ActiveRecord = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
            if (ActiveRecord is None):
                await Context.send("You do not have an active Mongoose Traveller character selected.")
                return

        DetailData        : dict                 = ActiveRecord.get("DetailData", {})
        EntityType        : str                  = str(ActiveRecord.get("EntityType", "Character"))
        ParentCharacterID : Typing.Optional[str] = ActiveRecord.get("ParentCharacterID")
        Characteristics   : dict[str, int]       = dict(DetailData.get("Characteristics", {}))
        MaxCharacteristics: dict[str, int]       = dict(DetailData.get("MaxCharacteristics", Characteristics))
        DefaultName       : str                  = str(ActiveRecord.get("Name", "Traveller"))
        CharacterName     : str                  = str(ParsedArguments.last("name", DefaultName))
        CharacterID       : str                  = str(ActiveRecord.get("ID", str(UUIDLibrary.uuid4())))
        ArmorData         : Typing.Any           = DetailData.get("Armor", {})
        ArmorProtection   : int                  = int(ArmorData.get("Protection", 0)) if isinstance(ArmorData, dict) else int(ArmorData or 0)

        DEXScore         : int                  = int(Characteristics.get("Dexterity", 7))
        DexterityModifier: int                  = self.StateService.CalculateCharacteristicModifier(DEXScore)
        BonusArg         : Typing.Optional[str] = ParsedArguments.last("b")
        if (BonusArg is not None) and BonusArg.strip().lstrip("+-").isdigit():
            DexterityModifier += int(BonusArg.strip())

        NetBoons: int = 0
        if ("boon" in ParsedArguments.OptionsDictionary) or ("adv" in ParsedArguments.OptionsDictionary):
            NetBoons += 1

        if ("bane" in ParsedArguments.OptionsDictionary) or ("dis" in ParsedArguments.OptionsDictionary):
            NetBoons -= 1

        Roll        : MGT2EState.MGT2ERollOutcome            = self.StateService.EvaluateRoll(Modifier = DexterityModifier, NetBoons = NetBoons)
        ENDScore    : int                                    = int(Characteristics.get("Endurance", 10))
        MaxENDScore : int                                    = int(MaxCharacteristics.get("Endurance", ENDScore))
        VehicleStats: Typing.Optional[dict[str, Typing.Any]] = None
        if (EntityType == "Vehicle"):
            CurrentHull : int = int(DetailData.get("HullPoints", 20))
            MaximumHull : int = int(DetailData.get("MaxHullPoints", CurrentHull))
            ENDScore          = CurrentHull
            MaxENDScore       = MaximumHull
            VehicleStats      = dict(DetailData)

        ControllerArg: Typing.Optional[str] = ParsedArguments.last("controller")
        ControllerID : str                  = ControllerArg.strip().lstrip("<@!").rstrip(">") if (ControllerArg is not None) else str(Context.author.id)
        IsHidden     : bool                 = ("h" in ParsedArguments.OptionsDictionary)
        NoteText     : Typing.Optional[str] = ParsedArguments.last("note")

        ExistingCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(CharacterName)
        if (ExistingCombatant is not None):
            ExistingCombatant.Initiative         = Roll.Total
            ExistingCombatant.CurrentHitPoints   = ENDScore
            ExistingCombatant.MaxHitPoints       = MaxENDScore
            ExistingCombatant.ArmorProtection    = ArmorProtection
            ExistingCombatant.Characteristics    = Characteristics
            ExistingCombatant.MaxCharacteristics = MaxCharacteristics
            ExistingCombatant.VehicleStats       = VehicleStats
            ExistingCombatant.ControllerDiscordID = ControllerID
            Encounter.SortCombatants()

        else:
            NewCombatant: Typing.Any = EncounterManager.CombatantEntry(ID = CharacterID, Name = CharacterName, Initiative = Roll.Total, CurrentHitPoints = ENDScore, MaxHitPoints = MaxENDScore, ArmorClass = 8, ArmorProtection = ArmorProtection, EntityType = EntityType, ParentCharacterID = ParentCharacterID, IsMonster = False, ControllerDiscordID = ControllerID, CharacterID = CharacterID, Characteristics = Characteristics, MaxCharacteristics = MaxCharacteristics, VehicleStats = VehicleStats, InitiativeBonus = DexterityModifier, IsHidden = IsHidden, Note = NoteText)
            Encounter.AddCombatant(NewCombatant)

        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        ConfirmEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName} Joined Combat", description = f"Initiative Roll: {Roll.BreakdownString}", color = COLOR_MGT2E_COMBAT)
        await Context.send(embed = ConfirmEmbed)

        IsDM        : bool                                      = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDM, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "add")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def AddCombatant(self, Context: Commands.Context, Name: str, InitiativeScore: int, EndurancePoints: int = 10, ArmorProtection: int = 0) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No combat encounter running in this channel.")
            return

        CharacteristicsMap : dict[str, int] = {
            "Endurance": EndurancePoints,
            "Strength" : 7,
            "Dexterity": 7
        }
        NewEntry: Typing.Any = EncounterManager.CombatantEntry(ID = str(UUIDLibrary.uuid4()), Name = Name, Initiative = InitiativeScore, CurrentHitPoints = EndurancePoints, MaxHitPoints = EndurancePoints, ArmorClass = 8, ArmorProtection = ArmorProtection, EntityType = "Other", IsMonster = True, Characteristics = dict(CharacteristicsMap), MaxCharacteristics = dict(CharacteristicsMap))
        Encounter.AddCombatant(NewEntry)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        await Context.send(f"Added **{Name}** (Init: {InitiativeScore}, END: {EndurancePoints}, Armor: {ArmorProtection}) to combat.")

        IsDM        : bool                                      = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDM, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "addother", aliases = ["other"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def AddOtherEntityCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        if not AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context):
            await Context.send("You lack permission to add Platform Other entities to combat. Requires Dungeon Master or Macro Master role.")
            return

        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send(f"No combat active. Start one with `{Context.prefix}init begin`.")
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        QueryName      : str                            = " ".join(ParsedArguments.PositionalArguments).strip()
        if not QueryName:
            await Context.send(f"Usage: `{Context.prefix}init addother <Name> [-name Override] [-h] [-controller @User]`")
            return

        OtherEntities: list[dict[str, Typing.Any]]            = await self.StateService.PlatformClient.FetchCharactersByEntityType("Other", GameSystem = "MGT2E")
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
            await Context.send(f"Could not find Mongoose Traveller `Other` entity matching `{QueryName}` on Platform.")
            return

        DetailData        : dict                        = MatchedOther.get("DetailData", {})
        Characteristics   : dict[str, int]              = dict(DetailData.get("Characteristics", {}))
        MaxCharacteristics: dict[str, int]              = dict(DetailData.get("MaxCharacteristics", Characteristics))
        EntityID          : str                         = str(MatchedOther.get("ID", str(UUIDLibrary.uuid4())))
        DisplayName       : str                         = str(ParsedArguments.last("name") or MatchedOther.get("Name", QueryName))
        ENDScore          : int                         = int(Characteristics.get("Endurance", 7))
        MaxENDScore       : int                         = int(MaxCharacteristics.get("Endurance", ENDScore))
        ArmorData         : Typing.Any                  = DetailData.get("Armor", {})
        ArmorProtection   : int                         = int(ArmorData.get("Protection", 0)) if isinstance(ArmorData, dict) else int(ArmorData or 0)
        DEXDM             : int                         = self.StateService.CalculateCharacteristicModifier(int(Characteristics.get("Dexterity", 7)))
        Roll              : MGT2EState.MGT2ERollOutcome = self.StateService.EvaluateRoll(Modifier = DEXDM)
        ControllerArg     : Typing.Optional[str]        = ParsedArguments.last("controller")
        ControllerID      : Typing.Optional[str]        = ControllerArg.strip().lstrip("<@!").rstrip(">") if (ControllerArg is not None) else None
        IsHidden          : bool                        = ("h" in ParsedArguments.OptionsDictionary)

        NewEntry: Typing.Any = EncounterManager.CombatantEntry(ID = EntityID, Name = DisplayName, Initiative = Roll.Total, CurrentHitPoints = ENDScore, MaxHitPoints = MaxENDScore, ArmorClass = 8, ArmorProtection = ArmorProtection, EntityType = "Other", IsMonster = True, ControllerDiscordID = ControllerID, CharacterID = EntityID, Characteristics = Characteristics, MaxCharacteristics = MaxCharacteristics, InitiativeBonus = DEXDM, IsHidden = IsHidden)
        Encounter.AddCombatant(NewEntry)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = True, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(content = f"Added **{DisplayName}** (Other) to combat (Init: {Roll.Total}).", embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "pass")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
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
        IsDM           : bool                                             = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        if (ActiveCombatant is not None) and (ActiveCombatant.ControllerDiscordID is not None) and (ActiveCombatant.ControllerDiscordID != CallerID) and (not IsDM):
            await Context.send(f"Only **{ActiveCombatant.Name}**'s controller or a DM may pass the turn.")
            return

        CleanTarget : str                                 = TargetQuery.strip()
        ResolvedList: list[TargetResolver.ResolvedTarget] = await self.TargetResolver.ResolveTargets([CleanTarget], GameSystem = "MGT2E", ChannelID = Context.channel.id, Encounter = Encounter)
        TargetID    : str                                 = ResolvedList[0].Combatant.ID if (ResolvedList and ResolvedList[0].Combatant is not None) else CleanTarget

        NextCombatant, RoundNumber, RoundWrapped = Encounter.PassTurn(TargetID)
        if (NextCombatant is None):
            await Context.send(f"Could not pass turn to `{TargetQuery}` (not found or already acted this round).")
            return

        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = CallerID, IsDungeonMaster = IsDM, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)

        MentionText: str = ""
        if (NextCombatant.ControllerDiscordID is not None):
            RoundNotice: str = f" (New Round {RoundNumber}!)" if RoundWrapped else ""
            MentionText      = f"<@{NextCombatant.ControllerDiscordID}>, it's **{NextCombatant.Name}**'s turn!{RoundNotice}"

        await Context.send(content = MentionText or None, embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "next", aliases = ["n"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def NextTurn(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        ActiveCombatant, _ = Encounter.AdvanceTurn()
        self.EffectHandler.TickTurnEffects(Encounter)
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        IsDM        : bool                                      = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDM, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)

        MentionText: str = ""
        if (ActiveCombatant is not None) and (ActiveCombatant.ControllerDiscordID is not None):
            MentionText = f"<@{ActiveCombatant.ControllerDiscordID}>, it's your turn!"

        await Context.send(content = MentionText or None, embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "prev", aliases = ["p"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def PreviousTurn(self, Context: Commands.Context) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Encounter.PreviousTurn()
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        IsDM        : bool                                      = AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context)
        StatusEmbed : Discord.Embed                             = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Context.author.id), IsDungeonMaster = IsDM, CommandPrefix = Context.prefix)
        ControlsView: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(self.EncounterManager, Context.channel.id, CommandPrefix = Context.prefix)
        await Context.send(embed = StatusEmbed, view = ControlsView)

    @InitiativeGroup.command(name = "armor")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CombatantArmor(self, Context: Commands.Context, TargetID: str, AmountText: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        try:
            Target.ArmorProtection = max(0, int(AmountText))
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"**{Target.Name}** Armor Protection set to **{Target.ArmorProtection}**.")

        except ValueError:
            await Context.send(f"Invalid armor amount. Example: `{Context.prefix}init armor {Target.Name} 4`")

    @InitiativeGroup.command(name = "round")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def SetEncounterRound(self, Context: Commands.Context, RoundNumberText: str) -> None:
        if not AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context):
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
            await Context.send(f"Invalid round number. Example: `{Context.prefix}init round 3`")

    @InitiativeGroup.command(name = "note")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CombatantNote(self, Context: Commands.Context, TargetID: str, *, NoteText: str = "") -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        Target: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (Target is None):
            await Context.send(f"Could not find combatant `{TargetID}`.")
            return

        CleanNote: Typing.Any = NoteText.strip() if NoteText.strip() else None
        Target.Note = CleanNote
        await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
        if (CleanNote is not None):
            await Context.send(f"Set note for **{Target.Name}**: *\"{CleanNote}\"*")

        else:
            await Context.send(f"Cleared note for **{Target.Name}**.")

    @InitiativeGroup.command(name = "reroll")
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
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

            Outcome: Typing.Any = self.StateService.EvaluateRoll(Modifier = Target.InitiativeBonus)
            Target.Initiative = Outcome.Total
            Encounter.SortCombatants()
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"Rerolled initiative for **{Target.Name}**: {Outcome.BreakdownString}")

        else:
            Lines: list[str] = []
            for Combatant in Encounter.Combatants:
                Outcome = self.StateService.EvaluateRoll(Modifier = Combatant.InitiativeBonus)
                Combatant.Initiative = Outcome.Total
                Lines.append(f"• **{Combatant.Name}**: {Outcome.Total}")

            Encounter.SortCombatants()
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send("Rerolled initiative for all combatants:\n" + "\n".join(Lines))

    @InitiativeGroup.command(name = "opt", aliases = ["c", "condition"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
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
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def RemoveCombatant(self, Context: Commands.Context, *, TargetID: str) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        if (Encounter is None):
            await Context.send("No active combat encounter in this channel.")
            return

        TargetCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant(TargetID)
        if (TargetCombatant is not None) and (TargetCombatant.ControllerDiscordID is not None) and (TargetCombatant.ControllerDiscordID != str(Context.author.id)):
            if not AuthorizationDecorators.IsDungeonMasterOrMacroMaster(Context):
                await Context.send("You lack permission to remove other players' combatants. Requires Dungeon Master or Macro Master role.")
                return

        Removed: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.RemoveCombatant(TargetID)
        if (Removed is not None):
            await self.EncounterManager.SaveEncounterAsync(Context.channel.id)
            await Context.send(f"Removed **{Removed.Name}** from combat.")

        else:
            await Context.send(f"Could not find combatant `{TargetID}`.")

async def setup(BotInstance: Commands.Bot) -> None:
    StateServiceInstance    : Typing.Optional[MGT2EState.MGT2EStateService]             = getattr(BotInstance, "MGT2EStateService", None)
    EncounterManagerInstance: Typing.Optional[EncounterManager.EncounterManagerService] = getattr(BotInstance, "EncounterManager", None)
    await BotInstance.add_cog(MGT2ECombatCommands(BotInstance, StateService = StateServiceInstance, EncounterManagerInstance = EncounterManagerInstance))
