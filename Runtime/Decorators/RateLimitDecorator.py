import typing                                     as Typing
import discord                                    as Discord
import discord.ext.commands                       as Commands
import Runtime.Services.RateLimitService          as RateLimit
import Runtime.Decorators.AuthorizationDecorators as AuthorizationDecorators

COLOR_RATE_LIMIT_EMBED: int = 0xA60000

class RateLimitExceeded(Commands.CheckFailure):
    def __init__(self, WaitSeconds: float, Category: str = "Standard") -> None:
        self.WaitSeconds: float = WaitSeconds
        self.Category   : str   = Category
        super().__init__(f"Rate limit exceeded. Try again in {WaitSeconds:.1f}s.")

def BuildRateLimitCooldownEmbed(WaitSeconds: float, Category: str = "Standard") -> Discord.Embed:
    EmbedMessage: Discord.Embed = Discord.Embed(title = "Rate Limit Reached", description = f"Please wait **{WaitSeconds:.1f}s** before executing another {Category.lower()} command.", color = COLOR_RATE_LIMIT_EMBED)
    EmbedMessage.set_footer(text = "Tally │ Token-Bucket Rate Limiter")
    return EmbedMessage

def RateLimit(Category: str = "Standard") -> Typing.Callable:
    async def Predicate(Context: Commands.Context) -> bool:
        if AuthorizationDecorators.IsMacroMasterOrAdmin(Context):
            return True

        RateLimitServiceInstance: Typing.Optional[RateLimit.RateLimitService] = getattr(Context.bot, "RateLimitService", None)
        if (RateLimitServiceInstance is None):
            return True

        IsAllowed, RemainingWait = RateLimitServiceInstance.CheckRateLimit(Context.author.id, Category = Category)
        if not IsAllowed:
            raise RateLimitExceeded(WaitSeconds = RemainingWait, Category = Category)

        return True

    return Commands.check(Predicate)
