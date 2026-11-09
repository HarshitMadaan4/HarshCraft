
"""
HarshCraftAI - Shared Minecraft World State

Converts raw observations received from the HarshCraft Fabric
mod into a consistent Python representation.

This module is shared by all AI skills:
    - Navigation
    - Gathering
    - Mining
    - Combat
    - Survival

It does not send actions or control the Minecraft player.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# ============================================================
# BASIC DATA STRUCTURES
# ============================================================

@dataclass
class Position:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @classmethod
    def from_dict(cls, data: Optional[dict]):
        data = data or {}

        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            z=float(data.get("z", 0.0)),
        )

    def distance_to(self, other: "Position") -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z

        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def horizontal_distance_to(self, other: "Position") -> float:
        dx = self.x - other.x
        dz = self.z - other.z

        return (dx * dx + dz * dz) ** 0.5

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
        }


# ============================================================
# PLAYER STATE
# ============================================================

@dataclass
class PlayerState:
    position: Position = field(default_factory=Position)

    yaw: float = 0.0
    pitch: float = 0.0

    health: float = 20.0
    food: float = 20.0

    on_ground: bool = False
    horizontal_collision: bool = False

    @classmethod
    def from_dict(cls, data: Optional[dict]):
        data = data or {}

        return cls(
            position=Position.from_dict(data),

            yaw=float(data.get("yaw", 0.0)),
            pitch=float(data.get("pitch", 0.0)),

            health=float(data.get("health", 20.0)),
            food=float(data.get("food", 20.0)),

            on_ground=bool(data.get("onGround", False)),
            horizontal_collision=bool(
                data.get("horizontalCollision", False)
            ),
        )


# ============================================================
# BLOCK STATE
# ============================================================

@dataclass
class BlockState:
    position: Position = field(default_factory=Position)
    block_type: str = "unknown"

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            position=Position.from_dict(data),
            block_type=str(
                data.get("type", data.get("block", "unknown"))
            ),
        )


# ============================================================
# ENTITY STATE
# ============================================================

@dataclass
class EntityState:
    position: Position = field(default_factory=Position)
    entity_type: str = "unknown"

    health: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict):
        health = data.get("health")

        return cls(
            position=Position.from_dict(data),

            entity_type=str(
                data.get(
                    "type",
                    data.get("name", "unknown")
                )
            ),

            health=(
                float(health)
                if health is not None
                else None
            ),
        )


# ============================================================
# COMPLETE WORLD STATE
# ============================================================

@dataclass
class WorldState:

    player: PlayerState = field(default_factory=PlayerState)

    nearby_blocks: list[BlockState] = field(default_factory=list)
    nearby_entities: list[EntityState] = field(default_factory=list)

    target: Optional[dict] = None
    crosshair: Optional[dict] = None

    raw_observation: dict = field(default_factory=dict)

    # --------------------------------------------------------
    # CREATE WORLD STATE FROM MINECRAFT JSON
    # --------------------------------------------------------

    @classmethod
    def from_dict(cls, observation: dict):

        if not isinstance(observation, dict):
            raise TypeError(
                "Minecraft observation must be a dictionary."
            )

        player_data = observation.get("player")

        if not isinstance(player_data, dict):
            raise ValueError(
                "Minecraft observation does not contain valid player data."
            )

        blocks_data = observation.get("nearbyBlocks") or []
        entities_data = observation.get("nearbyEntities") or []

        if not isinstance(blocks_data, list):
            raise TypeError("nearbyBlocks must be a list.")

        if not isinstance(entities_data, list):
            raise TypeError("nearbyEntities must be a list.")

        blocks = [
            BlockState.from_dict(block)
            for block in blocks_data
            if isinstance(block, dict)
        ]

        entities = [
            EntityState.from_dict(entity)
            for entity in entities_data
            if isinstance(entity, dict)
        ]

        return cls(
            player=PlayerState.from_dict(player_data),

            nearby_blocks=blocks,
            nearby_entities=entities,

            target=observation.get("target"),
            crosshair=observation.get("crosshair"),

            raw_observation=observation.copy(),
        )

    # --------------------------------------------------------
    # PLAYER POSITION
    # --------------------------------------------------------

    @property
    def player_position(self) -> Position:
        return self.player.position

    # --------------------------------------------------------
    # DISTANCE TO POSITION
    # --------------------------------------------------------

    def distance_to(self, position: Position) -> float:
        return self.player_position.distance_to(position)

    # --------------------------------------------------------
    # FIND NEARBY BLOCKS BY TYPE
    # --------------------------------------------------------

    def find_blocks(self, block_type: str) -> list[BlockState]:

        search_type = block_type.lower()

        return [
            block
            for block in self.nearby_blocks
            if search_type in block.block_type.lower()
        ]

    # --------------------------------------------------------
    # FIND NEARBY ENTITIES BY TYPE
    # --------------------------------------------------------

    def find_entities(self, entity_type: str) -> list[EntityState]:

        search_type = entity_type.lower()

        return [
            entity
            for entity in self.nearby_entities
            if search_type in entity.entity_type.lower()
        ]

    # --------------------------------------------------------
    # NEAREST BLOCK
    # --------------------------------------------------------

    def nearest_block(
            self,
            block_type: Optional[str] = None
    ) -> Optional[BlockState]:

        candidates = self.nearby_blocks

        if block_type is not None:
            candidates = self.find_blocks(block_type)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda block: self.distance_to(block.position)
        )

    # --------------------------------------------------------
    # NEAREST ENTITY
    # --------------------------------------------------------

    def nearest_entity(
            self,
            entity_type: Optional[str] = None
    ) -> Optional[EntityState]:

        candidates = self.nearby_entities

        if entity_type is not None:
            candidates = self.find_entities(entity_type)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda entity: self.distance_to(entity.position)
        )

    # --------------------------------------------------------
    # PLAYER STATUS
    # --------------------------------------------------------

    @property
    def is_alive(self) -> bool:
        return self.player.health > 0.0

    @property
    def is_moving_into_collision(self) -> bool:
        return self.player.horizontal_collision

    # --------------------------------------------------------
    # DEBUG INFORMATION
    # --------------------------------------------------------

    def summary(self) -> dict:

        return {
            "player_position": self.player_position.to_dict(),

            "yaw": self.player.yaw,
            "pitch": self.player.pitch,

            "health": self.player.health,
            "food": self.player.food,

            "on_ground": self.player.on_ground,
            "horizontal_collision": (
                self.player.horizontal_collision
            ),

            "nearby_block_count": len(self.nearby_blocks),
            "nearby_entity_count": len(self.nearby_entities),
        }
