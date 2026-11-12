import enum                                       as Enumeration
import typing                                     as Typing
import uuid                                       as UUIDLibrary
import pydantic                                   as Pydantic
import Services.DebugService                      as Debug
import Services.Automation.Validation.JSONCParser as JSONCParser

class ActionActivationType(str, Enumeration.Enum):
    Action      = "Action"
    BonusAction = "BonusAction"
    Reaction    = "Reaction"
    NoAction    = "NoAction"
    Attack      = "Attack"
    Minute      = "Minute"
    Hour        = "Hour"
    Special     = "Special"

class ActionEffectType(str, Enumeration.Enum):
    Target           = "Target"
    Attack           = "Attack"
    Save             = "Save"
    Damage           = "Damage"
    TempHP           = "TempHP"
    Heal             = "Heal"
    InitiativeEffect = "InitiativeEffect"
    Condition        = "Condition"
    Counter          = "Counter"
    Roll             = "Roll"
    Text             = "Text"
    Variable         = "Variable"
    Check            = "Check"
    Cast             = "Cast"
    RemoveIEffect    = "RemoveIEffect"

class PassiveEffectsDefinition(Pydantic.BaseModel):
    model_config       = Pydantic.ConfigDict(extra = "allow", populate_by_name = True)
    AttackAdvantage    : Typing.Optional[int]       = Pydantic.Field(default = None, alias = "attack_advantage")
    ToHitBonus         : Typing.Optional[str]       = Pydantic.Field(default = None, alias = "to_hit_bonus")
    DamageBonus        : Typing.Optional[str]       = Pydantic.Field(default = None, alias = "damage_bonus")
    ArmorClassBonus    : Typing.Optional[int]       = Pydantic.Field(default = None, alias = "ac_bonus")
    ArmorClassValue    : Typing.Optional[int]       = Pydantic.Field(default = None, alias = "ac_value")
    SaveBonus          : Typing.Optional[str]       = Pydantic.Field(default = None, alias = "save_bonus")
    SaveAdvantage      : Typing.Optional[list[str]] = Pydantic.Field(default = None, alias = "save_adv")
    SaveDisadvantage   : Typing.Optional[list[str]] = Pydantic.Field(default = None, alias = "save_dis")
    CheckBonus         : Typing.Optional[str]       = Pydantic.Field(default = None, alias = "check_bonus")
    CheckAdvantage     : Typing.Optional[list[str]] = Pydantic.Field(default = None, alias = "check_adv")
    CheckDisadvantage  : Typing.Optional[list[str]] = Pydantic.Field(default = None, alias = "check_dis")
    Resistances        : Typing.Optional[list[str]] = Pydantic.Field(default = None, alias = "resistances")
    Immunities         : Typing.Optional[list[str]] = Pydantic.Field(default = None, alias = "immunities")
    Vulnerabilities    : Typing.Optional[list[str]] = Pydantic.Field(default = None, alias = "vulnerabilities")
    IgnoredResistances : Typing.Optional[list[str]] = Pydantic.Field(default = None, alias = "ignored_resistances")
    MaxHitPointsBonus  : Typing.Optional[int]       = Pydantic.Field(default = None, alias = "max_hp_bonus")
    MaxHitPointsValue  : Typing.Optional[int]       = Pydantic.Field(default = None, alias = "max_hp_value")

class ButtonInteractionDefinition(Pydantic.BaseModel):
    model_config      = Pydantic.ConfigDict(extra = "allow", populate_by_name = True)
    Label             : str                                           = Pydantic.Field(default = "", alias = "label")
    Verb              : Typing.Optional[str]                          = Pydantic.Field(default = None, alias = "verb")
    Style             : Typing.Optional[int]                          = Pydantic.Field(default = 1, alias = "style")
    DefaultDC         : Typing.Optional[Typing.Union[str, int]]       = Pydantic.Field(default = None, alias = "defaultDC")
    DefaultAttackBonus: Typing.Optional[Typing.Union[str, int]]       = Pydantic.Field(default = None, alias = "defaultAttackBonus")
    Automation        : list["EffectNodeDefinition"]           = Pydantic.Field(default_factory = list, alias = "automation")

    @Pydantic.model_validator(mode = "before")
    @classmethod
    def NormalizeButtonData(cls, RawData: Typing.Any) -> Typing.Any:
        if not isinstance(RawData, dict):
            return RawData

        if ("label" in RawData) and not ("Label" in RawData):
            RawData["Label"] = RawData["label"]

        if ("verb" in RawData) and not ("Verb" in RawData):
            RawData["Verb"] = RawData["verb"]

        return RawData

class SubAttackInteractionDefinition(Pydantic.BaseModel):
    model_config  = Pydantic.ConfigDict(extra = "allow", populate_by_name = True)
    Name          : str                                           = Pydantic.Field(default = "", alias = "name")
    Verb          : Typing.Optional[str]                          = Pydantic.Field(default = None, alias = "verb")
    Phrase        : Typing.Optional[str]                          = Pydantic.Field(default = None, alias = "phrase")
    ActivationType: ActionActivationType                          = Pydantic.Field(default = ActionActivationType.Action, alias = "activation_type")
    Automation    : list["EffectNodeDefinition"]           = Pydantic.Field(default_factory = list, alias = "automation")

    @Pydantic.model_validator(mode = "before")
    @classmethod
    def NormalizeSubAttackData(cls, RawData: Typing.Any) -> Typing.Any:
        if not isinstance(RawData, dict):
            return RawData

        if ("name" in RawData) and not ("Name" in RawData):
            RawData["Name"] = RawData["name"]

        return RawData

class EffectNodeDefinition(Pydantic.BaseModel):
    model_config      = Pydantic.ConfigDict(extra = "allow", populate_by_name = True)
    Type              : ActionEffectType                                              = Pydantic.Field(alias = "type")
    Target            : Typing.Optional[Typing.Union[str, int]]                       = Pydantic.Field(default = None, alias = "target")
    Effects           : Typing.Optional[list["EffectNodeDefinition"]]          = Pydantic.Field(default = None, alias = "effects")
    SortBy            : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "sortBy")
    Hit               : Typing.Optional[list["EffectNodeDefinition"]]          = Pydantic.Field(default = None, alias = "hit")
    Miss              : Typing.Optional[list["EffectNodeDefinition"]]          = Pydantic.Field(default = None, alias = "miss")
    AttackBonus       : Typing.Optional[Typing.Union[str, int]]                       = Pydantic.Field(default = None, alias = "attackBonus")
    Advantage         : Typing.Optional[Typing.Union[str, int]]                       = Pydantic.Field(default = None, alias = "adv")
    Damage            : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "damage")
    DamageType        : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "damageType")
    Overheal          : bool                                                          = Pydantic.Field(default = False, alias = "overheal")
    Higher            : Typing.Optional[dict[str, str]]                        = Pydantic.Field(default = None, alias = "higher")
    CantripScale      : Typing.Optional[bool]                                         = Pydantic.Field(default = None, alias = "cantripScale")
    FixedValue        : Typing.Optional[bool]                                         = Pydantic.Field(default = None, alias = "fixedValue")
    Amount            : Typing.Optional[Typing.Union[str, int]]                       = Pydantic.Field(default = None, alias = "amount")
    Stat              : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "stat")
    DC                : Typing.Optional[Typing.Union[str, int]]                       = Pydantic.Field(default = None, alias = "dc")
    Fail              : Typing.Optional[list["EffectNodeDefinition"]]          = Pydantic.Field(default = None, alias = "fail")
    Success           : Typing.Optional[list["EffectNodeDefinition"]]          = Pydantic.Field(default = None, alias = "success")
    Ability           : Typing.Optional[Typing.Union[str, list[str]]]                 = Pydantic.Field(default = None, alias = "ability")
    Text              : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "text")
    Title             : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "title")
    Name              : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "name")
    Duration          : Typing.Optional[Typing.Union[int, str]]                       = Pydantic.Field(default = None, alias = "duration")
    TickOn            : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "tick_on_caster")
    End               : Typing.Optional[bool]                                         = Pydantic.Field(default = None, alias = "end")
    Concentration     : Typing.Optional[bool]                                         = Pydantic.Field(default = None, alias = "conc")
    PassiveEffects    : Typing.Optional[PassiveEffectsDefinition]                     = Pydantic.Field(default = None, alias = "passive_effects")
    Buttons           : Typing.Optional[list[ButtonInteractionDefinition]]     = Pydantic.Field(default = None, alias = "buttons")
    SubAttacks        : Typing.Optional[list[SubAttackInteractionDefinition]]  = Pydantic.Field(default = None, alias = "attacks")
    Condition         : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "condition")
    OnTrue            : Typing.Optional[list["EffectNodeDefinition"]]          = Pydantic.Field(default = None, alias = "onTrue")
    OnFalse           : Typing.Optional[list["EffectNodeDefinition"]]          = Pydantic.Field(default = None, alias = "onFalse")
    Value             : Typing.Optional[Typing.Union[str, int, float, bool]]          = Pydantic.Field(default = None, alias = "value")
    Counter           : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "counter")
    Spell             : Typing.Optional[str]                                          = Pydantic.Field(default = None, alias = "spell")
    Level             : Typing.Optional[int]                                          = Pydantic.Field(default = None, alias = "level")

    @Pydantic.model_validator(mode = "before")
    @classmethod
    def NormalizeRawNodeData(cls, RawData: Typing.Any) -> Typing.Any:
        if not isinstance(RawData, dict):
            return RawData

        RawType: str = str(RawData.get("type") or RawData.get("Type") or "").strip().lower()
        TypeMapping: dict[str, ActionEffectType] = {
            "target"          : ActionEffectType.Target,
            "attack"          : ActionEffectType.Attack,
            "save"            : ActionEffectType.Save,
            "damage"          : ActionEffectType.Damage,
            "temphp"          : ActionEffectType.TempHP,
            "heal"            : ActionEffectType.Heal,
            "ieffect"         : ActionEffectType.InitiativeEffect,
            "ieffect2"        : ActionEffectType.InitiativeEffect,
            "initiativeeffect": ActionEffectType.InitiativeEffect,
            "condition"       : ActionEffectType.Condition,
            "counter"         : ActionEffectType.Counter,
            "roll"            : ActionEffectType.Roll,
            "text"            : ActionEffectType.Text,
            "variable"        : ActionEffectType.Variable,
            "check"           : ActionEffectType.Check,
            "spell"           : ActionEffectType.Cast,
            "cast"            : ActionEffectType.Cast,
            "remove_ieffect"  : ActionEffectType.RemoveIEffect
        }

        NormalizedType: ActionEffectType = TypeMapping.get(RawType, ActionEffectType.Text)
        RawData["type"] = NormalizedType.value
        RawData["Type"] = NormalizedType.value

        if ("passive_effects" in RawData) and not ("PassiveEffects" in RawData):
            RawData["PassiveEffects"] = RawData["passive_effects"]

        if ("effects" in RawData) and isinstance(RawData.get("effects"), dict):
            RawData["PassiveEffects"] = RawData["effects"]
            del RawData["effects"]

        if ("conc" in RawData) and not ("Concentration" in RawData):
            RawData["Concentration"] = RawData["conc"]

        return RawData

ButtonInteractionDefinition.model_rebuild()
SubAttackInteractionDefinition.model_rebuild()
EffectNodeDefinition.model_rebuild()

class ActionDocumentDefinition(Pydantic.BaseModel):
    model_config  = Pydantic.ConfigDict(extra = "allow", populate_by_name = True)
    ID            : str                                     = Pydantic.Field(default_factory = lambda: str(UUIDLibrary.uuid4()))
    Name          : str                                     = Pydantic.Field(alias = "name")
    ActivationType: ActionActivationType                    = Pydantic.Field(default = ActionActivationType.Action, alias = "activation_type")
    Phrase        : Typing.Optional[str]                    = Pydantic.Field(default = None, alias = "phrase")
    ThumbnailURL  : Typing.Optional[str]                    = Pydantic.Field(default = None, alias = "thumb")
    Automation    : list[EffectNodeDefinition]       = Pydantic.Field(default_factory = list, alias = "automation")

def ValidateActionPayload(PayloadData: dict[str, Typing.Any]) -> ActionDocumentDefinition:
    try:
        ValidatedDocument: ActionDocumentDefinition = ActionDocumentDefinition.model_validate(PayloadData)
        return ValidatedDocument

    except Pydantic.ValidationError as ValidationErrorException:
        Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Action Payload Validation Failed: Error=\"{str(ValidationErrorException)}\"")
        raise ValueError(f"Action validation error: {str(ValidationErrorException)}") from ValidationErrorException

def ParseAndValidateJSONCAction(JSONCString: str) -> ActionDocumentDefinition:
    ParsedData: Typing.Any = JSONCParser.ParseJSONC(JSONCString)
    if not isinstance(ParsedData, dict):
        raise ValueError("Root JSONC action document must be an object/dictionary")

    return ValidateActionPayload(ParsedData)

def ValidateAutomationNodes(NodesList: list[dict[str, Typing.Any]]) -> list[EffectNodeDefinition]:
    ValidatedNodes: list[EffectNodeDefinition] = []
    for RawNode in NodesList:
        ValidatedNode: EffectNodeDefinition = EffectNodeDefinition.model_validate(RawNode)
        ValidatedNodes.append(ValidatedNode)

    return ValidatedNodes
