"""
robot_state.py — Robot State Machine

State transitions:
  IDLE → FETCH_POD (2s) → DELIVER → WAIT_AT_STATION (5s) → RETURN_POD (2s) → FINISH

Each robot entity is a lightweight data holder. All decision-making
is done by the CellAgent that currently hosts the robot.
"""

from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


class RobotState(Enum):
    IDLE            = auto()
    FETCH_POD       = auto()   # Picking up pod (timed)
    DELIVER         = auto()   # Moving toward station
    WAIT_AT_STATION = auto()   # Processing at station (timed)
    RETURN_POD      = auto()   # Returning pod to origin (timed then moving)
    FINISH          = auto()   # Task complete


class Action(Enum):
    STAY  = 0
    UP    = 1   # row - 1
    DOWN  = 2   # row + 1
    LEFT  = 3   # col - 1
    RIGHT = 4   # col + 1


# Direction deltas: (d_row, d_col)
ACTION_DELTAS: dict[Action, tuple[int, int]] = {
    Action.STAY:  ( 0,  0),
    Action.UP:    (-1,  0),
    Action.DOWN:  ( 1,  0),
    Action.LEFT:  ( 0, -1),
    Action.RIGHT: ( 0,  1),
}


@dataclass
class RobotEntity:
    """Lightweight robot data — all logic is in CellAgent / Simulator."""
    robot_id: int
    row: int
    col: int
    state: RobotState = RobotState.IDLE
    # Target workstation coordinates (set during DELIVER)
    target_row: int = -1
    target_col: int = -1
    # Pod info
    carrying_pod: bool = False
    pod_origin: Optional[tuple[int, int]] = None
    pod_sku: int = 0
    # Timer (ticks remaining for timed states)
    wait_timer: int = 0
    # Order tracking
    assigned_order_idx: int = -1

    @property
    def pos(self) -> tuple[int, int]:
        return (self.row, self.col)

    @property
    def has_target(self) -> bool:
        return self.target_row >= 0 and self.target_col >= 0

    @property
    def target_pos(self) -> tuple[int, int]:
        return (self.target_row, self.target_col)

    def clear_target(self) -> None:
        self.target_row = -1
        self.target_col = -1

    def __repr__(self) -> str:
        return (f"Robot#{self.robot_id} @({self.row},{self.col}) "
                f"state={self.state.name} target=({self.target_row},{self.target_col}) "
                f"carry={self.carrying_pod} wait={self.wait_timer}")
