import typing                         as Typing
import pydantic                       as Pydantic
import Services.DebugService          as Debug
import Services.Automation.AutomationModels as Models

class DynamicConditionDefinition(Pydantic.BaseModel):
    Name          : str
    Description   : Typing.Optional[str]                 = None
    PassiveEffects: Typing.Optional[Models.PassiveEffectsModel] = None
    Tags          : list[str]                            = Pydantic.Field(default_factory = list)

class DynamicConditionRegistry:
    def __init__(self) -> None:
        self.RegisteredConditions: dict[str, DynamicConditionDefinition] = {}

    def RegisterCondition(self, Name: str, PassiveEffects: Typing.Optional[Models.PassiveEffectsModel] = None, Description: Typing.Optional[str] = None, Tags: Typing.Optional[list[str]] = None) -> DynamicConditionDefinition:
        NormalizedKey: str = Name.strip().lower()
        Definition: DynamicConditionDefinition = DynamicConditionDefinition(
            Name           = Name.strip(),
            Description    = Description,
            PassiveEffects = PassiveEffects,
            Tags           = Tags if (Tags is not None) else []
        )
        self.RegisteredConditions[NormalizedKey] = Definition
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Registered Dynamic Condition: Name=\"{Definition.Name}\"")
        return Definition

    def UnregisterCondition(self, Name: str) -> bool:
        NormalizedKey: str = Name.strip().lower()
        if NormalizedKey in self.RegisteredConditions:
            del self.RegisteredConditions[NormalizedKey]
            Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Unregistered Dynamic Condition: Name=\"{Name}\"")
            return True

        return False

    def GetCondition(self, Name: str) -> Typing.Optional[DynamicConditionDefinition]:
        NormalizedKey: str = Name.strip().lower()
        return self.RegisteredConditions.get(NormalizedKey)

    def HasCondition(self, Name: str) -> bool:
        NormalizedKey: str = Name.strip().lower()
        return (NormalizedKey in self.RegisteredConditions)

    def ResolveConditionModifiers(self, ConditionNames: list[str]) -> list[Models.PassiveEffectsModel]:
        ActiveModifiersList: list[Models.PassiveEffectsModel] = []
        for CondName in ConditionNames:
            DefRecord: Typing.Optional[DynamicConditionDefinition] = self.GetCondition(CondName)
            if (DefRecord is not None) and (DefRecord.PassiveEffects is not None):
                ActiveModifiersList.append(DefRecord.PassiveEffects)

        return ActiveModifiersList

GLOBAL_CONDITION_REGISTRY: DynamicConditionRegistry = DynamicConditionRegistry()

