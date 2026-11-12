import json                                    as JSONLibrary
import pathlib                                 as PathLibrary
import typing                                  as Typing
import Services.DebugService                   as Debug
import Services.Compendium.SourceFilterService as SourceFilter

DEFAULT_5ETOOLS_DATA_PATH: PathLibrary.Path = PathLibrary.Path(__file__).resolve().parent.parent / "External" / "5ETools" / "data"

class CompendiumService:
    def __init__(self, DataDirectoryPath: Typing.Optional[PathLibrary.Path] = None) -> None:
        self.DataDirectoryPath: PathLibrary.Path          = DataDirectoryPath if (DataDirectoryPath is not None) else DEFAULT_5ETOOLS_DATA_PATH
        self.SourceFilter     : SourceFilter.SourceFilterService = SourceFilter.SourceFilterService()

        self.FeaturesList      : list[dict[str, Typing.Any]] = []
        self.OptionsList    : list[dict[str, Typing.Any]] = []
        self.RulesList      : list[dict[str, Typing.Any]] = []
        self.ClassesList    : list[dict[str, Typing.Any]] = []
        self.BackgroundsList: list[dict[str, Typing.Any]] = []
        self.SpeciesList    : list[dict[str, Typing.Any]] = []
        self.ConditionsList : list[dict[str, Typing.Any]] = []
        self.DeitiesList    : list[dict[str, Typing.Any]] = []
        self.VehiclesList   : list[dict[str, Typing.Any]] = []

        self.FeaturesLoaded      : bool = False
        self.OptionsLoaded    : bool = False
        self.RulesLoaded      : bool = False
        self.ClassesLoaded    : bool = False
        self.BackgroundsLoaded: bool = False
        self.SpeciesLoaded    : bool = False
        self.ConditionsLoaded : bool = False
        self.DeitiesLoaded    : bool = False
        self.VehiclesLoaded   : bool = False

    def LoadJSONFile(self, RelativePath: str) -> Typing.Optional[dict[str, Typing.Any]]:
        TargetFilePath: PathLibrary.Path = self.DataDirectoryPath / RelativePath
        if not TargetFilePath.exists():
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Compendium File Not Found: Path=\"{TargetFilePath}\"")
            return None

        try:
            with open(TargetFilePath, "r", encoding = "utf-8") as FileReader:
                LoadedData: dict[str, Typing.Any] = JSONLibrary.load(FileReader)
                return LoadedData

        except Exception as FileException:
            Debug.LogMessage(Level = Debug.LogLevel.Error, Message = f"Failed to Load Compendium File: Path=\"{TargetFilePath}\", Error=\"{str(FileException)}\"")
            return None

    def EnsureFeaturesLoaded(self) -> None:
        if self.FeaturesLoaded:
            return

        LoadedDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("feats.json")
        if (LoadedDictionary is not None):
            self.FeaturesList = list(LoadedDictionary.get("feat", []))

        self.FeaturesLoaded = True

    def EnsureOptionsLoaded(self) -> None:
        if self.OptionsLoaded:
            return

        CombinedOptions: list[dict[str, Typing.Any]] = []
        CharacterOptionsDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("charcreationoptions.json")
        if (CharacterOptionsDictionary is not None):
            for OptionItem in CharacterOptionsDictionary.get("charoption", []):
                OptionItem["OptionCategory"] = "Character Creation Option"
                CombinedOptions.append(OptionItem)

        OptionalFeaturesDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("optionalfeatures.json")
        if (OptionalFeaturesDictionary is not None):
            for FeatureItem in OptionalFeaturesDictionary.get("optionalfeature", []):
                FeatureItem["OptionCategory"] = "Optional Feature"
                CombinedOptions.append(FeatureItem)

        self.OptionsList   = CombinedOptions
        self.OptionsLoaded = True

    def EnsureRulesLoaded(self) -> None:
        if self.RulesLoaded:
            return

        CombinedRules: list[dict[str, Typing.Any]] = []
        VariantRulesDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("variantrules.json")
        if (VariantRulesDictionary is not None):
            for RuleItem in VariantRulesDictionary.get("variantrule", []):
                RuleItem["RuleType"] = "Rule"
                CombinedRules.append(RuleItem)

        TablesDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("tables.json")
        if (TablesDictionary is not None):
            for TableItem in TablesDictionary.get("table", []):
                TableItem["RuleType"] = "Table"
                CombinedRules.append(TableItem)

        self.RulesList   = CombinedRules
        self.RulesLoaded = True

    def EnsureClassesLoaded(self) -> None:
        if self.ClassesLoaded:
            return

        ClassDirectory: PathLibrary.Path = self.DataDirectoryPath / "class"
        LoadedClasses : list[dict[str, Typing.Any]] = []

        if ClassDirectory.exists():
            for FilePath in ClassDirectory.glob("class-*.json"):
                if FilePath.name.startswith("fluff-"):
                    continue

                try:
                    with open(FilePath, "r", encoding = "utf-8") as FileReader:
                        ClassDictionary: dict[str, Typing.Any] = JSONLibrary.load(FileReader)
                        ClassEntries: list[dict[str, Typing.Any]] = ClassDictionary.get("class", [])
                        SubclassesList: list[dict[str, Typing.Any]] = ClassDictionary.get("subclass", [])

                        for ClassRecord in ClassEntries:
                            ClassName: str = str(ClassRecord.get("name", ""))
                            ClassSource: str = str(ClassRecord.get("source", ""))
                            MatchingSubclasses: list[str] = [str(Sub.get("name", "")) for Sub in SubclassesList if ((str(Sub.get("className", "")).lower() == ClassName.lower()) and (str(Sub.get("classSource", "")).lower() == ClassSource.lower()))]
                            ClassRecord["AvailableSubclasses"] = MatchingSubclasses
                            LoadedClasses.append(ClassRecord)

                except Exception as ClassLoadError:
                    Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to load class file '{FilePath}': {str(ClassLoadError)}")

        self.ClassesList   = LoadedClasses
        self.ClassesLoaded = True

    def EnsureBackgroundsLoaded(self) -> None:
        if self.BackgroundsLoaded:
            return

        LoadedDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("backgrounds.json")
        if (LoadedDictionary is not None):
            self.BackgroundsList = list(LoadedDictionary.get("background", []))

        self.BackgroundsLoaded = True

    def EnsureSpeciesLoaded(self) -> None:
        if self.SpeciesLoaded:
            return

        LoadedDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("races.json")
        if (LoadedDictionary is not None):
            self.SpeciesList = list(LoadedDictionary.get("race", []))

        self.SpeciesLoaded = True

    def EnsureConditionsLoaded(self) -> None:
        if self.ConditionsLoaded:
            return

        CombinedConditions: list[dict[str, Typing.Any]] = []
        LoadedDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("conditionsdiseases.json")
        if (LoadedDictionary is not None):
            for CondItem in LoadedDictionary.get("condition", []):
                CondItem["ConditionKind"] = "Condition"
                CombinedConditions.append(CondItem)

            for DiseaseItem in LoadedDictionary.get("disease", []):
                DiseaseItem["ConditionKind"] = "Disease"
                CombinedConditions.append(DiseaseItem)

            for StatusItem in LoadedDictionary.get("status", []):
                StatusItem["ConditionKind"] = "Status"
                CombinedConditions.append(StatusItem)

        self.ConditionsList   = CombinedConditions
        self.ConditionsLoaded = True

    def EnsureDeitiesLoaded(self) -> None:
        if self.DeitiesLoaded:
            return

        LoadedDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("deities.json")
        if (LoadedDictionary is not None):
            self.DeitiesList = list(LoadedDictionary.get("deity", []))

        self.DeitiesLoaded = True

    def EnsureVehiclesLoaded(self) -> None:
        if self.VehiclesLoaded:
            return

        LoadedDictionary: Typing.Optional[dict[str, Typing.Any]] = self.LoadJSONFile("vehicles.json")
        if (LoadedDictionary is not None):
            self.VehiclesList = list(LoadedDictionary.get("vehicle", []))

        self.VehiclesLoaded = True

    def SelectBestMatch(self, Candidates: list[dict[str, Typing.Any]], QueryText: str) -> Typing.Optional[dict[str, Typing.Any]]:
        if not Candidates:
            return None

        CleanQuery  : str                         = QueryText.strip().lower()
        ExactMatches: list[dict[str, Typing.Any]] = [C for C in Candidates if str(C.get("name", "")).strip().lower() == CleanQuery]
        if ExactMatches:
            ExactMatches.sort(key = lambda C: self.SourceFilter.GetSourceRank(str(C.get("source", ""))))
            return ExactMatches[0]

        PrefixMatches: list[dict[str, Typing.Any]] = [C for C in Candidates if str(C.get("name", "")).strip().lower().startswith(CleanQuery)]
        if PrefixMatches:
            PrefixMatches.sort(key = lambda C: (self.SourceFilter.GetSourceRank(str(C.get("source", ""))), len(str(C.get("name", "")))))
            return PrefixMatches[0]

        Candidates.sort(key = lambda C: (self.SourceFilter.GetSourceRank(str(C.get("source", ""))), len(str(C.get("name", "")))))
        return Candidates[0]

    def GetFeature(self, FeatureQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureFeaturesLoaded()
        CleanQuery: str                         = FeatureQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [F for F in self.FeaturesList if CleanQuery in str(F.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def GetOption(self, OptionQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureOptionsLoaded()
        CleanQuery: str                         = OptionQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [O for O in self.OptionsList if CleanQuery in str(O.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def GetRule(self, RuleQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureRulesLoaded()
        CleanQuery: str                         = RuleQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [R for R in self.RulesList if CleanQuery in str(R.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def GetClass(self, ClassQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureClassesLoaded()
        CleanQuery: str                         = ClassQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [C for C in self.ClassesList if CleanQuery in str(C.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def GetBackground(self, BackgroundQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureBackgroundsLoaded()
        CleanQuery: str                         = BackgroundQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [B for B in self.BackgroundsList if CleanQuery in str(B.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def GetSpecies(self, SpeciesQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureSpeciesLoaded()
        CleanQuery: str                         = SpeciesQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [S for S in self.SpeciesList if CleanQuery in str(S.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def GetCondition(self, ConditionQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureConditionsLoaded()
        CleanQuery: str                         = ConditionQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [C for C in self.ConditionsList if CleanQuery in str(C.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def GetDeity(self, DeityQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureDeitiesLoaded()
        CleanQuery: str                         = DeityQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [D for D in self.DeitiesList if CleanQuery in str(D.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def GetVehicle(self, VehicleQuery: str) -> Typing.Optional[dict[str, Typing.Any]]:
        self.EnsureVehiclesLoaded()
        CleanQuery: str                         = VehicleQuery.strip().lower()
        Matches   : list[dict[str, Typing.Any]] = [V for V in self.VehiclesList if CleanQuery in str(V.get("name", "")).lower()]
        return self.SelectBestMatch(Matches, CleanQuery)

    def SearchAll(self, SearchQuery: str) -> dict[str, list[dict[str, Typing.Any]]]:
        self.EnsureFeaturesLoaded()
        self.EnsureOptionsLoaded()
        self.EnsureRulesLoaded()
        self.EnsureClassesLoaded()
        self.EnsureBackgroundsLoaded()
        self.EnsureSpeciesLoaded()
        self.EnsureConditionsLoaded()
        self.EnsureDeitiesLoaded()
        self.EnsureVehiclesLoaded()

        CleanQuery: str = SearchQuery.strip().lower()
        ResultsMap: dict[str, list[dict[str, Typing.Any]]] = dict()

        CategoryDatasets: list[tuple[str, list[dict[str, Typing.Any]]]] = [("Features", self.FeaturesList), ("Options", self.OptionsList), ("Rules", self.RulesList), ("Classes", self.ClassesList), ("Backgrounds", self.BackgroundsList), ("Species", self.SpeciesList), ("Conditions", self.ConditionsList), ("Deities", self.DeitiesList), ("Vehicles", self.VehiclesList)]

        for CategoryName, Dataset in CategoryDatasets:
            MatchedList: list[dict[str, Typing.Any]] = [Item for Item in Dataset if CleanQuery in str(Item.get("name", "")).lower()]
            if MatchedList:
                MatchedList.sort(key = lambda C: (self.SourceFilter.GetSourceRank(str(C.get("source", ""))), len(str(C.get("name", "")))))
                ResultsMap[CategoryName] = MatchedList[:5]

        return ResultsMap
