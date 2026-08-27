import os

import torch
from torch import nn


def save_checkpoint(model: nn.Module, out_dir: str, filename: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    torch.save(model.state_dict(), path)
    return path


def load_checkpoint(model: nn.Module, checkpoint_path: str, device: str) -> nn.Module:
    state = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state)
    return model
