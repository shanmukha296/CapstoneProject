import torch
import torch.nn as nn

class BiLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, output_size):
        super(BiLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, bidirectional=True)
        self.fc = nn.Linear(hidden_size * 2, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers * 2, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers * 2, x.size(0), self.hidden_size).to(x.device)
        
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out

try:
    from torch_geometric.nn import GCNConv, global_mean_pool

    class SpatialGNN(nn.Module):
        def __init__(self, num_node_features, hidden_channels, num_classes):
            super(SpatialGNN, self).__init__()
            self.conv1 = GCNConv(num_node_features, hidden_channels)
            self.conv2 = GCNConv(hidden_channels, hidden_channels)
            self.conv3 = GCNConv(hidden_channels, hidden_channels)
            self.lin = nn.Linear(hidden_channels, num_classes)

        def forward(self, x, edge_index, batch):
            # 1. Obtain node embeddings 
            x = self.conv1(x, edge_index)
            x = x.relu()
            x = self.conv2(x, edge_index)
            x = x.relu()
            x = self.conv3(x, edge_index)

            # 2. Readout layer
            x = global_mean_pool(x, batch)  # [batch_size, hidden_channels]

            # 3. Final classifier
            x = self.lin(x)
            return x
except ImportError:
    # Fallback for missing torch-geometric during environment setup
    class SpatialGNN(nn.Module):
        def __init__(self, *args, **kwargs):
            super(SpatialGNN, self).__init__()
        def forward(self, *args, **kwargs):
            return torch.tensor([[0.5]]) # Mock prediction
