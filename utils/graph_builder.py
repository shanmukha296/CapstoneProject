import torch
import numpy as np
from scipy.spatial import KDTree

try:
    from torch_geometric.data import Data, Batch
except ImportError:
    Data = None
    Batch = None

def build_crime_graph(current_lat, current_lng, regional_crimes, k_neighbors=5):
    """
    Constructs a graph where nodes are crime locations and edges are proximity-based.
    """
    if not regional_crimes or Data is None:
        return None

    # 1. Prepare Node Features (lat, lng, normalized crime rate/type)
    # For simplicity, we use [lat, lng] as features
    node_features = []
    coords = []
    
    # Add current location as a node
    coords.append([current_lat, current_lng])
    node_features.append([current_lat, current_lng, 0.5]) # 0.5 as neutral risk feature
    
    for crime in regional_crimes:
        coords.append([crime['lat'], crime['lng']])
        # Feature: [lat, lng, severity/type_encoding]
        node_features.append([crime['lat'], crime['lng'], 1.0]) 

    coords = np.array(coords)
    x = torch.tensor(node_features, dtype=torch.float)

    # 2. Build Edges using KDTree (K-Nearest Neighbors)
    tree = KDTree(coords)
    edge_index = []
    
    for i in range(len(coords)):
        distances, indices = tree.query(coords[i], k=k_neighbors + 1)
        for j in indices:
            if i != j:
                edge_index.append([i, j])
                edge_index.append([j, i]) # Undirected

    edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()

    # 3. Create PyG Data Object
    data = Data(x=x, edge_index=edge_index)
    return Batch.from_data_list([data])

def get_spatial_influence_links(current_lat, current_lng, regional_crimes):
    """
    Identifies high-influence neighbors for visualization.
    (Simulates GNN attention/propagation for frontend)
    """
    links = []
    for crime in regional_crimes:
        dist = np.sqrt((current_lat - crime['lat'])**2 + (current_lng - crime['lng'])**2)
        if dist < 0.05: # Proximity threshold (approx 5km)
            links.append({
                "from": [current_lat, current_lng],
                "to": [crime['lat'], crime['lng']],
                "intensity": max(0.2, 1.0 - (dist / 0.05))
            })
    return links[:10] # Top 10 influences
