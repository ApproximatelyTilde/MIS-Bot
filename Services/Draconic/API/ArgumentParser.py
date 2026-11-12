import re                             as RegularExpressions
import typing                         as Typing
import Services.Draconic.SandboxedScope as SandboxedScope

TOKEN_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"""(?:[^\s"']+|"[^"]*"|'[^']*')+""")

class ParsedArguments:
    def __init__(self, RawArgumentString: str) -> None:
        self.RawString          : str                          = RawArgumentString
        self.OptionsDictionary  : dict[str, list[str]]         = {}
        self.PositionalArguments: SandboxedScope.DraconicList  = SandboxedScope.DraconicList()
        self.IgnoredOptions     : set[str]                     = set()
        self.ParseArguments(RawArgumentString)

    def ParseArguments(self, ArgumentString: str) -> None:
        CleanTokens: list[str] = TOKEN_PATTERN.findall(ArgumentString)
        TokenIndex : int       = 0

        while (TokenIndex < len(CleanTokens)):
            TokenItem: str = CleanTokens[TokenIndex].strip()
            if TokenItem.startswith("\"") and TokenItem.endswith("\""):
                TokenItem = TokenItem[1:-1]

            elif TokenItem.startswith("'") and TokenItem.endswith("'"):
                TokenItem = TokenItem[1:-1]

            if TokenItem.startswith("-") and (len(TokenItem) > 1) and (not TokenItem[1:].isdigit()):
                FlagKey: str = TokenItem.lstrip("-").lower()
                OptionValuesList: list[str] = self.OptionsDictionary.setdefault(FlagKey, [])

                if (TokenIndex + 1 < len(CleanTokens)):
                    NextToken: str = CleanTokens[TokenIndex + 1].strip()
                    if NextToken.startswith("\"") and NextToken.endswith("\""):
                        NextToken = NextToken[1:-1]

                    elif NextToken.startswith("'") and NextToken.endswith("'"):
                        NextToken = NextToken[1:-1]

                    if not (NextToken.startswith("-") and (len(NextToken) > 1) and (not NextToken[1:].isdigit())):
                        OptionValuesList.append(NextToken)
                        TokenIndex += 2
                        continue

                OptionValuesList.append("True")
                TokenIndex += 1

            else:
                self.PositionalArguments.append(TokenItem)
                TokenIndex += 1

    def get(self, OptionName: str, DefaultValue: Typing.Any = None) -> Typing.Any:
        CleanOptionKey: str = OptionName.lstrip("-").lower()
        if CleanOptionKey in self.IgnoredOptions:
            return DefaultValue

        if CleanOptionKey in self.OptionsDictionary:
            ValuesList: list[str] = self.OptionsDictionary[CleanOptionKey]
            if (CleanOptionKey == "t"):
                SpecificTargets: SandboxedScope.DraconicList = SandboxedScope.DraconicList()
                for ValueString in ValuesList:
                    if ("," in ValueString):
                        for TargetPart in ValueString.split(","):
                            CleanTarget: str = TargetPart.strip()
                            if CleanTarget:
                                SpecificTargets.append(CleanTarget)

                    else:
                        SpecificTargets.append(ValueString.strip())

                return SpecificTargets

            return SandboxedScope.DraconicList(ValuesList)

        return DefaultValue

    def last(self, OptionName: str, DefaultValue: Typing.Any = None) -> Typing.Any:
        CleanOptionKey: str = OptionName.lstrip("-").lower()
        if CleanOptionKey in self.IgnoredOptions:
            return DefaultValue

        if CleanOptionKey in self.OptionsDictionary:
            ValuesList: list[str] = self.OptionsDictionary[CleanOptionKey]
            return ValuesList[-1] if ValuesList else DefaultValue

        return DefaultValue

    def adv(self, DefaultValue: int = 0) -> int:
        HasAdvantage   : bool = ("adv" in self.OptionsDictionary)
        HasDisadvantage: bool = (("dis" in self.OptionsDictionary) or ("disadv" in self.OptionsDictionary))

        if (HasAdvantage and HasDisadvantage):
            return 0

        if HasAdvantage:
            return 1

        if HasDisadvantage:
            return -1

        return DefaultValue

    def ignore(self, *OptionNames: str) -> None:
        for OptionName in OptionNames:
            self.IgnoredOptions.add(OptionName.lstrip("-").lower())

    def join(self, SeparatorString: str = " ") -> str:
        return SeparatorString.join(self.PositionalArguments)

def CreateArgumentParser(RawArgumentString: str) -> ParsedArguments:
    return ParsedArguments(RawArgumentString)

