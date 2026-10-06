"""The bench's runner on each machine: Harbor's agent adapters, driven one turn at a time.

The Techtree controller decides every step. This runner only installs the machine's one agent at baseline
(`setup`), reports its version (`version`) and hands it one prompt (`turn`), continuing the attempt's conversation
with the agent's own resume flag after the first turn. Harbor's trial and job runners are not used: the controller
keeps the rounds, and Harbor supplies the agent adapters and the trajectory format (ATIF).
"""
