from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

import numpy as np
import torch

from src.models import NeuralController

try:
    from mpe2 import simple_spread_v3

    ENV_SOURCE = "mpe2"
except ImportError:
    from pettingzoo.mpe import simple_spread_v3

    ENV_SOURCE = "pettingzoo.mpe"


ActionPolicy = Callable[[np.ndarray], np.ndarray]


@dataclass
class EpisodeMetrics:
    rewards: np.ndarray
    team_reward: float
    collision_rate: float
    coverage_rate: float
    mean_pairwise_distance: float
    mean_landmark_distance: float
    trajectories: np.ndarray | None = None
    landmark_positions: np.ndarray | None = None

    def to_dict(self) -> dict[str, float]:
        data = asdict(self)
        data["rewards"] = self.rewards.tolist()
        data["trajectories"] = None if self.trajectories is None else self.trajectories.tolist()
        data["landmark_positions"] = (
            None if self.landmark_positions is None else self.landmark_positions.tolist()
        )
        return data


class GenomePolicy:
    def __init__(self, model: NeuralController):
        self.model = model

    def __call__(self, observation: np.ndarray) -> np.ndarray:
        obs_tensor = torch.tensor(observation, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            action_values = self.model(obs_tensor).squeeze(0).numpy()
        return np.clip(action_values, 0.0, 1.0)


class RandomPolicy:
    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)

    def __call__(self, observation: np.ndarray) -> np.ndarray:
        del observation
        return self.rng.random(5, dtype=np.float32)


class ZeroPolicy:
    def __call__(self, observation: np.ndarray) -> np.ndarray:
        del observation
        return np.zeros(5, dtype=np.float32)


def make_env(num_agents: int = 3, max_cycles: int = 100, render_mode: str | None = None):
    return simple_spread_v3.env(
        N=num_agents,
        max_cycles=max_cycles,
        continuous_actions=True,
        render_mode=render_mode,
    )


def build_genome_policies(
    genomes: list[np.ndarray], input_dim: int, output_dim: int, hidden_dim: int
) -> list[GenomePolicy]:
    policies: list[GenomePolicy] = []
    for genome in genomes:
        model = NeuralController(input_dim, output_dim, hidden_dim)
        model.set_genome(genome)
        policies.append(GenomePolicy(model))
    return policies


def _pairwise_distances(positions: np.ndarray) -> np.ndarray:
    if len(positions) < 2:
        return np.empty(0, dtype=np.float32)
    distances = []
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            distances.append(np.linalg.norm(positions[i] - positions[j]))
    return np.asarray(distances, dtype=np.float32)


def _compute_world_metrics(world) -> tuple[float, float, float, float, np.ndarray, np.ndarray]:
    agent_positions = np.asarray([agent.state.p_pos for agent in world.agents], dtype=np.float32)
    landmark_positions = np.asarray(
        [landmark.state.p_pos for landmark in world.landmarks], dtype=np.float32
    )

    pairwise_distances = _pairwise_distances(agent_positions)
    mean_pairwise_distance = float(pairwise_distances.mean()) if pairwise_distances.size else 0.0

    collision_count = 0
    num_pairs = 0
    for i, first_agent in enumerate(world.agents):
        for second_agent in world.agents[i + 1 :]:
            distance = np.linalg.norm(first_agent.state.p_pos - second_agent.state.p_pos)
            threshold = first_agent.size + second_agent.size
            collision_count += int(distance <= threshold)
            num_pairs += 1
    collision_rate = float(collision_count / num_pairs) if num_pairs else 0.0

    occupied_landmarks = 0
    min_landmark_distances = []
    for landmark in world.landmarks:
        distances = np.linalg.norm(agent_positions - landmark.state.p_pos, axis=1)
        min_distance = float(distances.min())
        min_landmark_distances.append(min_distance)
        threshold = landmark.size + min(agent.size for agent in world.agents)
        if min_distance <= threshold:
            occupied_landmarks += 1
    coverage_rate = occupied_landmarks / max(1, len(world.landmarks))
    mean_landmark_distance = float(np.mean(min_landmark_distances))

    return (
        collision_rate,
        coverage_rate,
        mean_pairwise_distance,
        mean_landmark_distance,
        agent_positions,
        landmark_positions,
    )


def run_episode(
    policies: list[ActionPolicy],
    max_cycles: int = 100,
    seed: int | None = None,
    render_mode: str | None = None,
    collect_trajectory: bool = False,
) -> EpisodeMetrics:
    env = make_env(num_agents=len(policies), max_cycles=max_cycles, render_mode=render_mode)
    env.reset(seed=seed)
    raw_env = env.unwrapped if hasattr(env, "unwrapped") else env
    agents = env.agents[:]

    rewards = np.zeros(len(policies), dtype=np.float32)
    collision_total = 0.0
    coverage_total = 0.0
    pairwise_total = 0.0
    landmark_distance_total = 0.0
    metric_steps = 0

    landmark_positions = None
    trajectories = []
    if collect_trajectory:
        _, _, _, _, agent_positions, landmark_positions = _compute_world_metrics(raw_env.world)
        trajectories.append(agent_positions)

    for agent_name in env.agent_iter():
        observation, reward, termination, truncation, _ = env.last()
        agent_idx = agents.index(agent_name)
        rewards[agent_idx] += reward

        if termination or truncation:
            action = None
        else:
            action = policies[agent_idx](observation)

        env.step(action)

        if agent_name == agents[-1]:
            (
                collision_rate,
                coverage_rate,
                mean_pairwise_distance,
                mean_landmark_distance,
                agent_positions,
                landmark_positions,
            ) = _compute_world_metrics(raw_env.world)
            collision_total += collision_rate
            coverage_total += coverage_rate
            pairwise_total += mean_pairwise_distance
            landmark_distance_total += mean_landmark_distance
            metric_steps += 1

            if collect_trajectory:
                trajectories.append(agent_positions)

    env.close()

    normalizer = max(1, metric_steps)
    return EpisodeMetrics(
        rewards=rewards,
        team_reward=float(rewards.sum()),
        collision_rate=collision_total / normalizer,
        coverage_rate=coverage_total / normalizer,
        mean_pairwise_distance=pairwise_total / normalizer,
        mean_landmark_distance=landmark_distance_total / normalizer,
        trajectories=np.asarray(trajectories, dtype=np.float32) if collect_trajectory else None,
        landmark_positions=landmark_positions,
    )


def evaluate_population(
    population_genomes: list[np.ndarray],
    input_dim: int = 18,
    output_dim: int = 5,
    hidden_dim: int = 64,
    num_episodes: int = 3,
    max_cycles: int = 100,
    seed: int = 0,
) -> tuple[np.ndarray, dict[str, float]]:
    num_models = len(population_genomes)
    fitnesses = np.zeros(num_models, dtype=np.float32)

    models = [NeuralController(input_dim, output_dim, hidden_dim) for _ in range(num_models)]
    for index, genome in enumerate(population_genomes):
        models[index].set_genome(genome)

    generation_metrics = {
        "collision_rate": 0.0,
        "coverage_rate": 0.0,
        "mean_pairwise_distance": 0.0,
        "mean_landmark_distance": 0.0,
        "team_reward": 0.0,
    }
    total_rollouts = 0
    population_indices = np.arange(num_models)

    for genome_idx in range(num_models):
        teammate_pool = population_indices[population_indices != genome_idx]
        for episode_idx in range(num_episodes):
            episode_seed = seed + genome_idx * 1000 + episode_idx
            rng = np.random.default_rng(episode_seed)
            teammate_count = min(2, len(teammate_pool))
            teammate_indices = (
                rng.choice(teammate_pool, size=teammate_count, replace=False)
                if teammate_count
                else np.empty(0, dtype=np.int64)
            )
            team_indices = np.concatenate(([genome_idx], teammate_indices))
            rng.shuffle(team_indices)

            policies = [GenomePolicy(models[index]) for index in team_indices]
            episode_metrics = run_episode(policies, max_cycles=max_cycles, seed=episode_seed)
            focal_slot = int(np.where(team_indices == genome_idx)[0][0])
            fitnesses[genome_idx] += episode_metrics.rewards[focal_slot]

            generation_metrics["collision_rate"] += episode_metrics.collision_rate
            generation_metrics["coverage_rate"] += episode_metrics.coverage_rate
            generation_metrics["mean_pairwise_distance"] += (
                episode_metrics.mean_pairwise_distance
            )
            generation_metrics["mean_landmark_distance"] += (
                episode_metrics.mean_landmark_distance
            )
            generation_metrics["team_reward"] += episode_metrics.team_reward
            total_rollouts += 1

    fitnesses /= max(1, num_episodes)
    for key in generation_metrics:
        generation_metrics[key] /= max(1, total_rollouts)
    generation_metrics["episodes_per_genome"] = float(num_episodes)
    generation_metrics["env_source"] = ENV_SOURCE

    return fitnesses, generation_metrics


def evaluate_fixed_team(
    team_genomes: list[np.ndarray],
    input_dim: int,
    output_dim: int,
    hidden_dim: int,
    num_episodes: int,
    max_cycles: int,
    seed: int,
    collect_trajectory: bool = False,
) -> dict[str, object]:
    policies = build_genome_policies(team_genomes, input_dim, output_dim, hidden_dim)
    episodes = []
    for episode_idx in range(num_episodes):
        episode_metrics = run_episode(
            policies,
            max_cycles=max_cycles,
            seed=seed + episode_idx,
            collect_trajectory=collect_trajectory and episode_idx == 0,
        )
        episodes.append(episode_metrics)
    return summarize_episode_batch(episodes)


def evaluate_baseline_team(
    baseline: str,
    num_agents: int,
    num_episodes: int,
    max_cycles: int,
    seed: int,
) -> dict[str, object]:
    episodes = []
    for episode_idx in range(num_episodes):
        episode_seed = seed + episode_idx
        if baseline == "random":
            policies = [RandomPolicy(episode_seed + agent_idx) for agent_idx in range(num_agents)]
        elif baseline == "zero":
            policies = [ZeroPolicy() for _ in range(num_agents)]
        else:
            raise ValueError(f"Unknown baseline '{baseline}'")

        episode_metrics = run_episode(policies, max_cycles=max_cycles, seed=episode_seed)
        episodes.append(episode_metrics)

    return summarize_episode_batch(episodes)


def summarize_episode_batch(episodes: list[EpisodeMetrics]) -> dict[str, object]:
    team_rewards = np.asarray([episode.team_reward for episode in episodes], dtype=np.float32)
    collision_rates = np.asarray([episode.collision_rate for episode in episodes], dtype=np.float32)
    coverage_rates = np.asarray([episode.coverage_rate for episode in episodes], dtype=np.float32)
    pairwise_distances = np.asarray(
        [episode.mean_pairwise_distance for episode in episodes], dtype=np.float32
    )
    landmark_distances = np.asarray(
        [episode.mean_landmark_distance for episode in episodes], dtype=np.float32
    )

    first_with_trajectory = next(
        (episode for episode in episodes if episode.trajectories is not None),
        None,
    )

    return {
        "team_reward_mean": float(team_rewards.mean()),
        "team_reward_std": float(team_rewards.std()),
        "collision_rate_mean": float(collision_rates.mean()),
        "coverage_rate_mean": float(coverage_rates.mean()),
        "mean_pairwise_distance": float(pairwise_distances.mean()),
        "mean_landmark_distance": float(landmark_distances.mean()),
        "episodes": len(episodes),
        "sample_trajectory": (
            None if first_with_trajectory is None else first_with_trajectory.trajectories.tolist()
        ),
        "sample_landmarks": (
            None
            if first_with_trajectory is None or first_with_trajectory.landmark_positions is None
            else first_with_trajectory.landmark_positions.tolist()
        ),
    }
