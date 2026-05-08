import numpy as np

def initialize_population(size: int, genome_length: int) -> list[np.ndarray]:
    """
    Initializes a population of random genomes.
    Using a standard normal distribution (mean=0, std=1) for weights.
    Alternatively, one could instantiate `NeuralController` and use `get_genome()`,
    but random normal works well for starting evolution.
    """
    # Using std=0.5 to keep initial weights relatively small
    return [np.random.normal(loc=0.0, scale=0.5, size=genome_length) for _ in range(size)]

def selection(population: list[np.ndarray], fitnesses: np.ndarray, retain_rate: float = 0.2) -> list[np.ndarray]:
    """
    Selects the top performing genomes based on fitness.
    """
    num_retain = max(2, int(len(population) * retain_rate))
    
    # argsort sorts ascending, we want descending (highest fitness first)
    sorted_indices = np.argsort(fitnesses)[::-1]
    
    # Return copies to prevent modifying the original by reference
    retained = [population[i].copy() for i in sorted_indices[:num_retain]]
    return retained

def crossover(parent1: np.ndarray, parent2: np.ndarray) -> np.ndarray:
    """
    Performs uniform crossover between two parents.
    Each weight is randomly chosen from parent1 or parent2 with 50% probability.
    """
    mask = np.random.rand(len(parent1)) < 0.5
    child = np.where(mask, parent1, parent2)
    return child

def mutate(genome: np.ndarray, mutation_rate: float = 0.1, noise_std: float = 0.1) -> np.ndarray:
    """
    Applies Gaussian mutation to a genome.
    A fraction (mutation_rate) of the weights are perturbed by Gaussian noise.
    """
    child = genome.copy()
    mask = np.random.rand(len(child)) < mutation_rate
    noise = np.random.normal(0, noise_std, size=len(child))
    child[mask] += noise[mask]
    return child
