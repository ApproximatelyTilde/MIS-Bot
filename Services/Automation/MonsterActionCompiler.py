import re                                   as RegularExpressions
import typing                               as Typing
import Services.DebugService                as Debug
import Services.Automation.AutomationModels as Models

TAG_HIT_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"\{@hit\s+([+-]?\d+)\}", RegularExpressions.IGNORECASE)
RAW_HIT_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"([+-]?\d+)\s+to\s+hit", RegularExpressions.IGNORECASE)
TAG_DC_PATTERN     : RegularExpressions.Pattern = RegularExpressions.compile(r"\{@dc\s+(\d+)\}\s*([a-zA-Z]+)?", RegularExpressions.IGNORECASE)
RAW_DC_PATTERN     : RegularExpressions.Pattern = RegularExpressions.compile(r"DC\s+(\d+)\s+([a-zA-Z]+)?\s+saving\s+throw", RegularExpressions.IGNORECASE)
TAG_DAMAGE_PATTERN : RegularExpressions.Pattern = RegularExpressions.compile(r"\{@damage\s+([^}]+)\}\)?\s*([a-zA-Z]+)?\s*(?:damage)?", RegularExpressions.IGNORECASE)
RAW_DAMAGE_PATTERN : RegularExpressions.Pattern = RegularExpressions.compile(r"\(?(\d+d\d+(?:\s*[+-]\s*\d+)?)\)?\s*([a-zA-Z]+)?\s+damage", RegularExpressions.IGNORECASE)
TAG_COND_PATTERN   : RegularExpressions.Pattern = RegularExpressions.compile(r"\{@condition\s+([^}]+)\}", RegularExpressions.IGNORECASE)
CLEAN_TAGS_PATTERN : RegularExpressions.Pattern = RegularExpressions.compile(r"\{@[a-zA-Z]+\s+([^}]+)\}")

ABILITY_MAP: Typing.Dict[str, str] = {
    "strength"    : "str",
    "dexterity"   : "dex",
    "constitution": "con",
    "intelligence": "int",
    "wisdom"      : "wis",
    "charisma"    : "cha"
}

class MonsterActionCompiler:
    def __init__(self) -> None:
        pass

    def Strip5EToolsTags(self, RawText: str) -> str:
        Cleaned: str = CLEAN_TAGS_PATTERN.sub(r"\1", RawText)
        Cleaned      = Cleaned.replace("{@h}", "Hit: ")
        return Cleaned

    def ExtractActionEntriesText(self, ActionDictionary: Typing.Dict[str, Typing.Any]) -> str:
        Entries: list = ActionDictionary.get("entries", [])
        TextSegments: list[str] = []
        for Entry in Entries:
            if isinstance(Entry, str):
                TextSegments.append(Entry)

            elif isinstance(Entry, dict) and ("entries" in Entry):
                SubEntries = Entry.get("entries", [])
                for SubEntry in SubEntries:
                    if isinstance(SubEntry, str):
                        TextSegments.append(SubEntry)

        return " ".join(TextSegments)

    def ParseDamageNodes(self, ActionText: str) -> list[Models.EffectNode]:
        DamageNodes: list[Models.EffectNode] = []
        TagMatches = TAG_DAMAGE_PATTERN.findall(ActionText)
        if TagMatches:
            for FormulaText, TypeText in TagMatches:
                CleanFormula: str                   = FormulaText.strip()
                CleanType   : Typing.Optional[str]  = TypeText.strip().lower() if TypeText else None
                DamageNode  : Models.EffectNode     = Models.EffectNode(
                    Type       = Models.AutomationEffectType.Damage,
                    Damage     = CleanFormula,
                    DamageType = CleanType
                )
                DamageNodes.append(DamageNode)

        else:
            RawMatches = RAW_DAMAGE_PATTERN.findall(ActionText)
            for FormulaText, TypeText in RawMatches:
                CleanFormula = FormulaText.strip()
                CleanType    = TypeText.strip().lower() if TypeText else None
                DamageNode   = Models.EffectNode(
                    Type       = Models.AutomationEffectType.Damage,
                    Damage     = CleanFormula,
                    DamageType = CleanType
                )
                DamageNodes.append(DamageNode)

        return DamageNodes

    def ParseConditionNodes(self, ActionText: str) -> list[Models.EffectNode]:
        ConditionNodes: list[Models.EffectNode] = []
        CondMatches = TAG_COND_PATTERN.findall(ActionText)
        for CondName in CondMatches:
            ConditionNode: Models.EffectNode = Models.EffectNode(
                Type      = Models.AutomationEffectType.Condition,
                Condition = CondName.strip().title()
            )
            ConditionNodes.append(ConditionNode)

        return ConditionNodes

    def CompileAction(self, ActionDictionary: Typing.Dict[str, Typing.Any]) -> Models.ActionDocument:
        RawName: str    = str(ActionDictionary.get("name", "Action"))
        ActionName: str = self.Strip5EToolsTags(RawName).strip()
        ActionText: str = self.ExtractActionEntriesText(ActionDictionary)
        CleanText: str  = self.Strip5EToolsTags(ActionText)

        RootEffects: list[Models.EffectNode] = []

        HitMatch = TAG_HIT_PATTERN.search(ActionText) or RAW_HIT_PATTERN.search(ActionText)
        DCMatch  = TAG_DC_PATTERN.search(ActionText) or RAW_DC_PATTERN.search(ActionText)

        if (HitMatch is not None):
            AttackBonusValue: int = int(HitMatch.group(1))
            DamageNodes     : list[Models.EffectNode] = self.ParseDamageNodes(ActionText)
            ConditionNodes  : list[Models.EffectNode] = self.ParseConditionNodes(ActionText)

            HitEffects: list[Models.EffectNode] = []
            HitEffects.extend(DamageNodes)
            HitEffects.extend(ConditionNodes)

            AttackNode: Models.EffectNode = Models.EffectNode(
                Type    = Models.AutomationEffectType.Attack,
                Amount  = AttackBonusValue,
                Hit     = HitEffects,
                Miss    = []
            )

            TargetNode: Models.EffectNode = Models.EffectNode(
                Type    = Models.AutomationEffectType.Target,
                Target  = "each",
                Effects = [AttackNode]
            )
            RootEffects.append(TargetNode)

        elif (DCMatch is not None):
            DCValue     : int                  = int(DCMatch.group(1))
            RawAbility  : Typing.Optional[str] = DCMatch.group(2)
            AbilityStat : str                  = "dex"
            if (RawAbility is not None):
                AbilityStat = ABILITY_MAP.get(RawAbility.lower(), RawAbility[:3].lower())

            FailDamageNodes: list[Models.EffectNode] = self.ParseDamageNodes(ActionText)
            SuccessDamageNodes: list[Models.EffectNode] = []

            if ("half as much damage" in ActionText.lower()) or ("half damage" in ActionText.lower()):
                for FailNode in FailDamageNodes:
                    SuccessDamageNodes.append(
                        Models.EffectNode(
                            Type       = Models.AutomationEffectType.Damage,
                            Damage     = f"({FailNode.Damage})/2",
                            DamageType = FailNode.DamageType
                        )
                    )

            FailConditionNodes: list[Models.EffectNode] = self.ParseConditionNodes(ActionText)
            FailEffects: list[Models.EffectNode] = []
            FailEffects.extend(FailDamageNodes)
            FailEffects.extend(FailConditionNodes)

            SaveNode: Models.EffectNode = Models.EffectNode(
                Type    = Models.AutomationEffectType.Save,
                Stat    = AbilityStat,
                DC      = DCValue,
                Fail    = FailEffects,
                Success = SuccessDamageNodes
            )

            TargetNode = Models.EffectNode(
                Type    = Models.AutomationEffectType.Target,
                Target  = "each",
                Effects = [SaveNode]
            )
            RootEffects.append(TargetNode)

        else:
            TextNode: Models.EffectNode = Models.EffectNode(
                Type = Models.AutomationEffectType.Text,
                Text = CleanText
            )
            RootEffects.append(TextNode)

        Document: Models.ActionDocument = Models.ActionDocument(
            Name       = ActionName,
            Phrase     = CleanText[:200] if len(CleanText) > 200 else CleanText,
            Automation = RootEffects
        )
        return Document

    def FindAndCompileMonsterAction(self, MonsterData: Typing.Dict[str, Typing.Any], ActionQuery: str) -> Typing.Optional[Models.ActionDocument]:
        NormalizedQuery: str = ActionQuery.strip().lower()
        ActionLists: list[list] = [
            MonsterData.get("action", []),
            MonsterData.get("bonus", []),
            MonsterData.get("reaction", []),
            MonsterData.get("trait", [])
        ]

        for ActionList in ActionLists:
            if not isinstance(ActionList, list):
                continue

            for ActionEntry in ActionList:
                if not isinstance(ActionEntry, dict):
                    continue

                CandidateRawName: str = str(ActionEntry.get("name", ""))
                CandidateClean  : str = self.Strip5EToolsTags(CandidateRawName).strip().lower()
                if (NormalizedQuery == CandidateClean) or (NormalizedQuery in CandidateClean):
                    return self.CompileAction(ActionEntry)

        return None
