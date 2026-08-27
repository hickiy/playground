import argparse
import os
import sys

import torch
from torch import nn

CURRENT_DIR = os.path.dirname(__file__)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from config import TrainConfig
from data.mnist_data import get_dataloaders
from eval.evaluator import evaluate
from models.mlp import MLP
from train.trainer import train_one_epoch
from utils.checkpoint import load_checkpoint, save_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MNIST pipeline: download, train, evaluate, test"
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--data-root", type=str, default="data")
    parser.add_argument("--dataset-name", type=str, default="mnist")
    parser.add_argument("--model-name", type=str, default="mlp")
    parser.add_argument("--checkpoint", type=str, default="")
    parser.add_argument("--save-dir", type=str, default="checkpoints")
    parser.add_argument("--test-only", action="store_true")

    args = parser.parse_args()

    cfg = TrainConfig(
        batch_size=args.batch_size,
        lr=args.lr,
        epochs=args.epochs,
        data_root=args.data_root,
        dataset_name=args.dataset_name,
        checkpoint_dir=args.save_dir,
        model_name=args.model_name,
    )

    train_loader, test_loader = get_dataloaders(cfg)

    model = MLP().to(cfg.device)
    if args.checkpoint:
        load_checkpoint(model, args.checkpoint, cfg.device)
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    if not args.test_only:
        for epoch in range(cfg.epochs):
            avg_loss = train_one_epoch(
                model, train_loader, loss_fn, optimizer, cfg.device
            )
            accuracy = evaluate(model, test_loader, cfg.device)
            print(f"Epoch {epoch+1}/{cfg.epochs} - loss: {avg_loss:.4f}")
            print(f"Eval accuracy: {accuracy:.4f}")

        ckpt_name = f"{cfg.model_name}.pt"
        ckpt_path = save_checkpoint(model, cfg.checkpoint_dir, ckpt_name)
        print(f"Saved checkpoint: {ckpt_path}")

    test_accuracy = evaluate(model, test_loader, cfg.device)
    print(f"Test accuracy: {test_accuracy:.4f}")


if __name__ == "__main__":
    main()
