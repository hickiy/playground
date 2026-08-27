from torch.utils.data import DataLoader
from torchvision import datasets, transforms

import os

from config import TrainConfig


def get_dataloaders(cfg: TrainConfig) -> tuple[DataLoader, DataLoader]:
    transform = transforms.ToTensor()
    data_dir = os.path.join(cfg.data_root, cfg.dataset_name)
    train_data = datasets.MNIST(
        root=data_dir, train=True, download=True, transform=transform
    )
    test_data = datasets.MNIST(
        root=data_dir, train=False, download=True, transform=transform
    )

    train_loader = DataLoader(train_data, batch_size=cfg.batch_size, shuffle=True)
    test_loader = DataLoader(test_data, batch_size=cfg.batch_size)
    return train_loader, test_loader
