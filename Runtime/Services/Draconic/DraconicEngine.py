import ast                                      as AbstractSyntaxTree
import re                                       as RegularExpressions
import time                                     as TimeLibrary
import typing                                   as Typing
import Runtime.Services.DebugService            as Debug
import Runtime.Services.DiceService             as Dice
import Runtime.Services.Draconic.Exceptions     as Exceptions
import Runtime.Services.Draconic.SandboxedScope as SandboxedScope

DRAC2_BLOCK_PATTERN      : RegularExpressions.Pattern = RegularExpressions.compile(r"<drac2>(.*?)</drac2>", RegularExpressions.DOTALL | RegularExpressions.IGNORECASE)
DRAC1_EXPRESSION_PATTERN : RegularExpressions.Pattern = RegularExpressions.compile(r"\{\{(.*?)\}\}", RegularExpressions.DOTALL)
INLINE_DICE_PATTERN      : RegularExpressions.Pattern = RegularExpressions.compile(r"\{(\d+d\d+[^\}]*)\}", RegularExpressions.IGNORECASE)
ARGUMENT_INDEX_PATTERN   : RegularExpressions.Pattern = RegularExpressions.compile(r"%(\d+)%")
ALL_ARGUMENTS_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:%\*|&\*)")
MAXIMUM_AST_CACHE_ENTRIES: int                        = 512

BANNED_AST_NODES: tuple[type, ...] = (
    AbstractSyntaxTree.Import,
    AbstractSyntaxTree.ImportFrom,
    AbstractSyntaxTree.ClassDef,
    AbstractSyntaxTree.AsyncFunctionDef,
    AbstractSyntaxTree.AsyncFor,
    AbstractSyntaxTree.AsyncWith,
    AbstractSyntaxTree.Await,
    AbstractSyntaxTree.Yield,
    AbstractSyntaxTree.YieldFrom,
    AbstractSyntaxTree.Global,
    AbstractSyntaxTree.Nonlocal,
    AbstractSyntaxTree.Delete,
    AbstractSyntaxTree.With
)

BANNED_IDENTIFIERS: frozenset[str] = frozenset({
    "eval",
    "exec",
    "compile",
    "open",
    "globals",
    "locals",
    "vars",
    "breakpoint",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
    "input",
    "exit",
    "quit",
    "help",
    "copyright",
    "credits",
    "license"
})

class DraconicSecurityVisitor(AbstractSyntaxTree.NodeVisitor):
    def __init__(self, MaxStringLength: int = 50000) -> None:
        self.MaxStringLength: int = MaxStringLength

    def visit_Attribute(self, Node: AbstractSyntaxTree.Attribute) -> None:
        if Node.attr.startswith("_") or (Node.attr in SandboxedScope.BANNED_DUNDER_ATTRIBUTES):
            raise Exceptions.DraconicSecurityError(f"Access to private or dunder attribute '{Node.attr}' is prohibited")

        self.generic_visit(Node)

    def visit_Name(self, Node: AbstractSyntaxTree.Name) -> None:
        if (Node.id in BANNED_IDENTIFIERS):
            raise Exceptions.DraconicSecurityError(f"Access to restricted identifier '{Node.id}' is prohibited")

        if Node.id.startswith("_"):
            raise Exceptions.DraconicSecurityError(f"Access to private identifier '{Node.id}' is prohibited")

        self.generic_visit(Node)

    def visit_FunctionDef(self, Node: AbstractSyntaxTree.FunctionDef) -> None:
        if Node.name.startswith("_"):
            raise Exceptions.DraconicSecurityError(f"Private function definition '{Node.name}' is prohibited")

        self.generic_visit(Node)

    def visit_Constant(self, Node: AbstractSyntaxTree.Constant) -> None:
        if isinstance(Node.value, str) and (len(Node.value) > self.MaxStringLength):
            raise Exceptions.DraconicSecurityError("String literal exceeds maximum allowed length")

        self.generic_visit(Node)

    def generic_visit(self, Node: AbstractSyntaxTree.AST) -> None:
        if isinstance(Node, BANNED_AST_NODES):
            raise Exceptions.DraconicSecurityError(f"Syntax node type '{type(Node).__name__}' is prohibited in Draconic sandbox")

        super().generic_visit(Node)

class DraconicExecutionConfig:
    def __init__(self, MaxExecutionSeconds: float = 5.0, MaxLoopIterations: int = 10000, MaxRecursionDepth: int = 50, MaxStringLength: int = 50000, MaxInstructionCount: int = 10000) -> None:
        self.MaxExecutionSeconds: float = MaxExecutionSeconds
        self.MaxLoopIterations  : int   = MaxLoopIterations
        self.MaxRecursionDepth  : int   = MaxRecursionDepth
        self.MaxStringLength    : int   = MaxStringLength
        self.MaxInstructionCount: int   = MaxInstructionCount

class ASTExecutionContext:
    def __init__(self, Config: Typing.Optional[DraconicExecutionConfig] = None) -> None:
        self.Config            : DraconicExecutionConfig = Config if (Config is not None) else DraconicExecutionConfig()
        self.StartTime         : float                   = TimeLibrary.monotonic()
        self.LoopIterationCount: int                     = 0
        self.InstructionCount  : int                     = 0
        self.CallDepth         : int                     = 0

    def CheckExecutionLimits(self) -> None:
        ElapsedTime: float = TimeLibrary.monotonic() - self.StartTime
        if (ElapsedTime > self.Config.MaxExecutionSeconds):
            raise Exceptions.DraconicTimeoutError(f"Execution time limit of {self.Config.MaxExecutionSeconds}s exceeded")

        self.InstructionCount += 1
        if (self.InstructionCount > self.Config.MaxInstructionCount):
            raise Exceptions.DraconicExecutionError(f"Maximum instruction execution limit of {self.Config.MaxInstructionCount} exceeded")

    def IncrementLoopIterations(self) -> None:
        self.LoopIterationCount += 1
        if (self.LoopIterationCount > self.Config.MaxLoopIterations):
            raise Exceptions.DraconicExecutionError(f"Maximum loop iteration limit of {self.Config.MaxLoopIterations} exceeded")

        self.CheckExecutionLimits()

    def CheckCallDepth(self) -> None:
        if (self.CallDepth > self.Config.MaxRecursionDepth):
            raise Exceptions.DraconicExecutionError(f"Maximum recursion depth of {self.Config.MaxRecursionDepth} exceeded")

        self.CheckExecutionLimits()

class DraconicFunction:
    def __init__(self, FunctionNode: Typing.Union[AbstractSyntaxTree.FunctionDef, AbstractSyntaxTree.Lambda], ClosureScope: dict[str, Typing.Any], InterpreterInstance: "DraconicInterpreter") -> None:
        self.FunctionNode       : Typing.Union[AbstractSyntaxTree.FunctionDef, AbstractSyntaxTree.Lambda] = FunctionNode
        self.ClosureScope      : dict[str, Typing.Any]                                                  = ClosureScope
        self.InterpreterInstance: "DraconicInterpreter"                                                  = InterpreterInstance

    def __call__(self, *PositionalArguments: Typing.Any, **KeywordArguments: Typing.Any) -> Typing.Any:
        ArgumentDefinition: AbstractSyntaxTree.arguments = self.FunctionNode.args
        LocalScope        : dict[str, Typing.Any]        = dict(self.ClosureScope)

        TotalPositionalArguments: int              = len(PositionalArguments)
        ExpectedPositionalNames : list[str]        = [ArgItem.arg for ArgItem in ArgumentDefinition.args]
        DefaultValues           : list[Typing.Any] = [self.InterpreterInstance.EvaluateNode(DefaultNode, self.ClosureScope, self.InterpreterInstance.CurrentExecutionContext) for DefaultNode in ArgumentDefinition.defaults]

        DefaultsOffset: int = len(ExpectedPositionalNames) - len(DefaultValues)
        for ParameterIndex, ParameterName in enumerate(ExpectedPositionalNames):
            if (ParameterIndex < TotalPositionalArguments):
                LocalScope[ParameterName] = PositionalArguments[ParameterIndex]

            elif ParameterName in KeywordArguments:
                LocalScope[ParameterName] = KeywordArguments[ParameterName]

            elif (ParameterIndex >= DefaultsOffset):
                LocalScope[ParameterName] = DefaultValues[ParameterIndex - DefaultsOffset]

            else:
                raise Exceptions.DraconicExecutionError(f"Missing required parameter: '{ParameterName}'")

        if (ArgumentDefinition.vararg is not None):
            VarargName: Typing.Any = ArgumentDefinition.vararg.arg
            RemainingPositional: Typing.Any = PositionalArguments[len(ExpectedPositionalNames):]
            LocalScope[VarargName] = SandboxedScope.DraconicList(RemainingPositional)

        if (ArgumentDefinition.kwarg is not None):
            KwargName: Typing.Any = ArgumentDefinition.kwarg.arg
            RemainingKeywords: Typing.Any = ({KeyItem: ValueItem for KeyItem, ValueItem in KeywordArguments.items() if (KeyItem not in ExpectedPositionalNames)})
            LocalScope[KwargName] = SandboxedScope.DraconicDictionary(RemainingKeywords)

        self.InterpreterInstance.CurrentExecutionContext.CallDepth += 1
        self.InterpreterInstance.CurrentExecutionContext.CheckCallDepth()
        try:
            if isinstance(self.FunctionNode, AbstractSyntaxTree.Lambda):
                return self.InterpreterInstance.EvaluateNode(self.FunctionNode.body, LocalScope, self.InterpreterInstance.CurrentExecutionContext)

            try:
                self.InterpreterInstance.ExecuteStatements(self.FunctionNode.body, LocalScope, self.InterpreterInstance.CurrentExecutionContext)
                return None

            except Exceptions.ReturnSignal as Signal:
                return Signal.ReturnValue

        finally:
            self.InterpreterInstance.CurrentExecutionContext.CallDepth -= 1

class DraconicInterpreter:
    def __init__(self, Config: Typing.Optional[DraconicExecutionConfig] = None, DiceRoller: Typing.Optional[Dice.DiceRollerService] = None) -> None:
        self.Config                 : DraconicExecutionConfig                  = Config if (Config is not None) else DraconicExecutionConfig()
        self.BuiltinsFactory        : SandboxedScope.SafeBuiltinsFactory       = SandboxedScope.SafeBuiltinsFactory(DiceRoller)
        self.CurrentExecutionContext: ASTExecutionContext                      = ASTExecutionContext(self.Config)
        self.SecurityVisitor        : DraconicSecurityVisitor                  = DraconicSecurityVisitor(self.Config.MaxStringLength)
        self.BlockASTCache          : dict[str, AbstractSyntaxTree.Module]     = dict()
        self.ExpressionASTCache     : dict[str, AbstractSyntaxTree.Expression] = dict()

    def EvaluateNode(self, Node: AbstractSyntaxTree.AST, Scope: dict[str, Typing.Any], Context: ASTExecutionContext) -> Typing.Any:
        Context.CheckExecutionLimits()

        if isinstance(Node, AbstractSyntaxTree.Constant):
            return Node.value

        if isinstance(Node, AbstractSyntaxTree.Name):
            if (Node.id in BANNED_IDENTIFIERS):
                raise Exceptions.DraconicSecurityError(f"Access to restricted identifier '{Node.id}' is prohibited")

            if Node.id.startswith("_"):
                raise Exceptions.DraconicSecurityError(f"Access to private identifier '{Node.id}' is prohibited")

            if Node.id in Scope:
                return Scope[Node.id]

            raise NameError(f"Name '{Node.id}' is not defined")

        if isinstance(Node, AbstractSyntaxTree.UnaryOp):
            OperandValue: Typing.Any = self.EvaluateNode(Node.operand, Scope, Context)
            if isinstance(Node.op, AbstractSyntaxTree.UAdd):
                return +OperandValue

            if isinstance(Node.op, AbstractSyntaxTree.USub):
                return -OperandValue

            if isinstance(Node.op, AbstractSyntaxTree.Not):
                return not OperandValue

            if isinstance(Node.op, AbstractSyntaxTree.Invert):
                return ~OperandValue

            raise Exceptions.DraconicSecurityError(f"Unsupported unary operator: {type(Node.op).__name__}")

        if isinstance(Node, AbstractSyntaxTree.BinOp):
            LeftValue : Typing.Any = self.EvaluateNode(Node.left, Scope, Context)
            RightValue: Typing.Any = self.EvaluateNode(Node.right, Scope, Context)

            if isinstance(Node.op, AbstractSyntaxTree.Add):
                if isinstance(LeftValue, str) or isinstance(RightValue, str):
                    if (len(str(LeftValue)) + len(str(RightValue)) > Context.Config.MaxStringLength):
                        raise Exceptions.DraconicExecutionError(f"String length limit of {Context.Config.MaxStringLength} exceeded")

                return LeftValue + RightValue

            if isinstance(Node.op, AbstractSyntaxTree.Sub):
                return LeftValue - RightValue

            if isinstance(Node.op, AbstractSyntaxTree.Mult):
                if isinstance(LeftValue, str) and isinstance(RightValue, int):
                    if (RightValue > 0) and ((len(LeftValue) * RightValue) > Context.Config.MaxStringLength):
                        raise Exceptions.DraconicExecutionError(f"String length limit of {Context.Config.MaxStringLength} exceeded")

                elif isinstance(LeftValue, int) and isinstance(RightValue, str):
                    if (LeftValue > 0) and ((len(RightValue) * LeftValue) > Context.Config.MaxStringLength):
                        raise Exceptions.DraconicExecutionError(f"String length limit of {Context.Config.MaxStringLength} exceeded")

                return LeftValue * RightValue

            if isinstance(Node.op, AbstractSyntaxTree.Div):
                return LeftValue / RightValue

            if isinstance(Node.op, AbstractSyntaxTree.FloorDiv):
                return LeftValue // RightValue

            if isinstance(Node.op, AbstractSyntaxTree.Mod):
                return LeftValue % RightValue

            if isinstance(Node.op, AbstractSyntaxTree.Pow):
                if (abs(RightValue) > 100):
                    raise Exceptions.DraconicSecurityError("Exponent exceeds safety threshold")

                return LeftValue ** RightValue

            if isinstance(Node.op, AbstractSyntaxTree.BitAnd):
                return LeftValue & RightValue

            if isinstance(Node.op, AbstractSyntaxTree.BitOr):
                return LeftValue | RightValue

            if isinstance(Node.op, AbstractSyntaxTree.BitXor):
                return LeftValue ^ RightValue

            if isinstance(Node.op, AbstractSyntaxTree.LShift):
                return LeftValue << RightValue

            if isinstance(Node.op, AbstractSyntaxTree.RShift):
                return LeftValue >> RightValue

            raise Exceptions.DraconicSecurityError(f"Unsupported binary operator: {type(Node.op).__name__}")

        if isinstance(Node, AbstractSyntaxTree.BoolOp):
            if isinstance(Node.op, AbstractSyntaxTree.And):
                LastValue: Typing.Any = True
                for ValueNode in Node.values:
                    LastValue = self.EvaluateNode(ValueNode, Scope, Context)
                    if not LastValue:
                        return LastValue

                return LastValue

            if isinstance(Node.op, AbstractSyntaxTree.Or):
                LastValue = False
                for ValueNode in Node.values:
                    LastValue = self.EvaluateNode(ValueNode, Scope, Context)
                    if LastValue:
                        return LastValue

                return LastValue

            raise Exceptions.DraconicSecurityError(f"Unsupported boolean operator: {type(Node.op).__name__}")

        if isinstance(Node, AbstractSyntaxTree.Compare):
            CurrentLeft: Typing.Any = self.EvaluateNode(Node.left, Scope, Context)
            for ComparatorOp, ComparatorNode in zip(Node.ops, Node.comparators):
                ComparatorValue : Typing.Any = self.EvaluateNode(ComparatorNode, Scope, Context)
                ComparisonResult: bool       = False

                if isinstance(ComparatorOp, AbstractSyntaxTree.Eq):
                    ComparisonResult = (CurrentLeft == ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.NotEq):
                    ComparisonResult = (CurrentLeft != ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.Lt):
                    ComparisonResult = (CurrentLeft < ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.LtE):
                    ComparisonResult = (CurrentLeft <= ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.Gt):
                    ComparisonResult = (CurrentLeft > ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.GtE):
                    ComparisonResult = (CurrentLeft >= ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.In):
                    ComparisonResult = (CurrentLeft in ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.NotIn):
                    ComparisonResult = (CurrentLeft not in ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.Is):
                    ComparisonResult = (CurrentLeft is ComparatorValue)

                elif isinstance(ComparatorOp, AbstractSyntaxTree.IsNot):
                    ComparisonResult = (CurrentLeft is not ComparatorValue)

                else:
                    raise Exceptions.DraconicSecurityError(f"Unsupported comparison operator: {type(ComparatorOp).__name__}")

                if not ComparisonResult:
                    return False

                CurrentLeft = ComparatorValue

            return True

        if isinstance(Node, AbstractSyntaxTree.IfExp):
            TestResult: Typing.Any = self.EvaluateNode(Node.test, Scope, Context)
            if TestResult:
                return self.EvaluateNode(Node.body, Scope, Context)

            return self.EvaluateNode(Node.orelse, Scope, Context)

        if isinstance(Node, AbstractSyntaxTree.NamedExpr):
            CalculatedValue: Typing.Any = self.EvaluateNode(Node.value, Scope, Context)
            self.AssignTarget(Node.target, CalculatedValue, Scope, Context)
            return CalculatedValue

        if isinstance(Node, AbstractSyntaxTree.Call):
            CallableTarget: Typing.Any = self.EvaluateNode(Node.func, Scope, Context)
            if not callable(CallableTarget):
                raise Exceptions.DraconicExecutionError(f"Target is not callable: {CallableTarget}")

            EvaluatedArguments: list[Typing.Any] = []
            for ArgNode in Node.args:
                if isinstance(ArgNode, AbstractSyntaxTree.Starred):
                    StarredElements: Typing.Any = self.EvaluateNode(ArgNode.value, Scope, Context)
                    EvaluatedArguments.extend(StarredElements)

                else:
                    EvaluatedArguments.append(self.EvaluateNode(ArgNode, Scope, Context))

            EvaluatedKeywords: dict[str, Typing.Any] = dict()
            for KeywordItem in Node.keywords:
                if (KeywordItem.arg is not None):
                    EvaluatedKeywords[KeywordItem.arg] = self.EvaluateNode(KeywordItem.value, Scope, Context)

                else:
                    UnpackedDictionary: Typing.Any = self.EvaluateNode(KeywordItem.value, Scope, Context)
                    if isinstance(UnpackedDictionary, dict):
                        EvaluatedKeywords.update(UnpackedDictionary)

            return CallableTarget(*EvaluatedArguments, **EvaluatedKeywords)

        if isinstance(Node, AbstractSyntaxTree.Attribute):
            if Node.attr.startswith("_") or (Node.attr in SandboxedScope.BANNED_DUNDER_ATTRIBUTES):
                raise Exceptions.DraconicSecurityError(f"Access to private attribute '{Node.attr}' is prohibited")

            TargetObject: Typing.Any = self.EvaluateNode(Node.value, Scope, Context)
            if isinstance(TargetObject, dict):
                if Node.attr in TargetObject:
                    return TargetObject[Node.attr]

            return getattr(TargetObject, Node.attr)

        if isinstance(Node, AbstractSyntaxTree.Subscript):
            TargetObject             = self.EvaluateNode(Node.value, Scope, Context)
            IndexKey    : Typing.Any = self.EvaluateNode(Node.slice, Scope, Context)
            if isinstance(IndexKey, str) and (IndexKey.startswith("_") or (IndexKey in SandboxedScope.BANNED_DUNDER_ATTRIBUTES)):
                raise Exceptions.DraconicSecurityError(f"Access to private attribute or key '{IndexKey}' is prohibited")

            return TargetObject[IndexKey]

        if isinstance(Node, AbstractSyntaxTree.Slice):
            LowerValue: Typing.Any = self.EvaluateNode(Node.lower, Scope, Context) if (Node.lower is not None) else None
            UpperValue: Typing.Any = self.EvaluateNode(Node.upper, Scope, Context) if (Node.upper is not None) else None
            StepValue : Typing.Any = self.EvaluateNode(Node.step, Scope, Context) if (Node.step is not None) else None
            return slice(LowerValue, UpperValue, StepValue)

        if isinstance(Node, AbstractSyntaxTree.List):
            ResultList: SandboxedScope.DraconicList = SandboxedScope.DraconicList()
            for ElementNode in Node.elts:
                if isinstance(ElementNode, AbstractSyntaxTree.Starred):
                    StarredCollection: Typing.Any = self.EvaluateNode(ElementNode.value, Scope, Context)
                    ResultList.extend(StarredCollection)

                else:
                    ResultList.append(self.EvaluateNode(ElementNode, Scope, Context))

            return ResultList

        if isinstance(Node, AbstractSyntaxTree.Tuple):
            ResultTupleElements: list[Typing.Any] = []
            for ElementNode in Node.elts:
                if isinstance(ElementNode, AbstractSyntaxTree.Starred):
                    StarredCollection = self.EvaluateNode(ElementNode.value, Scope, Context)
                    ResultTupleElements.extend(StarredCollection)

                else:
                    ResultTupleElements.append(self.EvaluateNode(ElementNode, Scope, Context))

            return tuple(ResultTupleElements)

        if isinstance(Node, AbstractSyntaxTree.Set):
            ResultSet: SandboxedScope.DraconicSet = SandboxedScope.DraconicSet()
            for ElementNode in Node.elts:
                ResultSet.add(self.EvaluateNode(ElementNode, Scope, Context))

            return ResultSet

        if isinstance(Node, AbstractSyntaxTree.Dict):
            ResultDictionary: SandboxedScope.DraconicDictionary = SandboxedScope.DraconicDictionary()
            for KeyNode, ValueNode in zip(Node.keys, Node.values):
                if (KeyNode is not None):
                    EvaluatedKey: Typing.Any = self.EvaluateNode(KeyNode, Scope, Context)
                    EvaluatedValue: Typing.Any = self.EvaluateNode(ValueNode, Scope, Context)
                    ResultDictionary[EvaluatedKey] = EvaluatedValue

                else:
                    UnpackedDictionary = self.EvaluateNode(ValueNode, Scope, Context)
                    if isinstance(UnpackedDictionary, dict):
                        ResultDictionary.update(UnpackedDictionary)

            return ResultDictionary

        if isinstance(Node, AbstractSyntaxTree.ListComp):
            return self.EvaluateListComprehension(Node, Scope, Context)

        if isinstance(Node, AbstractSyntaxTree.DictComp):
            return self.EvaluateDictionaryComprehension(Node, Scope, Context)

        if isinstance(Node, AbstractSyntaxTree.SetComp):
            return self.EvaluateSetComprehension(Node, Scope, Context)

        if isinstance(Node, AbstractSyntaxTree.GeneratorExp):
            return self.EvaluateListComprehension(Node, Scope, Context)

        if isinstance(Node, AbstractSyntaxTree.FormattedValue):
            FormattedTarget: Typing.Any = self.EvaluateNode(Node.value, Scope, Context)
            SpecFormat     : str        = Node.format_spec.values[0].value if (Node.format_spec is not None and Node.format_spec.values and isinstance(Node.format_spec.values[0], AbstractSyntaxTree.Constant)) else ""
            FormattedOutput: str        = format(FormattedTarget, SpecFormat) if (SpecFormat) else str(FormattedTarget)
            if (len(FormattedOutput) > Context.Config.MaxStringLength):
                raise Exceptions.DraconicExecutionError(f"String length limit of {Context.Config.MaxStringLength} exceeded")

            return FormattedOutput

        if isinstance(Node, AbstractSyntaxTree.JoinedStr):
            JoinedComponents: list[str] = [str(self.EvaluateNode(PartNode, Scope, Context)) for PartNode in Node.values]
            ResultJoined    : str       = "".join(JoinedComponents)
            if (len(ResultJoined) > Context.Config.MaxStringLength):
                raise Exceptions.DraconicExecutionError(f"String length limit of {Context.Config.MaxStringLength} exceeded")

            return ResultJoined

        if isinstance(Node, AbstractSyntaxTree.Lambda):
            return DraconicFunction(Node, Scope, self)

        raise Exceptions.DraconicSecurityError(f"Unsupported syntax expression: {type(Node).__name__}")

    def EvaluateListComprehension(self, Node: Typing.Union[AbstractSyntaxTree.ListComp, AbstractSyntaxTree.GeneratorExp], Scope: dict[str, Typing.Any], Context: ASTExecutionContext) -> SandboxedScope.DraconicList:
        AccumulatedResults     : SandboxedScope.DraconicList = SandboxedScope.DraconicList()
        LocalComprehensionScope: dict[str, Typing.Any]       = dict(Scope)

        def RecursiveGeneratorExecution(GeneratorIndex: int) -> None:
            if (GeneratorIndex >= len(Node.generators)):
                EvaluatedElement: Typing.Any = self.EvaluateNode(Node.elt, LocalComprehensionScope, Context)
                AccumulatedResults.append(EvaluatedElement)
                return

            CurrentGenerator: AbstractSyntaxTree.comprehension = Node.generators[GeneratorIndex]
            IterableTarget  : Typing.Any                       = self.EvaluateNode(CurrentGenerator.iter, LocalComprehensionScope, Context)

            for LoopItem in IterableTarget:
                Context.IncrementLoopIterations()
                self.AssignTarget(CurrentGenerator.target, LoopItem, LocalComprehensionScope, Context)

                MeetsFilterConditions: bool = True
                for FilterCondition in CurrentGenerator.ifs:
                    if not self.EvaluateNode(FilterCondition, LocalComprehensionScope, Context):
                        MeetsFilterConditions = False
                        break

                if MeetsFilterConditions:
                    RecursiveGeneratorExecution(GeneratorIndex + 1)

        RecursiveGeneratorExecution(0)
        return AccumulatedResults

    def EvaluateDictionaryComprehension(self, Node: AbstractSyntaxTree.DictComp, Scope: dict[str, Typing.Any], Context: ASTExecutionContext) -> SandboxedScope.DraconicDictionary:
        AccumulatedResults     : SandboxedScope.DraconicDictionary = SandboxedScope.DraconicDictionary()
        LocalComprehensionScope: dict[str, Typing.Any]             = dict(Scope)

        def RecursiveGeneratorExecution(GeneratorIndex: int) -> None:
            if (GeneratorIndex >= len(Node.generators)):
                EvaluatedKey  : Typing.Any = self.EvaluateNode(Node.key, LocalComprehensionScope, Context)
                EvaluatedValue: Typing.Any = self.EvaluateNode(Node.value, LocalComprehensionScope, Context)
                AccumulatedResults[EvaluatedKey] = EvaluatedValue
                return

            CurrentGenerator: AbstractSyntaxTree.comprehension = Node.generators[GeneratorIndex]
            IterableTarget  : Typing.Any                       = self.EvaluateNode(CurrentGenerator.iter, LocalComprehensionScope, Context)

            for LoopItem in IterableTarget:
                Context.IncrementLoopIterations()
                self.AssignTarget(CurrentGenerator.target, LoopItem, LocalComprehensionScope, Context)

                MeetsFilterConditions: bool = True
                for FilterCondition in CurrentGenerator.ifs:
                    if not self.EvaluateNode(FilterCondition, LocalComprehensionScope, Context):
                        MeetsFilterConditions = False
                        break

                if MeetsFilterConditions:
                    RecursiveGeneratorExecution(GeneratorIndex + 1)

        RecursiveGeneratorExecution(0)
        return AccumulatedResults

    def EvaluateSetComprehension(self, Node: AbstractSyntaxTree.SetComp, Scope: dict[str, Typing.Any], Context: ASTExecutionContext) -> SandboxedScope.DraconicSet:
        AccumulatedResults     : SandboxedScope.DraconicSet = SandboxedScope.DraconicSet()
        LocalComprehensionScope: dict[str, Typing.Any]      = dict(Scope)

        def RecursiveGeneratorExecution(GeneratorIndex: int) -> None:
            if (GeneratorIndex >= len(Node.generators)):
                EvaluatedElement: Typing.Any = self.EvaluateNode(Node.elt, LocalComprehensionScope, Context)
                AccumulatedResults.add(EvaluatedElement)
                return

            CurrentGenerator: AbstractSyntaxTree.comprehension = Node.generators[GeneratorIndex]
            IterableTarget  : Typing.Any                       = self.EvaluateNode(CurrentGenerator.iter, LocalComprehensionScope, Context)

            for LoopItem in IterableTarget:
                Context.IncrementLoopIterations()
                self.AssignTarget(CurrentGenerator.target, LoopItem, LocalComprehensionScope, Context)

                MeetsFilterConditions: bool = True
                for FilterCondition in CurrentGenerator.ifs:
                    if not self.EvaluateNode(FilterCondition, LocalComprehensionScope, Context):
                        MeetsFilterConditions = False
                        break

                if MeetsFilterConditions:
                    RecursiveGeneratorExecution(GeneratorIndex + 1)

        RecursiveGeneratorExecution(0)
        return AccumulatedResults

    def AssignTarget(self, TargetNode: AbstractSyntaxTree.AST, AssignedValue: Typing.Any, Scope: dict[str, Typing.Any], Context: ASTExecutionContext) -> None:
        if isinstance(TargetNode, AbstractSyntaxTree.Name):
            if TargetNode.id.startswith("__"):
                raise Exceptions.DraconicSecurityError(f"Private identifier assignment prohibited: '{TargetNode.id}'")

            Scope[TargetNode.id] = AssignedValue
            return

        if isinstance(TargetNode, (AbstractSyntaxTree.Tuple, AbstractSyntaxTree.List)):
            TargetElements: list[AbstractSyntaxTree.AST] = TargetNode.elts
            ValuesList    : list[Typing.Any]             = list(AssignedValue)

            HasStarredTarget: bool = any(isinstance(Elem, AbstractSyntaxTree.Starred) for Elem in TargetElements)
            if not HasStarredTarget:
                if (len(TargetElements) != len(ValuesList)):
                    raise Exceptions.DraconicExecutionError(f"Cannot unpack {len(ValuesList)} values to {len(TargetElements)} targets")

                for SubTarget, SubValue in zip(TargetElements, ValuesList):
                    self.AssignTarget(SubTarget, SubValue, Scope, Context)

                return

            StarredIndex: int = next(Index for Index, Elem in enumerate(TargetElements) if isinstance(Elem, AbstractSyntaxTree.Starred))
            BeforeCount : int = StarredIndex
            AfterCount  : int = len(TargetElements) - StarredIndex - 1

            if (len(ValuesList) < (BeforeCount + AfterCount)):
                raise Exceptions.DraconicExecutionError(f"Not enough values to unpack for starred assignment")

            for Index in range(BeforeCount):
                self.AssignTarget(TargetElements[Index], ValuesList[Index], Scope, Context)

            MiddleValues: list[Typing.Any]           = ValuesList[BeforeCount:len(ValuesList) - AfterCount]
            StarredNode : AbstractSyntaxTree.Starred = TargetElements[StarredIndex]
            self.AssignTarget(StarredNode.value, SandboxedScope.DraconicList(MiddleValues), Scope, Context)

            for Index in range(AfterCount):
                TargetIndex: int = len(TargetElements) - AfterCount + Index
                ValueIndex : int = len(ValuesList) - AfterCount + Index
                self.AssignTarget(TargetElements[TargetIndex], ValuesList[ValueIndex], Scope, Context)

            return

        if isinstance(TargetNode, AbstractSyntaxTree.Subscript):
            TargetContainer: Typing.Any = self.EvaluateNode(TargetNode.value, Scope, Context)
            IndexKey       : Typing.Any = self.EvaluateNode(TargetNode.slice, Scope, Context)
            if isinstance(IndexKey, str) and (IndexKey.startswith("_") or (IndexKey in SandboxedScope.BANNED_DUNDER_ATTRIBUTES)):
                raise Exceptions.DraconicSecurityError(f"Private attribute assignment prohibited: '{IndexKey}'")

            TargetContainer[IndexKey] = AssignedValue
            return

        if isinstance(TargetNode, AbstractSyntaxTree.Attribute):
            if TargetNode.attr.startswith("_") or (TargetNode.attr in SandboxedScope.BANNED_DUNDER_ATTRIBUTES):
                raise Exceptions.DraconicSecurityError(f"Private attribute assignment prohibited: '{TargetNode.attr}'")

            TargetContainer = self.EvaluateNode(TargetNode.value, Scope, Context)
            if isinstance(TargetContainer, dict):
                TargetContainer[TargetNode.attr] = AssignedValue

            else:
                setattr(TargetContainer, TargetNode.attr, AssignedValue)

            return

        raise Exceptions.DraconicSecurityError(f"Unsupported assignment target: {type(TargetNode).__name__}")

    def ExecuteStatement(self, Statement: AbstractSyntaxTree.stmt, Scope: dict[str, Typing.Any], Context: ASTExecutionContext) -> Typing.Any:
        Context.CheckExecutionLimits()

        if isinstance(Statement, AbstractSyntaxTree.Assign):
            EvaluatedValue: Typing.Any = self.EvaluateNode(Statement.value, Scope, Context)
            for SingleTarget in Statement.targets:
                self.AssignTarget(SingleTarget, EvaluatedValue, Scope, Context)

            return None

        if isinstance(Statement, AbstractSyntaxTree.AugAssign):
            AugmentedValue: Typing.Any = self.EvaluateNode(Statement.value, Scope, Context)
            CurrentValue  : Typing.Any = self.EvaluateNode(Statement.target, Scope, Context)

            NewValue: Typing.Any = None
            if isinstance(Statement.op, AbstractSyntaxTree.Add):
                NewValue = CurrentValue + AugmentedValue

            elif isinstance(Statement.op, AbstractSyntaxTree.Sub):
                NewValue = CurrentValue - AugmentedValue

            elif isinstance(Statement.op, AbstractSyntaxTree.Mult):
                NewValue = CurrentValue * AugmentedValue

            elif isinstance(Statement.op, AbstractSyntaxTree.Div):
                NewValue = CurrentValue / AugmentedValue

            elif isinstance(Statement.op, AbstractSyntaxTree.FloorDiv):
                NewValue = CurrentValue // AugmentedValue

            elif isinstance(Statement.op, AbstractSyntaxTree.Mod):
                NewValue = CurrentValue % AugmentedValue

            elif isinstance(Statement.op, AbstractSyntaxTree.Pow):
                if (abs(AugmentedValue) > 100):
                    raise Exceptions.DraconicSecurityError("Exponent exceeds safety threshold")

                NewValue = CurrentValue ** AugmentedValue

            else:
                raise Exceptions.DraconicSecurityError(f"Unsupported augmented operator: {type(Statement.op).__name__}")

            self.AssignTarget(Statement.target, NewValue, Scope, Context)
            return None

        if isinstance(Statement, AbstractSyntaxTree.Expr):
            return self.EvaluateNode(Statement.value, Scope, Context)

        if isinstance(Statement, AbstractSyntaxTree.Return):
            EvaluatedReturn: Typing.Any = self.EvaluateNode(Statement.value, Scope, Context) if (Statement.value is not None) else None
            raise Exceptions.ReturnSignal(EvaluatedReturn)

        if isinstance(Statement, AbstractSyntaxTree.Break):
            raise Exceptions.BreakSignal()

        if isinstance(Statement, AbstractSyntaxTree.Continue):
            raise Exceptions.ContinueSignal()

        if isinstance(Statement, AbstractSyntaxTree.Pass):
            return None

        if isinstance(Statement, AbstractSyntaxTree.If):
            ConditionResult: Typing.Any = self.EvaluateNode(Statement.test, Scope, Context)
            if ConditionResult:
                return self.ExecuteStatements(Statement.body, Scope, Context)

            elif Statement.orelse:
                return self.ExecuteStatements(Statement.orelse, Scope, Context)

            return None

        if isinstance(Statement, AbstractSyntaxTree.For):
            IterableTarget: Typing.Any = self.EvaluateNode(Statement.iter, Scope, Context)
            LoopBroken    : bool       = False

            for ElementItem in IterableTarget:
                Context.IncrementLoopIterations()
                self.AssignTarget(Statement.target, ElementItem, Scope, Context)
                try:
                    self.ExecuteStatements(Statement.body, Scope, Context)

                except Exceptions.ContinueSignal:
                    continue

                except Exceptions.BreakSignal:
                    LoopBroken = True
                    break

            if (not LoopBroken) and Statement.orelse:
                return self.ExecuteStatements(Statement.orelse, Scope, Context)

            return None

        if isinstance(Statement, AbstractSyntaxTree.While):
            LoopBroken: bool = False
            while self.EvaluateNode(Statement.test, Scope, Context):
                Context.IncrementLoopIterations()
                try:
                    self.ExecuteStatements(Statement.body, Scope, Context)

                except Exceptions.ContinueSignal:
                    continue

                except Exceptions.BreakSignal:
                    LoopBroken = True
                    break

            if (not LoopBroken) and Statement.orelse:
                return self.ExecuteStatements(Statement.orelse, Scope, Context)

            return None

        if isinstance(Statement, AbstractSyntaxTree.FunctionDef):
            if Statement.name.startswith("_"):
                raise Exceptions.DraconicSecurityError(f"Private function name prohibited: '{Statement.name}'")

            Scope[Statement.name] = DraconicFunction(Statement, Scope, self)
            return None

        if isinstance(Statement, AbstractSyntaxTree.Try):
            try:
                return self.ExecuteStatements(Statement.body, Scope, Context)

            except (Exceptions.ReturnSignal, Exceptions.BreakSignal, Exceptions.ContinueSignal):
                raise

            except Exception as TrappedError:
                HandlerExecuted: bool = False
                for Handler in Statement.handlers:
                    if (Handler.type is None):
                        HandlerExecuted = True
                        if (Handler.name is not None):
                            Scope[Handler.name] = TrappedError

                        self.ExecuteStatements(Handler.body, Scope, Context)
                        break

                    ExpectedType: Typing.Any = self.EvaluateNode(Handler.type, Scope, Context)
                    if isinstance(TrappedError, ExpectedType):
                        HandlerExecuted = True
                        if (Handler.name is not None):
                            Scope[Handler.name] = TrappedError

                        self.ExecuteStatements(Handler.body, Scope, Context)
                        break

                if not HandlerExecuted:
                    raise

            finally:
                if Statement.finalbody:
                    self.ExecuteStatements(Statement.finalbody, Scope, Context)

            return None

        raise Exceptions.DraconicSecurityError(f"Unsupported statement: {type(Statement).__name__}")

    def ExecuteStatements(self, StatementsList: list[AbstractSyntaxTree.stmt], Scope: dict[str, Typing.Any], Context: ASTExecutionContext) -> Typing.Any:
        LastStatementResult: Typing.Any = None
        for StatementItem in StatementsList:
            LastStatementResult = self.ExecuteStatement(StatementItem, Scope, Context)

        return LastStatementResult

    def EvaluateDraconicBlock(self, CodeText: str, Scope: dict[str, Typing.Any]) -> str:
        CleanCode: str = CodeText.strip()
        if not CleanCode:
            return ""

        Context: ASTExecutionContext = ASTExecutionContext(self.Config)
        self.CurrentExecutionContext = Context
        try:
            if CleanCode in self.BlockASTCache:
                ParsedAST: AbstractSyntaxTree.Module = self.BlockASTCache[CleanCode]

            else:
                ParsedAST = AbstractSyntaxTree.parse(CleanCode, mode = "exec")
                self.SecurityVisitor.visit(ParsedAST)
                if (len(self.BlockASTCache) >= MAXIMUM_AST_CACHE_ENTRIES):
                    self.BlockASTCache.clear()

                self.BlockASTCache[CleanCode] = ParsedAST

            OutcomeResult: Typing.Any            = None
            try:
                OutcomeResult = self.ExecuteStatements(ParsedAST.body, Scope, Context)

            except Exceptions.ReturnSignal as Signal:
                OutcomeResult = Signal.ReturnValue

            OutcomeString: str = str(OutcomeResult) if (OutcomeResult is not None) else ""
            if (len(OutcomeString) > self.Config.MaxStringLength):
                raise Exceptions.DraconicExecutionError(f"String length limit of {self.Config.MaxStringLength} exceeded")

            return OutcomeString

        except Exception as ExecutionError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Draconic Block Error: Detail=\"{str(ExecutionError)}\"")
            return f"[Error: {str(ExecutionError)}]"

    def EvaluateDraconicExpression(self, ExpressionText: str, Scope: dict[str, Typing.Any]) -> str:
        CleanExpression: str = ExpressionText.strip()
        if not CleanExpression:
            return ""

        Context: ASTExecutionContext = ASTExecutionContext(self.Config)
        self.CurrentExecutionContext = Context
        try:
            if CleanExpression in self.ExpressionASTCache:
                ParsedAST: AbstractSyntaxTree.Expression = self.ExpressionASTCache[CleanExpression]

            else:
                ParsedAST = AbstractSyntaxTree.parse(CleanExpression, mode = "eval")
                self.SecurityVisitor.visit(ParsedAST)
                if (len(self.ExpressionASTCache) >= MAXIMUM_AST_CACHE_ENTRIES):
                    self.ExpressionASTCache.clear()

                self.ExpressionASTCache[CleanExpression] = ParsedAST

            OutcomeResult: Typing.Any = self.EvaluateNode(ParsedAST.body, Scope, Context)
            OutcomeString: str        = str(OutcomeResult)
            if (len(OutcomeString) > self.Config.MaxStringLength):
                raise Exceptions.DraconicExecutionError(f"String length limit of {self.Config.MaxStringLength} exceeded")

            return OutcomeString

        except Exception as EvalError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Draconic Expression Error: Detail=\"{str(EvalError)}\"")
            return f"[Error: {str(EvalError)}]"

    def FormatInlineDiceMatch(self, MatchObject: RegularExpressions.Match) -> str:
        DiceExpr: str = MatchObject.group(1)
        try:
            RollResult: int = self.BuiltinsFactory.Roll(DiceExpr)
            return str(RollResult)

        except Exception:
            return MatchObject.group(0)

    def InterpolateTemplate(self, TemplateText: str, Scope: dict[str, Typing.Any], ArgumentsList: list[str], ArgumentsString: str) -> str:
        WorkingText: str = TemplateText

        WorkingText = ALL_ARGUMENTS_PATTERN.sub(ArgumentsString, WorkingText)
        WorkingText = ARGUMENT_INDEX_PATTERN.sub(lambda M: (ArgumentsList[int(M.group(1)) - 1] if (0 <= (int(M.group(1)) - 1) < len(ArgumentsList)) else ""), WorkingText)
        WorkingText = DRAC2_BLOCK_PATTERN.sub(lambda M: self.EvaluateDraconicBlock(M.group(1), Scope), WorkingText)
        WorkingText = DRAC1_EXPRESSION_PATTERN.sub(lambda M: self.EvaluateDraconicExpression(M.group(1), Scope), WorkingText)
        WorkingText = INLINE_DICE_PATTERN.sub(self.FormatInlineDiceMatch, WorkingText)
        return WorkingText.strip()

