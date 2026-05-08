# Darwin-Swarm

Darwin-Swarm is an evolutionary multi-agent sandbox for studying whether simple neural controllers can discover coordination without gradient-based learning.

Instead of training with reinforcement learning, a population of small neural policies is evolved through selection, crossover, and mutation inside a shared multi-agent environment. The current project focuses on coordination in `simple_spread`, then measures whether behavior becomes less chaotic and more structured over generations.

## What the project demonstrates today

- Neuroevolution over a population of agents with fixed-lifetime controllers
- Reproducible seeded evaluation in a shared multi-agent environment
- Behavior tracking across generations:
  - landmark coverage
  - collision rate
  - agent spread
  - mean distance to landmarks
- Baseline comparisons against:
  - random-action teams
  - still / zero-action teams
- Saved artifacts for showcase and analysis:
  - fitness curve
  - behavior metric dashboard
  - baseline comparison chart
  - spatial heatmap for the best evolved team

## What it does not claim yet

This repo is not yet an open-ended artificial life platform or a full research benchmark suite. It is currently a compact, reproducible study of evolved coordination in one task environment. That narrower claim is still strong, and it is now supported by metrics instead of only anecdotal visuals.

## Core idea

Each agent is controlled by a small feedforward neural network.

- Inputs: local environment observations
- Outputs: continuous movement actions
- Genome: flattened network weights
- Learning during lifetime: none
- Adaptation mechanism: evolution across generations

The evolutionary loop is:

1. Initialize a population of random genomes
2. Evaluate each genome in shared-team episodes
3. Rank genomes by fitness
4. Keep top performers
5. Create offspring with crossover and mutation
6. Repeat

## Environment

The training script prefers `mpe2.simple_spread_v3` and falls back to `pettingzoo.mpe.simple_spread_v3` when needed. This keeps the project compatible with older installs while moving toward the newer environment package.

## Setup

To install the dependencies, run:

```bash
pip install -r requirements.txt
```

## Training

Run a standard experiment:

```bash
PYTHONPATH=. python src/main.py
```

Useful overrides:

```bash
PYTHONPATH=. python src/main.py \
  --population-size 50 \
  --num-generations 100 \
  --episodes-per-genome 5 \
  --max-cycles 100 \
  --seed 7
```

## Visualization

After training, render the elite team:

```bash
PYTHONPATH=. python src/visualize.py --checkpoint checkpoints/elite_genomes.pt
```

If the elite checkpoint is missing, the visualizer falls back to `checkpoints/best_genome.pt`.

## Outputs

Training writes the following artifacts:

- `checkpoints/best_genome.pt`
- `checkpoints/elite_genomes.pt`
- `logs/fitness_curve.png`
- `logs/behavior_metrics.png`
- `logs/baseline_comparison.png`
- `logs/best_team_heatmap.png`
- `logs/training_metrics.csv`
- `logs/summary.json`

## Key Improvements

This version includes several enhancements over earlier prototypes:

- Seeded evaluation for repeatability
- Tracked coordination metrics beyond simple rewards
- Explicit baseline comparisons (random and stationary)
- Elite-team checkpointing for consistent demonstrations
- Comprehensive logging and visualization pipeline

## Good next steps

If you want to push this from strong prototype to standout showcase, the best next upgrades are:

1. Add a simple scripted baseline, not just random and still
2. Save per-generation rollout videos or GIFs
3. Sweep environment settings such as agent count and `local_ratio`
4. Add an environment-change experiment to test collapse vs robustness
5. Graduate to a richer environment like `waterworld` after the analysis pipeline is stable
