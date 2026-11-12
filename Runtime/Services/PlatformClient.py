import base64                        as Base64Library
import hashlib                       as HashLibrary
import hmac                          as HMACLibrary
import json                          as JSONLibrary
import time                          as TimeLibrary
import typing                        as Typing
import httpx2                        as HTTPClient
import Runtime.Configuration.Config  as Config
import Runtime.Services.DebugService as Debug

DEFAULT_TOKEN_EXPIRATION_SECONDS: int = 3600

def EncodeBase64URL(DataBytes: bytes) -> str:
    return Base64Library.urlsafe_b64encode(DataBytes).rstrip(b"=").decode("utf-8")

class TallyPlatformClient:
    def __init__(self, BaseURL: Typing.Optional[str] = None, SecretKey: Typing.Optional[str] = None) -> None:
        self.BaseURL             : str                    = (BaseURL if (BaseURL is not None) else Config.GLOBAL_SETTINGS.PLATFORM_API_URL).rstrip("/")
        self.SecretKey           : str                    = SecretKey if (SecretKey is not None) else Config.GLOBAL_SETTINGS.SECRET_KEY
        self.HTTPClient          : HTTPClient.AsyncClient = HTTPClient.AsyncClient(base_url = self.BaseURL, timeout = 10.0)
        self.CachedServiceToken  : Typing.Optional[str]   = None
        self.TokenExpirationEpoch: int                    = 0

    def GenerateServiceToken(self, Subject: str = "Tally", Role: str = "Administrator") -> str:
        CurrentEpoch   : int = int(TimeLibrary.time())
        ExpirationEpoch: int = CurrentEpoch + DEFAULT_TOKEN_EXPIRATION_SECONDS
        HeaderData     : dict[str, str]        = {
            "alg": "HS256",
            "typ": "JWT"
        }
        PayloadData    : dict[str, Typing.Any] = {
            "sub"     : Subject,
            "role"    : Role,
            "in_guild": True,
            "iat"     : CurrentEpoch,
            "exp"     : ExpirationEpoch
        }
        EncodedHeader : str   = EncodeBase64URL(JSONLibrary.dumps(HeaderData, separators = (",", ":")).encode("utf-8"))
        EncodedPayload: str   = EncodeBase64URL(JSONLibrary.dumps(PayloadData, separators = (",", ":")).encode("utf-8"))
        SigningInput  : str   = f"{EncodedHeader}.{EncodedPayload}"
        HMACDigest    : bytes = HMACLibrary.new(self.SecretKey.encode("utf-8"), SigningInput.encode("utf-8"), HashLibrary.sha256).digest()
        EncodedSig    : str   = EncodeBase64URL(HMACDigest)
        GeneratedToken: str   = f"{SigningInput}.{EncodedSig}"
        self.CachedServiceToken   = GeneratedToken
        self.TokenExpirationEpoch = ExpirationEpoch
        return GeneratedToken

    def GetDefaultHeaders(self) -> dict[str, str]:
        CurrentEpoch: int = int(TimeLibrary.time())
        if (self.CachedServiceToken is None) or (CurrentEpoch >= (self.TokenExpirationEpoch - 60)):
            self.GenerateServiceToken()

        return {
            "Authorization": f"Bearer {self.CachedServiceToken}",
            "Accept"       : "application/json"
        }

    async def Close(self) -> None:
        await self.HTTPClient.aclose()

    async def CheckHealth(self) -> bool:
        try:
            RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
            ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters/Rules/DataStore", headers = RequestHeaders)
            IsSuccess     : bool                = (ResponseResult.status_code == 200)
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Platform Health Check: Status={ResponseResult.status_code}, Healthy={IsSuccess}")
            return IsSuccess

        except Exception as TransportError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Platform Health Check Failed: Error=\"{str(TransportError)}\"")
            return False

    async def FetchRulesDataStore(self) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters/Rules/DataStore", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        DataStoreDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Rules DataStore: System=\"{DataStoreDictionary.get("GameSystem")}\"")
        return DataStoreDictionary

    async def FetchClassRules(self) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters/Rules/Classes", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ClassesSummary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Class Rules: Count={len(ClassesSummary)}")
        return ClassesSummary

    async def FetchSpellcastingAbility(self, ClassName: str, SubclassName: Typing.Optional[str] = None) -> Typing.Optional[str]:
        RequestHeaders: dict[str, str] = self.GetDefaultHeaders()
        QueryParameters: dict[str, str] = {
            "ClassName": ClassName
        }
        if (SubclassName is not None):
            QueryParameters["SubclassName"] = SubclassName

        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters/Rules/SpellcastingAbility", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultData      : dict[str, Typing.Any] = ResponseResult.json()
        SpellcastAbility: Typing.Optional[str]  = ResultData.get("SpellcastingAbility")
        return SpellcastAbility

    async def FetchCantripsList(self) -> list[str]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters/Rules/Cantrips", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CantripsList: list[str] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Cantrips: Count={len(CantripsList)}")
        return CantripsList

    async def FetchEquipmentData(self) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters/Rules/EquipmentData", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        EquipmentData: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Equipment Data: Armors={len(EquipmentData.get("Armors", {}))}")
        return EquipmentData

    async def FetchAllCharacters(self) -> list[dict[str, Typing.Any]]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CharactersList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched All Characters: Count={len(CharactersList)}")
        return CharactersList

    async def FetchCharactersByDiscordID(self, DiscordID: str) -> list[dict[str, Typing.Any]]:
        AllCharacters   : list[dict[str, Typing.Any]] = await self.FetchAllCharacters()
        MatchingList    : list[dict[str, Typing.Any]] = []
        TargetDiscordStr: str                         = str(DiscordID).strip()
        for CharacterRecord in AllCharacters:
            SummaryData : dict[str, Typing.Any] = CharacterRecord.get("SummaryData", {})
            OwnerData   : dict[str, Typing.Any] = CharacterRecord.get("Owner", {})
            OwnerDiscord: str                   = str(OwnerData.get("DiscordID", "")).strip() or str(SummaryData.get("DiscordID", "")).strip()
            if (OwnerDiscord == TargetDiscordStr):
                MatchingList.append(CharacterRecord)

        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Matched Characters for DiscordID=\"{TargetDiscordStr}\": Count={len(MatchingList)}")
        return MatchingList

    async def FetchEntityRulesData(self, EndpointCategory: str, EntityName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        try:
            RequestHeaders : dict[str, str]        = self.GetDefaultHeaders()
            EncodedName    : str                   = HTTPClient.URL(EntityName).raw_path.decode("utf-8")
            QueryParameters: dict[str, Typing.Any] = dict(Source = Source) if (Source is not None) else dict()
            ResponseResult : HTTPClient.Response   = await self.HTTPClient.get(f"/API/Characters/Rules/{EndpointCategory}/{EncodedName}", params = QueryParameters if QueryParameters else None, headers = RequestHeaders)
            if (ResponseResult.status_code == 200):
                return ResponseResult.json()

            return None

        except Exception as FetchException:
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"{EndpointCategory} Query Failed: Name=\"{EntityName}\", Error=\"{str(FetchException)}\"")
            return None

    async def FetchSpellDetails(self, SpellName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Spells", SpellName, Source)

    async def FetchMonsterDetails(self, MonsterName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Monsters", MonsterName, Source)

    async def FetchItemDetails(self, ItemName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Items", ItemName, Source)

    async def FetchFeatDetails(self, FeatName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Feats", FeatName, Source)

    async def FetchOptionDetails(self, OptionName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Options", OptionName, Source)

    async def FetchRuleDetails(self, RuleName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Rules", RuleName, Source)

    async def FetchBackgroundDetails(self, BackgroundName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Backgrounds", BackgroundName, Source)

    async def FetchSpeciesDetails(self, SpeciesName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Species", SpeciesName, Source)

    async def FetchConditionDetails(self, ConditionName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Conditions", ConditionName, Source)

    async def FetchDeityDetails(self, DeityName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Deities", DeityName, Source)

    async def FetchVehicleDetails(self, VehicleName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Vehicles", VehicleName, Source)

    async def FetchClassDetails(self, ClassName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Classes", ClassName, Source)

    async def FetchSubclassDetails(self, SubclassName: str, Source: Typing.Optional[str] = None) -> Typing.Optional[dict[str, Typing.Any]]:
        return await self.FetchEntityRulesData("Subclasses", SubclassName, Source)

    async def SearchCompendium(self, QueryText: str, Category: Typing.Optional[str] = None, Limit: int = 5) -> dict[str, Typing.Any]:
        try:
            RequestHeaders : dict[str, str]        = self.GetDefaultHeaders()
            QueryParameters: dict[str, Typing.Any] = {
                "Query": QueryText,
                "Limit": Limit
            }
            if (Category is not None):
                QueryParameters["Category"] = Category

            ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters/Rules/Compendium/Search", params = QueryParameters, headers = RequestHeaders)
            if (ResponseResult.status_code == 200):
                return ResponseResult.json()

            return {
                "Query"  : QueryText,
                "Results": {}
            }

        except Exception as SearchException:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Compendium Search Failed: Query=\"{QueryText}\", Error=\"{str(SearchException)}\"")
            return {
                "Query"  : QueryText,
                "Results": {}
            }

    async def FetchCharacterActions(self, CharacterID: str) -> list[dict[str, Typing.Any]]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get(f"/API/Characters/{CharacterID}/Actions", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ActionsList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Character Actions: CharacterID=\"{CharacterID[:8]}…\", Count={len(ActionsList)}")
        return ActionsList

    async def CreateCharacterAction(self, CharacterID: str, ActionPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Actions", json = ActionPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CreatedAction: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Character Action on Platform: CharacterID=\"{CharacterID[:8]}…\"")
        return CreatedAction

    async def UpdateCharacterAction(self, CharacterID: str, ActionID: str, UpdatePayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.patch(f"/API/Characters/{CharacterID}/Actions/{ActionID}", json = UpdatePayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        UpdatedAction: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Character Action on Platform: ActionID=\"{ActionID[:8]}…\"")
        return UpdatedAction

    async def DeleteCharacterAction(self, CharacterID: str, ActionID: str) -> bool:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.delete(f"/API/Characters/{CharacterID}/Actions/{ActionID}", headers = RequestHeaders)
        IsSuccess     : bool                = (ResponseResult.status_code == 200)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Character Action on Platform: ActionID=\"{ActionID[:8]}…\", Success={IsSuccess}")
        return IsSuccess

    async def CreateOrUpdateCounter(self, CharacterID: str, CounterPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Counters", json = CounterPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created/Updated Counter on Platform: CharacterID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def MutateCounter(self, CharacterID: str, CounterName: str, Delta: Typing.Optional[int] = None, Value: Typing.Optional[int] = None, Operation: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        RequestHeaders   : dict[str, str]        = self.GetDefaultHeaders()
        PayloadDictionary: dict[str, Typing.Any] = dict()
        if (Delta is not None):
            PayloadDictionary["Delta"] = Delta

        if (Value is not None):
            PayloadDictionary["Value"] = Value

        if (Operation is not None):
            PayloadDictionary["Operation"] = Operation

        ResponseResult: HTTPClient.Response = await self.HTTPClient.patch(f"/API/Characters/{CharacterID}/Counters/{CounterName}", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Mutated Counter on Platform: Name=\"{CounterName}\", CharacterID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def SetCharacterVariables(self, CharacterID: str, VariablesPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Variables", json = VariablesPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Set Character Variables on Platform: CharacterID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def ValidateAutomationTree(self, AutomationList: list[dict[str, Typing.Any]]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post("/API/Automations/Validate", json = dict(Automation = AutomationList), headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ValidationResponse: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Validated Automation on Platform: Valid={ValidationResponse.get("IsValid")}")
        return ValidationResponse

    async def FetchServerSettings(self, GuildID: str) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get(f"/API/Servers/{GuildID}/Settings", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Server Settings from Platform: GuildID={GuildID}")
        return ResultDictionary

    async def SaveServerSettings(self, GuildID: str, SettingsPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.put(f"/API/Servers/{GuildID}/Settings", json = SettingsPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Saved Server Settings on Platform: GuildID={GuildID}")
        return ResultDictionary

    async def FetchCombatEncounter(self, ChannelID: str) -> Typing.Optional[dict[str, Typing.Any]]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get(f"/API/Combat/Encounters/{ChannelID}", headers = RequestHeaders)
        if (ResponseResult.status_code == 404):
            return None

        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Combat Encounter from Platform: ChannelID={ChannelID}")
        return ResultDictionary

    async def SaveCombatEncounter(self, ChannelID: str, EncounterPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.put(f"/API/Combat/Encounters/{ChannelID}", json = EncounterPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Saved Combat Encounter on Platform: ChannelID={ChannelID}")
        return ResultDictionary

    async def DeleteCombatEncounter(self, ChannelID: str) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.delete(f"/API/Combat/Encounters/{ChannelID}", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Combat Encounter on Platform: ChannelID={ChannelID}")
        return ResultDictionary

    async def FetchAliases(self, Scope: str, OwnerID: Typing.Optional[str] = None, ServerID: Typing.Optional[str] = None) -> list[dict[str, Typing.Any]]:
        RequestHeaders : dict[str, str]        = self.GetDefaultHeaders()
        QueryParameters: dict[str, Typing.Any] = {
            "Scope": Scope
        }
        if (OwnerID is not None):
            QueryParameters["OwnerID"] = OwnerID

        if (ServerID is not None):
            QueryParameters["ServerID"] = ServerID

        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Aliases", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultsList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Aliases from Platform: Scope={Scope}, Count={len(ResultsList)}")
        return ResultsList

    async def CreateAlias(self, AliasPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post("/API/Aliases", json = AliasPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Alias on Platform: Name=\"{AliasPayload.get("Name")}\"")
        return ResultDictionary

    async def UpdateAlias(self, AliasID: str, UpdatePayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.patch(f"/API/Aliases/{AliasID}", json = UpdatePayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Alias on Platform: ID={AliasID}")
        return ResultDictionary

    async def DeleteAlias(self, AliasID: str) -> bool:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.delete(f"/API/Aliases/{AliasID}", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        IsSuccess       : bool                  = bool(ResultDictionary.get("IsSuccess", False))
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Alias on Platform: ID={AliasID}, Success={IsSuccess}")
        return IsSuccess

    async def FetchSnippets(self, Scope: str, OwnerID: Typing.Optional[str] = None, ServerID: Typing.Optional[str] = None) -> list[dict[str, Typing.Any]]:
        RequestHeaders : dict[str, str]        = self.GetDefaultHeaders()
        QueryParameters: dict[str, Typing.Any] = {
            "Scope": Scope
        }
        if (OwnerID is not None):
            QueryParameters["OwnerID"] = OwnerID

        if (ServerID is not None):
            QueryParameters["ServerID"] = ServerID

        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Snippets", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultsList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Snippets from Platform: Scope={Scope}, Count={len(ResultsList)}")
        return ResultsList

    async def CreateSnippet(self, SnippetPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post("/API/Snippets", json = SnippetPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Snippet on Platform: Name=\"{SnippetPayload.get("Name")}\"")
        return ResultDictionary

    async def UpdateSnippet(self, SnippetID: str, UpdatePayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.patch(f"/API/Snippets/{SnippetID}", json = UpdatePayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Snippet on Platform: ID={SnippetID}")
        return ResultDictionary

    async def DeleteSnippet(self, SnippetID: str) -> bool:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.delete(f"/API/Snippets/{SnippetID}", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        IsSuccess       : bool                  = bool(ResultDictionary.get("IsSuccess", False))
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Snippet on Platform: ID={SnippetID}, Success={IsSuccess}")
        return IsSuccess

    async def FetchUserVariables(self, UserID: str, Name: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        RequestHeaders : dict[str, str]                  = self.GetDefaultHeaders()
        QueryParameters: Typing.Optional[dict[str, str]] = None
        if (Name is not None):
            QueryParameters = {
                "Name": Name
            }

        ResponseResult: HTTPClient.Response = await self.HTTPClient.get(f"/API/Variables/User/{UserID}", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched User Variables from Platform: UserID={UserID}")
        return ResultDictionary

    async def SaveUserVariable(self, UserID: str, Name: str, Value: Typing.Any = None) -> dict[str, Typing.Any]:
        RequestHeaders   : dict[str, str]        = self.GetDefaultHeaders()
        PayloadDictionary: dict[str, Typing.Any] = {
            "Name" : Name,
            "Value": Value
        }
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post(f"/API/Variables/User/{UserID}", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Saved User Variable on Platform: UserID={UserID}, Name=\"{Name}\"")
        return ResultDictionary

    async def FetchServerVariables(self, GuildID: str, Name: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        RequestHeaders : dict[str, str]                  = self.GetDefaultHeaders()
        QueryParameters: Typing.Optional[dict[str, str]] = None
        if (Name is not None):
            QueryParameters = {
                "Name": Name
            }

        ResponseResult: HTTPClient.Response = await self.HTTPClient.get(f"/API/Variables/Server/{GuildID}", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Server Variables from Platform: GuildID={GuildID}")
        return ResultDictionary

    async def SaveServerVariable(self, GuildID: str, Name: str, Value: Typing.Any = None) -> dict[str, Typing.Any]:
        RequestHeaders   : dict[str, str]        = self.GetDefaultHeaders()
        PayloadDictionary: dict[str, Typing.Any] = {
            "Name" : Name,
            "Value": Value
        }
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post(f"/API/Variables/Server/{GuildID}", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Saved Server Variable on Platform: GuildID={GuildID}, Name=\"{Name}\"")
        return ResultDictionary

    async def FetchGlobalVariable(self, GvarID: str) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get(f"/API/Variables/Global/{GvarID}", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Global Variable from Platform: ID={GvarID}")
        return ResultDictionary

    async def CreateGlobalVariable(self, Content: str, Name: Typing.Optional[str] = None, OwnerID: Typing.Optional[str] = None, ID: Typing.Optional[str] = None) -> str:
        RequestHeaders: dict[str, str] = self.GetDefaultHeaders()
        PayloadDictionary = {
            "Content": Content,
            "Name"   : Name,
            "OwnerID": OwnerID,
            "ID"     : ID
        }
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post("/API/Variables/Global", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        CreatedID       : str                   = str(ResultDictionary.get("ID", ""))
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Global Variable on Platform: ID={CreatedID}")
        return CreatedID

    async def ImportCharacter(self, ImportURL: str, DiscordID: str) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str] = self.GetDefaultHeaders()
        PayloadDictionary = {
            "ImportURL": ImportURL,
            "DiscordID": DiscordID
        }
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post("/API/Characters/Import", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Imported Character on Platform: Name=\"{ResultDictionary.get("Name")}\", DiscordID={DiscordID}")
        return ResultDictionary

    async def FetchCharacterCompanions(self, CharacterID: str) -> list[dict[str, Typing.Any]]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.get(f"/API/Characters/{CharacterID}/Companions", headers = RequestHeaders)
        if (ResponseResult.status_code == 404):
            return []

        ResponseResult.raise_for_status()
        CompanionsList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Character Companions: CharacterID=\"{CharacterID[:8]}…\", Count={len(CompanionsList)}")
        return CompanionsList

    async def FetchCharactersByEntityType(self, EntityType: str, GameSystem: Typing.Optional[str] = None) -> list[dict[str, Typing.Any]]:
        RequestHeaders : dict[str, str]        = self.GetDefaultHeaders()
        QueryParameters: dict[str, Typing.Any] = {
            "EntityType": EntityType
        }
        if (GameSystem is not None):
            QueryParameters["GameSystem"] = GameSystem

        ResponseResult: HTTPClient.Response = await self.HTTPClient.get("/API/Characters", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CharactersList: list[dict[str, Typing.Any]] = ResponseResult.json()

        TargetType  : str                         = EntityType.strip().lower()
        FilteredList: list[dict[str, Typing.Any]] = []
        for CharacterRecord in CharactersList:
            RecordType  : str = str(CharacterRecord.get("EntityType", "Character")).strip().lower()
            RecordSystem: str = str(CharacterRecord.get("GameSystem", "")).strip()
            if (RecordType == TargetType):
                if (GameSystem is None) or (RecordSystem == GameSystem):
                    FilteredList.append(CharacterRecord)

        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Characters by EntityType=\"{EntityType}\": Count={len(FilteredList)}")
        return FilteredList

    async def LinkOrCreateCompanion(self, CharacterID: str, CompanionID: Typing.Optional[str] = None, Name: Typing.Optional[str] = None, EntityType: str = "Companion") -> dict[str, Typing.Any]:
        RequestHeaders   : dict[str, str]        = self.GetDefaultHeaders()
        PayloadDictionary: dict[str, Typing.Any] = {
            "EntityType": EntityType
        }
        if (CompanionID is not None):
            PayloadDictionary["CompanionID"] = CompanionID

        if (Name is not None):
            PayloadDictionary["Name"] = Name

        ResponseResult: HTTPClient.Response = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Companions", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Linked Companion on Platform: ParentID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def TransferCharacterEntity(self, CharacterID: str, PayloadDictionary: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Transfer", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Transferred Entity on Platform: CharacterID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def ResolvePlatformUserIDByDiscordID(self, DiscordID: str) -> Typing.Optional[str]:
        MatchedList: list[dict[str, Typing.Any]] = await self.FetchCharactersByDiscordID(str(DiscordID))
        for Record in MatchedList:
            OwnerDictionary: dict[str, Typing.Any] = Record.get("Owner", {})
            OwnerID        : Typing.Optional[str]  = OwnerDictionary.get("ID")
            if (OwnerID is not None) and str(OwnerID).strip():
                return str(OwnerID).strip()

            FallbackOwnerID: Typing.Optional[str] = Record.get("OwnerID")
            if (FallbackOwnerID is not None) and str(FallbackOwnerID).strip():
                return str(FallbackOwnerID).strip()

        return None

    async def PersistCharacterState(self, CharacterID: str, StatePatch: dict[str, Typing.Any]) -> Typing.Optional[dict[str, Typing.Any]]:
        RequestHeaders: dict[str, str]      = self.GetDefaultHeaders()
        ResponseResult: HTTPClient.Response = await self.HTTPClient.patch(f"/API/Characters/{CharacterID}/State", json = StatePatch, headers = RequestHeaders)
        if (ResponseResult.status_code == 404):
            return None

        ResponseResult.raise_for_status()
        UpdatedRecord: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Persisted Character State on Platform: CharacterID=\"{CharacterID[:8]}…\"")
        return UpdatedRecord

    async def Close(self) -> None:
        await self.HTTPClient.aclose()

