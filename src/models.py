import torch
import torch.nn as nn
import numpy as np

class NeuralController(nn.Module):
    def __init__(self, input_dim: int, output_dim: int, hidden_dim: int = 64):
        super(NeuralController, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)
        
    def get_genome_length(self) -> int:
        """Returns the total number of parameters (weights + biases) in the network."""
        return sum(p.numel() for p in self.parameters())
        
    def set_genome(self, genome: np.ndarray):
        """Inject a flattened numpy array of weights into the network parameters."""
        assert len(genome) == self.get_genome_length(), f"Genome length mismatch. Expected {self.get_genome_length()}, got {len(genome)}"
        current_idx = 0
        for param in self.parameters():
            num_params = param.numel()
            param_data = genome[current_idx:current_idx+num_params]
            param_data = torch.tensor(param_data, dtype=torch.float32).view_as(param)
            param.data.copy_(param_data)
            current_idx += num_params
            
    def get_genome(self) -> np.ndarray:
        """Extract network parameters as a flattened numpy array."""
        params = []
        for param in self.parameters():
            params.append(param.data.cpu().numpy().flatten())
        return np.concatenate(params)

def test_genome_mapping():
    model = NeuralController(18, 5, 32)
    genome = model.get_genome()
    # Modify genome to verify it updates
    modified_genome = genome + 1.23
    model.set_genome(modified_genome)
    new_genome = model.get_genome()
    
    # Assert successful copy
    assert np.allclose(modified_genome, new_genome), "Genome mapping failed"
    print("Genome mapping test passed!")

if __name__ == "__main__":
    test_genome_mapping()
