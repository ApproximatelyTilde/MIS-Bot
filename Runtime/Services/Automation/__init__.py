import Runtime.Services.Automation.AutomationEngine         as AutomationEngineModule
import Runtime.Services.Automation.AutomationModels         as AutomationModelsModule
import Runtime.Services.Automation.DynamicConditionRegistry as DynamicConditionRegistryModule
import Runtime.Services.Automation.EffectContext            as EffectContextModule
import Runtime.Services.Automation.Effects.IEffectHandler   as IEffectHandlerModule
import Runtime.Services.Automation.Effects.DamageEffect     as DamageEffectModule
import Runtime.Services.Automation.ConcentrationManager     as ConcentrationManagerModule
import Runtime.Services.Automation.Validation               as ValidationModule

AutomationEngine            = AutomationEngineModule.AutomationEngine
ActionDocument              = AutomationModelsModule.ActionDocument
EffectNode                  = AutomationModelsModule.EffectNode
AutomationEffectType        = AutomationModelsModule.AutomationEffectType
PassiveEffectsModel         = AutomationModelsModule.PassiveEffectsModel
TargetEffectOutcome         = AutomationModelsModule.TargetEffectOutcome
AutomationExecutionResult   = AutomationModelsModule.AutomationExecutionResult
AutomationContext           = EffectContextModule.AutomationContext
DynamicConditionRegistry    = DynamicConditionRegistryModule.DynamicConditionRegistry
GLOBAL_CONDITION_REGISTRY   = DynamicConditionRegistryModule.GLOBAL_CONDITION_REGISTRY
IEffectHandler              = IEffectHandlerModule.IEffectHandler
DamageEffect                = DamageEffectModule
ConcentrationManager        = ConcentrationManagerModule.ConcentrationManager
Validation                  = ValidationModule
ParseJSONC                  = ValidationModule.ParseJSONC
ValidateActionPayload       = ValidationModule.ValidateActionPayload
ParseAndValidateJSONCAction = ValidationModule.ParseAndValidateJSONCAction
