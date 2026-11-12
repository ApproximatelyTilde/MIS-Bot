import typing                       as Typing
import discord.ext.commands         as Commands
import Runtime.Configuration.Config as Config

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsServiceInstance: Typing.Any = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsServiceInstance is not None):
        GuildID       : Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        ExpectedPrefix: str                  = ServerSettingsServiceInstance.GetCachedDND5EPrefix(GuildID)
        return (Context.prefix == ExpectedPrefix)

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)

def CheckMGT2EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsServiceInstance: Typing.Any = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsServiceInstance is not None):
        GuildID       : Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        ExpectedPrefix: str                  = ServerSettingsServiceInstance.GetCachedMGT2EPrefix(GuildID)
        return (Context.prefix == ExpectedPrefix)

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E)

def IsMacroMasterOrAdmin(Context: Commands.Context) -> bool:
    if (Context.guild is None):
        return True

    AuthorMember: Typing.Any = Context.author
    if (AuthorMember is None):
        return False

    GuildOwnerID: Typing.Optional[int] = getattr(Context.guild, "owner_id", None)
    if (GuildOwnerID is not None) and (getattr(AuthorMember, "id", None) == GuildOwnerID):
        return True

    AuthorPermissions: Typing.Any = getattr(AuthorMember, "guild_permissions", None)
    if (AuthorPermissions is not None):
        HasAdminPermissions: bool = getattr(AuthorPermissions, "administrator", False) or getattr(AuthorPermissions, "manage_guild", False)
        if HasAdminPermissions:
            return True

    TargetSuperUserRoleName: str              = Config.GLOBAL_SETTINGS.PLATFORM_SUPER_USER.lower()
    AuthorRoles            : list[Typing.Any] = getattr(AuthorMember, "roles", [])
    for AssignedRole in AuthorRoles:
        if (getattr(AssignedRole, "name", "").lower() == TargetSuperUserRoleName):
            return True

    ServerSettingsServiceInstance: Typing.Any = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsServiceInstance is not None):
        CachedSettings   : Typing.Any = getattr(ServerSettingsServiceInstance, "SettingsCache", {}).get(str(getattr(Context.guild, "id", "")))
        MacroMasterRoleID: Typing.Any = CachedSettings.MacroMasterRoleID if (CachedSettings is not None) else None
        if (MacroMasterRoleID is not None):
            for AssignedRole in AuthorRoles:
                if (str(getattr(AssignedRole, "id", "")) == MacroMasterRoleID):
                    return True

    return False

def RequireMacroMasterOrAdmin() -> Typing.Callable:
    return Commands.check(IsMacroMasterOrAdmin)

def IsDungeonMasterOrMacroMaster(Context: Commands.Context) -> bool:
    if (Context.guild is None):
        return True

    if IsMacroMasterOrAdmin(Context):
        return True

    AuthorMember: Typing.Any = Context.author
    if (AuthorMember is None):
        return False

    AuthorPermissions: Typing.Any = getattr(AuthorMember, "guild_permissions", None)
    if (AuthorPermissions is not None):
        HasChannelPermissions: bool = getattr(AuthorPermissions, "administrator", False) or getattr(AuthorPermissions, "manage_channels", False)
        if HasChannelPermissions:
            return True

    DMRolesAllowed: tuple[str, ...]  = ("dm", "game master", "dungeon master", "gm")
    AuthorRoles   : list[Typing.Any] = getattr(AuthorMember, "roles", [])
    for AssignedRole in AuthorRoles:
        if (getattr(AssignedRole, "name", "").lower() in DMRolesAllowed):
            return True

    return False

def RequireDungeonMasterOrMacroMaster() -> Typing.Callable:
    return Commands.check(IsDungeonMasterOrMacroMaster)
