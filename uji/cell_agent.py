"""
cell_agent.py — Cell Agent (autonomous computational core)

Each cell is an independent agent that:
  1. Knows its own position (row, col) and its 4-neighbors
  2. Holds a lock (bool) for the handshake protocol
  3. Can host at most one robot and/or one pod
  4. Maintains a local cost table V (LRTA*-inspired)

LRTA*-inspired navigation:
  - Each cell maintains V[target] = estimated cost to reach target.
  - Initially V = Manhattan distance from cell to target.
  - Blocked cells (locked, or pod collision) are treated as V = INF.
  - When robot enters Cell_A, Cell_A reads neighbors' V values and
    assigns higher transition probability to neighbors with lower V.
  - When robot departs Cell_A, Cell_A updates:
        V_self = max(V_self, min(V_neighbors) + 1)
    This prevents revisiting dead-ends by raising the cost of explored cells.

Handshake protocol:
  1. Source cell selects a direction via V-weighted random
  2. Source checks destination cell's lock
  3. If destination is unlocked → acquire lock, transfer robot, release source lock
  4. If destination is locked → action fails, robot stays
"""

from __future__ import annotations
import math
import random
from typing import Optional, TYPE_CHECKING

from robot_state import (
    RobotEntity, RobotState, Action, ACTION_DELTAS,
)

if TYPE_CHECKING:
    from config import PodConfig

V_INF: float = 1e9  # cost for blocked cells


class CellAgent:
    """Autonomous cell agent — the computational core of the distributed sim."""

    __slots__ = (
        'row', 'col', 'locked', 'robot', 'pod',
        '_neighbors', 'is_station', 'station_id',
        '_v_cost',
    )

    def __init__(self, row: int, col: int) -> None:
        self.row = row
        self.col = col
        self.locked: bool = False          # handshake lock
        self.robot: Optional[RobotEntity] = None
        self.pod: Optional[PodConfig] = None
        self._neighbors: dict[Action, "CellAgent"] = {}  # set by GridWorld
        self.is_station: bool = False
        self.station_id: int = -1
        # LRTA* local cost table: target (row, col) → V value
        self._v_cost: dict[tuple[int, int], float] = {}

    # ------------------------------------------------------------------
    # Neighbor management (set once by GridWorld)
    # ------------------------------------------------------------------
    def set_neighbor(self, action: Action, cell: "CellAgent") -> None:
        self._neighbors[action] = cell

    def get_neighbor(self, action: Action) -> Optional["CellAgent"]:
        return self._neighbors.get(action)

    # ------------------------------------------------------------------
    # LRTA* cost helpers
    # ------------------------------------------------------------------
    def _get_v(self, target: tuple[int, int]) -> float:
        """Get V value for a target, initializing to Manhattan distance if unseen."""
        if target not in self._v_cost:
            self._v_cost[target] = (abs(self.row - target[0])
                                    + abs(self.col - target[1]))
        return self._v_cost[target]

    def _get_neighbor_v(self, nb: "CellAgent", target: tuple[int, int],
                        robot: RobotEntity) -> float:
        """Get effective V of a neighbor, returning INF if blocked for this robot."""
        if nb.locked or nb.robot is not None:
            return V_INF
        if robot.carrying_pod and nb.pod is not None:
            return V_INF
        return nb._get_v(target)

    def _lrta_update(self, target: tuple[int, int], robot: RobotEntity) -> None:
        """LRTA* departure update: V_self = min(V_neighbors) + 1.

        Unlike classic LRTA* which uses max(V_self, ...) to guarantee
        monotonicity, we allow V to decrease because this is a dynamic
        environment — obstacles (robots, pods) appear and disappear,
        so inflated V from past blockages must be correctable.
        """
        min_nb_v = V_INF
        for nb in self._neighbors.values():
            v = self._get_neighbor_v(nb, target, robot)
            if v < min_nb_v:
                min_nb_v = v
        if min_nb_v < V_INF:
            self._v_cost[target] = min_nb_v + 1

    # ------------------------------------------------------------------
    # Action selection — LRTA*-based probability weighting
    # ------------------------------------------------------------------
    def select_action(self,
                      move_weight: float = 0.22,
                      stay_weight: float = 0.12,
                      enable_lrta: bool = True) -> Action:
        """Select an action for the robot hosted on this cell.

        Uses LRTA* V-costs: neighbors with lower V get higher probability.
        Only passable directions are considered.
        """
        robot = self.robot
        if robot is None:
            return Action.STAY

        # Build passable candidate actions with their V costs
        passable: list[tuple[Action, float]] = []  # (action, V_cost)
        for act in [Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT]:
            nb = self._neighbors.get(act)
            if nb is None:
                continue
            if nb.locked or nb.robot is not None:
                continue
            if robot.carrying_pod and nb.pod is not None:
                continue
            passable.append((act, nb._get_v(robot.target_pos) if robot.has_target else 0.0))

        if not passable:
            return Action.STAY  # no passable direction

        # --- If robot has no target: uniform random walk (encourage movement) ---
        if not robot.has_target:
            candidates = [act for act, _ in passable]
            candidates.append(Action.STAY)
            weights = [move_weight] * len(passable) + [stay_weight]
            return random.choices(candidates, weights=weights, k=1)[0]

        # --- V-cost weighted selection ---
        target = robot.target_pos

        # Convert V costs to weights: lower V → higher weight
        # Boltzmann-style: w = exp(-V / T)
        temperature = 1.0
        actions: list[Action] = []
        weights: list[float] = []
        best_v = float('inf')
        best_act: Action = Action.STAY
        for act, v_raw in passable:
            # When LRTA* is disabled, use fresh Manhattan distance
            v = v_raw if enable_lrta else (abs(self._neighbors[act].row - target[0])
                                           + abs(self._neighbors[act].col - target[1]))
            actions.append(act)
            weights.append(math.exp(-v / temperature))
            if v < best_v:
                best_v = v
                best_act = act

        # Epsilon-greedy: 85% pick best direction, 15% sample from Boltzmann
        if random.random() < 0.85:
            return best_act

        # STAY gets very low weight when we have a target
        actions.append(Action.STAY)
        weights.append(1e-6)

        return random.choices(actions, weights=weights, k=1)[0]

    # ------------------------------------------------------------------
    # Handshake protocol
    # ------------------------------------------------------------------
    def attempt_transfer(self,
                         action: Action,
                         move_weight: float = 0.22,
                         stay_weight: float = 0.12,
                         enable_lrta: bool = True) -> bool:
        """Attempt to transfer the hosted robot in the given direction.

        Returns True if transfer succeeded, False otherwise.
        On successful transfer, performs LRTA* V-update on source cell.

        Protocol:
          1. If action is STAY → no transfer needed, return True
          2. Get destination cell
          3. Check destination lock
          4. If unlocked → lock destination, transfer robot, unlock source
          5. If locked → fail
        """
        if action == Action.STAY:
            return True  # staying is always "successful"

        robot = self.robot
        if robot is None:
            return False

        dest = self.get_neighbor(action)
        if dest is None:
            return False  # no neighbor in that direction

        # Handshake: check destination lock
        if dest.locked:
            return False  # destination is locked by another transfer

        if dest.robot is not None:
            return False  # destination already has a robot

        # Pod collision: robot carrying a pod cannot enter a cell with a pod
        if robot.carrying_pod and dest.pod is not None:
            return False

        # Acquire destination lock
        dest.locked = True

        # Capture target before transfer for LRTA* update
        has_target = robot.has_target
        target = robot.target_pos if has_target else None

        # Transfer robot
        dest.robot = robot
        robot.row = dest.row
        robot.col = dest.col

        # Release source
        self.robot = None
        self.locked = False

        # Release destination lock
        dest.locked = False

        # LRTA* departure update on source cell (only when enabled)
        if enable_lrta and has_target and target is not None:
            self._lrta_update(target, robot)

        return True

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def cell_id(self) -> tuple[int, int]:
        return (self.row, self.col)

    @property
    def has_robot(self) -> bool:
        return self.robot is not None

    @property
    def has_pod(self) -> bool:
        return self.pod is not None

    def __repr__(self) -> str:
        parts = [f"Cell({self.row},{self.col})"]
        if self.locked:
            parts.append("LOCKED")
        if self.robot:
            parts.append(f"R{self.robot.robot_id}")
        if self.pod:
            parts.append(f"Pod(sku={self.pod.sku})")
        if self.is_station:
            parts.append(f"Station#{self.station_id}")
        return " ".join(parts)
