import typing                                       as Typing
import discord                                      as Discord
import discord.ui                                   as UserInterface
import pydantic                                     as Pydantic
import Runtime.Services.DiceService                 as Dice
import Runtime.Services.CharacterStateService       as CharacterState
import Runtime.Services.MGT2EStateService           as MGT2EState
import Runtime.Services.EncounterManagerService     as EncounterManager
import Runtime.Services.TargetResolverService       as TargetResolver
import Runtime.Application.Components.MGT2ERollView as MGT2ERollView
import Runtime.Application.Components.DND5ERollView as DND5ERollView

COLOR_DND5E_REQUEST: int = 0x0030A6
COLOR_MGT2E_REQUEST: int = 0x005E5E

class RollRequestSlot(Pydantic.BaseModel):
    model_config = Pydantic.ConfigDict(arbitrary_types_allowed = True)

    SlotID         : str
    DisplayName    : str
    AllowedUserID  : Typing.Optional[str]                             = None
    StrictUserOnly : bool                                             = False
    Combatant      : Typing.Optional[EncounterManager.CombatantEntry] = None
    CharacterRecord: Typing.Optional[dict[str, Typing.Any]]           = None
    IsCompleted    : bool                                             = False
    ResultSummary  : str                                              = ""

def IsMemberDungeonMaster(Interaction: Discord.Interaction) -> bool:
    if isinstance(Interaction.user, Discord.Member):
        if Interaction.user.guild_permissions.administrator:
            return True

        RoleNames: set[str] = {R.name.lower() for R in Interaction.user.roles}
        return bool(RoleNames.intersection({"dm", "dungeon master", "gm", "game master", "referee", "macro master"}))

    return False

class RollRequestSlotButton(UserInterface.Button):
    def __init__(self, Slot: RollRequestSlot, ParentView: "RollRequestView", RowIndex: int) -> None:
        LabelText : str                 = f"Roll ({Slot.DisplayName})"[:80] if (not Slot.IsCompleted) else f"Rolled ({Slot.DisplayName})"[:80]
        StyleValue: Discord.ButtonStyle = Discord.ButtonStyle.success if Slot.IsCompleted else Discord.ButtonStyle.primary
        super().__init__(label = LabelText, style = StyleValue, emoji = "✅" if Slot.IsCompleted else "🎲", disabled = Slot.IsCompleted, row = RowIndex)
        self.SlotID    : str               = Slot.SlotID
        self.ParentView: "RollRequestView" = ParentView

    async def callback(self, Interaction: Discord.Interaction) -> None:
        await self.ParentView.HandleSlotButtonClick(Interaction, self.SlotID)

class RollRequestView(UserInterface.View):
    def __init__(self, GameSystem: str, RollType: str, CheckQuery: str, RequesterName: str, TargetResolverInstance: TargetResolver.TargetResolverService, DiceRoller: Typing.Optional[Dice.DiceRollerService] = None, CharacteristicOverride: Typing.Optional[str] = None, TargetDifficultyOrDC: Typing.Optional[int] = None, AdvantageOrBoons: int = 0, SituationalModifier: int = 0, TargetSlots: Typing.Optional[list[RollRequestSlot]] = None) -> None:
        super().__init__(timeout = 600.0)
        self.GameSystem            : str                                  = GameSystem
        self.RollType              : str                                  = RollType
        self.CheckQuery            : str                                  = CheckQuery
        self.RequesterName         : str                                  = RequesterName
        self.TargetResolver        : TargetResolver.TargetResolverService = TargetResolverInstance
        self.DiceRoller            : Dice.DiceRollerService               = DiceRoller if (DiceRoller is not None) else Dice.DiceRollerService()
        self.CharacteristicOverride: Typing.Optional[str]                 = CharacteristicOverride
        self.TargetDifficultyOrDC  : Typing.Optional[int]                 = TargetDifficultyOrDC
        self.AdvantageOrBoons      : int                                  = AdvantageOrBoons
        self.SituationalModifier   : int                                  = SituationalModifier
        self.TargetSlots           : list[RollRequestSlot]                = TargetSlots if (TargetSlots is not None) else []
        self.OpenResults           : list[str]                            = []
        self.CompletedOpenCharacterIDs  : set[str]                             = set()
        self.RequestMessage        : Typing.Optional[Discord.Message]     = None

        self.RebuildControls()

    def RebuildControls(self) -> None:
        self.clear_items()
        if not self.TargetSlots:
            RollButton: UserInterface.Button = UserInterface.Button(label = "Roll", style = Discord.ButtonStyle.primary, emoji = "🎲", row = 0)
            RollButton.callback              = self.OnOpenRollClicked
            self.add_item(RollButton)

            EditButton: UserInterface.Button = UserInterface.Button(label = "Customize & Roll", style = Discord.ButtonStyle.secondary, emoji = "⚙️", row = 0)
            EditButton.callback              = self.OnOpenCustomizeClicked
            self.add_item(EditButton)
            return

        for Index, Slot in enumerate(self.TargetSlots[:20]):
            RowIndex: int = Index // 5
            self.add_item(RollRequestSlotButton(Slot, self, RowIndex))

    def BuildRequestEmbed(self) -> Discord.Embed:
        IsTraveller: bool = (self.GameSystem == "MGT2E")
        EmbedColor : int  = COLOR_MGT2E_REQUEST if IsTraveller else COLOR_DND5E_REQUEST

        if IsTraveller:
            StatLabel      : str = self.CharacteristicOverride or self.TargetResolver.MGT2EState.GetDefaultCharacteristicForSkill(self.CheckQuery)
            DifficultyValue: int = self.TargetDifficultyOrDC if (self.TargetDifficultyOrDC is not None) else MGT2EState.DEFAULT_DIFFICULTY_AVERAGE
            TitleText      : str = f"Roll Request: {self.CheckQuery.title()} ({StatLabel[:3].upper()})"
            ModDesc        : str = f"**Target Difficulty:** {DifficultyValue}"
            if (self.AdvantageOrBoons > 0):
                ModDesc += f" | **Boon (+{self.AdvantageOrBoons})**"

            elif (self.AdvantageOrBoons < 0):
                ModDesc += f" | **Bane ({self.AdvantageOrBoons})**"

        else:
            ModeLabel: str = "Saving Throw" if (self.RollType.lower() == "save") else "Check"
            TitleText      = f"Roll Request: {self.CheckQuery.title()} {ModeLabel}"
            ModDesc        = f"**Target DC:** {self.TargetDifficultyOrDC}" if (self.TargetDifficultyOrDC is not None) else "**Target DC:** Open"
            if (self.AdvantageOrBoons > 0):
                ModDesc += " | **Advantage**"

            elif (self.AdvantageOrBoons < 0):
                ModDesc += " | **Disadvantage**"

        if (self.SituationalModifier != 0):
            ModDesc += f" | **Modifier:** {self.SituationalModifier:+d}"

        RequestEmbed: Discord.Embed = Discord.Embed(title = TitleText, description = f"Requested by **{self.RequesterName}**\n{ModDesc}", color = EmbedColor)

        if self.TargetSlots:
            SlotLines: list[str] = []
            for Slot in self.TargetSlots:
                if Slot.IsCompleted:
                    SlotLines.append(f"✅ **{Slot.DisplayName}** — {Slot.ResultSummary}")

                else:
                    SlotLines.append(f"⏳ **{Slot.DisplayName}** — *Waiting for roll…*")

            RequestEmbed.add_field(name = "Targeted Characters", value = "\n".join(SlotLines)[:1020], inline = False)

        elif self.OpenResults:
            RequestEmbed.add_field(name = "Roll Results", value = "\n".join(self.OpenResults)[:1020], inline = False)

        else:
            RequestEmbed.add_field(name = "Roll Results", value = "*Click **Roll** below using your active character.*", inline = False)

        SystemFooter: str = "Mongoose Traveller" if IsTraveller else "Dungeons & Dragons"
        RequestEmbed.set_footer(text = f"Tally │ {SystemFooter} GM Roll Request")
        return RequestEmbed

    def ComputeMGT2ERollSummary(self, RecordOrCombatant: Typing.Any) -> tuple[MGT2EState.MGT2ERollOutcome, str]:
        MGT2EService   : MGT2EState.MGT2EStateService = self.TargetResolver.MGT2EState
        Characteristics: dict[str, int]               = {}
        Skills         : dict[str, int]               = {}

        if isinstance(RecordOrCombatant, dict):
            DetailData     : dict = RecordOrCombatant.get("DetailData", {})
            Characteristics       = DetailData.get("Characteristics", {})
            Skills                = DetailData.get("Skills", {})

        elif isinstance(RecordOrCombatant, EncounterManager.CombatantEntry):
            if (RecordOrCombatant.Characteristics is not None):
                Characteristics = RecordOrCombatant.Characteristics

            if (RecordOrCombatant.MonsterData is not None):
                Skills = RecordOrCombatant.MonsterData.get("Skills", {})

        QueryLower: str = self.CheckQuery.strip().lower()
        if QueryLower in MGT2EState.CHARACTERISTIC_LOOKUP:
            StatFullName: str = MGT2EState.CHARACTERISTIC_LOOKUP[QueryLower]
            StatDM      : int = MGT2EService.CalculateCharacteristicModifier(int(Characteristics.get(StatFullName, 7)))
            SkillMod    : int = 0

        else:
            StatFullName = self.CharacteristicOverride if (self.CharacteristicOverride is not None) else MGT2EService.GetDefaultCharacteristicForSkill(self.CheckQuery)
            StatDM       = MGT2EService.CalculateCharacteristicModifier(int(Characteristics.get(StatFullName, 7)))
            SkillMod     = MGT2EService.GetSkillModifier(Skills, self.CheckQuery)

        TotalMod  : int                         = StatDM + SkillMod + self.SituationalModifier
        DiffTarget: int                         = self.TargetDifficultyOrDC if (self.TargetDifficultyOrDC is not None) else MGT2EState.DEFAULT_DIFFICULTY_AVERAGE
        Outcome   : MGT2EState.MGT2ERollOutcome = MGT2EService.EvaluateRoll(Modifier = TotalMod, NetBoons = self.AdvantageOrBoons, TargetDifficulty = DiffTarget)
        Badge     : str                         = "✅ Success" if Outcome.IsSuccess else "❌ Failure"
        Summary   : str                         = f"**{Outcome.Total}** (Effect `{Outcome.Effect:+d}`) — {Badge}"
        return (Outcome, Summary)

    def ResolveMonsterModifierDND5E(self, MonsterData: dict[str, Typing.Any]) -> int:
        QueryLower: str = self.CheckQuery.strip().lower()
        AbilShortMap: dict[str, str] = {
            "strength"    : "str",
            "dexterity"   : "dex",
            "constitution": "con",
            "intelligence": "int",
            "wisdom"      : "wis",
            "charisma"    : "cha"
        }

        if (self.RollType.lower() == "save"):
            AbilityFullName: str        = CharacterState.ABILITY_ALIASES.get(QueryLower, "Dexterity")
            ShortKey       : str        = AbilShortMap.get(AbilityFullName.lower(), "dex")
            SavesDictionary: Typing.Any = MonsterData.get("save", {})
            if isinstance(SavesDictionary, dict) and (ShortKey in SavesDictionary):
                RawSaveValue: str = str(SavesDictionary[ShortKey]).replace("+", "").strip()
                if RawSaveValue.lstrip("-").isdigit():
                    return int(RawSaveValue)

            ScoreValue: int = int(MonsterData.get(ShortKey, 10))
            return (ScoreValue - 10) // 2

        if QueryLower in CharacterState.ABILITY_ALIASES:
            AbilityFullName = CharacterState.ABILITY_ALIASES[QueryLower]
            ShortKey        = AbilShortMap.get(AbilityFullName.lower(), "str")
            return (int(MonsterData.get(ShortKey, 10)) - 10) // 2

        ResolvedSkill   : str  = CharacterState.SKILL_ALIASES.get(QueryLower, QueryLower)
        SkillsDictionary: dict = MonsterData.get("skill", {})
        if isinstance(SkillsDictionary, dict):
            for SkillKey, SkillValue in SkillsDictionary.items():
                if (SkillKey.strip().lower() == ResolvedSkill):
                    RawSkillValue: str = str(SkillValue).replace("+", "").strip()
                    if RawSkillValue.lstrip("-").isdigit():
                        return int(RawSkillValue)

        MappedAbility: str = CharacterState.SKILL_ABILITY_MAPPING.get(ResolvedSkill, "Wisdom")
        ShortKey           = AbilShortMap.get(MappedAbility.lower(), "wis")
        return (int(MonsterData.get(ShortKey, 10)) - 10) // 2

    def ComputeDND5ERollSummary(self, RecordOrCombatant: Typing.Any) -> tuple[Dice.RollOutcome, str]:
        DNDService  : CharacterState.CharacterStateService = self.TargetResolver.CharacterState
        BaseModifier: int                                  = 0

        if isinstance(RecordOrCombatant, dict):
            DetailData: dict = RecordOrCombatant.get("DetailData", {})
            if (self.RollType.lower() == "save"):
                _, BaseModifier, _ = DNDService.GetSavingThrowModifier(DetailData, self.CheckQuery)

            elif self.CheckQuery.strip().lower() in CharacterState.ABILITY_ALIASES:
                _, _, BaseModifier = DNDService.GetAbilityModifier(DetailData, self.CheckQuery)
                if DNDService.HasJackOfAllTrades(DetailData):
                    BaseModifier += int(DetailData.get("ProficiencyBonus", 2)) // 2

            else:
                _, _, BaseModifier, _ = DNDService.GetSkillModifier(DetailData, self.CheckQuery)

        elif isinstance(RecordOrCombatant, EncounterManager.CombatantEntry) and (RecordOrCombatant.MonsterData is not None):
            BaseModifier = self.ResolveMonsterModifierDND5E(RecordOrCombatant.MonsterData)

        TotalMod: int              = BaseModifier + self.SituationalModifier
        DicePart: str              = "2d20kh1" if (self.AdvantageOrBoons > 0) else ("2d20kl1" if (self.AdvantageOrBoons < 0) else "1d20")
        Formula : str              = f"{DicePart}{"+" if (TotalMod >= 0) else ""}{TotalMod}"
        Outcome : Dice.RollOutcome = self.DiceRoller.EvaluateRoll(Formula)

        if (self.TargetDifficultyOrDC is not None):
            IsSuccess: bool = ((Outcome.Total >= self.TargetDifficultyOrDC) or Outcome.IsCriticalHit) and (not Outcome.IsCriticalMiss)
            Badge    : str  = " — ✅ Success" if IsSuccess else " — ❌ Failure"

        else:
            Badge = " — 🎯 Crit!" if Outcome.IsCriticalHit else (" — 💥 Crit Miss!" if Outcome.IsCriticalMiss else "")

        Summary: str = f"{Outcome.Breakdown} = **{Outcome.Total}**{Badge}"
        return (Outcome, Summary)

    async def HandleSlotButtonClick(self, Interaction: Discord.Interaction, SlotID: str) -> None:
        TargetSlot: Typing.Optional[RollRequestSlot] = None
        for Candidate in self.TargetSlots:
            if (Candidate.SlotID == SlotID):
                TargetSlot = Candidate
                break

        if (TargetSlot is None) or TargetSlot.IsCompleted:
            await Interaction.response.send_message("This roll slot has already been completed.", ephemeral = True)
            return

        CallerIDStr: str  = str(Interaction.user.id)
        IsDM       : bool = IsMemberDungeonMaster(Interaction)

        if TargetSlot.StrictUserOnly:
            if (TargetSlot.AllowedUserID != CallerIDStr):
                await Interaction.response.send_message(f"Only the mentioned player may roll for **{TargetSlot.DisplayName}**.", ephemeral = True)
                return

        else:
            if (TargetSlot.AllowedUserID is not None):
                if (TargetSlot.AllowedUserID != CallerIDStr) and (not IsDM):
                    await Interaction.response.send_message(f"Only **{TargetSlot.DisplayName}**'s controller or a DM/GM may click this roll.", ephemeral = True)
                    return

            elif not IsDM:
                await Interaction.response.send_message("Only a DM/GM may roll for uncontrolled entities.", ephemeral = True)
                return

        ChannelIDValue    : int | str = Interaction.channel.id if (Interaction.channel is not None) else 0
        IsMonsterCombatant: bool      = (TargetSlot.Combatant is not None) and (TargetSlot.Combatant.IsMonster or (TargetSlot.Combatant.EntityType == "Other")) and (TargetSlot.AllowedUserID is None)

        if (not IsMonsterCombatant) and ((TargetSlot.AllowedUserID == CallerIDStr) or TargetSlot.StrictUserOnly):
            IsValid, FreshRecord, GuardMessage = await self.TargetResolver.ValidateSystemGuard(Interaction.user.id, ChannelIDValue, self.GameSystem)
            if not IsValid:
                await Interaction.response.send_message(GuardMessage or f"Incompatible active character system for this `{self.GameSystem}` roll.", ephemeral = True)
                return

            if (TargetSlot.CharacterRecord is None) and (FreshRecord is not None):
                TargetSlot.CharacterRecord = FreshRecord

        RecordSource: Typing.Any = TargetSlot.CharacterRecord if (TargetSlot.CharacterRecord is not None) else TargetSlot.Combatant
        if (self.GameSystem == "MGT2E"):
            _, Summary = self.ComputeMGT2ERollSummary(RecordSource)

        else:
            _, Summary = self.ComputeDND5ERollSummary(RecordSource)

        TargetSlot.IsCompleted   = True
        TargetSlot.ResultSummary = Summary
        self.RebuildControls()
        await Interaction.response.edit_message(embed = self.BuildRequestEmbed(), view = self)

    async def OnOpenRollClicked(self, Interaction: Discord.Interaction) -> None:
        ChannelIDValue: int | str = Interaction.channel.id if (Interaction.channel is not None) else 0
        IsValid, ActiveRecord, GuardMessage = await self.TargetResolver.ValidateSystemGuard(Interaction.user.id, ChannelIDValue, self.GameSystem)
        if (not IsValid) or (ActiveRecord is None):
            await Interaction.response.send_message(GuardMessage or f"You do not have an active `{self.GameSystem}` character selected.", ephemeral = True)
            return

        CharacterID  : str = str(ActiveRecord.get("ID", Interaction.user.id))
        CharacterName: str = str(ActiveRecord.get("Name", Interaction.user.display_name))
        if CharacterID in self.CompletedOpenCharacterIDs:
            await Interaction.response.send_message(f"**{CharacterName}** has already rolled for this request.", ephemeral = True)
            return

        if (self.GameSystem == "MGT2E"):
            _, Summary = self.ComputeMGT2ERollSummary(ActiveRecord)

        else:
            _, Summary = self.ComputeDND5ERollSummary(ActiveRecord)

        self.CompletedOpenCharacterIDs.add(CharacterID)
        self.OpenResults.append(f"✅ **{CharacterName}** — {Summary}")
        await Interaction.response.edit_message(embed = self.BuildRequestEmbed(), view = self)

    async def OnOpenCustomizeClicked(self, Interaction: Discord.Interaction) -> None:
        ChannelIDValue: int | str = Interaction.channel.id if (Interaction.channel is not None) else 0
        IsValid, ActiveRecord, GuardMessage = await self.TargetResolver.ValidateSystemGuard(Interaction.user.id, ChannelIDValue, self.GameSystem)
        if (not IsValid) or (ActiveRecord is None):
            await Interaction.response.send_message(GuardMessage or f"You do not have an active `{self.GameSystem}` character selected.", ephemeral = True)
            return

        CharacterID  : str = str(ActiveRecord.get("ID", Interaction.user.id))
        CharacterName: str = str(ActiveRecord.get("Name", Interaction.user.display_name))

        async def OnInteractiveComplete(FinalInteraction: Discord.Interaction, OutcomeObject: Typing.Any, CheckLabel: str) -> None:
            if CharacterID not in self.CompletedOpenCharacterIDs:
                self.CompletedOpenCharacterIDs.add(CharacterID)
                if (self.GameSystem == "MGT2E"):
                    Badge: str = "✅ Success" if OutcomeObject.IsSuccess else "❌ Failure"
                    Line : str = f"✅ **{CharacterName}** (*{CheckLabel}*) — **{OutcomeObject.Total}** (Effect `{OutcomeObject.Effect:+d}`) — {Badge}"

                else:
                    Line = f"✅ **{CharacterName}** (*{CheckLabel}*) — {OutcomeObject.Breakdown} = **{OutcomeObject.Total}**"

                self.OpenResults.append(Line)
                if (self.RequestMessage is not None):
                    await self.RequestMessage.edit(embed = self.BuildRequestEmbed(), view = self)

        if (self.GameSystem == "MGT2E"):
            DifficultyValue: int                         = self.TargetDifficultyOrDC if (self.TargetDifficultyOrDC is not None) else MGT2EState.DEFAULT_DIFFICULTY_AVERAGE
            MGTView        : MGT2ERollView.MGT2ERollView = MGT2ERollView.MGT2ERollView(StateService = self.TargetResolver.MGT2EState, CharacterRecord = ActiveRecord, SelectedSkill = self.CheckQuery if (self.CheckQuery.lower() not in MGT2EState.CHARACTERISTIC_LOOKUP) else None, SelectedAttribute = self.CharacteristicOverride, TargetDifficulty = DifficultyValue, InvokerDiscordID = Interaction.user.id, TargetResolverInstance = self.TargetResolver, SituationalModifier = self.SituationalModifier, CompletionCallback = OnInteractiveComplete)
            await Interaction.response.send_message(content = f"Customize roll for **{CharacterName}**:", view = MGTView, ephemeral = True)

        else:
            DNDView: DND5ERollView.DND5ERollView = DND5ERollView.DND5ERollView(StateService = self.TargetResolver.CharacterState, CharacterRecord = ActiveRecord, DiceRoller = self.DiceRoller, InitialMode = self.RollType, SelectedQuery = self.CheckQuery, TargetDC = self.TargetDifficultyOrDC, AdvantageState = self.AdvantageOrBoons, SituationalBonus = self.SituationalModifier, InvokerDiscordID = Interaction.user.id, TargetResolverInstance = self.TargetResolver, CompletionCallback = OnInteractiveComplete)
            await Interaction.response.send_message(content = f"Customize roll for **{CharacterName}**:", view = DNDView, ephemeral = True)
