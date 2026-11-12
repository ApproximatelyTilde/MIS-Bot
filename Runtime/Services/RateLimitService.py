import time   as TimeLibrary

DEFAULT_STANDARD_CAPACITY       : float = 5.0
DEFAULT_STANDARD_WINDOW_SECONDS : float = 5.0
DEFAULT_SCRIPTING_CAPACITY      : float = 2.0
DEFAULT_SCRIPTING_WINDOW_SECONDS: float = 5.0

class RateLimitCategory:
    STANDARD : str = "Standard"
    SCRIPTING: str = "Scripting"

class RateLimitBucket:
    def __init__(self, Capacity: float, WindowSeconds: float) -> None:
        self.Capacity           : float = Capacity
        self.WindowSeconds      : float = WindowSeconds
        self.RefillRate         : float = Capacity / WindowSeconds
        self.Tokens             : float = Capacity
        self.LastRefillTimestamp: float = TimeLibrary.monotonic()

    def Consume(self, TokensRequired: float = 1.0) -> tuple[bool, float]:
        CurrentTime: float = TimeLibrary.monotonic()
        ElapsedTime: float = CurrentTime - self.LastRefillTimestamp
        self.LastRefillTimestamp = CurrentTime

        self.Tokens = min(self.Capacity, self.Tokens + (ElapsedTime * self.RefillRate))
        if (self.Tokens >= TokensRequired):
            self.Tokens -= TokensRequired
            return (True, 0.0)

        Shortfall           : float = TokensRequired - self.Tokens
        RemainingWaitSeconds: float = Shortfall / self.RefillRate
        return (False, RemainingWaitSeconds)

    def Reset(self) -> None:
        self.Tokens              = self.Capacity
        self.LastRefillTimestamp = TimeLibrary.monotonic()

class RateLimitService:
    def __init__(self) -> None:
        self.BucketsDictionary: dict[str, RateLimitBucket] = dict()

    def BuildBucketKey(self, UserID: int, Category: str) -> str:
        return f"{UserID}:{Category.lower()}"

    def GetOrCreateBucket(self, UserID: int, Category: str = "Standard") -> RateLimitBucket:
        BucketKey: str = self.BuildBucketKey(UserID, Category)
        if (BucketKey not in self.BucketsDictionary):
            NormalizedCategory: str   = Category.lower()
            Capacity          : float = DEFAULT_SCRIPTING_CAPACITY if (NormalizedCategory == "scripting") else DEFAULT_STANDARD_CAPACITY
            WindowSeconds     : float = DEFAULT_SCRIPTING_WINDOW_SECONDS if (NormalizedCategory == "scripting") else DEFAULT_STANDARD_WINDOW_SECONDS
            self.BucketsDictionary[BucketKey] = RateLimitBucket(Capacity = Capacity, WindowSeconds = WindowSeconds)

        return self.BucketsDictionary[BucketKey]

    def PruneIdleBuckets(self, MaxIdleSeconds: float = 600.0) -> int:
        CurrentTime: float     = TimeLibrary.monotonic()
        KeysToPrune: list[str] = []
        for BucketKey, Bucket in self.BucketsDictionary.items():
            IdleTime: float = CurrentTime - Bucket.LastRefillTimestamp
            if (IdleTime >= MaxIdleSeconds) and (Bucket.Tokens >= Bucket.Capacity):
                KeysToPrune.append(BucketKey)

        for TargetKey in KeysToPrune:
            del self.BucketsDictionary[TargetKey]

        return len(KeysToPrune)

    def CheckRateLimit(self, UserID: int, Category: str = "Standard", TokensRequired: float = 1.0) -> tuple[bool, float]:
        if (len(self.BucketsDictionary) > 500):
            self.PruneIdleBuckets()

        TargetBucket: RateLimitBucket = self.GetOrCreateBucket(UserID, Category)
        return TargetBucket.Consume(TokensRequired)

    def ResetUserLimits(self, UserID: int) -> None:
        PrefixPattern: str       = f"{UserID}:"
        KeysToDelete : list[str] = [BucketKey for BucketKey in self.BucketsDictionary.keys() if BucketKey.startswith(PrefixPattern)]
        for TargetKey in KeysToDelete:
            del self.BucketsDictionary[TargetKey]

    def ClearAllLimits(self) -> None:
        self.BucketsDictionary.clear()
