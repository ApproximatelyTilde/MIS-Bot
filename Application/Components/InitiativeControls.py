import typing                           as Typing
import discord                          as Discord
import Services.DebugService            as Debug
import Services.EncounterManagerService as EncounterManager

class InitiativeControlsView(Discord.ui.View):
    def __init__(self, EncounterManagerInstance: EncounterManager.EncounterManagerService, ChannelID: int | str) -> None:
        super().__init__(timeout = 300.0)
        self.EncounterManager: EncounterManager.EncounterManagerService = EncounterManagerInstance
        self.ChannelID       : str                                      = str(ChannelID)

    @Discord.ui.button(label = "Prev", style = Discord.ButtonStyle.secondary, emoji = "◀️")
    async def PreviousTurnButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(self.ChannelID)
        if (Encounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        Encounter.PreviousTurn()
        await self.EncounterManager.SaveEncounterAsync(self.ChannelID)
        UpdatedEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Encounter)
        await Interaction.response.edit_message(embed = UpdatedEmbed, view = self)

    @Discord.ui.button(label = "Next", style = Discord.ButtonStyle.primary, emoji = "▶️")
    async def NextTurnButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        Encounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(self.ChannelID)
        if (Encounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        Encounter.AdvanceTurn()
        await self.EncounterManager.SaveEncounterAsync(self.ChannelID)
        UpdatedEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(Encounter)
        await Interaction.response.edit_message(embed = UpdatedEmbed, view = self)

    @Discord.ui.button(label = "End", style = Discord.ButtonStyle.danger, emoji = "⏹️")
    async def EndCombatButton(self, Interaction: Discord.Interaction, Button: Discord.ui.Button) -> None:
        EndedEncounter: Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.EndEncounterAsync(self.ChannelID)
        if (EndedEncounter is None):
            await Interaction.response.send_message("No active combat encounter found in this channel.", ephemeral = True)
            return

        for ChildControl in self.children:
            ChildControl.disabled = True

        EndEmbed: Discord.Embed = self.EncounterManager.FormatEncounterEmbed(EndedEncounter)
        await Interaction.response.edit_message(embed = EndEmbed, view = self)
