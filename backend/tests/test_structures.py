"""Tests for the structure system."""


from app.simulation.structures import (
    Structure,
    StructureManager,
    STRUCTURE_COSTS,
    STRUCTURE_DEFINITIONS,
)


class TestStructureDataclass:
    def test_structure_creation(self):
        """Structure is created with correct default fields."""
        s = Structure(
            id="s1",
            structure_type="workbench",
            position=(5, 5),
            owner_id="agent_001",
        )
        assert s.id == "s1"
        assert s.structure_type == "workbench"
        assert s.position == (5, 5)
        assert s.owner_id == "agent_001"
        assert s.health == 100.0
        assert s.max_health == 100.0
        assert isinstance(s.properties, dict)

    def test_structure_defaults_no_owner(self):
        """Structure can be created without an owner."""
        s = Structure(id="s2", structure_type="wall", position=(0, 0))
        assert s.owner_id is None
        assert s.health == 100.0


class TestStructureDefinitions:
    def test_structure_costs_exist(self):
        """STRUCTURE_COSTS contains all expected structure types."""
        expected = {
            "workbench", "storage_hut", "house", "forge", "wall", "farm"
        }
        assert expected.issubset(set(STRUCTURE_COSTS.keys()))

    def test_workbench_cost(self):
        """workbench costs wood and stone."""
        assert STRUCTURE_COSTS["workbench"] == {"wood": 10, "stone": 5}

    def test_house_cost(self):
        """house costs wood, stone, and fiber."""
        assert STRUCTURE_COSTS["house"] == {"wood": 15, "stone": 8, "fiber": 5}

    def test_wall_cost(self):
        """wall costs wood and stone, is not passable."""
        assert STRUCTURE_COSTS["wall"] == {"wood": 5, "stone": 10}
        assert STRUCTURE_DEFINITIONS["wall"]["passable"] is False

    def test_farm_cost(self):
        """farm costs wood and fiber, is passable."""
        assert STRUCTURE_COSTS["farm"] == {"wood": 5, "fiber": 3}
        assert STRUCTURE_DEFINITIONS["farm"]["passable"] is True

    def test_structure_health_definitions(self):
        """Each structure has defined health in definitions."""
        assert STRUCTURE_DEFINITIONS["workbench"]["health"] == 50
        assert STRUCTURE_DEFINITIONS["storage_hut"]["health"] == 80
        assert STRUCTURE_DEFINITIONS["house"]["health"] == 200
        assert STRUCTURE_DEFINITIONS["forge"]["health"] == 100
        assert STRUCTURE_DEFINITIONS["wall"]["health"] == 300
        assert STRUCTURE_DEFINITIONS["farm"]["health"] == 30


class TestStructureManager:
    def test_add_and_get_structure(self):
        """Adding a structure makes it retrievable by ID."""
        mgr = StructureManager()
        s = Structure(id="s1", structure_type="workbench", position=(1, 2))
        mgr.add_structure(s)
        assert mgr.get_structure("s1") == s

    def test_get_structure_missing(self):
        """Getting a non-existent structure returns None."""
        mgr = StructureManager()
        assert mgr.get_structure("missing") is None

    def test_remove_structure(self):
        """Removing a structure deletes it from the manager."""
        mgr = StructureManager()
        s = Structure(id="s1", structure_type="workbench", position=(1, 2))
        mgr.add_structure(s)
        mgr.remove_structure("s1")
        assert mgr.get_structure("s1") is None

    def test_list_all(self):
        """list_all returns all added structures."""
        mgr = StructureManager()
        s1 = Structure(id="s1", structure_type="workbench", position=(1, 2))
        s2 = Structure(id="s2", structure_type="farm", position=(3, 4))
        mgr.add_structure(s1)
        mgr.add_structure(s2)
        all_structs = mgr.list_all()
        assert len(all_structs) == 2
        assert s1 in all_structs
        assert s2 in all_structs

    def test_get_structures_by_owner(self):
        """Filtering by owner returns only matching structures."""
        mgr = StructureManager()
        s1 = Structure(id="s1", structure_type="workbench", position=(1, 2), owner_id="a1")
        s2 = Structure(id="s2", structure_type="farm", position=(3, 4), owner_id="a1")
        s3 = Structure(id="s3", structure_type="wall", position=(5, 6), owner_id="a2")
        mgr.add_structure(s1)
        mgr.add_structure(s2)
        mgr.add_structure(s3)
        a1_structs = mgr.get_structures_by_owner("a1")
        assert len(a1_structs) == 2
        assert s1 in a1_structs
        assert s2 in a1_structs
        assert s3 not in a1_structs

    def test_get_structure_at_position(self):
        """Getting structure at a position returns the one there."""
        mgr = StructureManager()
        s = Structure(id="s1", structure_type="house", position=(2, 3))
        mgr.add_structure(s)
        assert mgr.get_structure_at((2, 3)) == s
        assert mgr.get_structure_at((9, 9)) is None

    def test_get_nearby_structures(self):
        """get_nearby_structures returns structures within radius."""
        mgr = StructureManager()
        s1 = Structure(id="s1", structure_type="workbench", position=(5, 5))
        s2 = Structure(id="s2", structure_type="farm", position=(7, 7))
        s3 = Structure(id="s3", structure_type="wall", position=(20, 20))
        mgr.add_structure(s1)
        mgr.add_structure(s2)
        mgr.add_structure(s3)
        nearby = mgr.get_nearby_structures((5, 5), radius=3)
        assert s1 in nearby
        assert s2 in nearby  # Chebyshev distance from (5,5) to (7,7) is 2, within 3
        assert s3 not in nearby
        nearby_1 = mgr.get_nearby_structures((5, 5), radius=1)
        assert s1 in nearby_1
        assert s2 not in nearby_1  # Chebyshev distance 2 > 1
        assert s3 not in nearby_1

    def test_get_nearby_structures_radius_3_includes_s2(self):
        """Structure at (7,7) is within radius 3 of (5,5)."""
        mgr = StructureManager()
        s1 = Structure(id="s1", structure_type="workbench", position=(5, 5))
        s2 = Structure(id="s2", structure_type="farm", position=(7, 7))
        mgr.add_structure(s1)
        mgr.add_structure(s2)
        nearby = mgr.get_nearby_structures((5, 5), radius=3)
        assert s1 in nearby
        assert s2 in nearby

    def test_add_structure_overwrites_at_same_position(self):
        """Adding a structure at an occupied position replaces the old one."""
        mgr = StructureManager()
        s1 = Structure(id="s1", structure_type="workbench", position=(1, 1))
        s2 = Structure(id="s2", structure_type="farm", position=(1, 1))
        mgr.add_structure(s1)
        mgr.add_structure(s2)
        assert mgr.get_structure_at((1, 1)) == s2
        assert mgr.get_structure("s1") is None

    def test_remove_structure_by_id_not_position(self):
        """Removing by ID leaves other structures intact."""
        mgr = StructureManager()
        s1 = Structure(id="s1", structure_type="workbench", position=(1, 1))
        s2 = Structure(id="s2", structure_type="farm", position=(2, 2))
        mgr.add_structure(s1)
        mgr.add_structure(s2)
        mgr.remove_structure("s1")
        assert mgr.get_structure("s2") == s2
        assert mgr.get_structure_at((2, 2)) == s2
