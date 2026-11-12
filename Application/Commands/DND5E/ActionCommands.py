import re                                       as RegularExpressions
import typing                                   as Typing
import discord                                  as Discord
import discord.ext.commands                     as Commands
import Configuration.Config                     as Config
import Services.DebugService                    as Debug
import Services.DiceService                     as DiceService
import Services.PlatformClient                  as PlatformClient
import Services.CharacterStateService           as CharacterStateService
import Services.EncounterManagerService         as EncounterManagerService
import Services.CompendiumTagRenderer           as TagRenderer
import Services.Automation.AutomationEngine      as AutomationEngine
import Services.Automation.AutomationModels      as AutomationModels
import Services.Automation.EffectContext         as EffectContext
import Services.Draconic.API.ArgumentParser      as ArgumentParser

COLOR_ATTACK_EMBED  : int = 0x0030A6
COLOR_CRITICAL_HIT  : int = 0x005E00
COLOR_CRITICAL_MISS : int = 0xA60000
COLOR_ERROR_EMBED   : int = 0xA60000

TARGET_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-t|--target)\s+([^\s-]+(?:\s+[^\s-]+)*)", RegularExpressions.IGNORECASE)
LEVEL_PATTERN : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-l|--level)\s+(\d+)", RegularExpressions.IGNORECASE)

def CheckDNDPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND)

class ActionCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterStateService.CharacterStateService] = None, EncounterManager: Typing.Optional[EncounterManagerService.EncounterManagerService] = None) -> None:
        self.BotInstance     : Commands.Bot                                    = BotInstance
        self.StateService    : CharacterStateService.CharacterStateService     = StateService if (StateService is not None) else CharacterStateService.CharacterStateService()
        self.EncounterManager: EncounterManagerService.EncounterManagerService = EncounterManager if (EncounterManager is not None) else EncounterManagerService.EncounterManagerService()
        self.DiceRoller      : DiceService.DiceRollerService                  = DiceService.DiceRollerService()
        self.PlatformClient  : PlatformClient.MISPlatformClient                = self.StateService.PlatformClient
        self.TagRenderer     : TagRenderer.CompendiumTagRenderer               = TagRenderer.CompendiumTagRenderer()

    @Commands.command(name = "attack", aliases = ["a"])
    @Commands.check(CheckDNDPrefix)
    async def AttackCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        TargetName  : Typing.Optional[str] = None
        CleanText   : str                  = ArgumentsText.strip()
        TargetMatch                        = TARGET_PATTERN.search(CleanText)
        if (TargetMatch is not None):
            TargetName = TargetMatch.group(1).strip()
            CleanText  = TARGET_PATTERN.sub("", CleanText).strip()

        Tokens: list[str] = CleanText.split()
        if not Tokens:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}a <weapon> [-t <target>] [flags]`")
            return

        WeaponQuery  : str  = Tokens[0].lower()
        TrailingFlags: str  = " ".join(Tokens[1:])
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharName     : str  = str(ActiveRecord.get("Name", "Hero"))
        CharID       : str  = str(ActiveRecord.get("ID", ""))

        CustomActionDoc: Typing.Optional[AutomationModels.ActionDocument] = None
        if CharID:
            try:
                CustomActions = await self.PlatformClient.FetchCharacterActions(CharID)
                for ActionDict in CustomActions:
                    CandidateName = str(ActionDict.get("Name", "")).lower()
                    if (WeaponQuery == CandidateName) or (WeaponQuery in CandidateName):
                        CustomActionDoc = AutomationModels.ActionDocument.model_validate(ActionDict)
                        break

            except Exception:
                pass

        if (CustomActionDoc is not None) and CustomActionDoc.Automation:
            ParsedArgs = ArgumentParser.ParsedArguments(ArgumentsText)
            Encounter  = self.EncounterManager.GetEncounter(Context.channel.id)
            Targets    : list[EncounterManagerService.CombatantEntry] = []
            if (Encounter is not None):
                TargetNames = ParsedArgs.get("t")
                for TName in TargetNames:
                    Matched = Encounter.FindCombatant(TName)
                    if (Matched is not None):
                        Targets.append(Matched)

            AutoContext = EffectContext.AutomationContext(
                Caster    = ActiveRecord,
                Targets   = Targets,
                Encounter = Encounter,
                Arguments = ParsedArgs
            )

            Engine = AutomationEngine.AutomationEngine(self.DiceRoller)
            Result = Engine.RunAutomation(CustomActionDoc, AutoContext)

            DescriptionLines: list[str] = []
            if CustomActionDoc.Phrase:
                DescriptionLines.append(f"*{CustomActionDoc.Phrase}*\n")

            for TargetOutcome in Result.TargetOutcomes:
                DescriptionLines.append(f"🎯 **Target: {TargetOutcome.TargetName}**")
                if (TargetOutcome.HitStatus is not None):
                    DescriptionLines.append(f"• **Attack:** {TargetOutcome.HitStatus} ({TargetOutcome.AttackTotal} vs AC {TargetOutcome.TargetArmorClass})")

                if (TargetOutcome.SaveResultTotal is not None):
                    SaveStatus: str = "Passed" if TargetOutcome.SaveSucceeded else "Failed"
                    DescriptionLines.append(f"• **Save:** {SaveStatus} ({TargetOutcome.SaveResultTotal} vs DC {TargetOutcome.SaveTargetDC})")

                if (TargetOutcome.DamageDealt > 0):
                    DamageTypeText: str = f" {TargetOutcome.DamageType}" if TargetOutcome.DamageType else ""
                    DescriptionLines.append(f"• **Damage:** {TargetOutcome.DamageDealt}{DamageTypeText}")

                if TargetOutcome.ConditionsApplied:
                    DescriptionLines.append(f"• **Conditions Applied:** {', '.join(TargetOutcome.ConditionsApplied)}")

                if TargetOutcome.EffectsAttached:
                    DescriptionLines.append(f"• **Effects Applied:** {', '.join(TargetOutcome.EffectsAttached)}")

                for Msg in TargetOutcome.NarrativeMessages:
                    DescriptionLines.append(f"• {Msg}")

                if (Encounter is not None):
                    TargetEntity = Encounter.FindCombatant(TargetOutcome.TargetName)
                    if (TargetEntity is not None):
                        DescriptionLines.append(f"• **HP:** {TargetEntity.CurrentHitPoints}/{TargetEntity.MaxHitPoints}")

                DescriptionLines.append("")

            for GlobalMsg in Result.GlobalNarrative:
                DescriptionLines.append(f"📢 {GlobalMsg}")

            ResultEmbed = Discord.Embed(
                title       = f"{CharName}: {CustomActionDoc.Name}",
                description = "\n".join(DescriptionLines).strip() or "Action resolved.",
                color       = COLOR_ATTACK_EMBED
            )
            ResultEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
            ResultEmbed.set_footer(text = "MIS-Bot • D&D 5E Custom Action")
            await Context.send(embed = ResultEmbed)
            return

        AttacksList  : list[dict]        = DetailData.get("Attacks", [])
        MatchedAttack: Typing.Optional[dict] = None
        for Atk in AttacksList:
            if WeaponQuery in str(Atk.get("Name", "")).lower():
                MatchedAttack = Atk
                break

        AttackBonus     : int = int(MatchedAttack.get("AttackBonus", 0)) if MatchedAttack else 5
        DamageExpression: str = str(MatchedAttack.get("DamageExpression", "1d8+3")) if MatchedAttack else "1d8+3"
        DamageType      : str = str(MatchedAttack.get("DamageType", "Slashing")) if MatchedAttack else "Slashing"
        AttackDisplayName: str = str(MatchedAttack.get("Name", WeaponQuery.title())) if MatchedAttack else WeaponQuery.title()

        ToHitFormula: str                     = f"1d20{'+' if AttackBonus >= 0 else ''}{AttackBonus} {TrailingFlags}".strip()
        AttackRoll  : DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(ToHitFormula)

        TargetCombatant: Typing.Optional[EncounterManagerService.CombatantEntry] = None
        HitStatusText  : str = ""
        Encounter      : Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)
        if (TargetName is not None) and (Encounter is not None):
            TargetCombatant = Encounter.FindCombatant(TargetName)
            if (TargetCombatant is not None):
                TargetAC: int = TargetCombatant.ArmorClass
                if AttackRoll.IsCriticalHit:
                    HitStatusText = f"\n\n🎯 **Critical Hit** vs {TargetCombatant.Name} (AC {TargetAC})!"

                elif AttackRoll.IsCriticalMiss:
                    HitStatusText = f"\n\n💥 **Critical Miss** vs {TargetCombatant.Name} (AC {TargetAC})!"

                elif (AttackRoll.Total >= TargetAC):
                    HitStatusText = f"\n\n⚔️ **Hit** vs {TargetCombatant.Name} (AC {TargetAC})!"

                else:
                    HitStatusText = f"\n\n🛡️ **Miss** vs {TargetCombatant.Name} (AC {TargetAC})!"

        DamageRoll: DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(DamageExpression)
        EmbedColor: int                     = COLOR_CRITICAL_HIT if AttackRoll.IsCriticalHit else (COLOR_CRITICAL_MISS if AttackRoll.IsCriticalMiss else COLOR_ATTACK_EMBED)

        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharName}: {AttackDisplayName}", description = f"**To Hit:** {AttackRoll.Breakdown} = **{AttackRoll.Total}**{HitStatusText}\n\n**Damage:** {DamageRoll.Breakdown} = **{DamageRoll.Total}** {DamageType}", color = EmbedColor)
        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E Combat Attack")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "cast")
    @Commands.check(CheckDNDPrefix)
    async def CastCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        CastLevel: Typing.Optional[int] = None
        CleanText: str                  = ArgumentsText.strip()
        LevelMatch                      = LEVEL_PATTERN.search(CleanText)
        if (LevelMatch is not None):
            CastLevel = int(LevelMatch.group(1))
            CleanText = LEVEL_PATTERN.sub("", CleanText).strip()

        TargetName : Typing.Optional[str] = None
        TargetMatch                       = TARGET_PATTERN.search(CleanText)
        if (TargetMatch is not None):
            TargetName = TargetMatch.group(1).strip()
            CleanText  = TARGET_PATTERN.sub("", CleanText).strip()

        SpellNameQuery: str = CleanText.strip()
        if not SpellNameQuery:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}cast <spell> [-l <level>] [-t <target>]`")
            return

        SpellRecord: Typing.Optional[dict] = await self.PlatformClient.FetchSpellDetails(SpellNameQuery)
        DetailData : dict                  = ActiveRecord.get("DetailData", {})
        CharName   : str                   = str(ActiveRecord.get("Name", "Hero"))

        ActualSpellName: str = str(SpellRecord.get("name", SpellNameQuery.title())) if SpellRecord else SpellNameQuery.title()
        BaseLevel      : int = int(SpellRecord.get("level", 1)) if SpellRecord else 1
        EffectiveLevel : int = CastLevel if (CastLevel is not None) else BaseLevel

        SlotInfoText: str = ""
        if (EffectiveLevel > 0):
            Available, Total = self.StateService.ModifySpellSlot(DetailData, EffectiveLevel, 1)
            SlotInfoText     = f"\n*Spent Level {EffectiveLevel} slot ({Available}/{Total} remaining)*"

        ProfBonus: int                   = int(DetailData.get("ProficiencyBonus", 2))
        _, _, WisMod                     = self.StateService.GetAbilityModifier(DetailData, "wis")
        SpellDC  : int                   = 8 + ProfBonus + WisMod
        SpellAtk : int                   = ProfBonus + WisMod
        StatsLine: str                   = f"**Spell Save DC:** {SpellDC} | **Spell Attack:** {'+' if SpellAtk >= 0 else ''}{SpellAtk}"

        DescriptionText: str = ""
        if SpellRecord:
            DescriptionText = f"\n\n{self.TagRenderer.RenderEntries(SpellRecord.get('entries', []))[:500]}…"

        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharName} casts {ActualSpellName}!", description = f"{StatsLine}{SlotInfoText}{DescriptionText}", color = COLOR_ATTACK_EMBED)
        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E Spellcasting")
        await Context.send(embed = ResponseEmbed)

    @Commands.group(name = "action", aliases = ["act"], invoke_without_command = True)
    @Commands.check(CheckDNDPrefix)
    async def ActionGroup(self, Context: Commands.Context) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active character selected.")
            return

        CharID: str = str(ActiveRecord.get("ID", ""))
        try:
            ActionsList: list[dict] = await self.PlatformClient.FetchCharacterActions(CharID)
            if not ActionsList:
                await Context.send(f"No custom actions registered for **{ActiveRecord.get('Name', 'Hero')}**.")
                return

            ActionNames: list[str] = [f"• **{Act.get('Name', 'Action')}** ({Act.get('ActivationType', 'Action')})" for Act in ActionsList]
            Embed = Discord.Embed(
                title       = f"Custom Actions: {ActiveRecord.get('Name', 'Hero')}",
                description = "\n".join(ActionNames),
                color       = COLOR_ATTACK_EMBED
            )
            await Context.send(embed = Embed)

        except Exception as FetchError:
            await Context.send(f"Failed to fetch actions: {str(FetchError)}")

    @ActionGroup.command(name = "list", aliases = ["ls"])
    @Commands.check(CheckDNDPrefix)
    async def ListActions(self, Context: Commands.Context) -> None:
        await self.ActionGroup(Context)

    @ActionGroup.command(name = "show", aliases = ["view"])
    @Commands.check(CheckDNDPrefix)
    async def ShowAction(self, Context: Commands.Context, *, ActionName: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active character selected.")
            return

        CharID: str = str(ActiveRecord.get("ID", ""))
        try:
            ActionsList: list[dict] = await self.PlatformClient.FetchCharacterActions(CharID)
            MatchedAction: Typing.Optional[dict] = None
            for Act in ActionsList:
                CandidateName: str = str(Act.get("Name", "")).lower()
                if (ActionName.lower() == CandidateName) or (ActionName.lower() in CandidateName):
                    MatchedAction = Act
                    break

            if (MatchedAction is None):
                await Context.send(f"Could not find custom action `{ActionName}`.")
                return

            ActionDoc = AutomationModels.ActionDocument.model_validate(MatchedAction)
            Lines: list[str] = [
                f"**Activation:** {ActionDoc.ActivationType.value}",
                f"**Phrase:** {ActionDoc.Phrase or 'None'}",
                f"**Effect Nodes:** {len(ActionDoc.Automation)}"
            ]
            for NodeIndex, NodeItem in enumerate(ActionDoc.Automation, 1):
                Lines.append(f"{NodeIndex}. Type: `{NodeItem.Type.value}`")

            Embed = Discord.Embed(
                title       = f"Action: {ActionDoc.Name}",
                description = "\n".join(Lines),
                color       = COLOR_ATTACK_EMBED
            )
            await Context.send(embed = Embed)

        except Exception as FetchError:
            await Context.send(f"Failed to show action: {str(FetchError)}")

    @ActionGroup.command(name = "delete", aliases = ["del", "remove", "rem"])
    @Commands.check(CheckDNDPrefix)
    async def DeleteAction(self, Context: Commands.Context, *, ActionName: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            await Context.send("You do not have an active character selected.")
            return

        CharID: str = str(ActiveRecord.get("ID", ""))
        try:
            ActionsList: list[dict] = await self.PlatformClient.FetchCharacterActions(CharID)
            MatchedAction: Typing.Optional[dict] = None
            for Act in ActionsList:
                CandidateName: str = str(Act.get("Name", "")).lower()
                if (ActionName.lower() == CandidateName) or (ActionName.lower() in CandidateName):
                    MatchedAction = Act
                    break

            if (MatchedAction is None):
                await Context.send(f"Could not find custom action `{ActionName}`.")
                return

            ActionID: str = str(MatchedAction.get("ID", ""))
            IsSuccess: bool = await self.PlatformClient.DeleteCharacterAction(CharID, ActionID)
            if IsSuccess:
                await Context.send(f"Deleted custom action **{MatchedAction.get('Name')}**.")

            else:
                await Context.send(f"Failed to delete custom action **{MatchedAction.get('Name')}**.")

        except Exception as DeleteError:
            await Context.send(f"Error deleting action: {str(DeleteError)}")

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(ActionCommands(BotInstance))

