"""
simulator.py — Distributed Simulation Orchestrator

Each tick:
  1. Collect all cells hosting robots, shuffle for fairness
  2. Each cell performs action selection + handshake transfer
  3. Process state transitions (timers, arrival detection, pod pickup)
  4. Check termination (all orders fulfilled, all robots FINISH)

There is no centralized pathfinding. All movement decisions are made
locally by individual cell agents via probability-weighted random walks.
"""

from __future__ import annotations
import random
from typing import Optional

from config import SimConfig, PodConfig, StationConfig
from grid_world import GridWorld
from cell_agent import CellAgent
from robot_state import RobotEntity, RobotState, Action

# Terminal output toggle
PRINT_SCREEN: bool = True


class DistributedSimulator:
    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self.grid = GridWorld(config.rows, config.cols)
        self.robots: list[RobotEntity] = []
        self.tick_count: int = 0
        self._stations: dict[int, StationConfig] = {}
        self._order_fulfilled: list[bool] = []
        # Track pod origins for return navigation
        self._pod_origins: set[tuple[int, int]] = set()
        self._occupied_pod_slots: set[tuple[int, int]] = set()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def setup(self) -> None:
        """Initialize grid with stations, pods, and robots from config."""
        cfg = self.config

        # Register stations
        for st in cfg.stations:
            cell = self.grid[st.row, st.col]
            cell.is_station = True
            cell.station_id = st.tar_id
            self._stations[st.tar_id] = st

        # Place pods
        for idx, pod in enumerate(cfg.pods):
            cell = self.grid[pod.row, pod.col]
            cell.pod = pod
            self._pod_origins.add((pod.row, pod.col))
            self._occupied_pod_slots.add((pod.row, pod.col))
            self._order_fulfilled.append(False)

        # Place robots
        for rid, (r, c) in enumerate(cfg.robot_starts):
            robot = RobotEntity(robot_id=rid, row=r, col=c)
            self.robots.append(robot)
            cell = self.grid[r, c]
            cell.robot = robot
            cell.locked = False

        if PRINT_SCREEN:
            print(f"[Sim] Initialized: {cfg.rows}x{cfg.cols} grid, "
                  f"{len(self.robots)} robots, {len(cfg.pods)} pods, "
                  f"{len(cfg.stations)} stations")

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------
    def tick(self) -> bool:
        """Execute one simulation tick. Returns True if simulation is still running."""
        self.tick_count += 1

        # Phase 0: Process timers for timed states
        self._process_timers()

        # Phase 0.5: Dispatch IDLE robots toward nearest unfulfilled pod
        self._dispatch_idle_robots()

        # Phase 1: Arrival and pod pickup detection
        self._detect_arrivals()

        # Phase 2: Movement — each cell with a robot selects action + handshake
        active_cells = self.grid.cells_with_robots()
        random.shuffle(active_cells)  # fairness

        for cell in active_cells:
            robot = cell.robot
            if robot is None:
                continue
            # Skip robots in timed states (FETCH_POD, WAIT_AT_STATION)
            if robot.state in (RobotState.FETCH_POD, RobotState.WAIT_AT_STATION):
                continue
            if robot.state == RobotState.FINISH:
                continue

            # Action selection by cell agent
            action = cell.select_action(
                move_weight=self.config.move_weight,
                stay_weight=self.config.stay_weight,
                enable_lrta=self.config.enable_lrta_update,
            )

            # Handshake transfer
            cell.attempt_transfer(
                action,
                move_weight=self.config.move_weight,
                stay_weight=self.config.stay_weight,
                enable_lrta=self.config.enable_lrta_update,
            )

        # Phase 3: Print status
        if PRINT_SCREEN:
            parts = " | ".join(
                f"R{r.robot_id}@({r.row},{r.col}) {r.state.name[:4]}"
                for r in self.robots
            )
            print(f"  Tick {self.tick_count:>3} | {parts}")

        # Check termination
        return self._is_running()

    # ------------------------------------------------------------------
    # Timer processing
    # ------------------------------------------------------------------
    def _process_timers(self) -> None:
        """Decrement timers for robots in timed states and transition when done."""
        for robot in self.robots:
            if robot.wait_timer > 0:
                robot.wait_timer -= 1
                if robot.wait_timer <= 0:
                    self._on_timer_done(robot)

    def _dispatch_idle_robots(self) -> None:
        """Assign nearest unfulfilled pod as target for IDLE robots.

        Also clears stale targets (pod already picked up by another robot).
        """
        # Collect unfulfilled pod positions (only pods still on the grid)
        avail_pod_positions: set[tuple[int, int]] = set()
        assigned_pods: set[int] = set()
        for r in self.robots:
            if r.assigned_order_idx >= 0:
                assigned_pods.add(r.assigned_order_idx)

        avail_pods: list[tuple[int, int, int]] = []  # (row, col, order_idx)
        for idx, pod in enumerate(self.config.pods):
            if not self._order_fulfilled[idx] and idx not in assigned_pods:
                cell = self.grid[pod.row, pod.col]
                if cell.pod is not None:
                    avail_pods.append((pod.row, pod.col, idx))
                    avail_pod_positions.add((pod.row, pod.col))

        for robot in self.robots:
            if robot.state != RobotState.IDLE:
                continue

            # Clear stale target if the pod at that position is gone
            if robot.has_target:
                tgt = (robot.target_row, robot.target_col)
                if tgt not in avail_pod_positions:
                    robot.clear_target()

            # (Re-)assign nearest available pod
            if not robot.has_target and avail_pods:
                best_dist = float('inf')
                best_pos = None
                for pr, pc, _ in avail_pods:
                    dist = abs(robot.row - pr) + abs(robot.col - pc)
                    if dist < best_dist:
                        best_dist = dist
                        best_pos = (pr, pc)
                if best_pos is not None:
                    robot.target_row, robot.target_col = best_pos

    def _on_timer_done(self, robot: RobotEntity) -> None:
        """Handle state transition when a timer expires."""
        if robot.state == RobotState.FETCH_POD:
            # Pod picked up — start delivering
            robot.state = RobotState.DELIVER
            if PRINT_SCREEN:
                print(f"[Sim]  Robot#{robot.robot_id} pod pickup complete → DELIVER "
                      f"target=({robot.target_row},{robot.target_col})  tick={self.tick_count}")

        elif robot.state == RobotState.WAIT_AT_STATION:
            # Station processing done — return pod
            robot.state = RobotState.RETURN_POD
            # Target nearest free pod slot (not necessarily the original)
            self._retarget_return_robot(robot)
            if PRINT_SCREEN:
                print(f"[Sim]  Robot#{robot.robot_id} → RETURN_POD  tick={self.tick_count}")

    def _retarget_return_robot(self, robot: RobotEntity) -> None:
        """Set target to nearest free pod origin slot for RETURN_POD robot."""
        free_slots = self._pod_origins - self._occupied_pod_slots
        if not free_slots:
            # Fallback to original if everything is occupied
            if robot.pod_origin is not None:
                robot.target_row, robot.target_col = robot.pod_origin
            return
        best_dist = float('inf')
        best_pos = None
        for pr, pc in free_slots:
            dist = abs(robot.row - pr) + abs(robot.col - pc)
            if dist < best_dist:
                best_dist = dist
                best_pos = (pr, pc)
        if best_pos is not None:
            robot.target_row, robot.target_col = best_pos

    # ------------------------------------------------------------------
    # Arrival and pod interaction
    # ------------------------------------------------------------------
    def _detect_arrivals(self) -> None:
        """Check robots for state transitions based on their current cell."""
        for robot in self.robots:
            cell = self.grid[robot.row, robot.col]

            if robot.state == RobotState.IDLE:
                # Check if there's an unassigned pod on this cell
                if cell.pod is not None:
                    self._pickup_pod(robot, cell)

            elif robot.state == RobotState.DELIVER:
                # Check if robot reached its target station
                if cell.is_station and cell.station_id == self._get_target_station_id(robot):
                    if robot.row == robot.target_row and robot.col == robot.target_col:
                        robot.state = RobotState.WAIT_AT_STATION
                        robot.wait_timer = self.config.wait_at_station_ticks
                        robot.clear_target()
                        if PRINT_SCREEN:
                            print(f"[Sim]  Robot#{robot.robot_id} delivered → "
                                  f"WAIT({self.config.wait_at_station_ticks}s)  tick={self.tick_count}")

            elif robot.state == RobotState.RETURN_POD:
                pos = (robot.row, robot.col)
                # Accept any free pod origin cell (not just the original)
                if pos in self._pod_origins and pos not in self._occupied_pod_slots:
                    self._return_pod(robot, cell)
                else:
                    # Dynamically retarget to nearest free slot each tick
                    self._retarget_return_robot(robot)

    def _pickup_pod(self, robot: RobotEntity, cell: CellAgent) -> None:
        """Robot picks up a pod — enter FETCH_POD timed state."""
        pod = cell.pod
        if pod is None:
            return

        # Find the order index for this pod
        order_idx = -1
        for idx, p in enumerate(self.config.pods):
            if p.row == pod.row and p.col == pod.col and not self._order_fulfilled[idx]:
                order_idx = idx
                break

        if order_idx < 0:
            return  # no unfulfilled order for this pod

        # Get target station
        st = self._stations.get(pod.target_station_id)
        if st is None:
            return

        robot.state = RobotState.FETCH_POD
        robot.wait_timer = self.config.fetch_pod_ticks
        robot.carrying_pod = True
        robot.pod_origin = (pod.row, pod.col)
        robot.pod_sku = pod.sku
        robot.target_row = st.row
        robot.target_col = st.col
        robot.assigned_order_idx = order_idx

        # Remove pod from cell
        cell.pod = None
        self._occupied_pod_slots.discard((pod.row, pod.col))

        if PRINT_SCREEN:
            print(f"[Sim]  Robot#{robot.robot_id} lifting pod@({pod.row},{pod.col}) "
                  f"sku={pod.sku} → station#{pod.target_station_id}  tick={self.tick_count}")

    def _return_pod(self, robot: RobotEntity, cell: CellAgent) -> None:
        """Robot returns pod to a free pod origin cell."""
        pos = (robot.row, robot.col)

        # Reconstruct a PodConfig for the returned pod
        pod_cfg = PodConfig(
            row=pos[0], col=pos[1],
            sku=robot.pod_sku,
            target_station_id=0,  # fulfilled
        )
        cell.pod = pod_cfg
        self._occupied_pod_slots.add(pos)

        # Mark order fulfilled
        if robot.assigned_order_idx >= 0:
            self._order_fulfilled[robot.assigned_order_idx] = True

        origin = robot.pod_origin
        robot.carrying_pod = False
        robot.pod_origin = None
        robot.pod_sku = 0
        robot.clear_target()
        robot.state = RobotState.FINISH
        robot.assigned_order_idx = -1

        if PRINT_SCREEN:
            print(f"[Sim]  Robot#{robot.robot_id} returned pod @({pos[0]},{pos[1]}) "
                  f"→ FINISH  tick={self.tick_count}")

    def _get_target_station_id(self, robot: RobotEntity) -> int:
        """Get the station ID the robot is currently targeting."""
        if robot.assigned_order_idx >= 0:
            return self.config.pods[robot.assigned_order_idx].target_station_id
        return -1

    # ------------------------------------------------------------------
    # Running check
    # ------------------------------------------------------------------
    def _is_running(self) -> bool:
        """True if simulation should continue."""
        # Check if any robot is still working
        for robot in self.robots:
            if robot.state not in (RobotState.FINISH, RobotState.IDLE):
                return True
        # Check if any IDLE robot could still pick up a pod
        for robot in self.robots:
            if robot.state == RobotState.IDLE:
                # Check if there are unfulfilled orders
                if any(not f for f in self._order_fulfilled):
                    return True
        return False

    # ------------------------------------------------------------------
    # High-level run
    # ------------------------------------------------------------------
    def run(self, max_ticks: int | None = None, callback=None) -> None:
        """Run simulation to completion or max ticks."""
        if max_ticks is None:
            max_ticks = self.config.max_ticks

        for _ in range(max_ticks):
            running = self.tick()
            if callback:
                callback(self)
            if not running:
                print(f"\n[Sim] All done in {self.tick_count} ticks.")
                return
        print(f"\n[Sim] Reached max ticks ({max_ticks}).")
