import numpy as np

GRID_SIZE = 5
GAMMA = 0.9

ACTION = [
    (-1,0), (0,1),
    (1,0), (0,-1),
    (0,0)
    ]

GOAL_STATE = (4, 3)

OBSTACLE = [
    (2,2), (2,3),
    (3,3),
    (4,2), (4,4),
    (5,2)
]

# 初始价值函数 V(s) = 0
V = np.zeros((GRID_SIZE, GRID_SIZE))
