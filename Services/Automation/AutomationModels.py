import enum     as Enumeration
import pydantic as Pydantic
import typing   as Typing
import uuid     as UUIDLibrary

class CustomActionActivationType(str, Enumeration.Enum):
    Action      = "Action"
    BonusAction = "BonusAction"
    Reaction    = "Reaction"
    NoAction    = "NoAction"
    Attack      = "Attack"
    Minute      = "Minute"
    Hour        = "Hour"
    Special     = "Special"

class AutomationEffectType(str, Enumeration.Enum):
    Target           = "Target"
    Attack           = "Attack"
    Damage           = "Damage"
    TempHP           = "TempHP"
    Heal             = "Heal"
    Save             = "Save"
    Check            = "Check"
    Text             = "Text"
    InitiativeEffect = "InitiativeEffect"
    Condition        = "Condition"
    Variable         = "Variable"
    Counter          = "Counter"
    Cast             = "Cast"

class PassiveEffectsModel(Pydantic.BaseModel):
    model_config       = Pydantic.ConfigDict(extra = "allow")
    AttackAdvantage    : Typing.Optional[int]            = None
    ToHitBonus         : Typing.Optional[str]            = None
    DamageBonus        : Typing.Optional[str]            = None
    ArmorClassBonus    : Typing.Optional[int]            = None
    ArmorClassValue    : Typing.Optional[int]            = None
    SaveBonus          : Typing.Optional[str]            = None
    SaveAdvantage      : Typing.Optional[list[str]]      = None
    SaveDisadvantage   : Typing.Optional[list[str]]      = None
    CheckBonus         : Typing.Optional[str]            = None
    CheckAdvantage     : Typing.Optional[list[str]]      = None
    CheckDisadvantage  : Typing.Optional[list[str]]      = None
    Resistances        : Typing.Optional[list[str]]      = None
    Immunities         : Typing.Optional[list[str]]      = None
    Vulnerabilities    : Typing.Optional[list[str]]      = None
    IgnoredResistances : Typing.Optional[list[str]]      = None

class EffectNode(Pydantic.BaseModel):
    model_config  = Pydantic.ConfigDict(extra = "allow")
    Type          : AutomationEffectType
    Target        : Typing.Optional[Typing.Union[str, int]]              = None
    Effects       : Typing.Optional[Typing.List["EffectNode"]]           = None
    Hit           : Typing.Optional[Typing.List["EffectNode"]]           = None
    Miss          : Typing.Optional[Typing.List["EffectNode"]]           = None
    Damage        : Typing.Optional[str]                                 = None
    DamageType    : Typing.Optional[str]                                 = None
    Higher        : Typing.Optional[Typing.Dict[str, str]]               = None
    Amount        : Typing.Optional[Typing.Union[str, int]]              = None
    Stat          : Typing.Optional[str]                                 = None
    DC            : Typing.Optional[Typing.Union[str, int]]              = None
    Fail          : Typing.Optional[Typing.List["EffectNode"]]           = None
    Success       : Typing.Optional[Typing.List["EffectNode"]]           = None
    Ability       : Typing.Optional[str]                                 = None
    Contest       : Typing.Optional[bool]                                = None
    Text          : Typing.Optional[str]                                 = None
    Name          : Typing.Optional[str]                                 = None
    Duration      : Typing.Optional[int]                                 = None
    TickOn        : Typing.Optional[str]                                 = None
    End           : Typing.Optional[bool]                                = None
    Concentration : Typing.Optional[bool]                                = None
    PassiveEffects: Typing.Optional[PassiveEffectsModel]                 = None
    Condition     : Typing.Optional[str]                                 = None
    TrueEffects   : Typing.Optional[Typing.List["EffectNode"]]           = None
    FalseEffects  : Typing.Optional[Typing.List["EffectNode"]]           = None
    Value         : Typing.Optional[Typing.Union[str, int, float, bool]] = None
    Counter       : Typing.Optional[str]                                 = None
    Operation     : Typing.Optional[str]                                 = None
    Spell         : Typing.Optional[str]                                 = None
    Level         : Typing.Optional[int]                                 = None

EffectNode.model_rebuild()

class ActionDocument(Pydantic.BaseModel):
    ID            : str                                = Pydantic.Field(default_factory = lambda: str(UUIDLibrary.uuid4()))
    Name          : str
    ActivationType: CustomActionActivationType         = CustomActionActivationType.Action
    Phrase        : Typing.Optional[str]               = None
    ThumbnailURL  : Typing.Optional[str]               = None
    Automation    : Typing.List[EffectNode]            = Pydantic.Field(default_factory = list)

class TargetEffectOutcome(Pydantic.BaseModel):
    TargetName        : str
    HitStatus         : Typing.Optional[str] = None
    AttackTotal       : Typing.Optional[int] = None
    TargetArmorClass  : Typing.Optional[int] = None
    SaveResultTotal   : Typing.Optional[int] = None
    SaveTargetDC      : Typing.Optional[int] = None
    SaveSucceeded     : Typing.Optional[bool] = None
    DamageDealt       : int                  = 0
    DamageType        : Typing.Optional[str] = None
    TemporaryHPGranted: int                  = 0
    ConditionsApplied : list[str]            = Pydantic.Field(default_factory = list)
    EffectsAttached   : list[str]            = Pydantic.Field(default_factory = list)
    NarrativeMessages : list[str]            = Pydantic.Field(default_factory = list)

class AutomationExecutionResult(Pydantic.BaseModel):
    ActionName        : str
    CasterName        : str
    Phrase            : Typing.Optional[str]      = None
    ThumbnailURL      : Typing.Optional[str]      = None
    TargetOutcomes    : list[TargetEffectOutcome] = Pydantic.Field(default_factory = list)
    GlobalNarrative   : list[str]                 = Pydantic.Field(default_factory = list)
    ConcentrationCast : bool                      = False
    ConcentrationName : Typing.Optional[str]      = None

