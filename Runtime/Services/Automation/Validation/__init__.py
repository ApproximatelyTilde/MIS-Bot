import Runtime.Services.Automation.Validation.JSONCParser      as JSONCParserModule
import Runtime.Services.Automation.Validation.ActionValidators as ActionValidatorsModule

JSONCParser                    = JSONCParserModule
ParseJSONC                     = JSONCParserModule.ParseJSONC
DumpJSONC                      = JSONCParserModule.DumpJSONC
NormalizeJSONC                 = JSONCParserModule.NormalizeJSONC
ActionValidators               = ActionValidatorsModule
ActionActivationType           = ActionValidatorsModule.ActionActivationType
ActionEffectType               = ActionValidatorsModule.ActionEffectType
PassiveEffectsDefinition       = ActionValidatorsModule.PassiveEffectsDefinition
ButtonInteractionDefinition    = ActionValidatorsModule.ButtonInteractionDefinition
SubAttackInteractionDefinition = ActionValidatorsModule.SubAttackInteractionDefinition
EffectNodeDefinition           = ActionValidatorsModule.EffectNodeDefinition
ActionDocumentDefinition       = ActionValidatorsModule.ActionDocumentDefinition
ValidateActionPayload          = ActionValidatorsModule.ValidateActionPayload
ParseAndValidateJSONCAction    = ActionValidatorsModule.ParseAndValidateJSONCAction
ValidateAutomationNodes        = ActionValidatorsModule.ValidateAutomationNodes
