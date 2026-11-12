import typing                                   as Typing
import discord                                  as Discord
import discord.ext.commands                     as Commands
import Runtime.Configuration.Config             as Config
import Runtime.Services.CharacterStateService   as CharacterState
import Runtime.Services.EncounterManagerService as EncounterManager

COLOR_TRACKING_EMBED: int = 0x0030A6
COLOR_HEALING_EMBED : int = 0x005E00
COLOR_DAMAGE_EMBED  : int = 0xA60000
COLOR_ERROR_EMBED   : int = 0xA60000

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance: Typing.Any = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)

class TrackingCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterState.CharacterStateService] = None, EncounterManagerInstance: Typing.Optional[EncounterManager.EncounterManagerService] = None) -> None:
        self.BotInstance     : Commands.Bot                                  = BotInstance
        self.StateService    : CharacterState.CharacterStateService          = StateService if (StateService is not None) else (getattr(BotInstance, "CharacterStateService", None) or CharacterState.CharacterStateService())
        self.EncounterManager: EncounterManager.EncounterManagerService = EncounterManagerInstance if (EncounterManagerInstance is not None) else (getattr(BotInstance, "EncounterManager", None) or EncounterManager.EncounterManagerService(PlatformClientInstance = self.StateService.PlatformClient))

    async def SyncHitPointsToEncounter(self, ChannelID: int | str, CharacterID: str, DetailData: dict) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(ChannelID)
        if (Encounter is None) or (not CharacterID):
            return

        HPBlock: dict = DetailData.get("HitPoints", {})
        CurHP  : int  = int(HPBlock.get("CurrentHitPoints", 10))
        TempHP : int  = int(HPBlock.get("TemporaryHitPoints", 0))
        Updated: bool = False
        for Combatant in Encounter.Combatants:
            if (Combatant.CharacterID == CharacterID) or (Combatant.ID == CharacterID):
                Combatant.CurrentHitPoints   = CurHP
                Combatant.TemporaryHitPoints = TempHP
                Updated                      = True

        if Updated:
            await self.EncounterManager.SaveEncounterAsync(ChannelID)

    @Commands.command(name = "hp")
    @Commands.check(CheckDND5EPrefix)
    async def HitPointsCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Context.prefix}character <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        Tokens       : list[str] = ArgumentsText.strip().split()
        DetailData   : dict      = ActiveRecord.get("DetailData", {})
        CharacterName: str       = str(ActiveRecord.get("Name", "Hero"))
        MaxHitPoints : int       = int(DetailData.get("HitPoints", {}).get("MaxHitPoints", 10))

        CharacterID : str       = str(ActiveRecord.get("ID", ""))

        if (len(Tokens) >= 2) and (Tokens[0].lower() in ("temp", "t")):
            try:
                TemporaryAmount: int = int(Tokens[1])
                _, CurrentHP, NewTemp = self.StateService.ModifyHitPoints(DetailData, TemporaryAmount, IsTemporary = True)
                await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
                await self.SyncHitPointsToEncounter(Context.channel.id, CharacterID, DetailData)
                ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Temporary Hit Points", description = f"Set temporary HP to **{NewTemp}**.\nCurrent HP: **{CurrentHP}/{MaxHitPoints}**", color = COLOR_TRACKING_EMBED)
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
                EmbedColor: Typing.Any = COLOR_HEALING_EMBED
                ExtraNotice: str     = "\n✨ **Regained consciousness!** Death saving throws reset." if ((OldHP == 0) and (NewHP > 0)) else ""
                DescriptionText: str = f"Healed **+{DeltaAmount}** HP.\n**{OldHP}** ➔ **{NewHP}** / {MaxHitPoints}{ExtraNotice}"

            elif FirstToken.startswith("-"):
                DeltaAmount = -int(FirstToken[1:])
                OldHP, NewHP, TempHP = self.StateService.ModifyHitPoints(DetailData, DeltaAmount)
                EmbedColor           = COLOR_DAMAGE_EMBED
                TemporaryNote: str        = f" (Temp HP remaining: {TempHP})" if (TempHP > 0) else ""
                DeathNote: str       = ""
                if (OldHP == 0):
                    FailCount: int = int(DetailData.get("DeathSaves", {}).get("FailureCount", 0))
                    DeathNote      = f"\n⚠️ **Took damage at 0 HP!** Recorded death save failure. ({FailCount}/3 Failures)"
                    if (FailCount >= 3):
                        DeathNote += f"\n💀 **{CharacterName} has died from 3 death save failures!**"

                DescriptionText = f"Took **{abs(DeltaAmount)}** damage.\n**{OldHP}** ➔ **{NewHP}** / {MaxHitPoints}{TemporaryNote}{DeathNote}"

            else:
                NewSetHP: int = int(FirstToken)
                OldHP: int = int(DetailData.get("HitPoints", {}).get("CurrentHitPoints", 10))
                DetailData.get("HitPoints", {})["CurrentHitPoints"] = max(0, min(MaxHitPoints, NewSetHP))
                if (OldHP == 0) and (NewSetHP > 0):
                    DetailData["DeathSaves"] = {
                        "SuccessCount": 0,
                        "FailureCount": 0
                    }

                EmbedColor      = COLOR_TRACKING_EMBED
                DescriptionText = f"Current HP set to **{NewSetHP}** / {MaxHitPoints} (was {OldHP})"

            await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
            await self.SyncHitPointsToEncounter(Context.channel.id, CharacterID, DetailData)
            ResponseEmbed = Discord.Embed(title = f"{CharacterName}: Hit Points Updated", description = DescriptionText, color = EmbedColor)
            ResponseEmbed.set_footer(text = f"Tally │ Dungeons & Dragons Resource Tracking")
            await Context.send(embed = ResponseEmbed)

        except ValueError:
            await Context.send(f"Invalid HP modifier: `{FirstToken}`. Use e.g. `{Context.prefix}hp -12`, `{Context.prefix}hp +8`, or `{Context.prefix}hp temp 5`.")

    @Commands.command(name = "slot")
    @Commands.check(CheckDND5EPrefix)
    async def SpellSlotCommand(self, Context: Commands.Context, LevelNumber: int, DeltaAmount: int = -1) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharacterName: str  = str(ActiveRecord.get("Name", "Hero"))

        AvailableSlots, TotalSlots = self.StateService.ModifySpellSlot(DetailData, LevelNumber, -DeltaAmount)
        if (TotalSlots == 0):
            await Context.send(f"{CharacterName} has no spell slots for Level {LevelNumber}.")
            return

        await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
        UsedSlots    : int           = TotalSlots - AvailableSlots
        SlotPills    : str           = " ".join("●" for _ in range(AvailableSlots)) + " " + " ".join("○" for _ in range(UsedSlots))
        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Level {LevelNumber} Spell Slots", description = f"Slots: `[{SlotPills.strip()}]`\n**{AvailableSlots} / {TotalSlots}** remaining", color = COLOR_TRACKING_EMBED)
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "rest")
    @Commands.check(CheckDND5EPrefix)
    async def RestCommand(self, Context: Commands.Context, RestType: str = "long") -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharacterName: str  = str(ActiveRecord.get("Name", "Hero"))

        RestResult: dict = self.StateService.ApplyRest(DetailData, RestType)
        await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
        if (RestResult.get("RestType") == "Long"):
            DescriptionText: str = f"**Long Rest Completed!**\n• Hit points restored to maximum (**{RestResult.get("HP")}** HP)\n• All spell slots replenished\n• Hit dice recovered (up to half total)\n• Death saving throws reset"

        else:
            DescriptionText = f"**Short Rest Completed!**\n• Short-rest features and Pact Magic slots replenished\n• Spend hit dice with `{Context.prefix}hd spend [N] [die]`"

        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Rest Completed", description = DescriptionText, color = COLOR_HEALING_EMBED)
        ResponseEmbed.set_footer(text = f"Tally │ Dungeons & Dragons Rest System")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "hd", aliases = ["hitdice"])
    @Commands.check(CheckDND5EPrefix)
    async def HitDiceCommand(self, Context: Commands.Context, *, ArgumentsText: Typing.Optional[str] = None) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Context.prefix}character <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharacterName: str  = str(ActiveRecord.get("Name", "Hero"))

        if (ArgumentsText is None):
            PoolList      : list[dict[str, Typing.Any]] = self.StateService.GetHitDicePool(DetailData)
            TotalAvailable: int                         = sum(int(P.get("Available", 0)) for P in PoolList)
            TotalPool     : int                         = sum(int(P.get("Total", 0)) for P in PoolList)
            PoolLines     : list[str]                   = [f"• **d{P.get("HitDie")}** ({P.get("ClassName")}): **{P.get("Available")} / {P.get("Total")}** available" for P in PoolList]
            Description   : str                         = "\n".join(PoolLines) + f"\n\n**Total:** {TotalAvailable} / {TotalPool} Hit Dice\nSpend with `{Context.prefix}hd spend [N] [die]`."
            PoolEmbed     : Discord.Embed               = Discord.Embed(title = f"{CharacterName}: Hit Dice Pool", description = Description, color = COLOR_TRACKING_EMBED)
            PoolEmbed.set_footer(text = f"Tally │ Dungeons & Dragons Hit Dice Tracking ({Context.prefix}hd)")
            await Context.send(embed = PoolEmbed)
            return

        TokensList  : list[str] = ArgumentsText.strip().split()
        FirstKeyword: str       = TokensList[0].lower()

        if (FirstKeyword == "reset"):
            self.StateService.ResetHitDice(DetailData)
            await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
            ResetEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Hit Dice Reset", description = "All hit dice have been restored to maximum.", color = COLOR_HEALING_EMBED)
            await Context.send(embed = ResetEmbed)
            return

        if (FirstKeyword == "set") and (len(TokensList) >= 3):
            try:
                CurrentValue: int                  = int(TokensList[1])
                MaxValue    : int                  = int(TokensList[2])
                DieTypeArg  : Typing.Optional[str] = TokensList[3] if (len(TokensList) >= 4) else None
                self.StateService.SetHitDice(DetailData, CurrentValue = CurrentValue, MaxValue = MaxValue, DieType = DieTypeArg)
                await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
                SetEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Hit Dice Updated", description = f"Hit dice set to **{CurrentValue} / {MaxValue}**.", color = COLOR_TRACKING_EMBED)
                await Context.send(embed = SetEmbed)
                return

            except ValueError:
                await Context.send(f"Invalid parameters for set: `{ArgumentsText}`. Usage: `{Context.prefix}hd set <current> <max> [die_type]`")
                return

        RemainingTokens: list[str]            = TokensList[1:] if (FirstKeyword == "spend") else TokensList
        CountToSpend   : int                  = 1
        TargetDieType  : Typing.Optional[str] = None

        if RemainingTokens:
            if RemainingTokens[0].isdigit():
                CountToSpend = int(RemainingTokens[0])
                if (len(RemainingTokens) >= 2):
                    TargetDieType = RemainingTokens[1]

            else:
                TargetDieType = RemainingTokens[0]
                if (len(RemainingTokens) >= 2) and RemainingTokens[1].isdigit():
                    CountToSpend = int(RemainingTokens[1])

        PoolList              = self.StateService.GetHitDicePool(DetailData)
        TotalAvailableHD: int = 0
        if (TargetDieType is not None):
            CleanDieStr: str = TargetDieType.strip().lower()
            if CleanDieStr.startswith("d"):
                CleanDieStr = CleanDieStr[1:]

            for P in PoolList:
                if (str(P.get("HitDie")) == CleanDieStr):
                    TotalAvailableHD += int(P.get("Available", 0))

        else:
            TotalAvailableHD = sum(int(P.get("Available", 0)) for P in PoolList)

        if (TotalAvailableHD < CountToSpend):
            ErrorEmbed: Discord.Embed = Discord.Embed(title = "Insufficient Hit Dice", description = f"{CharacterName} only has **{TotalAvailableHD}** hit dice available (requested {CountToSpend}).", color = COLOR_ERROR_EMBED)
            await Context.send(embed = ErrorEmbed)
            return

        TotalHealed, OldHP, RollsDetails, NewHP, MaxHP = self.StateService.SpendHitDice(DetailData, Count = CountToSpend, DieType = TargetDieType)
        await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
        RollBreakdownLines: list[str]                   = [f"• Rolled `1d{R.get("Die")}` ({R.get("Roll")}) + {R.get("ConstitutionModifier")} (CON) = **+{R.get("Total")}** HP" for R in RollsDetails]
        UpdatedPool       : list[dict[str, Typing.Any]] = self.StateService.GetHitDicePool(DetailData)
        RemainingSummary  : str                         = ", ".join(f"d{P.get("HitDie")}: {P.get("Available")}/{P.get("Total")}" for P in UpdatedPool)

        DescriptionLines: list[str] = [f"Spent **{CountToSpend}** Hit Dice and healed **+{TotalHealed}** HP.", f"**Hit Points:** **{OldHP}** ➔ **{NewHP}** / {MaxHP}", "", "**Roll Details:**", *RollBreakdownLines, "", f"**Remaining Hit Dice:** {RemainingSummary}"]

        SpendEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Short Rest Healing", description = "\n".join(DescriptionLines), color = COLOR_HEALING_EMBED)
        SpendEmbed.set_footer(text = f"Tally │ Dungeons & Dragons Hit Dice ({Context.prefix}hd)")
        await Context.send(embed = SpendEmbed)

    @Commands.command(name = "ds", aliases = ["deathsave"])
    @Commands.check(CheckDND5EPrefix)
    async def DeathSaveCommand(self, Context: Commands.Context, *, ActionArgument: Typing.Optional[str] = None) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Context.prefix}character <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharacterName: str  = str(ActiveRecord.get("Name", "Hero"))

        ActionCleaned: str = ActionArgument.strip().lower() if (ActionArgument is not None) else "roll"

        if ActionCleaned in ("reset", "clear"):
            self.StateService.ModifyDeathSaves(DetailData, Reset = True)
            await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
            ResetEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Death Saves Reset", description = "Death saving throws reset to 0 successes and 0 failures.", color = COLOR_TRACKING_EMBED)
            await Context.send(embed = ResetEmbed)
            return

        if ActionCleaned in ("success", "s", "+"):
            SuccessCount, FailureCount = self.StateService.ModifyDeathSaves(DetailData, DeltaSuccess = 1)
            await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
            SuccessPips, FailurePips   = self.StateService.FormatDeathSavePips(SuccessCount, FailureCount)
            StateLabel: Typing.Any = "Stable!" if (SuccessCount >= 3) else "Dying"
            SuccessEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Death Save Success Recorded", description = f"Successes: `[{SuccessPips}]` ({SuccessCount}/3)\nFailures:  `[{FailurePips}]` ({FailureCount}/3)\n\n**Status:** {StateLabel}", color = COLOR_HEALING_EMBED if (SuccessCount >= 3) else COLOR_TRACKING_EMBED)
            await Context.send(embed = SuccessEmbed)
            return

        if ActionCleaned in ("fail", "failure", "f", "-"):
            SuccessCount, FailureCount = self.StateService.ModifyDeathSaves(DetailData, DeltaFailure = 1)
            await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
            SuccessPips, FailurePips   = self.StateService.FormatDeathSavePips(SuccessCount, FailureCount)
            StateLabel                 = "💀 Dead!" if (FailureCount >= 3) else "Dying"
            FailEmbed: Discord.Embed   = Discord.Embed(title = f"{CharacterName}: Death Save Failure Recorded", description = f"Successes: `[{SuccessPips}]` ({SuccessCount}/3)\nFailures:  `[{FailurePips}]` ({FailureCount}/3)\n\n**Status:** {StateLabel}", color = COLOR_DAMAGE_EMBED)
            await Context.send(embed = FailEmbed)
            return

        RollOutcome: dict[str, Typing.Any] = self.StateService.RollDeathSave(DetailData)
        await self.StateService.SaveStateToPlatformAsync(ActiveRecord)
        EmbedColor : int                   = COLOR_TRACKING_EMBED
        if RollOutcome["RegainedConscious"] or RollOutcome["IsStable"]:
            EmbedColor = COLOR_HEALING_EMBED

        elif RollOutcome["IsDead"] or RollOutcome["IsNatural1"]:
            EmbedColor = COLOR_DAMAGE_EMBED

        DescriptionLines: list[str] = [f"**D20 Roll:** **{RollOutcome["RollValue"]}**" + (" *(Natural 20!)*" if (bool(RollOutcome["IsNatural20"])) else (" *(Natural 1!)*" if (bool(RollOutcome["IsNatural1"])) else "")), "", f"**Successes:** `[{RollOutcome["SuccessPips"]}]` ({RollOutcome["SuccessCount"]}/3)", f"**Failures:**  `[{RollOutcome["FailurePips"]}]` ({RollOutcome["FailureCount"]}/3)", "", f"**Status:** {RollOutcome["StatusMessage"]}"]

        if RollOutcome["RegainedConscious"]:
            DescriptionLines.append("\n✨ **Character has regained consciousness with 1 HP!**")

        elif RollOutcome["IsStable"]:
            DescriptionLines.append("\n🩺 **Character has stabilized!**")

        elif RollOutcome["IsDead"]:
            DescriptionLines.append("\n💀 **Character has succumbed to death!**")

        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Death Saving Throw", description = "\n".join(DescriptionLines), color = EmbedColor)
        ResponseEmbed.set_footer(text = f"Tally │ Dungeons & Dragons Death Saves ({Context.prefix}ds)")
        await Context.send(embed = ResponseEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(TrackingCommands(BotInstance))
