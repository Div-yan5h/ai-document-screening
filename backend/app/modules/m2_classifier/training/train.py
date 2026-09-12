"""
M2 Document Classifier — Model Training Script (Task C)
======================================================
Trains MobileNetV3-Small classifier on the leakage-safe train split
and evaluates on the held-out validation split.

Model Architecture: MobileNetV3-Small with Linear(1024, 4) head.
Pretrained Weights: ImageNet-1K (MobileNet_V3_Small_Weights.DEFAULT).
Target Classes: 0: passport, 1: visa, 2: id_card, 3: unknown.

Owner: P2
"""

import csv
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

from backend.app.modules.m2_classifier.classifier import TARGET_CLASSES, DocumentClassifier


# Paths
TRAINING_DIR = os.path.join(PROJECT_ROOT, "backend/app/modules/m2_classifier/training")
MANIFESTS_DIR = os.path.join(TRAINING_DIR, "manifests")
TRAIN_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "train_manifest.csv")
VAL_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "val_manifest.csv")

MODELS_DIR = os.path.join(PROJECT_ROOT, "backend/app/modules/m2_classifier/models/m2_classifier")
CHECKPOINT_PATH = os.path.join(MODELS_DIR, "m2_classifier.pth")

CLASS_TO_IDX = {cls_name: i for i, cls_name in enumerate(TARGET_CLASSES)}
IDX_TO_CLASS = {i: cls_name for i, cls_name in enumerate(TARGET_CLASSES)}

# Reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


class DocumentDataset(Dataset):
    """Dataset loading images specified in train/val manifests."""

    def __init__(self, manifest_path: str, transform=None):
        self.transform = transform
        self.samples: List[Tuple[str, int]] = []

        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                full_path = os.path.join(PROJECT_ROOT, row["path"])
                label_idx = CLASS_TO_IDX[row["class"]]
                self.samples.append((full_path, label_idx))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label


def get_transforms() -> Tuple[transforms.Compose, transforms.Compose]:
    """Builds preprocessing transforms matching DocumentClassifier runtime pipeline."""
    # Runtime normalization constants
    norm = transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    )

    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(p=0.3),
        transforms.ToTensor(),
        norm,
    ])

    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        norm,
    ])

    return train_transform, val_transform


def build_model(device: torch.device) -> nn.Module:
    """Builds MobileNetV3-Small with pretrained weights and 4-class head."""
    model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    in_features = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(in_features, len(TARGET_CLASSES))
    model.to(device)
    return model


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> Tuple[float, float]:
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for images, targets in loader:
        images, targets = images.to(device), targets.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, targets)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * images.size(0)
        _, preds = torch.max(outputs, 1)
        correct += (preds == targets).sum().item()
        total += targets.size(0)

    epoch_loss = running_loss / total
    epoch_acc = correct / total
    return epoch_loss, epoch_acc


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float, np.ndarray, np.ndarray]:
    model.eval()
    running_loss = 0.0
    all_preds: List[int] = []
    all_targets: List[int] = []

    for images, targets in loader:
        images, targets = images.to(device), targets.to(device)
        outputs = model(images)
        loss = criterion(outputs, targets)

        running_loss += loss.item() * images.size(0)
        _, preds = torch.max(outputs, 1)

        all_preds.extend(preds.cpu().numpy().tolist())
        all_targets.extend(targets.cpu().numpy().tolist())

    total = len(all_targets)
    val_loss = running_loss / total
    val_acc = np.mean(np.array(all_preds) == np.array(all_targets))
    return val_loss, float(val_acc), np.array(all_preds), np.array(all_targets)


def compute_metrics(targets: np.ndarray, preds: np.ndarray) -> Dict[str, Any]:
    """Computes per-class accuracy, precision, recall, F1, and 4x4 confusion matrix."""
    num_classes = len(TARGET_CLASSES)
    conf_matrix = np.zeros((num_classes, num_classes), dtype=int)

    for t, p in zip(targets, preds):
        conf_matrix[t, p] += 1

    per_class_metrics = {}
    precisions = []
    recalls = []
    f1s = []

    for idx, cls_name in enumerate(TARGET_CLASSES):
        tp = conf_matrix[idx, idx]
        fn = np.sum(conf_matrix[idx, :]) - tp
        fp = np.sum(conf_matrix[:, idx]) - tp
        total_cls = np.sum(conf_matrix[idx, :])

        acc = tp / total_cls if total_cls > 0 else 0.0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        precisions.append(prec)
        recalls.append(rec)
        f1s.append(f1)

        per_class_metrics[cls_name] = {
            "total": int(total_cls),
            "accuracy": float(acc),
            "precision": float(prec),
            "recall": float(rec),
            "f1": float(f1),
        }

    macro_prec = float(np.mean(precisions))
    macro_rec = float(np.mean(recalls))
    macro_f1 = float(np.mean(f1s))
    overall_acc = float(np.mean(targets == preds))

    return {
        "overall_accuracy": overall_acc,
        "macro_precision": macro_prec,
        "macro_recall": macro_rec,
        "macro_f1": macro_f1,
        "per_class": per_class_metrics,
        "confusion_matrix": conf_matrix,
    }


def main():
    print("=== M2 TRAINING TASK C: MOBILENETV3-SMALL DOCUMENT CLASSIFIER ===")

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Hardware Device: {device}")

    # Datasets and Loaders
    train_tf, val_tf = get_transforms()
    train_dataset = DocumentDataset(TRAIN_MANIFEST_PATH, transform=train_tf)
    val_dataset = DocumentDataset(VAL_MANIFEST_PATH, transform=val_tf)

    print(f"Loaded Train Dataset: {len(train_dataset)} images")
    print(f"Loaded Validation Dataset: {len(val_dataset)} images")

    batch_size = 32
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    # Model & Optimization
    model = build_model(device)
    criterion = nn.CrossEntropyLoss()
    learning_rate = 1e-4
    weight_decay = 1e-4
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    epochs = 10
    best_val_acc = 0.0
    best_epoch = 0
    best_preds: Optional[np.ndarray] = None
    best_targets: Optional[np.ndarray] = None
    best_state_dict = None

    start_time = time.time()
    print("\n--- Beginning Training Loop (10 Epochs) ---")
    print(f"{'Epoch':<8} {'Train Loss':<14} {'Train Acc':<12} {'Val Loss':<12} {'Val Acc':<12} {'Elapsed':<10}")
    print("-" * 70)

    for epoch in range(1, epochs + 1):
        ep_start = time.time()
        tr_loss, tr_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc, preds, targets = evaluate(model, val_loader, criterion, device)
        ep_time = time.time() - ep_start

        print(f"{epoch:<8} {tr_loss:<14.4f} {tr_acc * 100:<11.2f}% {val_loss:<12.4f} {val_acc * 100:<11.2f}% {ep_time:<9.1f}s")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            best_preds = preds
            best_targets = targets
            best_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}

    total_duration = time.time() - start_time
    print("-" * 70)
    print(f"Training completed in {total_duration:.1f}s. Best Epoch: {best_epoch} with Val Acc: {best_val_acc * 100:.2f}%\n")

    # Save Best Checkpoint
    os.makedirs(MODELS_DIR, exist_ok=True)
    assert best_state_dict is not None

    # Format: plain state_dict directly accepted by DocumentClassifier.load_model()
    torch.save(best_state_dict, CHECKPOINT_PATH)
    checkpoint_size_mb = os.path.getsize(CHECKPOINT_PATH) / (1024 * 1024)
    print(f"Saved Best Checkpoint to: {CHECKPOINT_PATH} ({checkpoint_size_mb:.2f} MB)")

    # Evaluate Best Checkpoint Metrics on Held-out Validation Set
    assert best_targets is not None and best_preds is not None
    metrics = compute_metrics(best_targets, best_preds)

    print("\n" + "=" * 65)
    print("FINAL HELD-OUT VALIDATION METRICS (BEST CHECKPOINT)")
    print("=" * 65)
    print(f"Overall Validation Accuracy: {metrics['overall_accuracy'] * 100:.2f}%")
    print(f"Macro Precision:             {metrics['macro_precision'] * 100:.2f}%")
    print(f"Macro Recall:                {metrics['macro_recall'] * 100:.2f}%")
    print(f"Macro F1 Score:              {metrics['macro_f1'] * 100:.2f}%\n")

    print(f"{'Class':<12} {'Total':<8} {'Accuracy':<12} {'Precision':<12} {'Recall':<12} {'F1':<10}")
    print("-" * 65)
    for cls_name, pm in metrics["per_class"].items():
        print(f"{cls_name:<12} {pm['total']:<8} {pm['accuracy']*100:<11.2f}% {pm['precision']*100:<11.2f}% {pm['recall']*100:<11.2f}% {pm['f1']*100:<9.2f}%")
    print("-" * 65)

    print("\n4x4 Confusion Matrix (Rows = Ground Truth, Columns = Predicted):")
    print("Class Order: [0: passport, 1: visa, 2: id_card, 3: unknown]")
    print(f"{'':<12} {'passport':<10} {'visa':<10} {'id_card':<10} {'unknown':<10}")
    for idx, cls_name in enumerate(TARGET_CLASSES):
        row_str = "  ".join(f"{metrics['confusion_matrix'][idx, c]:<8}" for c in range(4))
        print(f"{cls_name:<12} {row_str}")

    # Checkpoint Verification
    print("\n--- Checkpoint Verification & Safety Checks ---")
    runtime_classifier = DocumentClassifier(device="cpu")
    success = runtime_classifier.load_model(CHECKPOINT_PATH)
    assert success, "Failed to load checkpoint into DocumentClassifier!"
    print("1. Checkpoint successfully loaded into runtime DocumentClassifier: PASS")

    # Verify keys match runtime model
    rt_keys = set(runtime_classifier.model.state_dict().keys())
    saved_keys = set(best_state_dict.keys())
    assert rt_keys == saved_keys, "State dict keys mismatch!"
    print(f"2. State dict keys exact match ({len(saved_keys)} keys): PASS")

    # Verify output head dimensions
    head_weight = runtime_classifier.model.classifier[3].weight
    assert head_weight.shape == (4, 1024), f"Unexpected head shape: {head_weight.shape}"
    print(f"3. Output head shape is exactly (4, 1024) [4 target classes]: PASS")

    # Verify no NaN / Inf weights
    for name, param in runtime_classifier.model.named_parameters():
        assert not torch.isnan(param).any(), f"NaN found in {name}!"
        assert not torch.isinf(param).any(), f"Inf found in {name}!"
    print("4. Weights sanity check (zero NaN/Inf values): PASS")

    # Run direct inference sample
    dummy_input = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        out = runtime_classifier.model(dummy_input)
        probs = torch.softmax(out, dim=1).numpy()[0]
    assert len(probs) == 4, "Output probabilities shape mismatch!"
    print(f"5. Test forward pass successful. Output probabilities: {probs.round(4).tolist()}: PASS")

    print("\nTask C completed successfully!")


if __name__ == "__main__":
    main()
