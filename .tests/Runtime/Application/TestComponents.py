import typing                                            as Typing
import unittest.mock                                     as MockLibrary
import discord                                           as Discord
import pytest                                            as Pytest
import Runtime.Application.Components.VersionView        as VersionView
import Runtime.Application.Components.InitiativeControls as InitiativeControls
import Runtime.Application.Components.MGT2ERollView      as MGT2ERollView
import Runtime.Application.Components.DND5ERollView      as DND5ERollView
import Runtime.Application.Components.RollRequestView    as RollRequestView
import Runtime.Services.CompendiumTagRenderer            as CompendiumTagRenderer
import Runtime.Services.EncounterManagerService          as EncounterManager
import Runtime.Services.MGT2EStateService                as MGT2EState
import Runtime.Services.CharacterStateService            as CharacterState
import Runtime.Services.TargetResolverService            as TargetResolver

class TestComponents:
    def TestVersionViewFourOrFewerVersions(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()
        RecordData      : dict[str, Typing.Any]                       = {
            "source"  : "XPHB",
            "Versions": [{"Source": "XPHB", "PublicationYear": 2024, "Data": {}}, {"Source": "PHB", "PublicationYear": 2014, "Data": {}}]
        }
        MockFormatter: MockLibrary.MagicMock   = MockLibrary.MagicMock(return_value = Discord.Embed(title = "Spell"))
        ViewInstance : VersionView.VersionView = VersionView.VersionView(RecordData = RecordData, TagRendererInstance = RendererInstance, FormatterFunction = MockFormatter)

        assert (len(ViewInstance.children) == 2)
        ButtonOne: Discord.ui.Button = Typing.cast(Discord.ui.Button, ViewInstance.children[0])
        ButtonTwo: Discord.ui.Button = Typing.cast(Discord.ui.Button, ViewInstance.children[1])
        assert (ButtonOne.label == "XPHB (2024)")
        assert (ButtonOne.disabled is True)
        assert (ButtonTwo.label == "PHB (2014)")
        assert (ButtonTwo.disabled is False)

    def TestVersionViewMoreThanFourVersions(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()
        RecordData      : dict[str, Typing.Any]                       = {
            "source"  : "SRC1",
            "Versions": [{"Source": "SRC1", "PublicationYear": 2020, "Data": {}}, {"Source": "SRC2", "PublicationYear": 2021, "Data": {}}, {"Source": "SRC3", "PublicationYear": 2022, "Data": {}}, {"Source": "SRC4", "PublicationYear": 2023, "Data": {}}, {"Source": "SRC5", "PublicationYear": 2024, "Data": {}}]
        }
        MockFormatter: MockLibrary.MagicMock   = MockLibrary.MagicMock(return_value = Discord.Embed(title = "Item"))
        ViewInstance : VersionView.VersionView = VersionView.VersionView(RecordData = RecordData, TagRendererInstance = RendererInstance, FormatterFunction = MockFormatter)

        assert (len(ViewInstance.children) == 1)
        assert isinstance(ViewInstance.children[0], Discord.ui.Select)
        SelectMenu: Discord.ui.Select = Typing.cast(Discord.ui.Select, ViewInstance.children[0])
        assert (len(SelectMenu.options) == 5)

    def TestCreateVersionPromptEmbed(self) -> None:
        VersionsList: list[dict[str, Typing.Any]] = [{"Source": "XPHB", "SourceDisplayName": "Player's Handbook 2024", "PublicationYear": 2024, "IsPrimary": True}, {"Source": "PHB", "SourceDisplayName": "Player's Handbook 2014", "PublicationYear": 2014, "IsPrimary": False}]
        PromptEmbed : Discord.Embed               = VersionView.CreateVersionPromptEmbed(CanonicalName = "Fireball", CategoryName = "Spells", VersionsList = VersionsList)
        assert ("Fireball" in str(PromptEmbed.title))
        assert (len(PromptEmbed.fields) == 1)
        assert ("Available Versions (Spells)" == PromptEmbed.fields[0].name)
        assert ("[Primary]" in str(PromptEmbed.fields[0].value))

    def TestCompendiumUnifiedPickerViewSubclasses(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()
        MockClient      : MockLibrary.MagicMock                       = MockLibrary.MagicMock()
        SearchResults   : dict[str, list[dict[str, Typing.Any]]]      = {
            "Subclasses": [
                {
                    "name"            : "Berserker",
                    "source"          : "PHB",
                    "AvailableSources": ["PHB"]
                }
            ],
            "Classes"   : [
                {
                    "name"            : "Barbarian",
                    "source"          : "PHB",
                    "AvailableSources": ["PHB"]
                }
            ]
        }
        FormatterMap    : dict[str, Typing.Any]                       = {
            "Subclasses": RendererInstance.FormatSubclassEmbed,
            "Classes"   : RendererInstance.FormatClassEmbed
        }
        PickerView      : VersionView.CompendiumUnifiedPickerView     = VersionView.CompendiumUnifiedPickerView(SearchResults = SearchResults, PlatformClientInstance = MockClient, TagRendererInstance = RendererInstance, FormatterMapping = FormatterMap)

        assert (len(PickerView.children) == 1)
        assert isinstance(PickerView.children[0], Discord.ui.Select)
        SelectMenu: Discord.ui.Select = Typing.cast(Discord.ui.Select, PickerView.children[0])
        assert (len(SelectMenu.options) == 2)
        assert (SelectMenu.options[0].label == "[Subclass] Berserker")
        assert (SelectMenu.options[1].label == "[Class] Barbarian")

    def TestInitiativeControlsViewButtons(self) -> None:
        MockManager : EncounterManager.EncounterManagerService  = EncounterManager.EncounterManagerService()
        ViewInstance: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(EncounterManagerInstance = MockManager, ChannelID = "12345")
        assert (len(ViewInstance.children) == 3)
        LabelsList: list[str] = [str(getattr(Child, "label", "")) for Child in ViewInstance.children]
        assert ("Prev" in LabelsList)
        assert ("Next" in LabelsList)
        assert ("End" in LabelsList)

    def TestMGT2ERollViewButtonsAndAttributes(self) -> None:
        StateService   : MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        CharacterRecord: dict[str, Typing.Any]        = {
            "Name"      : "Traveller Hero",
            "DetailData": {
                "Characteristics": {
                    "Strength"      : 8,
                    "Dexterity"     : 10,
                    "Endurance"     : 7,
                    "Intelligence"  : 9,
                    "Education"     : 11,
                    "SocialStanding": 6
                },
                "Skills"         : {
                    "pilot": 2
                }
            }
        }
        ViewInstance   : MGT2ERollView.MGT2ERollView  = MGT2ERollView.MGT2ERollView(StateService = StateService, CharacterRecord = CharacterRecord, SelectedSkill = "pilot", SelectedAttribute = "Dexterity")
        assert (len(ViewInstance.children) == 3)
        assert (ViewInstance.NetBoons == 0)
        assert (ViewInstance.SelectedAttribute == "Dexterity")

    def TestPopcornInitiativeControlsViewDropdown(self) -> None:
        ManagerService: EncounterManager.EncounterManagerService = EncounterManager.EncounterManagerService()
        Encounter     : EncounterManager.CombatEncounter         = ManagerService.CreateEncounter(ChannelID = "pop-1", GameSystem = "MGT2E", InitiativeMode = "Popcorn")
        Encounter.AddCombatant(EncounterManager.CombatantEntry(ID = "c1", Name = "Scout One", Initiative = 7, CurrentHitPoints = 8, MaxHitPoints = 8))
        Encounter.AddCombatant(EncounterManager.CombatantEntry(ID = "c2", Name = "Pirate", Initiative = 6, CurrentHitPoints = 7, MaxHitPoints = 7))

        ViewInstance: InitiativeControls.InitiativeControlsView = InitiativeControls.InitiativeControlsView(ManagerService, ChannelID = "pop-1", CommandPrefix = ".")
        assert (len(ViewInstance.children) == 2)
        assert isinstance(ViewInstance.children[0], Discord.ui.Select)
        assert isinstance(ViewInstance.children[1], Discord.ui.Button)
        assert (ViewInstance.children[1].label == "End")

    def TestMGT2ERollViewWithoutPreselectedSkillAddsSkillSelect(self) -> None:
        StateService   : MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        CharacterRecord: dict[str, Typing.Any]        = {
            "Name"      : "Traveller Hero",
            "DetailData": {
                "Characteristics": {
                    "Strength"      : 7,
                    "Dexterity"     : 9,
                    "Endurance"     : 8,
                    "Intelligence"  : 8,
                    "Education"     : 10,
                    "SocialStanding": 6
                },
                "Skills"         : {
                    "astrogation": 1,
                    "pilot"      : 2
                }
            }
        }
        ViewInstance: MGT2ERollView.MGT2ERollView = MGT2ERollView.MGT2ERollView(StateService = StateService, CharacterRecord = CharacterRecord, SelectedSkill = None, InvokerDiscordID = 100)
        assert (len(ViewInstance.children) == 4)
        assert isinstance(ViewInstance.SkillMenu, Discord.ui.Select)

    def TestDND5ERollViewControls(self) -> None:
        DNDService     : CharacterState.CharacterStateService = CharacterState.CharacterStateService()
        CharacterRecord: dict[str, Typing.Any]                = {
            "Name"      : "Cleric",
            "DetailData": {
                "ProficiencyBonus": 3,
                "AbilityScores"   : {
                    "Strength"    : {
                        "TotalScore": 14,
                        "Modifier"  : 2
                    },
                    "Dexterity"   : {
                        "TotalScore": 12,
                        "Modifier"  : 1
                    },
                    "Constitution": {
                        "TotalScore": 14,
                        "Modifier"  : 2
                    },
                    "Intelligence": {
                        "TotalScore": 10,
                        "Modifier"  : 0
                    },
                    "Wisdom"      : {
                        "TotalScore": 18,
                        "Modifier"  : 4
                    },
                    "Charisma"    : {
                        "TotalScore": 10,
                        "Modifier"  : 0
                    }
                }
            }
        }
        ViewInstance: DND5ERollView.DND5ERollView = DND5ERollView.DND5ERollView(StateService = DNDService, CharacterRecord = CharacterRecord, InitialMode = "Save", SelectedQuery = "wis", TargetDC = 14)
        assert (ViewInstance.RollMode == "Save")
        assert (len(ViewInstance.children) == 4)

    @Pytest.mark.asyncio
    async def TestRollRequestViewStrictMentionAndSystemGuard(self) -> None:
        SharedContext: dict[str, str]                       = {}
        DNDService   : CharacterState.CharacterStateService = CharacterState.CharacterStateService(ActiveSystemByContext = SharedContext)
        MGT2EService : MGT2EState.MGT2EStateService         = MGT2EState.MGT2EStateService(ActiveSystemByContext = SharedContext)
        Resolver     : TargetResolver.TargetResolverService = TargetResolver.TargetResolverService(CharacterStateInstance = DNDService, MGT2EStateInstance = MGT2EService, ActiveSystemByContext = SharedContext)

        TravellerCharacter: dict[str, Typing.Any] = {
            "ID"        : "trav-1",
            "Name"      : "Captain Kira",
            "GameSystem": "MGT2E",
            "DetailData": {"Characteristics": {
                "Dexterity": 11
            }, "Skills": {
                "pilot": 2
            }}
        }
        DND5ECharacter: dict[str, Typing.Any] = {
            "ID"        : "dnd-1",
            "Name"      : "Barbarian Grok",
            "GameSystem": "DND5E",
            "DetailData": {}
        }
        MGT2EService.CharacterCache["trav-1"] = TravellerCharacter
        DNDService.CharacterCache["dnd-1"]    = DND5ECharacter
        MGT2EService.SetActiveCharacter("101", "500", "trav-1")

        Slot       : RollRequestView.RollRequestSlot = RollRequestView.RollRequestSlot(SlotID = "101", DisplayName = "Captain Kira", AllowedUserID = "101", StrictUserOnly = True, CharacterRecord = TravellerCharacter)
        RequestView: RollRequestView.RollRequestView = RollRequestView.RollRequestView(GameSystem = "MGT2E", RollType = "check", CheckQuery = "pilot", RequesterName = "Referee", TargetResolverInstance = Resolver, TargetDifficultyOrDC = 8, TargetSlots = [Slot])

        Embed: Typing.Any = RequestView.BuildRequestEmbed()
        assert ("Captain Kira" in str(Embed.fields[0].value))
        assert ("<@101>" not in str(Embed.fields[0].value))

        WrongUserInteraction: MockLibrary.MagicMock = MockLibrary.MagicMock()
        WrongUserInteraction.user                   = MockLibrary.MagicMock(id = 202)
        WrongUserInteraction.channel                = MockLibrary.MagicMock(id = 500)
        WrongUserInteraction.response               = MockLibrary.AsyncMock()
        await RequestView.HandleSlotButtonClick(WrongUserInteraction, "101")
        WrongUserInteraction.response.send_message.assert_awaited_once()
        assert (Slot.IsCompleted is False)

        DNDService.SetActiveCharacter("101", "500", "dnd-1")
        SwitchedInteraction: MockLibrary.MagicMock = MockLibrary.MagicMock()
        SwitchedInteraction.user                   = MockLibrary.MagicMock(id = 101)
        SwitchedInteraction.channel                = MockLibrary.MagicMock(id = 500)
        SwitchedInteraction.response               = MockLibrary.AsyncMock()
        await RequestView.HandleSlotButtonClick(SwitchedInteraction, "101")
        SwitchedInteraction.response.send_message.assert_awaited_once()
        assert (Slot.IsCompleted is False)

        MGT2EService.SetActiveCharacter("101", "500", "trav-1")
        ValidInteraction: MockLibrary.MagicMock = MockLibrary.MagicMock()
        ValidInteraction.user                   = MockLibrary.MagicMock(id = 101)
        ValidInteraction.channel                = MockLibrary.MagicMock(id = 500)
        ValidInteraction.response               = MockLibrary.AsyncMock()
        await RequestView.HandleSlotButtonClick(ValidInteraction, "101")
        ValidInteraction.response.edit_message.assert_awaited_once()
        assert (Slot.IsCompleted is True)
        assert ("Success" in Slot.ResultSummary) or ("Failure" in Slot.ResultSummary)
