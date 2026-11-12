import Runtime.Services.RateLimitService as RateLimit

class TestRateLimitService:
    def TestRateLimitBucketTokenConsumption(self) -> None:
        Bucket: RateLimit.RateLimitBucket = RateLimit.RateLimitBucket(Capacity = 5.0, WindowSeconds = 5.0)
        assert (Bucket.Tokens == 5.0)

        IsAllowedFirst, WaitFirst = Bucket.Consume(TokensRequired = 2.0)
        assert (IsAllowedFirst is True)
        assert (WaitFirst == 0.0)
        assert (2.9 <= Bucket.Tokens <= 3.1)

        IsAllowedSecond, WaitSecond = Bucket.Consume(TokensRequired = 3.0)
        assert (IsAllowedSecond is True)
        assert (WaitSecond == 0.0)

        IsAllowedThird, WaitThird = Bucket.Consume(TokensRequired = 1.0)
        assert (IsAllowedThird is False)
        assert (WaitThird > 0.0)

    def TestRateLimitBucketReset(self) -> None:
        Bucket: RateLimit.RateLimitBucket = RateLimit.RateLimitBucket(Capacity = 4.0, WindowSeconds = 4.0)
        Bucket.Consume(TokensRequired = 4.0)
        assert (Bucket.Tokens < 1.0)

        Bucket.Reset()
        assert (Bucket.Tokens == 4.0)

    def TestBuildBucketKey(self) -> None:
        ServiceInstance: RateLimit.RateLimitService = RateLimit.RateLimitService()
        GeneratedKey   : str                        = ServiceInstance.BuildBucketKey(123456789, "Standard")
        assert (GeneratedKey == "123456789:standard")

    def TestGetOrCreateBucketCategories(self) -> None:
        ServiceInstance: RateLimit.RateLimitService = RateLimit.RateLimitService()
        StandardBucket : RateLimit.RateLimitBucket  = ServiceInstance.GetOrCreateBucket(1001, Category = "Standard")
        assert (StandardBucket.Capacity == RateLimit.DEFAULT_STANDARD_CAPACITY)

        ScriptingBucket: RateLimit.RateLimitBucket  = ServiceInstance.GetOrCreateBucket(1001, Category = "Scripting")
        assert (ScriptingBucket.Capacity == RateLimit.DEFAULT_SCRIPTING_CAPACITY)

    def TestCheckRateLimitServiceFlow(self) -> None:
        ServiceInstance: RateLimit.RateLimitService = RateLimit.RateLimitService()
        for _ in range(5):
            AllowedStatus, RemainingWait = ServiceInstance.CheckRateLimit(2002, Category = "Standard", TokensRequired = 1.0)
            assert (AllowedStatus is True)
            assert (RemainingWait == 0.0)

        DenyStatus, WaitTime = ServiceInstance.CheckRateLimit(2002, Category = "Standard", TokensRequired = 1.0)
        assert (DenyStatus is False)
        assert (WaitTime > 0.0)

    def TestResetUserLimits(self) -> None:
        ServiceInstance: RateLimit.RateLimitService = RateLimit.RateLimitService()
        ServiceInstance.CheckRateLimit(3003, Category = "Standard")
        ServiceInstance.CheckRateLimit(3003, Category = "Scripting")
        ServiceInstance.CheckRateLimit(4004, Category = "Standard")

        assert ("3003:standard" in ServiceInstance.BucketsDictionary)
        assert ("3003:scripting" in ServiceInstance.BucketsDictionary)
        assert ("4004:standard" in ServiceInstance.BucketsDictionary)

        ServiceInstance.ResetUserLimits(3003)
        assert ("3003:standard" not in ServiceInstance.BucketsDictionary)
        assert ("3003:scripting" not in ServiceInstance.BucketsDictionary)
        assert ("4004:standard" in ServiceInstance.BucketsDictionary)

    def TestClearAllLimits(self) -> None:
        ServiceInstance: RateLimit.RateLimitService = RateLimit.RateLimitService()
        ServiceInstance.CheckRateLimit(5005, Category = "Standard")
        ServiceInstance.CheckRateLimit(6006, Category = "Standard")
        assert (len(ServiceInstance.BucketsDictionary) == 2)

        ServiceInstance.ClearAllLimits()
        assert (len(ServiceInstance.BucketsDictionary) == 0)
