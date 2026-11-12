import ast                                               as AbstractSyntaxTree
import re                                                as RegularExpressions
import types                                             as TypesLibrary
import typing                                            as Typing
import pydantic                                          as Pydantic
import Runtime.Services.DiceService                      as Dice
import Runtime.Services.EncounterManagerService          as EncounterManager
import Runtime.Services.Draconic.DraconicEngine          as DraconicEngine
import Runtime.Services.Draconic.Exceptions              as Exceptions
import Runtime.Services.Draconic.SandboxedScope          as SandboxedScope
import Runtime.Services.Draconic.API.CharacterController as CharacterController
import Runtime.Services.Draconic.API.CombatController    as CombatController
import Runtime.Services.Draconic.API.ArgumentParser      as ArgumentParser
import Runtime.Services.Draconic.API.VariableManager     as VariableManager
import Runtime.Services.PlatformClient                   as PlatformClient

DRAC2_BLOCK_PATTERN     : RegularExpressions.Pattern = DraconicEngine.DRAC2_BLOCK_PATTERN
DRAC1_EXPRESSION_PATTERN: RegularExpressions.Pattern = DraconicEngine.DRAC1_EXPRESSION_PATTERN
INLINE_DICE_PATTERN     : RegularExpressions.Pattern = DraconicEngine.INLINE_DICE_PATTERN
ARGUMENT_INDEX_PATTERN  : RegularExpressions.Pattern = DraconicEngine.ARGUMENT_INDEX_PATTERN
ALL_ARGUMENTS_PATTERN   : RegularExpressions.Pattern = DraconicEngine.ALL_ARGUMENTS_PATTERN

DraconicSecurityError  = Exceptions.DraconicSecurityError
DraconicExecutionError = Exceptions.DraconicExecutionError

class DraconicEvaluationContext(Pydantic.BaseModel):
    CharacterData  : Typing.Optional[dict[str, Typing.Any]]            = None
    EncounterData  : Typing.Optional[EncounterManager.CombatEncounter] = None
    AuthorID       : str                                               = ""
    AuthorName     : str                                               = ""
    ChannelID      : str                                               = ""
    Arguments      : list[str]                                         = Pydantic.Field(default_factory = list)
    ArgumentsString: str                                               = ""
    UserVariables  : dict[str, Typing.Any]                             = Pydantic.Field(default_factory = dict)
    ServerVariables: dict[str, Typing.Any]                             = Pydantic.Field(default_factory = dict)
    GlobalVariables: dict[str, Typing.Any]                             = Pydantic.Field(default_factory = dict)
    model_config                                                       = Pydantic.ConfigDict(arbitrary_types_allowed = True)

class SafeASTEvaluator:
    def __init__(self, GlobalScope: dict[str, Typing.Any]) -> None:
        self.Globals    : dict[str, Typing.Any]          = GlobalScope
        self.Interpreter: DraconicEngine.DraconicInterpreter = DraconicEngine.DraconicInterpreter()
        self.Context    : DraconicEngine.ASTExecutionContext = DraconicEngine.ASTExecutionContext()

    def LookupVariable(self, VariableName: str) -> Typing.Any:
        if VariableName in self.Globals:
            return self.Globals[VariableName]

        raise NameError(f"Name '{VariableName}' is not defined")

    def EvaluateNode(self, Node: AbstractSyntaxTree.AST) -> Typing.Any:
        return self.Interpreter.EvaluateNode(Node, self.Globals, self.Context)

    def ExecuteStatements(self, Statements: list[AbstractSyntaxTree.stmt]) -> Typing.Any:
        return self.Interpreter.ExecuteStatements(Statements, self.Globals, self.Context)

class DraconicScriptService:
    def __init__(self, DiceRoller: Typing.Optional[Dice.DiceRollerService] = None, PlatformClientInstance: Typing.Optional[PlatformClient.TallyPlatformClient] = None) -> None:
        self.DiceRoller    : Dice.DiceRollerService       = DiceRoller if (DiceRoller is not None) else Dice.DiceRollerService()
        self.PlatformClient: PlatformClient.TallyPlatformClient    = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.TallyPlatformClient()
        self.Engine        : DraconicEngine.DraconicInterpreter = DraconicEngine.DraconicInterpreter(DiceRoller = self.DiceRoller)

    def Roll(self, ExpressionString: str) -> int:
        return self.Engine.BuiltinsFactory.Roll(ExpressionString)

    def VerboseRoll(self, ExpressionString: str) -> str:
        VerboseOutcome: SandboxedScope.VerboseRollResult = self.Engine.BuiltinsFactory.VerboseRoll(ExpressionString)
        return str(VerboseOutcome)

    def BuildGlobalScope(self, Context: DraconicEvaluationContext) -> dict[str, Typing.Any]:
        SafeBuiltins: dict[str, Typing.Any] = self.Engine.BuiltinsFactory.BuildBaseScope()
        SafeBuiltins["args"]                = SandboxedScope.DraconicList(Context.Arguments)
        SafeBuiltins["arg_str"]             = Context.ArgumentsString
        SafeBuiltins["argparse"]            = lambda ArgText = None: ArgumentParser.CreateArgumentParser(ArgText if (ArgText is not None) else Context.ArgumentsString)

        AuthorScope: TypesLibrary.SimpleNamespace = TypesLibrary.SimpleNamespace(id = Context.AuthorID, name = Context.AuthorName)
        SafeBuiltins["author"] = AuthorScope

        GuildID   : Typing.Optional[str]            = Context.EncounterData.GuildID if (Context.EncounterData is not None) else None
        VariableManagerInstance: VariableManager.VariableManager = VariableManager.VariableManager(CharacterRecord = Context.CharacterData, UserID = Context.AuthorID, GuildID = GuildID, PlatformClientInstance = self.PlatformClient, UserVariables = Context.UserVariables, ServerVariables = Context.ServerVariables, GlobalVariables = Context.GlobalVariables)
        SafeBuiltins["cvar"]        = VariableManagerInstance.cvar
        SafeBuiltins["uvar"]        = VariableManagerInstance.uvar
        SafeBuiltins["svar"]        = VariableManagerInstance.svar
        SafeBuiltins["gvar"]        = VariableManagerInstance.gvar
        SafeBuiltins["get_cvar"]    = VariableManagerInstance.GetCVAR
        SafeBuiltins["set_cvar"]    = VariableManagerInstance.SetCVAR
        SafeBuiltins["delete_cvar"] = VariableManagerInstance.DeleteCVAR
        SafeBuiltins["get_uvar"]    = VariableManagerInstance.GetUVAR
        SafeBuiltins["set_uvar"]    = VariableManagerInstance.SetUVAR
        SafeBuiltins["delete_uvar"] = VariableManagerInstance.DeleteUVAR
        SafeBuiltins["get_svar"]    = VariableManagerInstance.GetSVAR
        SafeBuiltins["set_svar"]    = VariableManagerInstance.SetSVAR
        SafeBuiltins["delete_svar"] = VariableManagerInstance.DeleteSVAR
        SafeBuiltins["get_gvar"]    = VariableManagerInstance.GetGVAR
        SafeBuiltins["get"]         = lambda Name, Default = None: VariableManagerInstance.GetVariable(Name, Default)
        SafeBuiltins["set"]         = lambda Name, Value: VariableManagerInstance.SetCVAR(Name, Value) if (Context.CharacterData is not None) else VariableManagerInstance.SetUVAR(Name, Value)
        SafeBuiltins["exists"]      = lambda Name: (VariableManagerInstance.GetVariable(Name) is not None)

        if (Context.CharacterData is not None):
            LiveCharacterController: CharacterController.CharacterController = CharacterController.CharacterController(Context.CharacterData, self.PlatformClient)
            SafeBuiltins["character"] = LiveCharacterController
            SafeBuiltins["name"]      = LiveCharacterController.name
            SafeBuiltins["hp"]        = LiveCharacterController.hp
            SafeBuiltins["max_hp"]    = LiveCharacterController.max_hp
            SafeBuiltins["ac"]        = LiveCharacterController.ac

        if (Context.EncounterData is not None):
            LiveCombatController: CombatController.CombatController = CombatController.CombatController(Context.EncounterData, Context.AuthorID)
            SafeBuiltins["combat"] = LiveCombatController

        return SafeBuiltins

    def EvaluateDraconicBlock(self, CodeString: str, Context: DraconicEvaluationContext) -> str:
        GlobalScope: dict[str, Typing.Any] = self.BuildGlobalScope(Context)
        return self.Engine.EvaluateDraconicBlock(CodeString, GlobalScope)

    def EvaluateDraconicExpression(self, ExpressionString: str, Context: DraconicEvaluationContext) -> str:
        GlobalScope: dict[str, Typing.Any] = self.BuildGlobalScope(Context)
        return self.Engine.EvaluateDraconicExpression(ExpressionString, GlobalScope)

    def InterpolateTemplate(self, TemplateText: str, Context: DraconicEvaluationContext) -> str:
        GlobalScope: dict[str, Typing.Any] = self.BuildGlobalScope(Context)
        return self.Engine.InterpolateTemplate(TemplateText, GlobalScope, Context.Arguments, Context.ArgumentsString)
