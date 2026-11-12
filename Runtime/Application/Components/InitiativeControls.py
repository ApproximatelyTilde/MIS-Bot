import typing                                   as Typing
import discord                                  as Discord
import Runtime.Services.EncounterManagerService as EncounterManager

class PopcornTargetSelect(Discord.ui.Select):
    def __init__(self, EncounterManagerInstance: EncounterManager.EncounterManagerService, ChannelID: str, OptionsList: list[Discord.SelectOption], CommandPrefix: str) -> None:
        super().__init__(placeholder = "Pass Turn To…", options = OptionsList[:25], row = 0)
        self.EncounterManager: EncounterManager.EncounterManagerService = EncounterManagerInstance
        self.ChannelID       : str                                      = ChannelID
        self.CommandPrefix   : str                                      = CommandPrefix

    async def callback(self, Interaction: Discord.Interaction) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(self.ChannelID)
        if (Encounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        ActiveCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.GetActiveCombatant()
        CallerID       : str                                              = str(Interaction.user.id)
        IsDM           : bool                                             = False
        if isinstance(Interaction.user, Discord.Member):
            if Interaction.user.guild_permissions.administrator:
                IsDM = True

            else:
                RoleNames: set[str] = {R.name.lower() for R in Interaction.user.roles}
                IsDM                = bool(RoleNames.intersection({"dm", "dungeon master", "gm", "game master", "referee", "macro master"}))

        if (ActiveCombatant is not None) and (ActiveCombatant.ControllerDiscordID is not None) and (ActiveCombatant.ControllerDiscordID != CallerID) and (not IsDM):
            await Interaction.response.send_message(f"Only **{ActiveCombatant.Name}**'s controller or a DM/GM may pass the turn.", ephemeral = True)
            return

        SelectedID: str = self.values[0]
        TargetCombatant, _, RoundWrapped = Encounter.PassTurn(SelectedID)
        if (TargetCombatant is None):
            await Interaction.response.send_message("Could not pass turn to that combatant (already acted this round).", ephemeral = True)
            return

        await self.EncounterManager.SaveEncounterAsync(self.ChannelID)
        UpdatedView : InitiativeControlsView = InitiativeControlsView(self.EncounterManager, self.ChannelID, CommandPrefix = self.CommandPrefix)
        UpdatedEmbed: Discord.Embed          = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = CallerID, IsDungeonMaster = IsDM, CommandPrefix = self.CommandPrefix)

        ContentText: Typing.Optional[str] = None
        if (TargetCombatant.ControllerDiscordID is not None):
            RoundNote  : str = f" (New Round {Encounter.RoundNumber}!)" if RoundWrapped else ""
            ContentText      = f"<@{TargetCombatant.ControllerDiscordID}>, it's **{TargetCombatant.Name}**'s turn!{RoundNote}"

        await Interaction.response.edit_message(content = ContentText, embed = UpdatedEmbed, view = UpdatedView)

class InitiativeControlsView(Discord.ui.View):
    def __init__(self, EncounterManagerInstance: EncounterManager.EncounterManagerService, ChannelID: int | str, CommandPrefix: Typing.Optional[str] = None) -> None:
        super().__init__(timeout = 300.0)
        self.EncounterManager: EncounterManager.EncounterManagerService = EncounterManagerInstance
        self.ChannelID       : str                                      = str(ChannelID)
        Encounter            : Typing.Optional[EncounterManager.CombatEncounter] = self.EncounterManager.GetEncounter(self.ChannelID)
        self.CommandPrefix   : str                                      = CommandPrefix if (CommandPrefix is not None) else ("." if ((Encounter is not None) and (Encounter.GameSystem == "MGT2E")) else "!")

        if (Encounter is not None) and (Encounter.InitiativeMode == "Popcorn"):
            self.clear_items()
            RemainingList: list[EncounterManager.CombatantEntry] = Encounter.GetRemainingCombatants()
            SelectOptions: list[Discord.SelectOption]            = []
            for Combatant in RemainingList[:25]:
                LabelText: str = f"{Combatant.Name}"[:100]
                SelectOptions.append(Discord.SelectOption(label = LabelText, value = Combatant.ID))

            if SelectOptions:
                self.add_item(PopcornTargetSelect(self.EncounterManager, self.ChannelID, SelectOptions, self.CommandPrefix))

            EndButton         : Discord.ui.Button = Discord.ui.Button(label = "End", style = Discord.ButtonStyle.danger, emoji = "⏹️", row = 1)
            EndButton.callback                    = self.EndCombatCallback
            self.add_item(EndButton)

    @Discord.ui.button(label = "Prev", style = Discord.ButtonStyle.secondary, emoji = "◀️")
    async def PreviousTurnButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(self.ChannelID)
        if (Encounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        Encounter.PreviousTurn()
        await self.EncounterManager.SaveEncounterAsync(self.ChannelID)
        UpdatedEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Interaction.user.id), CommandPrefix = self.CommandPrefix)
        await Interaction.response.edit_message(embed = UpdatedEmbed, view = self)

    @Discord.ui.button(label = "Next", style = Discord.ButtonStyle.primary, emoji = "▶️")
    async def NextTurnButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(self.ChannelID)
        if (Encounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        Encounter.AdvanceTurn()
        await self.EncounterManager.SaveEncounterAsync(self.ChannelID)
        UpdatedEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Encounter, ViewerDiscordID = str(Interaction.user.id), CommandPrefix = self.CommandPrefix)
        await Interaction.response.edit_message(embed = UpdatedEmbed, view = self)

    @Discord.ui.button(label = "End", style = Discord.ButtonStyle.danger, emoji = "⏹️")
    async def EndCombatButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        await self.EndCombatCallback(Interaction)

    async def EndCombatCallback(self, Interaction: Discord.Interaction) -> None:
        EndedEncounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.EndEncounterAsync(self.ChannelID)
        if (EndedEncounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        for ChildControl in self.children:
            if hasattr(ChildControl, "disabled"):
                ChildControl.disabled = True

        EndEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(EndedEncounter, CommandPrefix = self.CommandPrefix)
        await Interaction.response.edit_message(embed = EndEmbed, view = self)
