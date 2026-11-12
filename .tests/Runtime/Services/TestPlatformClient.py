import base64                          as Base64Library
import hashlib                         as HashLibrary
import hmac                            as HMACLibrary
import json                            as JSONLibrary
import typing                          as Typing
import unittest.mock                   as MockLibrary
import pytest                          as Pytest
import Runtime.Services.PlatformClient as PlatformClient

class TestPlatformClient:
    def TestEncodeBase64URL(self) -> None:
        InputBytes  : bytes = b"Tally Testing String Value"
        EncodedValue: str   = PlatformClient.EncodeBase64URL(InputBytes)
        assert ("=" not in EncodedValue)

        DecodedBytes: bytes = Base64Library.urlsafe_b64decode(EncodedValue + "==")
        assert (DecodedBytes == InputBytes)

    def TestGenerateServiceTokenStructureAndSignature(self) -> None:
        ClientInstance: PlatformClient.TallyPlatformClient = PlatformClient.TallyPlatformClient(BaseURL = "http://127.0.0.1:8000", SecretKey = "TestSecretKeyPlatform12345")
        ServiceToken  : str                                = ClientInstance.GenerateServiceToken(Subject = "TallyTest", Role = "Tester")
        TokenParts    : list[str]                          = ServiceToken.split(".")
        assert (len(TokenParts) == 3)

        HeaderJSON : dict[str, str] = JSONLibrary.loads(Base64Library.urlsafe_b64decode(TokenParts[0] + "==").decode("utf-8"))
        assert (HeaderJSON["alg"] == "HS256")
        assert (HeaderJSON["typ"] == "JWT")

        PayloadJSON: dict[str, str] = JSONLibrary.loads(Base64Library.urlsafe_b64decode(TokenParts[1] + "==").decode("utf-8"))
        assert (PayloadJSON["sub"] == "TallyTest")
        assert (PayloadJSON["role"] == "Tester")
        assert ("iat" in PayloadJSON)
        assert ("exp" in PayloadJSON)

        SigningInput: str   = f"{TokenParts[0]}.{TokenParts[1]}"
        HMACDigest  : bytes = HMACLibrary.new("TestSecretKeyPlatform12345".encode("utf-8"), SigningInput.encode("utf-8"), HashLibrary.sha256).digest()
        ExpectedSig : str   = PlatformClient.EncodeBase64URL(HMACDigest)
        assert (TokenParts[2] == ExpectedSig)

    def TestGetDefaultHeaders(self) -> None:
        ClientInstance: PlatformClient.TallyPlatformClient = PlatformClient.TallyPlatformClient(BaseURL = "http://127.0.0.1:8000", SecretKey = "TestSecretKeyPlatform12345")
        Headers       : dict[str, str]                     = ClientInstance.GetDefaultHeaders()
        assert ("Authorization" in Headers)
        assert (Headers["Authorization"].startswith("Bearer "))
        assert (Headers["Accept"] == "application/json")

    @Pytest.mark.asyncio
    async def TestFetchSubclassDetails(self) -> None:
        ClientInstance: PlatformClient.TallyPlatformClient = PlatformClient.TallyPlatformClient(BaseURL = "http://127.0.0.1:8000", SecretKey = "TestSecretKeyPlatform12345")
        MockResponse: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockResponse.status_code                           = 200
        MockResponse.json.return_value                     = {
            "name"     : "Berserker",
            "className": "Barbarian",
            "source"   : "PHB"
        }

        with MockLibrary.patch.object(ClientInstance.HTTPClient, "get", return_value = MockResponse) as MockGet:
            SubclassResult: Typing.Optional[dict[str, Typing.Any]] = await ClientInstance.FetchSubclassDetails("Berserker", Source = "PHB")
            assert (SubclassResult is not None)
            assert (SubclassResult.get("name") == "Berserker")
            MockGet.assert_called_once()
            ArgsList, KwargsDict = MockGet.call_args
            assert (ArgsList[0] == "/API/Characters/Rules/Subclasses/Berserker")
            assert (KwargsDict["params"] == {"Source": "PHB"})

        await ClientInstance.Close()

    @Pytest.mark.asyncio
    async def TestCompanionEntityAndStatePersistenceEndpoints(self) -> None:
        ClientInstance: PlatformClient.TallyPlatformClient = PlatformClient.TallyPlatformClient(BaseURL = "http://127.0.0.1:8000", SecretKey = "TestSecretKeyPlatform12345")
        MockCompResponse: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockCompResponse.status_code  = 200
        MockCompResponse.json.return_value = [{"ID": "comp-1", "Name": "Survey Drone", "EntityType": "Companion", "GameSystem": "MGT2E"}]
        with MockLibrary.patch.object(ClientInstance.HTTPClient, "get", return_value = MockCompResponse) as MockGet:
            Comps: Typing.Any = await ClientInstance.FetchCharacterCompanions("char-99")
            assert (len(Comps) == 1)
            assert (Comps[0]["Name"] == "Survey Drone")
            assert (MockGet.call_args[0][0] == "/API/Characters/char-99/Companions")

        MockPatchResponse: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPatchResponse.status_code  = 200
        MockPatchResponse.json.return_value = {"ID": "char-99", "DetailData": {"Currency": {
            "Credits": 900
        }}}
        with MockLibrary.patch.object(ClientInstance.HTTPClient, "patch", return_value = MockPatchResponse) as MockPatch:
            Updated: Typing.Any = await ClientInstance.PersistCharacterState("char-99", {"DetailData": {"Currency": {
                "Credits": 900
            }}})
            assert (Updated is not None)
            assert (Updated["DetailData"]["Currency"]["Credits"] == 900)
            assert (MockPatch.call_args[0][0] == "/API/Characters/char-99/State")

        MockEntityResponse: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockEntityResponse.status_code  = 200
        MockEntityResponse.json.return_value = [{"ID": "other-1", "Name": "Imperial Patrol", "EntityType": "Other", "GameSystem": "MGT2E", "Owner": {
            "ID"       : "user-1",
            "DiscordID": "12345"
        }}]
        with MockLibrary.patch.object(ClientInstance.HTTPClient, "get", return_value = MockEntityResponse) as MockGetEntity:
            Others: Typing.Any = await ClientInstance.FetchCharactersByEntityType("Other", GameSystem = "MGT2E")
            assert (len(Others) == 1)
            assert (MockGetEntity.call_args[1]["params"] == {"EntityType": "Other", "GameSystem": "MGT2E"})
            ResolvedOwner: Typing.Any = await ClientInstance.ResolvePlatformUserIDByDiscordID("12345")
            assert (ResolvedOwner == "user-1")

        MockPostResponse: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPostResponse.status_code  = 200
        MockPostResponse.json.return_value = {
            "ID"               : "comp-1",
            "ParentCharacterID": "char-99",
            "EntityType"       : "Companion"
        }
        with MockLibrary.patch.object(ClientInstance.HTTPClient, "post", return_value = MockPostResponse) as MockPost:
            Linked: Typing.Any = await ClientInstance.LinkOrCreateCompanion("char-99", CompanionID = "comp-1", EntityType = "Companion")
            assert (Linked["ParentCharacterID"] == "char-99")
            assert (MockPost.call_args[0][0] == "/API/Characters/char-99/Companions")

            Transferred: Typing.Any = await ClientInstance.TransferCharacterEntity("comp-1", {"OwnerID": "user-2", "ParentCharacterID": None})
            assert (Transferred["ID"] == "comp-1")
            assert (MockPost.call_args[0][0] == "/API/Characters/comp-1/Transfer")
            assert (MockPost.call_args[1]["json"] == {"OwnerID": "user-2", "ParentCharacterID": None})

        await ClientInstance.Close()
