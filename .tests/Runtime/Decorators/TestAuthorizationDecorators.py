import typing                                     as Typing
import unittest.mock                              as MockLibrary
import discord.ext.commands                       as Commands
import Runtime.Configuration.Config               as Config
import Runtime.Decorators.AuthorizationDecorators as AuthorizationDecorators

class TestAuthorizationDecorators:
    def TestCheckDND5EPrefixWithServerSettings(self) -> None:
        MockBot             : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockService         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockBot.ServerSettingsService               = MockService
        MockService.GetCachedDND5EPrefix.return_value = "!dnd"

        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.id                                = 123456789

        MockContextValid    : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContextValid.bot                        = MockBot
        MockContextValid.guild                      = MockGuild
        MockContextValid.prefix                     = "!dnd"

        assert (AuthorizationDecorators.CheckDND5EPrefix(MockContextValid) is True)

        MockContextInvalid  : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContextInvalid.bot                      = MockBot
        MockContextInvalid.guild                    = MockGuild
        MockContextInvalid.prefix                   = "!other"

        assert (AuthorizationDecorators.CheckDND5EPrefix(MockContextInvalid) is False)

    def TestCheckDND5EPrefixWithoutServerSettings(self) -> None:
        MockBot             : MockLibrary.MagicMock = MockLibrary.MagicMock(spec = Commands.Bot)
        del MockBot.ServerSettingsService

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.bot                             = MockBot
        MockContext.prefix                          = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E

        assert (AuthorizationDecorators.CheckDND5EPrefix(MockContext) is True)

    def TestCheckMGT2EPrefixWithServerSettings(self) -> None:
        MockBot             : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockService         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockBot.ServerSettingsService               = MockService
        MockService.GetCachedMGT2EPrefix.return_value = ".mgt"

        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.id                                = 987654321

        MockContextValid    : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContextValid.bot                        = MockBot
        MockContextValid.guild                      = MockGuild
        MockContextValid.prefix                     = ".mgt"

        assert (AuthorizationDecorators.CheckMGT2EPrefix(MockContextValid) is True)

        MockContextInvalid  : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContextInvalid.bot                      = MockBot
        MockContextInvalid.guild                    = MockGuild
        MockContextInvalid.prefix                   = ".other"

        assert (AuthorizationDecorators.CheckMGT2EPrefix(MockContextInvalid) is False)

    def TestCheckMGT2EPrefixWithoutServerSettings(self) -> None:
        MockBot             : MockLibrary.MagicMock = MockLibrary.MagicMock(spec = Commands.Bot)
        del MockBot.ServerSettingsService

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.bot                             = MockBot
        MockContext.prefix                          = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E

        assert (AuthorizationDecorators.CheckMGT2EPrefix(MockContext) is True)

    def TestIsMacroMasterOrAdminDirectMessage(self) -> None:
        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = None

        assert (AuthorizationDecorators.IsMacroMasterOrAdmin(MockContext) is True)

    def TestIsMacroMasterOrAdminGuildOwner(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.owner_id                          = 111222333

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111222333

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor

        assert (AuthorizationDecorators.IsMacroMasterOrAdmin(MockContext) is True)

    def TestIsMacroMasterOrAdminAdministratorPermission(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = True
        MockPermissions.manage_guild                = False

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111111111
        MockAuthor.guild_permissions                = MockPermissions

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor

        assert (AuthorizationDecorators.IsMacroMasterOrAdmin(MockContext) is True)

    def TestIsMacroMasterOrAdminManageGuildPermission(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = False
        MockPermissions.manage_guild                = True

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111111111
        MockAuthor.guild_permissions                = MockPermissions

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor

        assert (AuthorizationDecorators.IsMacroMasterOrAdmin(MockContext) is True)

    def TestIsMacroMasterOrAdminNamedRoleMatch(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = False
        MockPermissions.manage_guild                = False

        MockRole            : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockRole.name                               = "Macro Master"

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111111111
        MockAuthor.guild_permissions                = MockPermissions
        MockAuthor.roles                            = [MockRole]

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor

        assert (AuthorizationDecorators.IsMacroMasterOrAdmin(MockContext) is True)

    def TestIsMacroMasterOrAdminCachedRoleIDMatch(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.id                                = 555555
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = False
        MockPermissions.manage_guild                = False

        MockRole            : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockRole.name                               = "Helper"
        MockRole.id                                 = 777888

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111111111
        MockAuthor.guild_permissions                = MockPermissions
        MockAuthor.roles                            = [MockRole]

        MockSettings        : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockSettings.MacroMasterRoleID              = "777888"

        MockService         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockService.SettingsCache                   = {
            "555555": MockSettings
        }

        MockBot             : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockBot.ServerSettingsService               = MockService

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor
        MockContext.bot                             = MockBot

        assert (AuthorizationDecorators.IsMacroMasterOrAdmin(MockContext) is True)

    def TestIsMacroMasterOrAdminDenied(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.id                                = 555555
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = False
        MockPermissions.manage_guild                = False

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111111111
        MockAuthor.guild_permissions                = MockPermissions
        MockAuthor.roles                            = []

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor

        assert (AuthorizationDecorators.IsMacroMasterOrAdmin(MockContext) is False)

    def TestIsDungeonMasterOrMacroMasterWithDMRole(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = False
        MockPermissions.manage_guild                = False
        MockPermissions.manage_channels             = False

        MockRole            : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockRole.name                               = "Dungeon Master"

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111111111
        MockAuthor.guild_permissions                = MockPermissions
        MockAuthor.roles                            = [MockRole]

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor

        assert (AuthorizationDecorators.IsDungeonMasterOrMacroMaster(MockContext) is True)

    def TestIsDungeonMasterOrMacroMasterWithManageChannels(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = False
        MockPermissions.manage_guild                = False
        MockPermissions.manage_channels             = True

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111111111
        MockAuthor.guild_permissions                = MockPermissions
        MockAuthor.roles                            = []

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor

        assert (AuthorizationDecorators.IsDungeonMasterOrMacroMaster(MockContext) is True)

    def TestRequireDecoratorsReturnCallable(self) -> None:
        MacroMasterDecorator: Typing.Callable = AuthorizationDecorators.RequireMacroMasterOrAdmin()
        assert callable(MacroMasterDecorator)

        DungeonMasterDecorator: Typing.Callable = AuthorizationDecorators.RequireDungeonMasterOrMacroMaster()
        assert callable(DungeonMasterDecorator)
