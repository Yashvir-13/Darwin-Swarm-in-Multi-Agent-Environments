from __future__ import annotations

import csv
import json
import os

import matplotlib.pyplot as plt
import numpy as np


def plot_fitness(history: dict[str, list[float]], output_path: str) -> None:
    plt.figure(figsize=(10, 5))
    plt.plot(history["avg_fitness"], label="Average Fitness", color="royalblue")
    plt.plot(history["max_fitness"], label="Best Fitness", color="forestgreen")
    plt.plot(history["min_fitness"], label="Worst Fitness", color="firebrick", alpha=0.6)
    plt.fill_between(
        range(len(history["avg_fitness"])),
        history["min_fitness"],
        history["max_fitness"],
        color="lightgray",
        alpha=0.35,
    )
    plt.xlabel("Generation")
    plt.ylabel("Fitness")
    plt.title("Darwin-Swarm Fitness Progress")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_behavior_metrics(history: dict[str, list[float]], output_path: str) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    generations = np.arange(1, len(history["coverage_rate"]) + 1)

    axes[0, 0].plot(generations, history["coverage_rate"], color="darkgreen")
    axes[0, 0].set_title("Landmark Coverage")
    axes[0, 0].set_ylabel("Coverage Rate")

    axes[0, 1].plot(generations, history["collision_rate"], color="darkred")
    axes[0, 1].set_title("Collision Rate")

    axes[1, 0].plot(generations, history["mean_pairwise_distance"], color="darkorange")
    axes[1, 0].set_title("Agent Spread")
    axes[1, 0].set_xlabel("Generation")
    axes[1, 0].set_ylabel("Mean Pairwise Distance")

    axes[1, 1].plot(generations, history["mean_landmark_distance"], color="purple")
    axes[1, 1].set_title("Landmark Distance")
    axes[1, 1].set_xlabel("Generation")

    for axis in axes.flat:
        axis.grid(True, alpha=0.3)

    fig.suptitle("Behavior Metrics Across Evolution")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_baseline_comparison(results: dict[str, dict[str, float]], output_path: str) -> None:
    labels = list(results.keys())
    reward_values = [results[label]["team_reward_mean"] for label in labels]
    coverage_values = [results[label]["coverage_rate_mean"] for label in labels]
    collision_values = [results[label]["collision_rate_mean"] for label in labels]

    x = np.arange(len(labels))
    width = 0.25

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    axes[0].bar(x, reward_values, width=width, color=["#2e8b57", "#4682b4", "#999999"])
    axes[0].set_title("Team Reward")
    axes[0].set_xticks(x, labels)

    axes[1].bar(x, coverage_values, width=width, color=["#2e8b57", "#4682b4", "#999999"])
    axes[1].set_title("Coverage Rate")
    axes[1].set_xticks(x, labels)

    axes[2].bar(x, collision_values, width=width, color=["#2e8b57", "#4682b4", "#999999"])
    axes[2].set_title("Collision Rate")
    axes[2].set_xticks(x, labels)

    for axis in axes:
        axis.grid(True, axis="y", alpha=0.25)

    fig.suptitle("Evolved Team vs Baselines")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_heatmap(
    trajectories: list[list[list[float]]] | None,
    landmark_positions: list[list[float]] | None,
    output_path: str,
) -> None:
    if not trajectories:
        return

    trajectory_array = np.asarray(trajectories, dtype=np.float32)
    num_agents = trajectory_array.shape[1]

    fig, axes = plt.subplots(1, num_agents, figsize=(4 * num_agents, 4), sharex=True, sharey=True)
    if num_agents == 1:
        axes = [axes]

    for agent_idx, axis in enumerate(axes):
        x_coords = trajectory_array[:, agent_idx, 0]
        y_coords = trajectory_array[:, agent_idx, 1]
        axis.hist2d(x_coords, y_coords, bins=30, range=[[-1.2, 1.2], [-1.2, 1.2]], cmap="viridis")
        if landmark_positions:
            landmarks = np.asarray(landmark_positions, dtype=np.float32)
            axis.scatter(landmarks[:, 0], landmarks[:, 1], c="red", marker="x", s=60)
        axis.set_title(f"Agent {agent_idx + 1}")
        axis.set_xlabel("x")
        axis.grid(False)

    axes[0].set_ylabel("y")
    fig.suptitle("Best Team Spatial Footprint")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def save_metrics_csv(history: dict[str, list[float]], output_path: str) -> None:
    fieldnames = list(history.keys())
    rows = zip(*(history[field] for field in fieldnames))
    with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(fieldnames)
        writer.writerows(rows)


def save_json(data: dict, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
