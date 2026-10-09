# Deployment plan

This phase stops before deployment. A later deployment phase must first verify
the source hash, exact schema/interface parity, clean worktree, current runner,
and a successful no-state-change deploy simulation. Only then may an operator
choose a network and separately authorize an actual deployment transaction.

No frontend, faucet, live blockchain write, Studio-dev deployment, GitHub
repository, or push is part of this repository.
