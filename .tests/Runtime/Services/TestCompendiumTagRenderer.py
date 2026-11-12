import typing                                 as Typing
import discord                                as Discord
import Runtime.Services.CompendiumTagRenderer as CompendiumTagRenderer

class TestCompendiumTagRenderer:
    def TestRenderTagsFormatting(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()
        assert (RendererInstance.RenderTags("{@b Bold Text}") == "**Bold Text**")
        assert (RendererInstance.RenderTags("{@i Italic Text}") == "*Italic Text*")
        assert (RendererInstance.RenderTags("{@strike Strikethrough}") == "~~Strikethrough~~")
        assert (RendererInstance.RenderTags("{@code SampleCode}") == "`SampleCode`")
        assert (RendererInstance.RenderTags("{@spell Fireball|PHB}") == "**Fireball**")
        assert (RendererInstance.RenderTags("{@subclass Berserker|Barbarian|PHB}") == "**Berserker**")
        assert (RendererInstance.RenderTags("{@condition Poisoned}") == "*Poisoned*")
        assert (RendererInstance.RenderTags("{@dice 2d6 + 3}") == "`2d6 + 3`")
        assert (RendererInstance.RenderTags("{@chance 50}") == "50%")
        assert (RendererInstance.RenderTags("{@recharge 5}") == "(Recharge 5-6)")
        assert (RendererInstance.RenderTags("{@recharge 6}") == "(Recharge 6-6)")

    def TestRenderEntriesStringAndList(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()
        assert (RendererInstance.RenderEntries("Plain text description") == "Plain text description")

        ListEntries : list[str] = ["First paragraph.", "Second paragraph."]
        RenderedList: str       = RendererInstance.RenderEntries(ListEntries)
        assert (RenderedList == "First paragraph.\n\nSecond paragraph.")

    def TestRenderEntriesDictionaryTypes(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()

        EntriesDictionary: dict[str, Typing.Any] = {
            "type"   : "entries",
            "name"   : "Special Feature",
            "entries": ["Detail line."]
        }
        RenderedEntries: str = RendererInstance.RenderEntries(EntriesDictionary)
        assert ("**Special Feature**\nDetail line." == RenderedEntries)

        ListDictionary: dict[str, Typing.Any] = {
            "type" : "list",
            "items": ["Item One", "Item Two"]
        }
        RenderedItems: str = RendererInstance.RenderEntries(ListDictionary)
        assert ("• Item One\n• Item Two" == RenderedItems)

        InsetDictionary: dict[str, Typing.Any] = {
            "type"   : "inset",
            "entries": ["Quoted sidebar."]
        }
        RenderedInset: str = RendererInstance.RenderEntries(InsetDictionary)
        assert ("> Quoted sidebar." == RenderedInset)

        TableDictionary: dict[str, Typing.Any] = {
            "type"     : "table",
            "caption"  : "Dice Table",
            "colLabels": ["Roll", "Result"],
            "rows"     : [["1", "Fail"], ["2", "Pass"]]
        }
        RenderedTable: str = RendererInstance.RenderEntries(TableDictionary)
        assert ("**Dice Table**" in RenderedTable)
        assert ("Roll | Result" in RenderedTable)
        assert ("1 | Fail" in RenderedTable)

    def TestFormatSpellEmbed(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()
        SpellData       : dict[str, Typing.Any]                       = {
            "name"      : "Fireball",
            "level"     : 3,
            "school"    : "V",
            "source"    : "PHB",
            "time"      : [{"number": 1, "unit": "action"}],
            "range"     : {"distance": {
                "amount": 150,
                "type"  : "feet"
            }},
            "components": {
                "v": True,
                "s": True,
                "m": "a tiny ball of bat guano"
            },
            "duration"  : [{"type": "instant"}],
            "entries"   : ["A bright streak flashes from your pointing finger."]
        }

        SpellEmbed: Discord.Embed = RendererInstance.FormatSpellEmbed(SpellData, RuleSetEnforcementMode = "Standard")
        assert (SpellEmbed.title == "Fireball")
        assert (SpellEmbed.description == "*3-level Evocation*")
        assert (SpellEmbed.color is not None)
        assert (SpellEmbed.color.value == CompendiumTagRenderer.COLOR_COMPENDIUM_EMBED)

        FieldNamesList: list[str] = [Field.name for Field in SpellEmbed.fields]
        assert ("Casting Time" in FieldNamesList)
        assert ("Range" in FieldNamesList)
        assert ("Components" in FieldNamesList)
        assert ("Duration" in FieldNamesList)
        assert ("Description" in FieldNamesList)
        assert ("⚠️ Legacy 2014 Content Notice" in FieldNamesList)

    def TestFormatSubclassEmbed(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()
        SubclassData    : dict[str, Typing.Any]                       = {
            "name"               : "Berserker",
            "className"          : "Barbarian",
            "source"             : "PHB",
            "spellcastingAbility": "cha",
            "casterProgression"  : "1/3",
            "subclassFeatures"   : ["Frenzy|Barbarian|PHB|Berserker|3", "Mindless Rage|Barbarian|PHB|Berserker|6"],
            "subclassTableGroups": [
                {
                    "title"    : "Spell Slots",
                    "colLabels": ["Level", "1st"],
                    "rows"     : [["3rd", "2"]]
                }
            ],
            "entries"            : ["For some barbarians, rage is a means to an end."]
        }

        SubclassEmbed: Discord.Embed = RendererInstance.FormatSubclassEmbed(SubclassData, RuleSetEnforcementMode = "Standard")
        assert (SubclassEmbed.title == "Berserker (Barbarian)")
        assert (SubclassEmbed.description == "*Barbarian Subclass*")
        assert (SubclassEmbed.color is not None)
        assert (SubclassEmbed.color.value == CompendiumTagRenderer.COLOR_COMPENDIUM_EMBED)

        FieldNamesList: list[str] = [Field.name for Field in SubclassEmbed.fields]
        assert ("Spellcasting Ability" in FieldNamesList)
        assert ("Caster Progression" in FieldNamesList)
        assert ("Subclass Features" in FieldNamesList)
        assert ("Spell Slots" in FieldNamesList)
        assert ("Description & Overview" in FieldNamesList)
        assert ("⚠️ Legacy 2014 Content Notice" in FieldNamesList)
        assert ("Legacy 2014" in str(SubclassEmbed.footer.text))

    def TestFormatSubclassEmbed2024(self) -> None:
        RendererInstance: CompendiumTagRenderer.CompendiumTagRenderer = CompendiumTagRenderer.CompendiumTagRenderer()
        SubclassData    : dict[str, Typing.Any]                       = {
            "name"     : "Path of the Berserker",
            "className": "Barbarian",
            "source"   : "XPHB",
            "entries"  : ["Updated rage features."]
        }

        SubclassEmbed: Discord.Embed = RendererInstance.FormatSubclassEmbed(SubclassData, RuleSetEnforcementMode = "Standard")
        assert (SubclassEmbed.title == "Path of the Berserker (Barbarian)")
        assert ("D&D 2024" in str(SubclassEmbed.footer.text))

        FieldNamesList: list[str] = [Field.name for Field in SubclassEmbed.fields]
        assert ("⚠️ Legacy 2014 Content Notice" not in FieldNamesList)
