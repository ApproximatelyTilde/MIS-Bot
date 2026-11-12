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
        ExpirationEpoch: int                    = CurrentEpoch + DEFAULT_TOKEN_EXPIRATION_SECONDS
        HeaderData     : Typing.Dict[str, str]  = {"alg": "HS256", "typ": "JWT"}
        PayloadData    : Typing.Dict[str, Typing.Any] = {
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

    def GetDefaultHeaders(self) -> Typing.Dict[str, str]:
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

    async def FetchRulesDataStore(self) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/DataStore", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        DataStoreDictionary: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Rules DataStore: System=\"{DataStoreDictionary.get("GameSystem")}\"")
        return DataStoreDictionary

    async def FetchClassRules(self) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/Classes", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ClassesSummary: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Class Rules: Count={len(ClassesSummary)}")
        return ClassesSummary

    async def FetchSpellcastingAbility(self, ClassName: str, SubclassName: Typing.Optional[str] = None) -> Typing.Optional[str]:
        RequestHeaders = self.GetDefaultHeaders()
        QueryParameters: Typing.Dict[str, str] = {"ClassName": ClassName}
        if (SubclassName is not None):
            QueryParameters["SubclassName"] = SubclassName

        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/SpellcastingAbility", params = QueryParameters, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultData      : Typing.Dict[str, Typing.Any] = ResponseResult.json()
        SpellcastAbility: Typing.Optional[str]         = ResultData.get("SpellcastingAbility")
        return SpellcastAbility

    async def FetchCantripsList(self) -> Typing.List[str]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/Cantrips", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CantripsList: Typing.List[str] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Cantrips: Count={len(CantripsList)}")
        return CantripsList

    async def FetchEquipmentData(self) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters/Rules/EquipmentData", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        EquipmentData: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Equipment Data: Armors={len(EquipmentData.get("Armors", {}))}")
        return EquipmentData

    async def FetchAllCharacters(self) -> Typing.List[Typing.Dict[str, Typing.Any]]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get("/API/Characters", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CharactersList: Typing.List[Typing.Dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched All Characters: Count={len(CharactersList)}")
        return CharactersList

    async def FetchCharactersByDiscordID(self, DiscordID: str) -> Typing.List[Typing.Dict[str, Typing.Any]]:
        AllCharacters   : Typing.List[Typing.Dict[str, Typing.Any]] = await self.FetchAllCharacters()
        MatchingList    : Typing.List[Typing.Dict[str, Typing.Any]] = []
        TargetDiscordStr: str                                       = str(DiscordID).strip()
        for CharacterRecord in AllCharacters:
            SummaryData: Typing.Dict[str, Typing.Any] = CharacterRecord.get("SummaryData", {})
            OwnerData  : Typing.Dict[str, Typing.Any] = CharacterRecord.get("Owner", {})
            OwnerDiscord: str = str(OwnerData.get("DiscordID", "")).strip() or str(SummaryData.get("DiscordID", "")).strip()
            if (OwnerDiscord == TargetDiscordStr):
                MatchingList.append(CharacterRecord)

        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Matched Characters for DiscordID=\"{TargetDiscordStr}\": Count={len(MatchingList)}")
        return MatchingList

    async def FetchSpellDetails(self, SpellName: str) -> Typing.Optional[Typing.Dict[str, Typing.Any]]:
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

    async def FetchMonsterDetails(self, MonsterName: str) -> Typing.Optional[Typing.Dict[str, Typing.Any]]:
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

    async def FetchItemDetails(self, ItemName: str) -> Typing.Optional[Typing.Dict[str, Typing.Any]]:
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

    async def FetchCharacterActions(self, CharacterID: str) -> Typing.List[Typing.Dict[str, Typing.Any]]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.get(f"/API/Characters/{CharacterID}/Actions", headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ActionsList: Typing.List[Typing.Dict[str, Typing.Any]] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Fetched Character Actions: CharID=\"{CharacterID[:8]}…\", Count={len(ActionsList)}")
        return ActionsList

    async def CreateCharacterAction(self, CharacterID: str, ActionPayload: Typing.Dict[str, Typing.Any]) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Actions", json = ActionPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        CreatedAction: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Character Action on Platform: CharID=\"{CharacterID[:8]}…\"")
        return CreatedAction

    async def UpdateCharacterAction(self, CharacterID: str, ActionID: str, UpdatePayload: Typing.Dict[str, Typing.Any]) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.patch(f"/API/Characters/{CharacterID}/Actions/{ActionID}", json = UpdatePayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        UpdatedAction: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Character Action on Platform: ActionID=\"{ActionID[:8]}…\"")
        return UpdatedAction

    async def DeleteCharacterAction(self, CharacterID: str, ActionID: str) -> bool:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.delete(f"/API/Characters/{CharacterID}/Actions/{ActionID}", headers = RequestHeaders)
        IsSuccess      : bool = (ResponseResult.status_code == 200)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Character Action on Platform: ActionID=\"{ActionID[:8]}…\", Success={IsSuccess}")
        return IsSuccess

    async def CreateOrUpdateCounter(self, CharacterID: str, CounterPayload: Typing.Dict[str, Typing.Any]) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Counters", json = CounterPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created/Updated Counter on Platform: CharID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def MutateCounter(self, CharacterID: str, CounterName: str, Delta: Typing.Optional[int] = None, Value: Typing.Optional[int] = None, Operation: Typing.Optional[str] = None) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        PayloadDictionary: Typing.Dict[str, Typing.Any] = {}
        if (Delta is not None):
            PayloadDictionary["Delta"] = Delta

        if (Value is not None):
            PayloadDictionary["Value"] = Value

        if (Operation is not None):
            PayloadDictionary["Operation"] = Operation

        ResponseResult = await self.HTTPClient.patch(f"/API/Characters/{CharacterID}/Counters/{CounterName}", json = PayloadDictionary, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Mutated Counter on Platform: Name=\"{CounterName}\", CharID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def SetCharacterVariables(self, CharacterID: str, VariablesPayload: Typing.Dict[str, Typing.Any]) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post(f"/API/Characters/{CharacterID}/Variables", json = VariablesPayload, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ResultDictionary: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Set Character Variables on Platform: CharID=\"{CharacterID[:8]}…\"")
        return ResultDictionary

    async def ValidateAutomationTree(self, AutomationList: Typing.List[Typing.Dict[str, Typing.Any]]) -> Typing.Dict[str, Typing.Any]:
        RequestHeaders = self.GetDefaultHeaders()
        ResponseResult = await self.HTTPClient.post("/API/Automations/Validate", json = {"Automation": AutomationList}, headers = RequestHeaders)
        ResponseResult.raise_for_status()
        ValidationResponse: Typing.Dict[str, Typing.Any] = ResponseResult.json()
        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Validated Automation on Platform: Valid={ValidationResponse.get("IsValid")}")
        return ValidationResponse

    async def Close(self) -> None:
        await self.HTTPClient.aclose()

