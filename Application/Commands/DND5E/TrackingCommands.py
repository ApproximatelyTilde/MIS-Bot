import typing                             as Typing
import discord                            as Discord
import discord.ext.commands               as Commands
import Configuration.Config               as Config
import Services.DebugService              as Debug
import Services.CharacterStateService     as CharacterStateService

COLOR_TRACKING_EMBED: int = 0x0030A6
COLOR_HEALING_EMBED : int = 0x005E00
COLOR_DAMAGE_EMBED  : int = 0xA60000
COLOR_ERROR_EMBED   : int = 0xA60000

def CheckDNDPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND)

class TrackingCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterStateService.CharacterStateService] = None) -> None:
        self.BotInstance : Commands.Bot                                = BotInstance
        self.StateService: CharacterStateService.CharacterStateService = StateService if (StateService is not None) else CharacterStateService.CharacterStateService()

    @Commands.command(name = "hp")
    @Commands.check(CheckDNDPrefix)
    async def HitPointsCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        Tokens      : list[str] = ArgumentsText.strip().split()
        DetailData  : dict      = ActiveRecord.get("DetailData", {})
        CharName    : str       = str(ActiveRecord.get("Name", "Hero"))
        MaxHitPoints: int       = int(DetailData.get("HitPoints", {}).get("MaxHitPoints", 10))

        if (len(Tokens) >= 2) and (Tokens[0].lower() in ("temp", "t")):
            try:
                TempAmount: int = int(Tokens[1])
                _, CurrentHP, NewTemp = self.StateService.ModifyHitPoints(DetailData, TempAmount, IsTemp = True)
                EmbedColor = COLOR_TRACKING_EMBED
                ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharName}: Temporary Hit Points", description = f"Set temporary HP to **{NewTemp}**.\nCurrent HP: **{CurrentHP}/{MaxHitPoints}**", color = EmbedColor)
                await Context.send(embed = ResponseEmbed)
                return

            except ValueError:
                await Context.send(f"Invalid temporary HP value: `{Tokens[1]}`")
                return

        FirstToken: str = Tokens[0]
        try:
            if FirstToken.startswith("+"):
                DeltaAmount: int = int(FirstToken[1:])
                OldHP, NewHP, TempHP = self.StateService.ModifyHitPoints(DetailData, DeltaAmount)
                EmbedColor = COLOR_HEALING_EMBED
                DescriptionText = f"Healed **+{DeltaAmount}** HP.\n**{OldHP}** ➔ **{NewHP}** / {MaxHitPoints}"

            elif FirstToken.startswith("-"):
                DeltaAmount = -int(FirstToken[1:])
                OldHP, NewHP, TempHP = self.StateService.ModifyHitPoints(DetailData, DeltaAmount)
                EmbedColor = COLOR_DAMAGE_EMBED
                TempNote = f" (Temp HP remaining: {TempHP})" if (TempHP > 0) else ""
                DescriptionText = f"Took **{abs(DeltaAmount)}** damage.\n**{OldHP}** ➔ **{NewHP}** / {MaxHitPoints}{TempNote}"

            else:
                NewSetHP: int = int(FirstToken)
                OldHP = int(DetailData.get("HitPoints", {}).get("CurrentHitPoints", 10))
                DetailData.get("HitPoints", {})["CurrentHitPoints"] = max(0, min(MaxHitPoints, NewSetHP))
                EmbedColor = COLOR_TRACKING_EMBED
                DescriptionText = f"Current HP set to **{NewSetHP}** / {MaxHitPoints} (was {OldHP})"

            ResponseEmbed = Discord.Embed(title = f"{CharName}: Hit Points Updated", description = DescriptionText, color = EmbedColor)
            ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E Resource Tracking")
            await Context.send(embed = ResponseEmbed)

        except ValueError:
            await Context.send(f"Invalid HP modifier: `{FirstToken}`. Use e.g. `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}hp -12`, `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}hp +8`, or `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}hp temp 5`.")

    @Commands.command(name = "slot")
    @Commands.check(CheckDNDPrefix)
    async def SpellSlotCommand(self, Context: Commands.Context, LevelNumber: int, DeltaAmount: int = -1) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        DetailData: dict = ActiveRecord.get("DetailData", {})
        CharName  : str  = str(ActiveRecord.get("Name", "Hero"))

        AvailableSlots, TotalSlots = self.StateService.ModifySpellSlot(DetailData, LevelNumber, -DeltaAmount)
        if (TotalSlots == 0):
            await Context.send(f"{CharName} has no spell slots for Level {LevelNumber}.")
            return

        UsedSlots: int = TotalSlots - AvailableSlots
        SlotPills: str = " ".join("●" for _ in range(AvailableSlots)) + " " + " ".join("○" for _ in range(UsedSlots))
        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharName}: Level {LevelNumber} Spell Slots", description = f"Slots: `[{SlotPills.strip()}]`\n**{AvailableSlots} / {TotalSlots}** remaining", color = COLOR_TRACKING_EMBED)
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "rest")
    @Commands.check(CheckDNDPrefix)
    async def RestCommand(self, Context: Commands.Context, RestType: str = "long") -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        DetailData: dict = ActiveRecord.get("DetailData", {})
        CharName  : str  = str(ActiveRecord.get("Name", "Hero"))

        RestResult: dict = self.StateService.ApplyRest(DetailData, RestType)
        if (RestResult.get("RestType") == "Long"):
            DescriptionText: str = f"**Long Rest Completed!**\n• Hit points restored to maximum (**{RestResult.get('HP')}** HP)\n• All spell slots replenished\n• Hit dice recovered"

        else:
            DescriptionText = f"**Short Rest Completed!**\n• Short-rest features and Pact Magic slots replenished"

        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharName}: Rest Completed", description = DescriptionText, color = COLOR_HEALING_EMBED)
        ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E Rest System")
        await Context.send(embed = ResponseEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(TrackingCommands(BotInstance))

