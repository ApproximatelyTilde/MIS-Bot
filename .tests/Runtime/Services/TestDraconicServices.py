import ast                                      as AbstractSyntaxTree
import pytest                                   as Pytest
import Runtime.Services.Draconic.Exceptions     as Exceptions
import Runtime.Services.Draconic.SandboxedScope as SandboxedScope
import Runtime.Services.Draconic.DraconicEngine as DraconicEngine

class TestDraconicServices:
    def TestDraconicListOperations(self) -> None:
        ListInstance: SandboxedScope.DraconicList = SandboxedScope.DraconicList([1, 2, 3])
        ListInstance.append(4)
        assert (len(ListInstance) == 4)
        assert (ListInstance[3] == 4)

        ListInstance.extend([5, 6])
        assert (len(ListInstance) == 6)

        ListInstance.insert(0, 0)
        assert (ListInstance[0] == 0)

    def TestDraconicListSizeLimit(self) -> None:
        ListInstance : SandboxedScope.DraconicList = SandboxedScope.DraconicList()
        OriginalLimit: int                         = SandboxedScope.MAX_CONTAINER_SIZE
        try:
            SandboxedScope.MAX_CONTAINER_SIZE     = 3
            ListInstance.append(1)
            ListInstance.append(2)
            ListInstance.append(3)

            with Pytest.raises(Exceptions.DraconicExecutionError):
                ListInstance.append(4)

        finally:
            SandboxedScope.MAX_CONTAINER_SIZE     = OriginalLimit

    def TestDraconicDictionaryItemAndAttributeAccess(self) -> None:
        DictionaryInstance: SandboxedScope.DraconicDictionary = SandboxedScope.DraconicDictionary()
        DictionaryInstance["name"]                            = "Tally"
        assert (DictionaryInstance["name"] == "Tally")
        assert (DictionaryInstance.name == "Tally")

        DictionaryInstance.score = 100
        assert (DictionaryInstance["score"] == 100)
        assert (DictionaryInstance.score == 100)
        assert (DictionaryInstance.get("unknown", 42) == 42)

    def TestDraconicDictionaryBannedDunderKeyAccess(self) -> None:
        DictionaryInstance: SandboxedScope.DraconicDictionary = SandboxedScope.DraconicDictionary()

        with Pytest.raises(Exceptions.DraconicSecurityError):
            _ = DictionaryInstance["__class__"]

        with Pytest.raises(Exceptions.DraconicSecurityError):
            DictionaryInstance["__globals__"] = {}

        with Pytest.raises(Exceptions.DraconicSecurityError):
            _ = DictionaryInstance._private

        with Pytest.raises(Exceptions.DraconicSecurityError):
            DictionaryInstance._private = 1

    def TestDraconicSetOperations(self) -> None:
        SetInstance: SandboxedScope.DraconicSet = SandboxedScope.DraconicSet([1, 2])
        SetInstance.add(3)
        assert (3 in SetInstance)

        SetInstance.update([4, 5])
        assert (len(SetInstance) == 5)

    def TestDraconicExceptionsHierarchy(self) -> None:
        assert issubclass(Exceptions.DraconicSecurityError, Exceptions.DraconicException)
        assert issubclass(Exceptions.DraconicExecutionError, Exceptions.DraconicException)
        assert issubclass(Exceptions.DraconicTimeoutError, Exceptions.DraconicException)
        assert issubclass(Exceptions.DraconicSyntaxError, Exceptions.DraconicException)

    def TestDraconicEngineBannedNamesAndNodes(self) -> None:
        assert ("eval" in DraconicEngine.BANNED_IDENTIFIERS)
        assert ("exec" in DraconicEngine.BANNED_IDENTIFIERS)
        assert ("open" in DraconicEngine.BANNED_IDENTIFIERS)
        assert ("__import__" in DraconicEngine.BANNED_IDENTIFIERS)

        assert (AbstractSyntaxTree.Import in DraconicEngine.BANNED_AST_NODES)
        assert (AbstractSyntaxTree.ImportFrom in DraconicEngine.BANNED_AST_NODES)
        assert (AbstractSyntaxTree.ClassDef in DraconicEngine.BANNED_AST_NODES)
