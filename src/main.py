import argparse
import os
import time

import numpy as np
import torch

from src.environment import ENV_SOURCE, evaluate_baseline_team, evaluate_fixed_team, evaluate_population
from src.evolution import crossover, initialize_population, mutate, selection
from src.models import NeuralController
from src.reporting import (
    ensure_dir,
    plot_baseline_comparison,
    plot_behavior_metrics,
    plot_fitness,
    plot_heatmap,
    save_json,
    save_metrics_csv,
)


INPUT_DIM = 18
OUTPUT_DIM = 5
HIDDEN_DIM = 64

CHECKPOINT_DIR = "checkpoints"
LOG_DIR = "logs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evolve multi-agent coordination in Darwin-Swarm.")
    parser.add_argument("--population-size", type=int, default=50)
    parser.add_argument("--num-generations", type=int, default=100)
    parser.add_argument("--episodes-per-genome", type=int, default=5)
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--mutation-rate", type=float, default=0.1)
    parser.add_argument("--noise-std", type=float, default=0.1)
    parser.add_argument("--retain-rate", type=float, default=0.2)
    parser.add_argument("--elite-fraction", type=float, default=0.06)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--baseline-episodes", type=int, default=12)
    return parser.parse_args()


def initialize_history() -> dict[str, list[float]]:
    return {
        "generation": [],
        "min_fitness": [],
        "max_fitness": [],
        "avg_fitness": [],
        "collision_rate": [],
        "coverage_rate": [],
        "mean_pairwise_distance": [],
        "mean_landmark_distance": [],
        "team_reward": [],
    }


def append_generation(
    history: dict[str, list[float]],
    generation: int,
    fitnesses: np.ndarray,
    behavior_metrics: dict[str, float],
) -> None:
    history["generation"].append(generation)
    history["min_fitness"].append(float(np.min(fitnesses)))
    history["max_fitness"].append(float(np.max(fitnesses)))
    history["avg_fitness"].append(float(np.mean(fitnesses)))
    history["collision_rate"].append(float(behavior_metrics["collision_rate"]))
    history["coverage_rate"].append(float(behavior_metrics["coverage_rate"]))
    history["mean_pairwise_distance"].append(float(behavior_metrics["mean_pairwise_distance"]))
    history["mean_landmark_distance"].append(float(behavior_metrics["mean_landmark_distance"]))
    history["team_reward"].append(float(behavior_metrics["team_reward"]))


def save_generation_artifacts(history: dict[str, list[float]]) -> None:
    plot_fitness(history, os.path.join(LOG_DIR, "fitness_curve.png"))
    plot_behavior_metrics(history, os.path.join(LOG_DIR, "behavior_metrics.png"))
    save_metrics_csv(history, os.path.join(LOG_DIR, "training_metrics.csv"))


def evaluate_showcase_artifacts(
    elite_genomes: list[np.ndarray],
    args: argparse.Namespace,
) -> tuple[dict[str, dict[str, float]], dict[str, object]]:
    evolved_summary = evaluate_fixed_team(
        team_genomes=elite_genomes,
        input_dim=INPUT_DIM,
        output_dim=OUTPUT_DIM,
        hidden_dim=HIDDEN_DIM,
        num_episodes=args.baseline_episodes,
        max_cycles=args.max_cycles,
        seed=args.seed + 50_000,
        collect_trajectory=True,
    )
    baseline_results = {
        "Evolved": evolved_summary,
        "Random": evaluate_baseline_team(
            baseline="random",
            num_agents=len(elite_genomes),
            num_episodes=args.baseline_episodes,
            max_cycles=args.max_cycles,
            seed=args.seed + 60_000,
        ),
        "Still": evaluate_baseline_team(
            baseline="zero",
            num_agents=len(elite_genomes),
            num_episodes=args.baseline_episodes,
            max_cycles=args.max_cycles,
            seed=args.seed + 70_000,
        ),
    }
    return baseline_results, evolved_summary


def main() -> None:
    args = parse_args()
    if args.population_size < 3:
        raise ValueError("population-size must be at least 3 for the simple_spread team setup.")

    ensure_dir(CHECKPOINT_DIR)
    ensure_dir(LOG_DIR)

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    dummy_model = NeuralController(INPUT_DIM, OUTPUT_DIM, HIDDEN_DIM)
    genome_length = dummy_model.get_genome_length()
    print(
        f"Initializing population={args.population_size}, genome_length={genome_length}, env={ENV_SOURCE}"
    )

    population = initialize_population(args.population_size, genome_length)
    history = initialize_history()

    best_overall_fitness = -float("inf")
    final_elites: list[np.ndarray] = []

    start_time = time.time()

    for generation in range(1, args.num_generations + 1):
        generation_seed = args.seed + generation * 10_000
        generation_start = time.time()

        fitnesses, behavior_metrics = evaluate_population(
            population,
            input_dim=INPUT_DIM,
            output_dim=OUTPUT_DIM,
            hidden_dim=HIDDEN_DIM,
            num_episodes=args.episodes_per_genome,
            max_cycles=args.max_cycles,
            seed=generation_seed,
        )

        append_generation(history, generation, fitnesses, behavior_metrics)

        best_index = int(np.argmax(fitnesses))
        if float(fitnesses[best_index]) > best_overall_fitness:
            best_overall_fitness = float(fitnesses[best_index])
            torch.save(
                torch.tensor(population[best_index].copy()),
                os.path.join(CHECKPOINT_DIR, "best_genome.pt"),
            )

        sorted_indices = np.argsort(fitnesses)[::-1]
        elite_count = min(3, len(population))
        final_elites = [population[index].copy() for index in sorted_indices[:elite_count]]
        torch.save(
            torch.tensor(np.stack(final_elites)),
            os.path.join(CHECKPOINT_DIR, "elite_genomes.pt"),
        )

        generation_time = time.time() - generation_start
        print(
            f"Gen {generation:03d} | Min {history['min_fitness'][-1]:8.2f} | "
            f"Max {history['max_fitness'][-1]:8.2f} | Avg {history['avg_fitness'][-1]:8.2f} | "
            f"Coverage {history['coverage_rate'][-1]:.3f} | "
            f"Collision {history['collision_rate'][-1]:.3f} | Time {generation_time:5.1f}s"
        )

        parents = selection(population, fitnesses, retain_rate=args.retain_rate)
        next_generation = []
        elite_keep = max(1, int(args.population_size * args.elite_fraction))
        for elite_idx in range(min(elite_keep, len(parents))):
            next_generation.append(parents[elite_idx].copy())

        while len(next_generation) < args.population_size:
            parent_indices = np.random.choice(len(parents), 2, replace=False)
            child = crossover(parents[parent_indices[0]], parents[parent_indices[1]])
            child = mutate(
                child,
                mutation_rate=args.mutation_rate,
                noise_std=args.noise_std,
            )
            next_generation.append(child)

        population = next_generation

        if generation % 5 == 0 or generation == args.num_generations:
            save_generation_artifacts(history)

    total_time = time.time() - start_time
    print(f"\nEvolution complete in {total_time:.2f}s")
    print(f"Best individual fitness: {best_overall_fitness:.2f}")

    baseline_results, evolved_summary = evaluate_showcase_artifacts(final_elites, args)
    plot_baseline_comparison(
        baseline_results,
        os.path.join(LOG_DIR, "baseline_comparison.png"),
    )
    plot_heatmap(
        evolved_summary["sample_trajectory"],
        evolved_summary["sample_landmarks"],
        os.path.join(LOG_DIR, "best_team_heatmap.png"),
    )

    summary_payload = {
        "config": vars(args),
        "env_source": ENV_SOURCE,
        "best_overall_fitness": best_overall_fitness,
        "final_generation": {
            "min_fitness": history["min_fitness"][-1],
            "max_fitness": history["max_fitness"][-1],
            "avg_fitness": history["avg_fitness"][-1],
            "coverage_rate": history["coverage_rate"][-1],
            "collision_rate": history["collision_rate"][-1],
            "mean_pairwise_distance": history["mean_pairwise_distance"][-1],
            "mean_landmark_distance": history["mean_landmark_distance"][-1],
        },
        "baseline_results": baseline_results,
        "artifacts": {
            "fitness_curve": os.path.join(LOG_DIR, "fitness_curve.png"),
            "behavior_metrics": os.path.join(LOG_DIR, "behavior_metrics.png"),
            "baseline_comparison": os.path.join(LOG_DIR, "baseline_comparison.png"),
            "best_team_heatmap": os.path.join(LOG_DIR, "best_team_heatmap.png"),
            "training_metrics_csv": os.path.join(LOG_DIR, "training_metrics.csv"),
        },
    }
    save_json(summary_payload, os.path.join(LOG_DIR, "summary.json"))


if __name__ == "__main__":
    main()
