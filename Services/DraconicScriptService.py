import ast                             as AbstractSyntaxTree
import math                            as MathLibrary
import re                              as RegularExpressions
import types                           as TypesLibrary
import typing                          as Typing
import pydantic                        as Pydantic
import Services.DebugService           as Debug
import Services.DiceService            as DiceService
import Services.EncounterManagerService as EncounterManagerService
import Services.Draconic.DraconicEngine           as DraconicEngine
import Services.Draconic.Exceptions               as Exceptions
import Services.Draconic.SandboxedScope           as SandboxedScope
import Services.Draconic.API.CharacterController  as CharacterController
import Services.Draconic.API.CombatController     as CombatController
import Services.Draconic.API.ArgumentParser       as ArgumentParser
import Services.PlatformClient                    as PlatformClient

DRAC2_BLOCK_PATTERN    : RegularExpressions.Pattern = DraconicEngine.DRAC2_BLOCK_PATTERN
DRAC1_EXPRESSION_PATTERN: RegularExpressions.Pattern = DraconicEngine.DRAC1_EXPRESSION_PATTERN
INLINE_DICE_PATTERN    : RegularExpressions.Pattern = DraconicEngine.INLINE_DICE_PATTERN
ARGUMENT_INDEX_PATTERN : RegularExpressions.Pattern = DraconicEngine.ARGUMENT_INDEX_PATTERN
ALL_ARGUMENTS_PATTERN  : RegularExpressions.Pattern = DraconicEngine.ALL_ARGUMENTS_PATTERN

DraconicSecurityError  = Exceptions.DraconicSecurityError
DraconicExecutionError = Exceptions.DraconicExecutionError

class DraconicEvaluationContext(Pydantic.BaseModel):
    CharacterData   : Typing.Optional[dict[str, Typing.Any]]                  = None
    EncounterData   : Typing.Optional[EncounterManagerService.CombatEncounter] = None
    AuthorID        : str                                                     = ""
    AuthorName      : str                                                     = ""
    ChannelID       : str                                                     = ""
    Arguments       : list[str]                                               = Pydantic.Field(default_factory = list)
    ArgumentsString : str                                                     = ""
    model_config                                                              = Pydantic.ConfigDict(arbitrary_types_allowed = True)

class SafeASTEvaluator:
    def __init__(self, GlobalScope: dict[str, Typing.Any]) -> None:
        self.Globals    : dict[str, Typing.Any]          = GlobalScope
        self.Interpreter: DraconicEngine.DraconicInterpreter = DraconicEngine.DraconicInterpreter()
        self.Context    : DraconicEngine.ASTExecutionContext = DraconicEngine.ASTExecutionContext()

    def LookupVariable(self, IdentifierName: str) -> Typing.Any:
        if IdentifierName in self.Globals:
            return self.Globals[IdentifierName]

        raise NameError(f"Name '{IdentifierName}' is not defined")

    def EvaluateNode(self, Node: AbstractSyntaxTree.AST) -> Typing.Any:
        return self.Interpreter.EvaluateNode(Node, self.Globals, self.Context)

    def ExecuteStatements(self, Statements: list[AbstractSyntaxTree.stmt]) -> Typing.Any:
        return self.Interpreter.ExecuteStatements(Statements, self.Globals, self.Context)

class DraconicScriptService:
    def __init__(self, DiceRoller: Typing.Optional[DiceService.DiceRollerService] = None, PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None) -> None:
        self.DiceRoller    : DiceService.DiceRollerService       = DiceRoller if (DiceRoller is not None) else DiceService.DiceRollerService()
        self.PlatformClient: PlatformClient.MISPlatformClient    = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.MISPlatformClient()
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

        AuthorScope: TypesLibrary.SimpleNamespace = TypesLibrary.SimpleNamespace(
            id   = Context.AuthorID,
            name = Context.AuthorName
        )
        SafeBuiltins["author"] = AuthorScope

        if (Context.CharacterData is not None):
            LiveCharController: CharacterController.CharacterController = CharacterController.CharacterController(Context.CharacterData, self.PlatformClient)
            SafeBuiltins["character"] = LiveCharController
            SafeBuiltins["name"]      = LiveCharController.name
            SafeBuiltins["hp"]        = LiveCharController.hp
            SafeBuiltins["max_hp"]    = LiveCharController.max_hp
            SafeBuiltins["ac"]        = LiveCharController.ac

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
