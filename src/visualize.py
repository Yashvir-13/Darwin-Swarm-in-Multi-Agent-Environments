import argparse
import os
import time

import numpy as np
import torch

from src.environment import GenomePolicy, make_env
from src.models import NeuralController


INPUT_DIM = 18
OUTPUT_DIM = 5
HIDDEN_DIM = 64


def load_policies(checkpoint_path: str) -> list[GenomePolicy]:
    try:
        checkpoint_tensor = torch.load(checkpoint_path, weights_only=True)
    except TypeError:
        checkpoint_tensor = torch.load(checkpoint_path)
    genomes = checkpoint_tensor.numpy()

    if genomes.ndim == 1:
        genomes = np.stack([genomes] * 3)

    policies = []
    for genome in genomes:
        model = NeuralController(INPUT_DIM, OUTPUT_DIM, HIDDEN_DIM)
        model.set_genome(genome)
        policies.append(GenomePolicy(model))
    return policies


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize evolved Darwin-Swarm agents.")
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="checkpoints/elite_genomes.pt",
        help="Path to elite team checkpoint. Falls back to cloning a single genome if needed.",
    )
    parser.add_argument("--num-episodes", type=int, default=3)
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--seed", type=int, default=99)
    args = parser.parse_args()

    checkpoint_path = args.checkpoint
    if not os.path.exists(checkpoint_path):
        checkpoint_path = "checkpoints/best_genome.pt"

    if not os.path.exists(checkpoint_path):
        print("No checkpoint found. Run src/main.py first.")
        return

    policies = load_policies(checkpoint_path)
    env = make_env(num_agents=len(policies), max_cycles=args.max_cycles, render_mode="human")

    print(f"Loading checkpoint {checkpoint_path}...")
    for episode_idx in range(args.num_episodes):
        print(f"--- Episode {episode_idx + 1} ---")
        env.reset(seed=args.seed + episode_idx)
        agents = env.agents[:]

        for agent_name in env.agent_iter():
            observation, _, termination, truncation, _ = env.last()
            agent_idx = agents.index(agent_name)

            if termination or truncation:
                action = None
            else:
                action = policies[agent_idx](observation)

            env.step(action)
            time.sleep(1.0 / max(1, args.fps * len(agents)))

    env.close()


if __name__ == "__main__":
    main()
