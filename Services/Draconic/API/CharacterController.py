import typing                                     as Typing
import Services.PlatformClient                    as PlatformClient
import Services.Draconic.Exceptions               as Exceptions
import Services.Draconic.SandboxedScope           as SandboxedScope
import Services.Draconic.API.CustomCounterManager as CounterManager

class CharacterController:
    def __init__(self, CharacterRecord: dict[str, Typing.Any], PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None) -> None:
        self.CharacterRecord: dict[str, Typing.Any]                    = CharacterRecord
        self.PlatformClient : PlatformClient.MISPlatformClient         = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.MISPlatformClient()
        self.DetailData     : dict[str, Typing.Any]                    = CharacterRecord.setdefault("DetailData", {})
        self.CounterManager : CounterManager.CustomCounterManager      = CounterManager.CustomCounterManager(CharacterRecord, self.PlatformClient)
        self.InitializeAttributes()

    def InitializeAttributes(self) -> None:
        AttributesMap: dict[str, Typing.Any] = self.DetailData.get("Attributes", {})
        STRScore     : int                   = int(AttributesMap.get("Strength", 10))
        DEXScore     : int                   = int(AttributesMap.get("Dexterity", 10))
        CONScore     : int                   = int(AttributesMap.get("Constitution", 10))
        INTScore     : int                   = int(AttributesMap.get("Intelligence", 10))
        WISScore     : int                   = int(AttributesMap.get("Wisdom", 10))
        CHAScore     : int                   = int(AttributesMap.get("Charisma", 10))

        self.stats: SandboxedScope.DraconicDict = SandboxedScope.DraconicDict({
            "strength"        : STRScore,
            "dexterity"       : DEXScore,
            "constitution"    : CONScore,
            "intelligence"    : INTScore,
            "wisdom"          : WISScore,
            "charisma"        : CHAScore,
            "strength_mod"    : (STRScore - 10) // 2,
            "dexterity_mod"   : (DEXScore - 10) // 2,
            "constitution_mod": (CONScore - 10) // 2,
            "intelligence_mod": (INTScore - 10) // 2,
            "wisdom_mod"      : (WISScore - 10) // 2,
            "charisma_mod"    : (CHAScore - 10) // 2
        })

        ClassesList: list[dict[str, Typing.Any]] = self.DetailData.get("Classes", [])
        LevelsMap  : SandboxedScope.DraconicDict = SandboxedScope.DraconicDict()
        for ClassItem in ClassesList:
            ClassName: str = str(ClassItem.get("ClassName", "Adventurer"))
            ClassLvl : int = int(ClassItem.get("Level", 1))
            LevelsMap[ClassName] = ClassLvl

        self.levels: SandboxedScope.DraconicDict = LevelsMap

        ProfBonus: int = int(self.DetailData.get("ProficiencyBonus", 2))
        SavesMap : SandboxedScope.DraconicDict = SandboxedScope.DraconicDict()
        ProficientSaves: list[str] = [str(S).lower() for S in self.DetailData.get("Proficiencies", {}).get("SavingThrows", [])]
        for StatName in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            StatMod: int  = self.stats[f"{StatName}_mod"]
            IsProf : bool = (StatName in ProficientSaves) or (StatName[:3] in ProficientSaves)
            TotalSaveMod  = StatMod + (ProfBonus if IsProf else 0)
            SavesMap[StatName] = TotalSaveMod
            SavesMap[StatName[:3]] = TotalSaveMod

        self.saves: SandboxedScope.DraconicDict = SavesMap

        SkillsMap: SandboxedScope.DraconicDict = SandboxedScope.DraconicDict()
        SkillsProficiencies: list[dict[str, Typing.Any]] = self.DetailData.get("Proficiencies", {}).get("Skills", [])
        ProficiencyTierMap : dict[str, str]              = {str(P.get("SkillName", "")).lower(): str(P.get("ProficiencyTier", "")) for P in SkillsProficiencies}

        SkillBaseMap: dict[str, str] = {
            "athletics": "strength", "acrobatics": "dexterity", "sleight_of_hand": "dexterity",
            "stealth": "dexterity", "arcana": "intelligence", "history": "intelligence",
            "investigation": "intelligence", "nature": "intelligence", "religion": "intelligence",
            "animal_handling": "wisdom", "insight": "wisdom", "medicine": "wisdom",
            "perception": "wisdom", "survival": "wisdom", "deception": "charisma",
            "intimidation": "charisma", "performance": "charisma", "persuasion": "charisma"
        }

        for SkillIdentifier, AssociatedAttribute in SkillBaseMap.items():
            NormalizedKey: str = SkillIdentifier.replace("_", " ")
            TierName     : str = ProficiencyTierMap.get(NormalizedKey, "")
            StatMod      : int = self.stats[f"{AssociatedAttribute}_mod"]
            Multiplier   : float = 2.0 if (TierName == "Expertise") else (1.0 if (TierName == "Proficient") else (0.5 if (TierName == "HalfProficient") else 0.0))
            SkillsMap[SkillIdentifier] = StatMod + int(ProfBonus * Multiplier)

        self.skills: SandboxedScope.DraconicDict = SkillsMap

    @property
    def name(self) -> str:
        return str(self.CharacterRecord.get("Name", "Hero"))

    @property
    def level(self) -> int:
        return int(self.DetailData.get("TotalLevel", 1))

    @property
    def pb(self) -> int:
        return int(self.DetailData.get("ProficiencyBonus", 2))

    @property
    def proficiency_bonus(self) -> int:
        return self.pb

    @property
    def hp(self) -> int:
        HitPointsData: dict[str, Typing.Any] = self.DetailData.get("HitPoints", {})
        return int(HitPointsData.get("CurrentHitPoints", 10))

    @property
    def max_hp(self) -> int:
        HitPointsData: dict[str, Typing.Any] = self.DetailData.get("HitPoints", {})
        return int(HitPointsData.get("MaxHitPoints", 10))

    @property
    def temp_hp(self) -> int:
        HitPointsData: dict[str, Typing.Any] = self.DetailData.get("HitPoints", {})
        return int(HitPointsData.get("TemporaryHitPoints", 0))

    @property
    def ac(self) -> int:
        ArmorClassData: dict[str, Typing.Any] = self.DetailData.get("ArmorClass", {})
        return int(ArmorClassData.get("TotalArmorClass", 10))

    def modify_hp(self, AmountDelta: int, Overflow: bool = False) -> int:
        HitPointsData: dict[str, Typing.Any] = self.DetailData.setdefault("HitPoints", {})
        CurrentHP    : int                   = int(HitPointsData.get("CurrentHitPoints", 10))
        MaxHP        : int                   = int(HitPointsData.get("MaxHitPoints", 10))
        TempHP       : int                   = int(HitPointsData.get("TemporaryHitPoints", 0))

        if (AmountDelta < 0):
            DamageRemaining: int = abs(AmountDelta)
            if (TempHP > 0):
                AbsorbedDamage = min(TempHP, DamageRemaining)
                TempHP         -= AbsorbedDamage
                DamageRemaining -= AbsorbedDamage

            NewCurrentHP = CurrentHP - DamageRemaining
            if not Overflow:
                NewCurrentHP = max(0, NewCurrentHP)

        else:
            NewCurrentHP = CurrentHP + AmountDelta
            if not Overflow:
                NewCurrentHP = min(MaxHP, NewCurrentHP)

        HitPointsData["CurrentHitPoints"]   = NewCurrentHP
        HitPointsData["TemporaryHitPoints"] = TempHP
        return NewCurrentHP

    def set_temp_hp(self, AmountValue: int) -> int:
        HitPointsData: dict[str, Typing.Any] = self.DetailData.setdefault("HitPoints", {})
        HitPointsData["TemporaryHitPoints"] = max(0, AmountValue)
        return HitPointsData["TemporaryHitPoints"]

    def use_slot(self, SlotLevel: int) -> bool:
        Spellcasting: dict[str, Typing.Any] = self.DetailData.get("Spellcasting", {})
        SpellSlots  : list[dict]            = Spellcasting.get("SpellSlots", [])

        for SlotEntry in SpellSlots:
            if (int(SlotEntry.get("Level", 0)) == SlotLevel):
                TotalSlots: int = int(SlotEntry.get("TotalSlots", 0))
                UsedSlots : int = int(SlotEntry.get("UsedSlots", 0))
                if (UsedSlots < TotalSlots):
                    SlotEntry["UsedSlots"]      = UsedSlots + 1
                    SlotEntry["AvailableSlots"] = TotalSlots - (UsedSlots + 1)
                    return True

                return False

        return False

    def get_slots(self, SlotLevel: int) -> int:
        Spellcasting: dict[str, Typing.Any] = self.DetailData.get("Spellcasting", {})
        SpellSlots  : list[dict]            = Spellcasting.get("SpellSlots", [])

        for SlotEntry in SpellSlots:
            if (int(SlotEntry.get("Level", 0)) == SlotLevel):
                return int(SlotEntry.get("AvailableSlots", 0))

        return 0

    def get_max_slots(self, SlotLevel: int) -> int:
        Spellcasting: dict[str, Typing.Any] = self.DetailData.get("Spellcasting", {})
        SpellSlots  : list[dict]            = Spellcasting.get("SpellSlots", [])

        for SlotEntry in SpellSlots:
            if (int(SlotEntry.get("Level", 0)) == SlotLevel):
                return int(SlotEntry.get("TotalSlots", 0))

        return 0

    def set_slots(self, SlotLevel: int, AvailableCount: int) -> int:
        Spellcasting: dict[str, Typing.Any] = self.DetailData.setdefault("Spellcasting", {})
        SpellSlots  : list[dict]            = Spellcasting.setdefault("SpellSlots", [])

        for SlotEntry in SpellSlots:
            if (int(SlotEntry.get("Level", 0)) == SlotLevel):
                TotalSlots: int = int(SlotEntry.get("TotalSlots", 0))
                SafeCount : int = max(0, min(TotalSlots, AvailableCount))
                SlotEntry["AvailableSlots"] = SafeCount
                SlotEntry["UsedSlots"]      = TotalSlots - SafeCount
                return SafeCount

        return 0

    def reset_slots(self) -> None:
        Spellcasting: dict[str, Typing.Any] = self.DetailData.get("Spellcasting", {})
        for SlotEntry in Spellcasting.get("SpellSlots", []):
            TotalSlots: int = int(SlotEntry.get("TotalSlots", 0))
            SlotEntry["UsedSlots"]      = 0
            SlotEntry["AvailableSlots"] = TotalSlots

    def create_cc(self, Name: str, MinValue: Typing.Optional[int] = 0, MaxValue: Typing.Optional[int] = None, ResetTo: Typing.Optional[int] = None, ResetOn: str = "LongRest", Description: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        return self.CounterManager.CreateCounter(Name, MinValue, MaxValue, ResetTo, ResetOn, Description)

    def delete_cc(self, Name: str) -> bool:
        return self.CounterManager.DeleteCounter(Name)

    def get_cc(self, Name: str) -> int:
        return self.CounterManager.GetCounter(Name)

    def get_cc_max(self, Name: str) -> Typing.Optional[int]:
        return self.CounterManager.GetCounterMax(Name)

    def get_cc_min(self, Name: str) -> Typing.Optional[int]:
        return self.CounterManager.GetCounterMin(Name)

    def mod_cc(self, Name: str, DeltaValue: int, StrictMode: bool = False) -> int:
        return self.CounterManager.ModifyCounter(Name, DeltaValue, StrictMode)

    def set_cc(self, Name: str, Value: int, StrictMode: bool = False) -> int:
        return self.CounterManager.SetCounter(Name, Value, StrictMode)

    def reset_cc(self, Name: str) -> int:
        return self.CounterManager.ResetCounter(Name)

    def cc_exists(self, Name: str) -> bool:
        return self.CounterManager.CounterExists(Name)

    def get_cvar(self, Name: str, DefaultValue: Typing.Any = None) -> Typing.Any:
        return self.CounterManager.GetVariable(Name, DefaultValue)

    def set_cvar(self, Name: str, Value: Typing.Any) -> None:
        self.CounterManager.SetVariable(Name, Value)

    def delete_cvar(self, Name: str) -> bool:
        return self.CounterManager.DeleteVariable(Name)

