import typing                           as Typing
import Runtime.Services.AliasingService as Aliasing

class TestAliasingService:
    def TestSetAndGetUserAlias(self) -> None:
        ServiceInstance: Aliasing.AliasingService = Aliasing.AliasingService()
        CreatedEntry   : Aliasing.AliasEntry      = ServiceInstance.SetUserAlias(UserID = "1001", Name = "QuickAttack", Content = "1d20 + 5")
        assert (CreatedEntry.Name == "quickattack")
        assert (CreatedEntry.Content == "1d20 + 5")
        assert (CreatedEntry.CreatorDiscordID == "1001")

        RetrievedEntry: Typing.Optional[Aliasing.AliasEntry] = ServiceInstance.GetAlias("quickattack", UserID = "1001")
        assert (RetrievedEntry is not None)
        assert (RetrievedEntry.Content == "1d20 + 5")

    def TestDeleteUserAlias(self) -> None:
        ServiceInstance: Aliasing.AliasingService = Aliasing.AliasingService()
        ServiceInstance.SetUserAlias(UserID = "1002", Name = "Fire", Content = "3d6")

        assert (ServiceInstance.DeleteUserAlias(UserID = "1002", Name = "Fire") is True)
        assert (ServiceInstance.DeleteUserAlias(UserID = "1002", Name = "Fire") is False)
        assert (ServiceInstance.GetAlias("fire", UserID = "1002") is None)

    def TestServerAliasLifecycle(self) -> None:
        ServiceInstance   : Aliasing.AliasingService = Aliasing.AliasingService()
        CreatedServerEntry: Aliasing.AliasEntry      = ServiceInstance.SetServerAlias(ServerID = "guild-1", CreatorDiscordID = "1003", Name = "GuildHelp", Content = "Rules list")
        assert (CreatedServerEntry.Name == "guildhelp")
        assert (CreatedServerEntry.ServerID == "guild-1")

        RetrievedEntry: Typing.Optional[Aliasing.AliasEntry] = ServiceInstance.GetAlias("guildhelp", UserID = "9999", ServerID = "guild-1")
        assert (RetrievedEntry is not None)
        assert (RetrievedEntry.Content == "Rules list")

        ServerList: list[Aliasing.AliasEntry] = ServiceInstance.ListServerAliases("guild-1")
        assert (len(ServerList) == 1)

        assert (ServiceInstance.DeleteServerAlias("guild-1", "guildhelp") is True)
        assert (len(ServiceInstance.ListServerAliases("guild-1")) == 0)

    def TestCollaboratorAliasAccess(self) -> None:
        ServiceInstance: Aliasing.AliasingService = Aliasing.AliasingService()
        SharedEntry    : Aliasing.AliasEntry      = ServiceInstance.SetUserAlias(UserID = "owner-1", Name = "TeamMacro", Content = "Cast Spell")
        SharedEntry.CollaboratorIDs = ["collaborator-2"]

        FoundForOwner: Typing.Optional[Aliasing.AliasEntry] = ServiceInstance.GetAlias("teammacro", UserID = "owner-1")
        assert (FoundForOwner is not None)

        FoundForCollaborator: Typing.Optional[Aliasing.AliasEntry] = ServiceInstance.GetAlias("teammacro", UserID = "collaborator-2")
        assert (FoundForCollaborator is not None)

        FoundForStranger: Typing.Optional[Aliasing.AliasEntry] = ServiceInstance.GetAlias("teammacro", UserID = "stranger-3")
        assert (FoundForStranger is None)

        CollabList: list[Aliasing.AliasEntry] = ServiceInstance.ListUserAliases("collaborator-2")
        assert (len(CollabList) == 1)
        assert (CollabList[0].Name == "teammacro")
