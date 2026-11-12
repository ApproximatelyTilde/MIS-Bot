import re                                           as RegularExpressions
import typing                                       as Typing
import discord                                      as Discord
import discord.ext.commands                         as Commands
import Runtime.Configuration.Config                 as Config
import Runtime.Services.DebugService                as Debug
import Runtime.Services.DiceService                 as Dice
import Runtime.Services.PlatformClient              as PlatformClient
import Runtime.Services.CharacterStateService       as CharacterState
import Runtime.Services.EncounterManagerService     as EncounterManager
import Runtime.Services.TargetResolverService       as TargetResolver
import Runtime.Services.CompendiumTagRenderer       as TagRenderer
import Runtime.Services.Automation.AutomationEngine as AutomationEngine
import Runtime.Services.Automation.AutomationModels as AutomationModels
import Runtime.Services.Automation.EffectContext    as EffectContext
import Runtime.Services.Automation.Validation       as Validation
import Runtime.Services.Draconic.API.ArgumentParser as ArgumentParser

COLOR_ATTACK_EMBED : int = 0x0030A6
COLOR_CRITICAL_HIT : int = 0x005E00
COLOR_CRITICAL_MISS: int = 0xA60000
COLOR_ERROR_EMBED  : int = 0xA60000

TARGET_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-t|--target)\s+([^\s-]+(?:\s+[^\s-]+)*)", RegularExpressions.IGNORECASE)
LEVEL_PATTERN : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-l|--level)\s+(\d+)", RegularExpressions.IGNORECASE)

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance: Typing.Any = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)

class ActionCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterState.CharacterStateService] = None, EncounterManagerInstance: Typing.Optional[EncounterManager.EncounterManagerService] = None, TargetResolverInstance: Typing.Optional[TargetResolver.TargetResolverService] = None) -> None:
        self.BotInstance     : Commands.Bot                              = BotInstance
        self.StateService    : CharacterState.CharacterStateService      = StateService if (StateService is not None) else (getattr(BotInstance, "CharacterStateService", None) or CharacterState.CharacterStateService())
        ResolvedManager      : Typing.Optional[EncounterManager.EncounterManagerService] = EncounterManagerInstance if (EncounterManagerInstance is not None) else getattr(BotInstance, "EncounterManager", None)
        self.EncounterManager: EncounterManager.EncounterManagerService  = ResolvedManager if (ResolvedManager is not None) else EncounterManager.EncounterManagerService()
        self.TargetResolver  : TargetResolver.TargetResolverService          = TargetResolverInstance if (TargetResolverInstance is not None) else (getattr(BotInstance, "TargetResolverService", None) or TargetResolver.TargetResolverService(CharacterStateInstance = self.StateService))
        self.DiceRoller      : Dice.DiceRollerService                        = Dice.DiceRollerService()
        self.PlatformClient  : PlatformClient.TallyPlatformClient            = self.StateService.PlatformClient
        self.TagRenderer     : TagRenderer.CompendiumTagRenderer             = TagRenderer.CompendiumTagRenderer()

    @Commands.command(name = "attack", aliases = ["a"])
    @Commands.check(CheckDND5EPrefix)
    async def AttackCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalList : list[str]                      = list(ParsedArguments.PositionalArguments)
        if not PositionalList:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}a <weapon> [-t <target>] [flags]`")
            return

        WeaponQuery: str       = PositionalList[0].lower()
        FlagParts  : list[str] = []
        AdvState   : int       = ParsedArguments.adv()
        if (AdvState == 1):
            FlagParts.append("-adv")

        elif (AdvState == -1):
            FlagParts.append("-dis")

        BonusArg: Typing.Optional[str] = ParsedArguments.last("b")
        if (BonusArg is not None):
            FlagParts.append(BonusArg if BonusArg.startswith(("+", "-")) else f"+{BonusArg}")

        TrailingFlags: str  = " ".join(FlagParts).strip()
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharacterName: str  = str(ActiveRecord.get("Name", "Hero"))
        CharacterID  : str  = str(ActiveRecord.get("ID", ""))

        Encounter      : Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        TargetTokens   : list[str]                                         = ParsedArguments.get("t") or []
        ResolvedTargets: list[TargetResolver.ResolvedTarget]               = await self.TargetResolver.ResolveTargets(TargetTokens, GameSystem = "DND5E", ChannelID = Context.channel.id, Encounter = Encounter) if TargetTokens else []
        for ResolvedTarget in ResolvedTargets:
            if ResolvedTarget.SystemMismatch and (ResolvedTarget.MentionedUserID is not None):
                await Context.send(ResolvedTarget.ErrorMessage or "Targeted player does not have an active Dungeons & Dragons character.")
                return

        TargetsList: list[EncounterManager.CombatantEntry] = [R.Combatant for R in ResolvedTargets if (R.Combatant is not None)]

        CustomActionDoc: Typing.Optional[AutomationModels.ActionDocument] = None
        if CharacterID:
            try:
                CustomActions: Typing.Any = await self.PlatformClient.FetchCharacterActions(CharacterID)
                for ActionDictionary in CustomActions:
                    CandidateName: Typing.Any = str(ActionDictionary.get("Name", "")).lower()
                    if (WeaponQuery == CandidateName) or (WeaponQuery in CandidateName):
                        CustomActionDoc = AutomationModels.ActionDocument.model_validate(ActionDictionary)
                        break

            except Exception as ActionFetchError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to fetch custom actions: {str(ActionFetchError)}")

        if (CustomActionDoc is not None) and CustomActionDoc.Automation:
            AutoContext: Typing.Any = EffectContext.AutomationContext(Caster = ActiveRecord, Targets = TargetsList, Encounter = Encounter, Arguments = ParsedArguments)

            Engine: Typing.Any = AutomationEngine.AutomationEngine(self.DiceRoller)
            Result: Typing.Any = Engine.RunAutomation(CustomActionDoc, AutoContext)

            for ResolvedTarget in ResolvedTargets:
                if ResolvedTarget.IsSynthetic and (ResolvedTarget.Combatant is not None) and (ResolvedTarget.CharacterRecord is not None):
                    HPBlock: dict = ResolvedTarget.CharacterRecord.setdefault("DetailData", {}).setdefault("HitPoints", {})
                    HPBlock["CurrentHitPoints"]   = ResolvedTarget.Combatant.CurrentHitPoints
                    HPBlock["TemporaryHitPoints"] = ResolvedTarget.Combatant.TemporaryHitPoints
                    await self.StateService.SaveStateToPlatformAsync(ResolvedTarget.CharacterRecord)

            DescriptionLines: list[str] = []
            if CustomActionDoc.Phrase:
                DescriptionLines.append(f"*{CustomActionDoc.Phrase}*\n")

            for TargetOutcome in Result.TargetOutcomes:
                DescriptionLines.append(f"🎯 **Target: {TargetOutcome.TargetName}**")
                if (TargetOutcome.HitStatus is not None):
                    DescriptionLines.append(f"• **Attack:** {TargetOutcome.HitStatus} ({TargetOutcome.AttackTotal} vs AC {TargetOutcome.TargetArmorClass})")

                if (TargetOutcome.SaveResultTotal is not None):
                    SaveStatus: str = "Passed" if (TargetOutcome.SaveSucceeded) else "Failed"
                    DescriptionLines.append(f"• **Save:** {SaveStatus} ({TargetOutcome.SaveResultTotal} vs DC {TargetOutcome.SaveTargetDC})")

                if (TargetOutcome.DamageDealt > 0):
                    DamageTypeText: str = f" {TargetOutcome.DamageType}" if (TargetOutcome.DamageType) else ""
                    DescriptionLines.append(f"• **Damage:** {TargetOutcome.DamageDealt}{DamageTypeText}")

                if TargetOutcome.ConditionsApplied:
                    DescriptionLines.append(f"• **Conditions Applied:** {", ".join(TargetOutcome.ConditionsApplied)}")

                if TargetOutcome.EffectsAttached:
                    DescriptionLines.append(f"• **Effects Applied:** {", ".join(TargetOutcome.EffectsAttached)}")

                for NarrativeMessage in TargetOutcome.NarrativeMessages:
                    DescriptionLines.append(f"• {NarrativeMessage}")

                for TargetCombatant in TargetsList:
                    if (TargetCombatant.Name.lower() == TargetOutcome.TargetName.lower()):
                        DescriptionLines.append(f"• **HP:** {TargetCombatant.CurrentHitPoints}/{TargetCombatant.MaxHitPoints}")
                        break

                DescriptionLines.append("")

            for GlobalMessage in Result.GlobalNarrative:
                DescriptionLines.append(f"📢 {GlobalMessage}")

            if (Encounter is not None):
                await self.EncounterManager.SaveEncounterAsync(Context.channel.id)

            ResultEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: {CustomActionDoc.Name}", description = "\n".join(DescriptionLines).strip() or "Action resolved.", color = COLOR_ATTACK_EMBED)
            ResultEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
            ResultEmbed.set_footer(text = "Tally │ Dungeons & Dragons Custom Action")
            await Context.send(embed = ResultEmbed)
            return

        AttacksList  : list[dict]            = DetailData.get("Attacks", [])
        MatchedAttack: Typing.Optional[dict] = None
        for AttackEntry in AttacksList:
            if WeaponQuery in str(AttackEntry.get("Name", "")).lower():
                MatchedAttack = AttackEntry
                break

        if (MatchedAttack is None):
            MissingAttackEmbed: Discord.Embed = Discord.Embed(title = "Attack Not Found", description = f"No attack matching `{WeaponQuery}` was found on **{CharacterName}**.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = MissingAttackEmbed)
            return

        AttackBonus      : int = int(MatchedAttack.get("AttackBonus", 0))
        DamageExpression : str = str(MatchedAttack.get("DamageExpression", ""))
        DamageType       : str = str(MatchedAttack.get("DamageType", ""))
        AttackDisplayName: str = str(MatchedAttack.get("Name", WeaponQuery.title()))
        if not DamageExpression:
            InvalidAttackEmbed: Discord.Embed = Discord.Embed(title = "Incomplete Attack Data", description = f"Attack **{AttackDisplayName}** on **{CharacterName}** is missing a damage expression.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = InvalidAttackEmbed)
            return

        ToHitFormula: str              = f"1d20{"+" if (AttackBonus >= 0) else ""}{AttackBonus} {TrailingFlags}".strip()
        AttackRoll  : Dice.RollOutcome = self.DiceRoller.EvaluateRoll(ToHitFormula)

        HitStatusLines: list[str] = []
        for TargetCombatant in TargetsList:
            TargetAC: int = TargetCombatant.ArmorClass
            if AttackRoll.IsCriticalHit:
                HitStatusLines.append(f"🎯 **Critical Hit** vs **{TargetCombatant.Name}** (AC {TargetAC})!")

            elif AttackRoll.IsCriticalMiss:
                HitStatusLines.append(f"💥 **Critical Miss** vs **{TargetCombatant.Name}** (AC {TargetAC})!")

            elif (AttackRoll.Total >= TargetAC):
                HitStatusLines.append(f"⚔️ **Hit** vs **{TargetCombatant.Name}** (AC {TargetAC})!")

            else:
                HitStatusLines.append(f"🛡️ **Miss** vs **{TargetCombatant.Name}** (AC {TargetAC})!")

        HitStatusText: str              = ("\n\n" + "\n".join(HitStatusLines)) if HitStatusLines else ""
        DamageRoll   : Dice.RollOutcome = self.DiceRoller.EvaluateRoll(DamageExpression)
        EmbedColor   : int              = COLOR_CRITICAL_HIT if (AttackRoll.IsCriticalHit) else (COLOR_CRITICAL_MISS if (AttackRoll.IsCriticalMiss) else COLOR_ATTACK_EMBED)

        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: {AttackDisplayName}", description = f"**To Hit:** {AttackRoll.Breakdown} = **{AttackRoll.Total}**{HitStatusText}\n\n**Damage:** {DamageRoll.Breakdown} = **{DamageRoll.Total}** {DamageType}", color = EmbedColor)
        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = "Tally │ Dungeons & Dragons Combat Attack")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "cast")
    @Commands.check(CheckDND5EPrefix)
    async def CastCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalList : list[str]                      = list(ParsedArguments.PositionalArguments)
        if not PositionalList:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}cast <spell> [-l <level>] [-t <target>]`")
            return

        CastLevel: Typing.Optional[int] = None
        LevelArg : Typing.Optional[str] = ParsedArguments.last("l") or ParsedArguments.last("level")
        if (LevelArg is not None) and LevelArg.strip().isdigit():
            CastLevel = int(LevelArg.strip())

        SpellNameQuery : str                                               = " ".join(PositionalList).strip()
        Encounter      : Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        TargetTokens   : list[str]                                         = ParsedArguments.get("t") or []
        ResolvedTargets: list[TargetResolver.ResolvedTarget]               = await self.TargetResolver.ResolveTargets(TargetTokens, GameSystem = "DND5E", ChannelID = Context.channel.id, Encounter = Encounter) if TargetTokens else []
        for ResolvedTarget in ResolvedTargets:
            if ResolvedTarget.SystemMismatch and (ResolvedTarget.MentionedUserID is not None):
                await Context.send(ResolvedTarget.ErrorMessage or "Targeted player does not have an active Dungeons & Dragons character.")
                return

        SpellRecord  : Typing.Optional[dict] = await self.PlatformClient.FetchSpellDetails(SpellNameQuery)
        if (SpellRecord is None):
            MissingSpellEmbed: Discord.Embed = Discord.Embed(title = "Spell Not Found", description = f"No spell matching `{SpellNameQuery}` was found in the compendium.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = MissingSpellEmbed)
            return

        DetailData     : dict = ActiveRecord.get("DetailData", {})
        CharacterName  : str  = str(ActiveRecord.get("Name", "Hero"))
        ActualSpellName: str  = str(SpellRecord.get("name", SpellNameQuery.title()))
        BaseLevel      : int  = int(SpellRecord.get("level", 0))
        EffectiveLevel : int  = CastLevel if (CastLevel is not None) else BaseLevel

        SlotStatusText: str = ""
        if (EffectiveLevel > 0):
            Available, Total = self.StateService.ModifySpellSlot(DetailData, EffectiveLevel, 1)
            SlotStatusText     = f"\n*Spent Level {EffectiveLevel} slot ({Available}/{Total} remaining)*"
            await self.StateService.SaveStateToPlatformAsync(ActiveRecord)

        ProficiencyBonus: int = int(DetailData.get("ProficiencyBonus", 2))
        _, _, WisdomModifier = self.StateService.GetAbilityModifier(DetailData, "wis")
        SpellDC  : int = 8 + ProficiencyBonus + WisdomModifier
        SpellAttack : int = ProficiencyBonus + WisdomModifier
        StatsLine: str = f"**Spell Save DC:** {SpellDC} | **Spell Attack:** {"+" if (SpellAttack >= 0) else ""}{SpellAttack}"

        TargetsLine: str = ""
        if ResolvedTargets:
            TargetLabels: list[str] = [f"**{R.DisplayName}**" + (f" (AC {R.Combatant.ArmorClass})" if (R.Combatant is not None) else "") for R in ResolvedTargets]
            TargetsLine             = f"\n**Targets:** {", ".join(TargetLabels)}"

        DescriptionText: str = ""
        if SpellRecord:
            DescriptionText = f"\n\n{self.TagRenderer.RenderEntries(SpellRecord.get("entries", []))[:500]}…"

        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName} casts {ActualSpellName}!", description = f"{StatsLine}{SlotStatusText}{TargetsLine}{DescriptionText}", color = COLOR_ATTACK_EMBED)
        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = "Tally │ Dungeons & Dragons Spellcasting")
        await Context.send(embed = ResponseEmbed)

    @Commands.group(name = "action", aliases = ["act"], invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def ActionGroup(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active character selected.")
            return

        CharacterID: str = str(ActiveRecord.get("ID", ""))
        try:
            ActionsList: list[dict] = await self.PlatformClient.FetchCharacterActions(CharacterID)
            if not ActionsList:
                await Context.send(f"No custom actions registered for **{ActiveRecord.get("Name", "Hero")}**.")
                return

            ActionNames: list[str]     = [f"• **{Act.get("Name", "Action")}** ({Act.get("ActivationType", "Action")})" for Act in ActionsList]
            Embed      : Discord.Embed = Discord.Embed(title = f"Custom Actions: {ActiveRecord.get("Name", "Hero")}", description = "\n".join(ActionNames), color = COLOR_ATTACK_EMBED)
            await Context.send(embed = Embed)

        except Exception as FetchError:
            await Context.send(f"Failed to fetch actions: {str(FetchError)}")

    @ActionGroup.command(name = "list", aliases = ["ls"])
    @Commands.check(CheckDND5EPrefix)
    async def ListActions(self, Context: Commands.Context) -> None:
        await self.ActionGroup(Context)

    @ActionGroup.command(name = "show", aliases = ["view"])
    @Commands.check(CheckDND5EPrefix)
    async def ShowAction(self, Context: Commands.Context, *, ActionName: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active character selected.")
            return

        CharacterID: str = str(ActiveRecord.get("ID", ""))
        try:
            ActionsList  : list[dict]            = await self.PlatformClient.FetchCharacterActions(CharacterID)
            MatchedAction: Typing.Optional[dict] = None
            for Act in ActionsList:
                CandidateName: str = str(Act.get("Name", "")).lower()
                if (ActionName.lower() == CandidateName) or (ActionName.lower() in CandidateName):
                    MatchedAction = Act
                    break

            if (MatchedAction is None):
                await Context.send(f"Could not find custom action `{ActionName}`.")
                return

            ActionDoc: Typing.Any = AutomationModels.ActionDocument.model_validate(MatchedAction)
            Lines    : list[str]  = [f"**Activation:** {ActionDoc.ActivationType.value}", f"**Phrase:** {ActionDoc.Phrase or "None"}", f"**Effect Nodes:** {len(ActionDoc.Automation)}"]
            for NodeIndex, NodeItem in enumerate(ActionDoc.Automation, 1):
                Lines.append(f"{NodeIndex}. Type: `{NodeItem.Type.value}`")

            Embed: Discord.Embed = Discord.Embed(title = f"Action: {ActionDoc.Name}", description = "\n".join(Lines), color = COLOR_ATTACK_EMBED)
            await Context.send(embed = Embed)

        except Exception as FetchError:
            await Context.send(f"Failed to show action: {str(FetchError)}")

    @ActionGroup.command(name = "delete", aliases = ["del", "remove", "rem"])
    @Commands.check(CheckDND5EPrefix)
    async def DeleteAction(self, Context: Commands.Context, *, ActionName: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active character selected.")
            return

        CharacterID: str = str(ActiveRecord.get("ID", ""))
        try:
            ActionsList  : list[dict]            = await self.PlatformClient.FetchCharacterActions(CharacterID)
            MatchedAction: Typing.Optional[dict] = None
            for Act in ActionsList:
                CandidateName: str = str(Act.get("Name", "")).lower()
                if (ActionName.lower() == CandidateName) or (ActionName.lower() in CandidateName):
                    MatchedAction = Act
                    break

            if (MatchedAction is None):
                await Context.send(f"Could not find custom action `{ActionName}`.")
                return

            ActionID : str  = str(MatchedAction.get("ID", ""))
            IsSuccess: bool = await self.PlatformClient.DeleteCharacterAction(CharacterID, ActionID)
            if IsSuccess:
                await Context.send(f"Deleted custom action **{MatchedAction.get("Name")}**.")

            else:
                await Context.send(f"Failed to delete custom action **{MatchedAction.get("Name")}**.")

        except Exception as DeleteError:
            await Context.send(f"Error deleting action: {str(DeleteError)}")

    @ActionGroup.command(name = "import", aliases = ["add", "create"])
    @Commands.check(CheckDND5EPrefix)
    async def ImportActionCommand(self, Context: Commands.Context, *, ActionJSONC: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active character selected.")
            return

        CharacterID: str = str(ActiveRecord.get("ID", ""))
        try:
            CleanJSONC: str = ActionJSONC.strip()
            if "```" in CleanJSONC:
                Lines     : list[str] = [L for L in CleanJSONC.splitlines() if not L.strip().startswith("```")]
                CleanJSONC            = "\n".join(Lines).strip()

            ActionDoc    : Validation.ActionDocumentDefinition = Validation.ParseAndValidateJSONCAction(CleanJSONC)
            ActionPayload: dict[str, Typing.Any]               = ActionDoc.model_dump(by_alias = True)
            CreatedAction: dict[str, Typing.Any]               = await self.PlatformClient.CreateCharacterAction(CharacterID, ActionPayload)

            SuccessEmbed: Discord.Embed = Discord.Embed(title = f"Custom Action Registered: {ActionDoc.Name}", description = f"Action **`{ActionDoc.Name}`** successfully registered for **{ActiveRecord.get("Name")}**.\n\n**Activation:** `{ActionDoc.ActivationType.value}`\n**Effect Nodes:** {len(ActionDoc.Automation)}", color = COLOR_ATTACK_EMBED)
            await Context.send(embed = SuccessEmbed)

        except Exception as ImportError:
            await Context.send(f"Failed to import action: {str(ImportError)}")

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(ActionCommands(BotInstance))

