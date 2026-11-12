import typing                         as Typing
import discord                        as Discord
import discord.ext.commands           as Commands
import Configuration.Config           as Config
import Services.DebugService          as Debug
import Services.DiceService           as DiceService
import Services.CharacterStateService as CharacterStateService

COLOR_CRITICAL_HIT : int = 0x005E00
COLOR_CRITICAL_MISS: int = 0xA60000
COLOR_STANDARD_ROLL: int = 0x0030A6
COLOR_ERROR_EMBED  : int = 0xA60000

def CheckDNDPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND)

class CheckCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterStateService.CharacterStateService] = None) -> None:
        self.BotInstance : Commands.Bot                                = BotInstance
        self.StateService: CharacterStateService.CharacterStateService = StateService if (StateService is not None) else CharacterStateService.CharacterStateService()
        self.DiceRoller  : DiceService.DiceRollerService               = DiceService.DiceRollerService()

    @Commands.command(name = "check", aliases = ["c"])
    @Commands.check(CheckDNDPrefix)
    async def CheckCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        Tokens: list[str] = ArgumentsText.strip().split()
        if not Tokens:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}c <skill|ability> [flags]`")
            return

        FirstToken   : str  = Tokens[0].lower()
        TrailingFlags: str  = " ".join(Tokens[1:])
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharName     : str  = str(ActiveRecord.get("Name", "Hero"))

        if FirstToken in CharacterStateService.ABILITY_ALIASES:
            AbilityName, _, AbilityMod = self.StateService.GetAbilityModifier(DetailData, FirstToken)
            RollFormula: str = f"1d20{'+' if AbilityMod >= 0 else ''}{AbilityMod} {TrailingFlags}".strip()
            Outcome    : DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(RollFormula)

            EmbedColor: int = COLOR_STANDARD_ROLL
            CritText  : str = ""
            if Outcome.IsCriticalHit:
                EmbedColor = COLOR_CRITICAL_HIT
                CritText   = "\n\n🎯 **Critical Hit!**"

            elif Outcome.IsCriticalMiss:
                EmbedColor = COLOR_CRITICAL_MISS
                CritText   = "\n\n💥 **Critical Miss!**"

            ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharName}: {AbilityName} Check", description = f"{Outcome.Breakdown}\n\n# **{Outcome.Total}**{CritText}", color = EmbedColor)
            ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
            ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E Check")
            await Context.send(embed = ResponseEmbed)
            return

        SkillTitle, AssocAbil, SkillMod, TierName = self.StateService.GetSkillModifier(DetailData, FirstToken)
        RollFormula = f"1d20{'+' if SkillMod >= 0 else ''}{SkillMod} {TrailingFlags}".strip()
        Outcome     = self.DiceRoller.EvaluateRoll(RollFormula)

        EmbedColor = COLOR_STANDARD_ROLL
        CritText   = ""
        if Outcome.IsCriticalHit:
            EmbedColor = COLOR_CRITICAL_HIT
            CritText   = "\n\n🎯 **Critical Hit!**"

        elif Outcome.IsCriticalMiss:
            EmbedColor = COLOR_CRITICAL_MISS
            CritText   = "\n\n💥 **Critical Miss!**"

        TierNote: str = f" ({TierName})" if (TierName != "None") else ""
        ResponseEmbed = Discord.Embed(title = f"{CharName}: {SkillTitle} Check{TierNote}", description = f"{Outcome.Breakdown}\n\n# **{Outcome.Total}**{CritText}", color = EmbedColor)
        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E Skill Check ({AssocAbil})")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "save", aliases = ["s"])
    @Commands.check(CheckDNDPrefix)
    async def SaveCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        Tokens: list[str] = ArgumentsText.strip().split()
        if not Tokens:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}s <ability> [flags]`")
            return

        AbilityQuery : str  = Tokens[0].lower()
        TrailingFlags: str  = " ".join(Tokens[1:])
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharName     : str  = str(ActiveRecord.get("Name", "Hero"))

        AbilityName, SaveMod, IsProf = self.StateService.GetSavingThrowModifier(DetailData, AbilityQuery)
        RollFormula  : str           = f"1d20{'+' if SaveMod >= 0 else ''}{SaveMod} {TrailingFlags}".strip()
        Outcome      : DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(RollFormula)

        EmbedColor: int = COLOR_STANDARD_ROLL
        CritText  : str = ""
        if Outcome.IsCriticalHit:
            EmbedColor = COLOR_CRITICAL_HIT
            CritText   = "\n\n🎯 **Critical Hit!**"

        elif Outcome.IsCriticalMiss:
            EmbedColor = COLOR_CRITICAL_MISS
            CritText   = "\n\n💥 **Critical Miss!**"

        ProfNote: str = " *(Proficient)*" if IsProf else ""
        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharName}: {AbilityName} Saving Throw{ProfNote}", description = f"{Outcome.Breakdown}\n\n# **{Outcome.Total}**{CritText}", color = EmbedColor)
        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E Saving Throw")
        await Context.send(embed = ResponseEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(CheckCommands(BotInstance))

