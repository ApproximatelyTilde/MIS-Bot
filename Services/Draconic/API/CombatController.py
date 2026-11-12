import typing                             as Typing
import Services.EncounterManagerService     as EncounterManager
import Services.Draconic.SandboxedScope     as SandboxedScope
import Services.Draconic.API.CombatantController as CombatantController

class CombatController:
    def __init__(self, Encounter: EncounterManager.CombatEncounter, CurrentAuthorDiscordID: Typing.Optional[str] = None) -> None:
        self.Encounter             : EncounterManager.CombatEncounter = Encounter
        self.CurrentAuthorDiscordID: Typing.Optional[str]             = CurrentAuthorDiscordID

    @property
    def is_active(self) -> bool:
        return self.Encounter.IsActive

    @property
    def round(self) -> int:
        return self.Encounter.RoundNumber

    @property
    def current(self) -> Typing.Optional[CombatantController.CombatantController]:
        ActiveCombatant: Typing.Optional[EncounterManager.CombatantEntry] = self.Encounter.GetActiveCombatant()
        return CombatantController.CombatantController(ActiveCombatant) if (ActiveCombatant is not None) else None

    @property
    def current_turn(self) -> str:
        ActiveCurrent = self.current
        return ActiveCurrent.name if (ActiveCurrent is not None) else ""

    @property
    def combatant_count(self) -> int:
        return len(self.Encounter.Combatants)

    @property
    def combatants(self) -> SandboxedScope.DraconicList:
        WrappedList: SandboxedScope.DraconicList = SandboxedScope.DraconicList()
        for CombatantEntry in self.Encounter.Combatants:
            WrappedList.append(CombatantController.CombatantController(CombatantEntry))

        return WrappedList

    @property
    def me(self) -> Typing.Optional[CombatantController.CombatantController]:
        if (self.CurrentAuthorDiscordID is None):
            return None

        TargetDiscordID: str = str(self.CurrentAuthorDiscordID).strip()
        for CombatantEntry in self.Encounter.Combatants:
            if (str(CombatantEntry.ControllerDiscordID or "").strip() == TargetDiscordID):
                return CombatantController.CombatantController(CombatantEntry)

        return None

    def get_combatant(self, CombatantName: str) -> Typing.Optional[CombatantController.CombatantController]:
        FoundEntry: Typing.Optional[EncounterManager.CombatantEntry] = self.Encounter.FindCombatant(CombatantName)
        return CombatantController.CombatantController(FoundEntry) if (FoundEntry is not None) else None

    def add_combatant(self, Name: str, HitPoints: int, ArmorClass: int = 10, InitiativeScore: int = 0) -> CombatantController.CombatantController:
        NewID: str = f"combatant-{len(self.Encounter.Combatants) + 1}"
        Entry: EncounterManager.CombatantEntry = EncounterManager.CombatantEntry(
            ID                 = NewID,
            Name               = Name.strip(),
            Initiative         = InitiativeScore,
            CurrentHitPoints   = HitPoints,
            MaxHitPoints       = HitPoints,
            ArmorClass         = ArmorClass,
            Conditions         = []
        )
        self.Encounter.AddCombatant(Entry)
        return CombatantController.CombatantController(Entry)

    def remove_combatant(self, CombatantName: str) -> bool:
        RemovedEntry: Typing.Optional[EncounterManager.CombatantEntry] = self.Encounter.RemoveCombatant(CombatantName)
        return (RemovedEntry is not None)
