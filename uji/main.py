"""
main.py — Entry point for Distributed Cell-Agent Warehouse Simulation

Usage:
  python main.py                     # visual mode (default)
  python main.py --console           # console-only mode
  python main.py --config path.json  # load custom map config
"""

from __future__ import annotations
import argparse
import sys

from config import default_config, load_config
from simulator import DistributedSimulator


VISUALIZE = True


def build_sim(config_path: str | None = None, no_lrta: bool = False) -> DistributedSimulator:
    """Build and initialize the simulator."""
    if config_path:
        cfg = load_config(config_path)
    else:
        cfg = default_config()

    if no_lrta:
        cfg.enable_lrta_update = False

    sim = DistributedSimulator(cfg)
    sim.setup()
    return sim


def run_console(config_path: str | None = None, no_lrta: bool = False) -> None:
    """Run simulation in console-only mode."""
    print("=" * 60)
    print("  Distributed Cell-Agent Warehouse Simulation (Console)")
    print("=" * 60)
    sim = build_sim(config_path, no_lrta=no_lrta)
    sim.run()


def run_visual(config_path: str | None = None, no_lrta: bool = False) -> None:
    """Run simulation with matplotlib visualization."""
    try:
        from visualizer import Visualizer
    except ImportError:
        print("[Warning] matplotlib not available, falling back to console mode.")
        run_console(config_path, no_lrta=no_lrta)
        return

    sim = build_sim(config_path, no_lrta=no_lrta)
    viz = Visualizer(sim)
    viz.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distributed Cell-Agent Warehouse Simulation"
    )
    parser.add_argument("--console", action="store_true",
                        help="Run in console-only mode (no visualization)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to JSON map configuration file")
    parser.add_argument("--no-lrta", action="store_true",
                        help="Disable LRTA* V-update (use pure Manhattan heuristic)")
    args = parser.parse_args()

    if args.console:
        run_console(args.config, no_lrta=args.no_lrta)
    else:
        run_visual(args.config, no_lrta=args.no_lrta)


if __name__ == "__main__":
    main()
#  python distributed_simulation/main.py --config distributed_simulation/map_config.json