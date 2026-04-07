"""
config.py — Configuration for Distributed Cell-Agent Simulation

Loads map configuration from JSON or provides inline defaults.
Generates orders: each pod gets one SKU and a target station.
"""

from __future__ import annotations
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class StationConfig:
    tar_id: int
    row: int
    col: int


@dataclass
class PodConfig:
    row: int
    col: int
    sku: int
    target_station_id: int


@dataclass
class SimConfig:
    rows: int
    cols: int
    stations: list[StationConfig]
    pods: list[PodConfig]
    robot_starts: list[tuple[int, int]]
    # Timing (in ticks)
    fetch_pod_ticks: int = 2
    wait_at_station_ticks: int = 5
    return_pod_ticks: int = 2
    # Probability weights for action selection
    move_weight: float = 0.22        # per-direction (UP/DOWN/LEFT/RIGHT)
    stay_weight: float = 0.08        # STAY action (low to encourage movement)
    # LRTA* update toggle
    enable_lrta_update: bool = False   # True = update V on departure; False = pure Manhattan heuristic
    # Visualization
    tick_interval: float = 0.5
    max_ticks: int = 1000


def default_config() -> SimConfig:
    """Default 10×10 grid with 4 stations, 10 pods, 10 robots."""
    stations = [
        StationConfig(tar_id=1, row=1, col=9),
        StationConfig(tar_id=2, row=1, col=0),
        StationConfig(tar_id=3, row=8, col=0),
        StationConfig(tar_id=4, row=8, col=9),
    ]
    pods = [
        PodConfig(row=2, col=2, sku=1, target_station_id=1),
        PodConfig(row=3, col=2, sku=2, target_station_id=2),
        PodConfig(row=4, col=2, sku=3, target_station_id=3),
        PodConfig(row=5, col=2, sku=4, target_station_id=4),
        PodConfig(row=6, col=2, sku=1, target_station_id=1),
        PodConfig(row=2, col=4, sku=2, target_station_id=2),
        PodConfig(row=3, col=4, sku=2, target_station_id=2),
        PodConfig(row=4, col=4, sku=4, target_station_id=4),
        PodConfig(row=5, col=4, sku=1, target_station_id=1),
        PodConfig(row=6, col=4, sku=2, target_station_id=2),
    ]
    robot_starts = [
        (0, 2), (0, 5), (0, 7),
        (9, 2), (9, 5), (9, 7),
        (5, 0), (5, 9),
        (1, 5), (8, 5),
    ]
    return SimConfig(
        rows=10, cols=10,
        stations=stations,
        pods=pods,
        robot_starts=robot_starts,
    )


def load_config(path: str | Path) -> SimConfig:
    """Load configuration from a JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)

    rows = cols = data["map_size"]
    stations = [
        StationConfig(tar_id=s["tar_id"], row=s["row"], col=s["col"])
        for s in data["stations"]
    ]

    # Build pods from pod_blocks (each cell in block = one pod)
    pods: list[PodConfig] = []
    station_ids = [s.tar_id for s in stations]
    for block in data.get("pod_blocks", []):
        for dr in range(block["num_rows"]):
            for dc in range(block["num_cols"]):
                r = block["origin_row"] + dr
                c = block["origin_col"] + dc
                # Assign random station and SKU
                tid = random.choice(station_ids)
                sku = random.randint(1, 4)
                pods.append(PodConfig(row=r, col=c, sku=sku,
                                      target_station_id=tid))

    # Robot starts: from config or auto-generate on perimeter
    robot_starts: list[tuple[int, int]] = []
    if "robot_starts" in data:
        robot_starts = [(r["row"], r["col"]) for r in data["robot_starts"]]
    else:
        # Auto-place on top and bottom rows
        n = data.get("num_robots", len(pods))
        for i in range(n):
            if i < cols:
                robot_starts.append((0, i % cols))
            else:
                robot_starts.append((rows - 1, i % cols))

    return SimConfig(
        rows=rows, cols=cols,
        stations=stations,
        pods=pods,
        robot_starts=robot_starts,
    )
