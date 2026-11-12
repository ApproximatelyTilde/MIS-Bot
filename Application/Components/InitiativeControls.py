import typing                            as Typing
import discord                           as Discord
import Services.DebugService             as Debug
import Services.EncounterManagerService  as EncounterManagerService

class InitiativeControlsView(Discord.ui.View):
    def __init__(self, EncounterManagerInstance: EncounterManagerService.EncounterManagerService, ChannelID: int | str) -> None:
        super().__init__(timeout = 300.0)
        self.EncounterManager: EncounterManagerService.EncounterManagerService = EncounterManagerInstance
        self.ChannelID       : str                                             = str(ChannelID)

    @Discord.ui.button(label = "Prev", style = Discord.ButtonStyle.secondary, emoji = "◀️")
    async def PreviousTurnButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(self.ChannelID)
        if (Encounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        Encounter.PreviousTurn()
        UpdatedEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Encounter)
        await Interaction.response.edit_message(embed = UpdatedEmbed, view = self)

    @Discord.ui.button(label = "Next", style = Discord.ButtonStyle.primary, emoji = "▶️")
    async def NextTurnButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        Encounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(self.ChannelID)
        if (Encounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        Encounter.AdvanceTurn()
        UpdatedEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Encounter)
        await Interaction.response.edit_message(embed = UpdatedEmbed, view = self)

    @Discord.ui.button(label = "End", style = Discord.ButtonStyle.danger, emoji = "⏹️")
    async def EndCombatButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        EndedEncounter: Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.EndEncounter(self.ChannelID)
        if (EndedEncounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        for ChildControl in self.children:
            ChildControl.disabled = True

        EndEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(EndedEncounter)
        await Interaction.response.edit_message(embed = EndEmbed, view = self)

