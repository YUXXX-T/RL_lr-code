"""
visualizer.py — Matplotlib Visualization for Distributed Cell-Agent Simulation

Dark-themed grid visualization with:
  - Cell grid with state coloring
  - Robot markers (color-coded by state)
  - Pod markers (triangles)
  - Station markers (stars)
  - Status bar with tick count and robot states
  - Real-time animation
"""

from __future__ import annotations
import time
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from robot_state import RobotState

if TYPE_CHECKING:
    from simulator import DistributedSimulator
    from config import SimConfig


# ── Color palette ──────────────────────────────────────────────────────
ROBOT_COLORS = [
    "#00ff88", "#ff6644", "#44aaff", "#ffcc00", "#cc44ff",
    "#ff4488", "#44ffdd", "#ff8800", "#aaffaa", "#8888ff",
    "#ff3333", "#33ff99", "#3399ff", "#ffff33", "#ff33cc",
    "#33ffff", "#cc9933", "#9933cc", "#33cc66", "#6633ff",
]

STATE_COLORS = {
    RobotState.IDLE:            "#888888",
    RobotState.FETCH_POD:       "#ffaa00",
    RobotState.DELIVER:         "#00ccff",
    RobotState.WAIT_AT_STATION: "#ff4488",
    RobotState.RETURN_POD:      "#aa44ff",
    RobotState.FINISH:          "#44ff44",
}

POD_COLOR     = "#88ddff"
STATION_COLOR = "#ff3333"
BG_COLOR      = "#1a1a2e"
CELL_BG       = "#0f0f1a"
GRID_COLOR    = "#334466"
LOCK_COLOR    = "#ff2222"


class Visualizer:
    def __init__(self, sim: "DistributedSimulator") -> None:
        self.sim = sim
        self.cfg = sim.config
        self.rows = self.cfg.rows
        self.cols = self.cfg.cols

    def run(self) -> None:
        """Run the visual simulation loop."""
        sim = self.sim
        cfg = self.cfg

        fig, ax = plt.subplots(1, 1, figsize=(10, 10))
        fig.patch.set_facecolor(BG_COLOR)
        ax.set_facecolor(CELL_BG)

        # Setup axes
        ax.set_xlim(-0.5, self.cols - 0.5)
        ax.set_ylim(-0.5, self.rows - 0.5)
        ax.set_aspect("equal")
        ax.tick_params(colors="gray", labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#333355")
        # Grid lines
        for x in np.arange(-0.5, self.cols, 1):
            ax.axvline(x, color=GRID_COLOR, lw=0.5, zorder=1)
        for y in np.arange(-0.5, self.rows, 1):
            ax.axhline(y, color=GRID_COLOR, lw=0.5, zorder=1)
        # Tick labels (row 0 at top)
        ax.set_xticks(range(self.cols))
        ax.set_xticklabels(range(self.cols), color="#aaaacc", fontsize=7)
        ax.xaxis.tick_top()
        ax.xaxis.set_label_position("top")
        ax.set_yticks(range(self.rows))
        ax.set_yticklabels(range(self.rows - 1, -1, -1), color="#aaaacc", fontsize=7)

        ax.set_title("Distributed Cell-Agent Simulation", color="white",
                      fontsize=13, pad=12, fontweight="bold")

        def gy(r: int) -> int:
            """Convert row to plot y (flip so row 0 is at top)."""
            return self.rows - 1 - r

        # ── Static markers: Stations ──
        for st in cfg.stations:
            ax.plot(st.col, gy(st.row), "r*", markersize=16, zorder=6,
                    markeredgecolor="white", markeredgewidth=0.5)
            ax.text(st.col, gy(st.row) + 0.38, f"S{st.tar_id}",
                    color="white", fontsize=7, fontweight="bold",
                    ha="center", va="bottom", zorder=7)

        # ── Dynamic markers ──
        # Pod markers
        pod_dots = []
        for idx, pod in enumerate(cfg.pods):
            d, = ax.plot(pod.col, gy(pod.row), "^", markersize=11, zorder=5,
                         color=POD_COLOR, markeredgecolor="white",
                         markeredgewidth=0.8)
            pod_dots.append((d, pod.row, pod.col))

        # Robot markers
        robot_dots = []
        for rid, (r, c) in enumerate(cfg.robot_starts):
            color = ROBOT_COLORS[rid % len(ROBOT_COLORS)]
            d, = ax.plot(c, gy(r), "o", markersize=13, zorder=8,
                         color=color, markeredgecolor="white",
                         markeredgewidth=1.2)
            robot_dots.append(d)

        # Robot ID labels
        robot_labels = []
        for rid, (r, c) in enumerate(cfg.robot_starts):
            txt = ax.text(c, gy(r), str(rid), color="black",
                          fontsize=6, fontweight="bold",
                          ha="center", va="center", zorder=9)
            robot_labels.append(txt)

        # Lock indicators (small red squares on locked cells)
        lock_scat = ax.scatter([], [], s=40, marker="s", color=LOCK_COLOR,
                               alpha=0.6, zorder=4, label="Locked")

        # Status text
        status_txt = fig.text(0.5, 0.01, "Initializing…",
                              ha="center", fontsize=9, color="white",
                              fontfamily="monospace")

        # Legend
        legend_patches = [
            mpatches.Patch(color=STATE_COLORS[s], label=s.name)
            for s in RobotState
        ]
        ax.legend(handles=legend_patches, loc="upper left", fontsize=6,
                  facecolor="#1a1a3a", edgecolor="#334466", labelcolor="white",
                  ncol=2)

        plt.tight_layout(rect=[0, 0.04, 1, 0.96])
        plt.ion()
        plt.show()

        def update_frame() -> None:
            # Update robot positions and colors
            for rid, dot in enumerate(robot_dots):
                robot = sim.robots[rid]
                dot.set_data([robot.col], [gy(robot.row)])
                dot.set_color(STATE_COLORS.get(robot.state, "#ffffff"))
                # Edge glow for carrying pod
                if robot.carrying_pod:
                    dot.set_markeredgecolor("#ffcc00")
                    dot.set_markeredgewidth(2.0)
                else:
                    dot.set_markeredgecolor("white")
                    dot.set_markeredgewidth(1.2)

            # Update robot labels
            for rid, txt in enumerate(robot_labels):
                robot = sim.robots[rid]
                txt.set_position((robot.col, gy(robot.row)))

            # Update pod positions
            for idx, (dot, orow, ocol) in enumerate(pod_dots):
                # Check if a robot is carrying this pod
                carrier = None
                for robot in sim.robots:
                    if robot.carrying_pod and robot.pod_origin == (orow, ocol):
                        carrier = robot
                        break
                if carrier is not None:
                    dot.set_data([carrier.col], [gy(carrier.row)])
                    dot.set_alpha(0.6)  # translucent when carried
                else:
                    # Check if pod is back at some cell
                    cell = sim.grid[orow, ocol]
                    if cell.pod is not None:
                        dot.set_data([ocol], [gy(orow)])
                        dot.set_alpha(1.0)
                    else:
                        # Pod was picked up and not yet returned
                        dot.set_alpha(0.0)

            # Update locked cell indicators
            locked_pts = []
            for cell in sim.grid.all_cells():
                if cell.locked:
                    locked_pts.append([cell.col, gy(cell.row)])
            if locked_pts:
                lock_scat.set_offsets(locked_pts)
            else:
                lock_scat.set_offsets(np.empty((0, 2)))

            # Status bar
            parts = []
            for r in sim.robots:
                state_short = r.state.name[:4]
                suffix = f"W{r.wait_timer}" if r.wait_timer > 0 else ""
                parts.append(f"R{r.robot_id}@({r.row},{r.col}) {state_short}{suffix}")
            status_txt.set_text(f"Tick {sim.tick_count:>3}  |  " + "  |  ".join(parts))

            fig.canvas.draw()
            fig.canvas.flush_events()

        # Initial frame
        update_frame()
        time.sleep(0.5)

        # Simulation loop
        for _ in range(cfg.max_ticks):
            still_running = sim.tick()
            update_frame()
            time.sleep(cfg.tick_interval)
            if not still_running:
                status_txt.set_text(f"✓ All done in {sim.tick_count} ticks!")
                fig.canvas.draw()
                fig.canvas.flush_events()
                break

        plt.ioff()
        plt.show()
