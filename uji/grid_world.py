"""
grid_world.py — Grid World (hosts all CellAgents)

Creates an rows × cols grid of CellAgent objects and links each cell
to its 4-neighbors. Provides lookup and pod/station registration.
"""

from __future__ import annotations
from typing import Optional

from cell_agent import CellAgent
from robot_state import Action


class GridWorld:
    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols

        # Create cell agents
        self._cells: list[list[CellAgent]] = [
            [CellAgent(r, c) for c in range(cols)]
            for r in range(rows)
        ]

        # Link 4-neighbors
        for r in range(rows):
            for c in range(cols):
                cell = self._cells[r][c]
                if r > 0:
                    cell.set_neighbor(Action.UP, self._cells[r - 1][c])
                if r < rows - 1:
                    cell.set_neighbor(Action.DOWN, self._cells[r + 1][c])
                if c > 0:
                    cell.set_neighbor(Action.LEFT, self._cells[r][c - 1])
                if c < cols - 1:
                    cell.set_neighbor(Action.RIGHT, self._cells[r][c + 1])

    def __getitem__(self, pos: tuple[int, int]) -> CellAgent:
        r, c = pos
        return self._cells[r][c]

    def all_cells(self):
        """Iterate over all cells row by row."""
        for row in self._cells:
            yield from row

    def cells_with_robots(self) -> list[CellAgent]:
        """Return all cells that currently host a robot."""
        return [cell for cell in self.all_cells() if cell.has_robot]

    def __repr__(self) -> str:
        return f"GridWorld({self.rows}x{self.cols})"
