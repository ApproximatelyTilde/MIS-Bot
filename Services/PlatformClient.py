import base64                as Base64Library
import datetime              as DateTime
import hashlib               as HashLibrary
import hmac                  as HMACLibrary
import json                  as JSONLibrary
import time                  as TimeLibrary
import typing                as Typing
import httpx                 as HTTPClient
import Configuration.Config  as Config
import Services.DebugService as Debug

DEFAULT_TOKEN_EXPIRATION_SECONDS: int = 3600

def EncodeBase64URL(DataBytes: bytes) -> str:
    return Base64Library.urlsafe_b64encode(DataBytes).rstrip(b"=").decode("utf-8")

class MISPlatformClient:
    def __init__(self, BaseURL: Typing.Optional[str] = None, SecretKey: Typing.Optional[str] = None) -> None:
        self.BaseURL   : str                    = (BaseURL if (BaseURL is not None) else Config.GLOBAL_SETTINGS.PLATFORM_API_URL).rstrip("/")
        self.SecretKey : str                    = SecretKey if (SecretKey is not None) else Config.GLOBAL_SETTINGS.SECRET_KEY
        self.HTTPClient: HTTPClient.AsyncClient = HTTPClient.AsyncClient(base_url = self.BaseURL, timeout = 10.0)

    def GenerateServiceToken(self, Subject: str = "MIS-Bot-Service", Role: str = "Administrator") -> str:
        CurrentEpoch   : int                    = int(TimeLibrary.time())
        ExpirationEpoch: int                          = CurrentEpoch + DEFAULT_TOKEN_EXPIRATION_SECONDS
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
        return GeneratedToken

    def GetDefaultHeaders(self) -> dict[str, str]:
        ServiceToken: str = self.GenerateServiceToken()
        return {
            "Authorization": f"Bearer {ServiceToken}",
            "Accept"       : "application/json"
        }

    async def CheckHealth(self) -> bool:
        try:
            RequestHeaders = self.GetDefaultHeaders()
            ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/DataStore", headers = RequestHeaders)
            IsSuccess      : bool = (ResponseResult.status_code == 200)
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Platform Health Check: Status={ResponseResult.status_code}, Healthy={IsSuccess}")
            return IsSuccess

        except Exception as TransportError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Platform Health Check Failed: Error=\"{str(TransportError)}\"")
            return False

    async def FetchRulesDataStore(self) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/DataStore", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        DataStoreDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Rules DataStore: System=\"{DataStoreDictionary.get("GameSystem")}\"")
        return DataStoreDictionary

    async def FetchClassRules(self) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/Classes", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ClassesSummary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Class Rules: Count={len(ClassesSummary)}")
        return ClassesSummary

    async def FetchSpellcastingAbility(self, ClassName: str, SubclassName: Typing.Optional[str] = None) -> Typing.Optional[str]:
        RequestHeaders = self.GetDefaultHeaders()
        QueryParameters: dict[str, str] = {
            "ClassName": ClassName
        }
        if (SubclassName is not None):
            QueryParameters["SubclassName"] = SubclassName

        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/SpellcastingAbility", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultData      : dict[str, Typing.Any] = ResponseResult.json()
        SpellcastAbility: Typing.Optional[str]         = ResultData.get("SpellcastingAbility")
        return SpellcastAbility

    async def FetchCantripsList(self) -> list[str]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/Cantrips", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CantripsList: list[str] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Cantrips: Count={len(CantripsList)}")
        return CantripsList

    async def FetchEquipmentData(self) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/EquipmentData", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        EquipmentData: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Equipment Data: Armors={len(EquipmentData.get("Armors", {}))}")
        return EquipmentData

    async def FetchAllCharacters(self) -> list[dict[str, Typing.Any]]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CharactersList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched All Characters: Count={len(CharactersList)}")
        return CharactersList

    async def FetchCharactersByDiscordID(self, DiscordID: str) -> list[dict[str, Typing.Any]]:
        AllCharacters   : list[dict[str, Typing.Any]] = await self.FetchAllCharacters()
        MatchingList    : list[dict[str, Typing.Any]] = []
        TargetDiscordStr: str                                       = str(DiscordID).strip()
        for CharacterRecord in AllCharacters:
            SummaryData: dict[str, Typing.Any] = CharacterRecord.get("SummaryData", {})
            OwnerData  : dict[str, Typing.Any] = CharacterRecord.get("Owner", {})
            OwnerDiscord: str = str(OwnerData.get("DiscordID", "")).strip() or str(SummaryData.get("DiscordID", "")).strip()
            if (OwnerDiscord == TargetDiscordStr):
                MatchingList.append(CharacterRecord)

        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Matched Characters for DiscordID=\"{TargetDiscordStr}\": Count={len(MatchingList)}")
        return MatchingList

    async def FetchSpellDetails(self, SpellName: str) -> Typing.Optional[dict[str, Typing.Any]]:
        try:
            RequestHeaders = self.GetDefaultHeaders()
            EncodedName    = HTTPClient.URL(SpellName).raw_path.decode("utf-8")
            ResponseResult = await self.HTTPClient.get(f"/API/Characters/Rules/Spells/{EncodedName}", headers = RequestHeaders)
            if (ResponseResult.status_code == 200):
                return ResponseResult.json()

            return None

        except Exception as FetchException:
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Spell Query Failed: Name=\"{SpellName}\", Error=\"{str(FetchException)}\"")
            return None

    async def FetchMonsterDetails(self, MonsterName: str) -> Typing.Optional[dict[str, Typing.Any]]:
        try:
            RequestHeaders = self.GetDefaultHeaders()
            EncodedName    = HTTPClient.URL(MonsterName).raw_path.decode("utf-8")
            ResponseResult = await self.HTTPClient.get(f"/API/Characters/Rules/Monsters/{EncodedName}", headers = RequestHeaders)
            if (ResponseResult.status_code == 200):
                return ResponseResult.json()

            return None

        except Exception as FetchException:
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Monster Query Failed: Name=\"{MonsterName}\", Error=\"{str(FetchException)}\"")
            return None

    async def FetchItemDetails(self, ItemName: str) -> Typing.Optional[dict[str, Typing.Any]]:
        try:
            RequestHeaders = self.GetDefaultHeaders()
            EncodedName    = HTTPClient.URL(ItemName).raw_path.decode("utf-8")
            ResponseResult = await self.HTTPClient.get(f"/API/Characters/Rules/Items/{EncodedName}", headers = RequestHeaders)
            if (ResponseResult.status_code == 200):
                return ResponseResult.json()

            return None

        except Exception as FetchException:
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Item Query Failed: Name=\"{ItemName}\", Error=\"{str(FetchException)}\"")
            return None

    async def FetchCharacterActions(self, CharacterID: str) -> list[dict[str, Typing.Any]]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get(f"/API/Characters/{CharacterID}/Actions", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ActionsList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Character Actions: CharacterID=\"{CharacterID[:8]}…\", Count={len(ActionsList)}")
        return ActionsList

    async def CreateCharacterAction(self, CharacterID: str, ActionPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Actions", json = ActionPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CreatedAction: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Character Action on Platform: CharacterID=\"{CharacterID[:8]}…\"")
        return CreatedAction

    async def UpdateCharacterAction(self, CharacterID: str, ActionID: str, UpdatePayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.patch(f"/API/Characters/{CharacterID}/Actions/{ActionID}", json = UpdatePayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        UpdatedAction: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Character Action on Platform: ActionID=\"{ActionID[:8]}…\"")
        return UpdatedAction

    async def DeleteCharacterAction(self, CharacterID: str, ActionID: str) -> bool:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.delete(f"/API/Characters/{CharacterID}/Actions/{ActionID}", headers = RequestHeaders)
        IsSuccess      : bool = (ResponseResult.status_code == 200)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Character Action on Platform: ActionID=\"{ActionID[:8]}…\", Success={IsSuccess}")
        return IsSuccess

    async def CreateOrUpdateCounter(self, CharacterID: str, CounterPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Counters", json = CounterPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created/Updated Counter on Platform: CharacterID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def MutateCounter(self, CharacterID: str, CounterName: str, Delta: Typing.Optional[int] = None, Value: Typing.Optional[int] = None, Operation: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        PayloadDictionary: dict[str, Typing.Any] = dict()
        if (Delta is not None):
            PayloadDictionary["Delta"] = Delta

        if (Value is not None):
            PayloadDictionary["Value"] = Value

        if (Operation is not None):
            PayloadDictionary["Operation"] = Operation

        ResponseResult = await self.HTTPClient.patch(f"/API/Characters/{CharacterID}/Counters/{CounterName}", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Mutated Counter on Platform: Name=\"{CounterName}\", CharacterID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def SetCharacterVariables(self, CharacterID: str, VariablesPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Variables", json = VariablesPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Set Character Variables on Platform: CharacterID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def ValidateAutomationTree(self, AutomationList: list[dict[str, Typing.Any]]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post("/API/Automations/Validate", json = dict(Automation = AutomationList), headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ValidationResponse: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Validated Automation on Platform: Valid={ValidationResponse.get("IsValid")}")
        return ValidationResponse

    async def FetchServerSettings(self, GuildID: str) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get(f"/API/Servers/{GuildID}/Settings", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Server Settings from Platform: GuildID={GuildID}")
        return ResultDictionary

    async def SaveServerSettings(self, GuildID: str, SettingsPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.put(f"/API/Servers/{GuildID}/Settings", json = SettingsPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Saved Server Settings on Platform: GuildID={GuildID}")
        return ResultDictionary

    async def FetchCombatEncounter(self, ChannelID: str) -> Typing.Optional[dict[str, Typing.Any]]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get(f"/API/Combat/Encounters/{ChannelID}", headers = RequestHeaders)
        if (ResponseResult.status_code == 404):
            return None

        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Combat Encounter from Platform: ChannelID={ChannelID}")
        return ResultDictionary

    async def SaveCombatEncounter(self, ChannelID: str, EncounterPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.put(f"/API/Combat/Encounters/{ChannelID}", json = EncounterPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Saved Combat Encounter on Platform: ChannelID={ChannelID}")
        return ResultDictionary

    async def DeleteCombatEncounter(self, ChannelID: str) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.delete(f"/API/Combat/Encounters/{ChannelID}", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Combat Encounter on Platform: ChannelID={ChannelID}")
        return ResultDictionary

    async def FetchAliases(self, Scope: str, OwnerID: Typing.Optional[str] = None, ServerID: Typing.Optional[str] = None) -> list[dict[str, Typing.Any]]:
        RequestHeaders  = self.GetDefaultHeaders()
        QueryParameters = {
            "Scope": Scope
        }
        if (OwnerID is not None):
            QueryParameters["OwnerID"] = OwnerID

        if (ServerID is not None):
            QueryParameters["ServerID"] = ServerID

        ResponseResult = await self.HTTPClient.get("/API/Aliases", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultsList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Aliases from Platform: Scope={Scope}, Count={len(ResultsList)}")
        return ResultsList

    async def CreateAlias(self, AliasPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post("/API/Aliases", json = AliasPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Alias on Platform: Name=\"{AliasPayload.get("Name")}\"")
        return ResultDictionary

    async def UpdateAlias(self, AliasID: str, UpdatePayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.patch(f"/API/Aliases/{AliasID}", json = UpdatePayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Alias on Platform: ID={AliasID}")
        return ResultDictionary

    async def DeleteAlias(self, AliasID: str) -> bool:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.delete(f"/API/Aliases/{AliasID}", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        IsSuccess       : bool                         = bool(ResultDictionary.get("IsSuccess", False))
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Alias on Platform: ID={AliasID}, Success={IsSuccess}")
        return IsSuccess

    async def FetchSnippets(self, Scope: str, OwnerID: Typing.Optional[str] = None, ServerID: Typing.Optional[str] = None) -> list[dict[str, Typing.Any]]:
        RequestHeaders  = self.GetDefaultHeaders()
        QueryParameters = {
            "Scope": Scope
        }
        if (OwnerID is not None):
            QueryParameters["OwnerID"] = OwnerID

        if (ServerID is not None):
            QueryParameters["ServerID"] = ServerID

        ResponseResult = await self.HTTPClient.get("/API/Snippets", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultsList: list[dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Snippets from Platform: Scope={Scope}, Count={len(ResultsList)}")
        return ResultsList

    async def CreateSnippet(self, SnippetPayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post("/API/Snippets", json = SnippetPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Snippet on Platform: Name=\"{SnippetPayload.get("Name")}\"")
        return ResultDictionary

    async def UpdateSnippet(self, SnippetID: str, UpdatePayload: dict[str, Typing.Any]) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.patch(f"/API/Snippets/{SnippetID}", json = UpdatePayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Snippet on Platform: ID={SnippetID}")
        return ResultDictionary

    async def DeleteSnippet(self, SnippetID: str) -> bool:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.delete(f"/API/Snippets/{SnippetID}", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        IsSuccess       : bool                         = bool(ResultDictionary.get("IsSuccess", False))
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Snippet on Platform: ID={SnippetID}, Success={IsSuccess}")
        return IsSuccess

    async def FetchUserVariables(self, UserID: str, Name: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        RequestHeaders                                   = self.GetDefaultHeaders()
        QueryParameters: Typing.Optional[dict[str, str]] = None
        if (Name is not None):
            QueryParameters = {
                "Name": Name
            }

        ResponseResult  = await self.HTTPClient.get(f"/API/Variables/User/{UserID}", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched User Variables from Platform: UserID={UserID}")
        return ResultDictionary

    async def SaveUserVariable(self, UserID: str, Name: str, Value: Typing.Any = None) -> dict[str, Typing.Any]:
        RequestHeaders    = self.GetDefaultHeaders()
        PayloadDictionary = {
            "Name" : Name,
            "Value": Value
        }
        ResponseResult    = await self.HTTPClient.post(f"/API/Variables/User/{UserID}", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Saved User Variable on Platform: UserID={UserID}, Name=\"{Name}\"")
        return ResultDictionary

    async def FetchServerVariables(self, GuildID: str, Name: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        RequestHeaders                                   = self.GetDefaultHeaders()
        QueryParameters: Typing.Optional[dict[str, str]] = None
        if (Name is not None):
            QueryParameters = {
                "Name": Name
            }

        ResponseResult  = await self.HTTPClient.get(f"/API/Variables/Server/{GuildID}", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Server Variables from Platform: GuildID={GuildID}")
        return ResultDictionary

    async def SaveServerVariable(self, GuildID: str, Name: str, Value: Typing.Any = None) -> dict[str, Typing.Any]:
        RequestHeaders    = self.GetDefaultHeaders()
        PayloadDictionary = {
            "Name" : Name,
            "Value": Value
        }
        ResponseResult    = await self.HTTPClient.post(f"/API/Variables/Server/{GuildID}", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Saved Server Variable on Platform: GuildID={GuildID}, Name=\"{Name}\"")
        return ResultDictionary

    async def FetchGlobalVariable(self, GvarID: str) -> dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get(f"/API/Variables/Global/{GvarID}", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Global Variable from Platform: ID={GvarID}")
        return ResultDictionary

    async def CreateGlobalVariable(self, Content: str, Name: Typing.Optional[str] = None, OwnerID: Typing.Optional[str] = None, ID: Typing.Optional[str] = None) -> str:
        RequestHeaders    = self.GetDefaultHeaders()
        PayloadDictionary = {
            "Content": Content,
            "Name"   : Name,
            "OwnerID": OwnerID,
            "ID"     : ID
        }
        ResponseResult    = await self.HTTPClient.post("/API/Variables/Global", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        CreatedID       : str                          = str(ResultDictionary.get("ID", ""))
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Global Variable on Platform: ID={CreatedID}")
        return CreatedID

    async def ImportCharacter(self, ImportURL: str, DiscordID: str) -> dict[str, Typing.Any]:
        RequestHeaders    = self.GetDefaultHeaders()
        PayloadDictionary = {
            "ImportURL": ImportURL,
            "DiscordID": DiscordID
        }
        ResponseResult    = await self.HTTPClient.post("/API/Characters/Import", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Imported Character on Platform: Name=\"{ResultDictionary.get("Name")}\", DiscordID={DiscordID}")
        return ResultDictionary

    async def Close(self) -> None:
        await self.HTTPClient.aclose()

