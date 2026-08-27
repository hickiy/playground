from dataclasses import dataclass

import torch


@dataclass
class TrainConfig:
    batch_size: int = 64
    lr: float = 1e-3
    epochs: int = 3
    data_root: str = "data"
    dataset_name: str = "mnist"
    checkpoint_dir: str = "checkpoints"
    model_name: str = "mlp"
    # device: str = "cuda" if torch.cuda.is_available() else "cpu"
    device: str = "cpu"
