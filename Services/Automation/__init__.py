import Services.Automation.AutomationEngine        as AutomationEngineModule
import Services.Automation.AutomationModels        as AutomationModelsModule
import Services.Automation.DynamicConditionRegistry as DynamicConditionRegistryModule
import Services.Automation.EffectContext           as EffectContextModule
import Services.Automation.Effects.IEffectHandler  as IEffectHandlerModule

AutomationEngine          = AutomationEngineModule.AutomationEngine
ActionDocument            = AutomationModelsModule.ActionDocument
EffectNode                = AutomationModelsModule.EffectNode
AutomationEffectType      = AutomationModelsModule.AutomationEffectType
PassiveEffectsModel       = AutomationModelsModule.PassiveEffectsModel
TargetEffectOutcome       = AutomationModelsModule.TargetEffectOutcome
AutomationExecutionResult = AutomationModelsModule.AutomationExecutionResult
AutomationContext         = EffectContextModule.AutomationContext
DynamicConditionRegistry  = DynamicConditionRegistryModule.DynamicConditionRegistry
GLOBAL_CONDITION_REGISTRY = DynamicConditionRegistryModule.GLOBAL_CONDITION_REGISTRY
IEffectHandler            = IEffectHandlerModule.IEffectHandler
