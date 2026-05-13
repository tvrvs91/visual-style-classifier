"""
E5 — CLIP linear-probe и zero-shot classification.

Сравниваем три подхода:
  1. EfficientNet-B0 fine-tune (baseline, v3, val_acc ≈ 0.726)
  2. CLIP ViT-B/32 image embeddings + sklearn LogisticRegression (linear probe)
  3. CLIP zero-shot через текстовые prompts «a {style} photo»

Используем `open_clip` (open-source реализация CLIP с одинаковым API).
Если он не установлен — пытаемся transformers.CLIPModel.

Запуск:
  pip install open_clip_torch
  python clip_probe.py \\
    --data-dir ./dataset \\
    --out-dir ./out/clip \\
    --model ViT-B-32 \\
    --pretrained openai

Артефакты:
  out/clip/linear_probe_metrics.json
  out/clip/zero_shot_metrics.json
  out/clip/confusion_matrix_lp.png
  out/clip/confusion_matrix_zs.png
  out/clip/comparison_table.csv
  out/clip/clip_embeddings.npy
  out/clip/clip_labels.npy
  out/clip/tsne_clip.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image


CLASS_PROMPTS = {
    # Несколько вариантов prompt'а на класс (усреднение text embedding'ов
    # уменьшает дисперсию zero-shot).
    "airy": [
        "an airy bright photograph", "a soft pastel light photo",
        "a light high-key photograph",
    ],
    "dark": [
        "a dark moody photograph with deep shadows", "a low-light photograph",
        "a photo with predominantly dark tones",
    ],
    "dramatic": [
        "a dramatic high-contrast photograph",
        "a cinematic photo with strong chiaroscuro lighting",
        "a photo with intense light and shadow",
    ],
    "golden_hour": [
        "a golden hour photograph with warm sunlight",
        "a photo taken at sunset with golden light",
        "a warm orange-toned photograph",
    ],
    "minimalist": [
        "a minimalist photograph with negative space",
        "a photo with a single subject and lots of empty space",
        "a clean minimal composition",
    ],
    "monochrome": [
        "a black and white photograph",
        "a monochrome grayscale photo",
        "a desaturated photograph without color",
    ],
    "neon": [
        "a neon-lit photograph with vibrant colors",
        "a cyberpunk neon photograph at night",
        "a photo with bright neon lights",
    ],
    "vintage": [
        "a vintage photograph with film grain",
        "a retro nostalgic photograph",
        "an old-fashioned faded photo",
    ],
}


def load_clip(model_name: str, pretrained: str, device: torch.device):
    """Грузит CLIP через open_clip (или fallback на transformers)."""
    try:
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained, device=device)
        tokenizer = open_clip.get_tokenizer(model_name)
        model.eval()
        backend = "open_clip"
    except ImportError:
        from transformers import CLIPModel, CLIPProcessor
        hub = "openai/clip-vit-base-patch32"
        model = CLIPModel.from_pretrained(hub).to(device).eval()
        processor = CLIPProcessor.from_pretrained(hub)
        preprocess = lambda img: processor(images=img, return_tensors="pt")["pixel_values"][0]
        tokenizer = lambda texts: processor(text=texts, return_tensors="pt", padding=True)
        backend = "transformers"
    return model, preprocess, tokenizer, backend


def encode_images(model, preprocess, dataset, device, backend, batch_size: int = 32):
    from torch.utils.data import DataLoader
    embs, labs = [], []

    def collate(batch):
        imgs = [preprocess(item[0]) for item in batch]
        return torch.stack(imgs), torch.tensor([item[1] for item in batch])

    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False,
                        num_workers=0, collate_fn=collate)
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            if backend == "open_clip":
                feats = model.encode_image(x)
            else:  # transformers
                feats = model.get_image_features(pixel_values=x)
            feats = feats / feats.norm(dim=-1, keepdim=True)
            embs.append(feats.cpu().numpy())
            labs.append(y.numpy())
    return np.concatenate(embs), np.concatenate(labs)


def encode_text_prompts(model, tokenizer, prompts: list[str], device, backend):
    with torch.no_grad():
        if backend == "open_clip":
            tokens = tokenizer(prompts).to(device)
            feats = model.encode_text(tokens)
        else:
            inputs = tokenizer(prompts)
            inputs = {k: v.to(device) for k, v in inputs.items()}
            feats = model.get_text_features(**inputs)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy()


class ImageFolderRaw:
    """ImageFolder который возвращает PIL.Image, без torchvision-transform,
    чтобы CLIP-preprocess мог обработать сам."""

    def __init__(self, root: Path):
        from torchvision import datasets
        self.ds = datasets.ImageFolder(root)
        self.classes = self.ds.classes

    def __len__(self):
        return len(self.ds)

    def __getitem__(self, i):
        path, label = self.ds.samples[i]
        return Image.open(path).convert("RGB"), label


def plot_confusion(cm: np.ndarray, class_names: list[str], title: str, out_path: Path):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(cm, cmap="Reds")
    ax.set_xticks(range(len(class_names)))
    ax.set_yticks(range(len(class_names)))
    ax.set_xticklabels(class_names, rotation=45, ha="right")
    ax.set_yticklabels(class_names)
    ax.set_xlabel("Predicted"); ax.set_ylabel("True")
    for i in range(len(class_names)):
        for j in range(len(class_names)):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=9)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--out-dir", default=Path("./out/clip"), type=Path)
    p.add_argument("--model", default="ViT-B-32")
    p.add_argument("--pretrained", default="openai")
    args = p.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    print(f"Loading CLIP {args.model} ({args.pretrained})...")
    model, preprocess, tokenizer, backend = load_clip(args.model, args.pretrained, device)
    print(f"  backend: {backend}")

    train_ds = ImageFolderRaw(args.data_dir / "train")
    val_ds = ImageFolderRaw(args.data_dir / "val")
    class_names = val_ds.classes
    assert train_ds.classes == val_ds.classes, "train/val classes mismatch"
    print(f"Classes: {class_names}")

    print("Encoding train images via CLIP...")
    X_tr, y_tr = encode_images(model, preprocess, train_ds, device, backend)
    print(f"  train embeddings: {X_tr.shape}")

    print("Encoding val images via CLIP...")
    X_va, y_va = encode_images(model, preprocess, val_ds, device, backend)
    print(f"  val embeddings: {X_va.shape}")

    np.save(args.out_dir / "clip_embeddings_train.npy", X_tr)
    np.save(args.out_dir / "clip_embeddings_val.npy", X_va)
    np.save(args.out_dir / "clip_labels_train.npy", y_tr)
    np.save(args.out_dir / "clip_labels_val.npy", y_va)

    # --- Linear probe -------------------------------------------------------
    print("\nLinear probe (sklearn LogisticRegression on CLIP embeddings)...")
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (accuracy_score, f1_score,
                                 classification_report, confusion_matrix)

    clf = LogisticRegression(C=1.0, max_iter=2000, n_jobs=-1)
    clf.fit(X_tr, y_tr)
    pred_lp = clf.predict(X_va)

    lp_metrics = {
        "accuracy": float(accuracy_score(y_va, pred_lp)),
        "macro_f1": float(f1_score(y_va, pred_lp, average="macro")),
        "weighted_f1": float(f1_score(y_va, pred_lp, average="weighted")),
        "per_class": classification_report(y_va, pred_lp, target_names=class_names,
                                           output_dict=True, zero_division=0),
    }
    (args.out_dir / "linear_probe_metrics.json").write_text(
        json.dumps(lp_metrics, indent=2, ensure_ascii=False))
    print(f"  acc={lp_metrics['accuracy']:.4f}  macro_F1={lp_metrics['macro_f1']:.4f}  "
          f"weighted_F1={lp_metrics['weighted_f1']:.4f}")
    plot_confusion(confusion_matrix(y_va, pred_lp), class_names,
                   "CLIP linear probe confusion matrix",
                   args.out_dir / "confusion_matrix_lp.png")

    # --- Zero-shot ---------------------------------------------------------
    print("\nZero-shot via text prompts...")
    text_centroids = []
    for cls in class_names:
        prompts = CLASS_PROMPTS.get(cls, [f"a {cls} photo"])
        text_feats = encode_text_prompts(model, tokenizer, prompts, device, backend)
        text_centroids.append(text_feats.mean(axis=0))
    text_centroids = np.stack(text_centroids)
    text_centroids = text_centroids / np.linalg.norm(text_centroids, axis=1, keepdims=True)

    sim = X_va @ text_centroids.T  # (N_val, n_classes)
    pred_zs = sim.argmax(axis=1)

    zs_metrics = {
        "accuracy": float(accuracy_score(y_va, pred_zs)),
        "macro_f1": float(f1_score(y_va, pred_zs, average="macro")),
        "weighted_f1": float(f1_score(y_va, pred_zs, average="weighted")),
        "per_class": classification_report(y_va, pred_zs, target_names=class_names,
                                           output_dict=True, zero_division=0),
    }
    (args.out_dir / "zero_shot_metrics.json").write_text(
        json.dumps(zs_metrics, indent=2, ensure_ascii=False))
    print(f"  acc={zs_metrics['accuracy']:.4f}  macro_F1={zs_metrics['macro_f1']:.4f}")
    plot_confusion(confusion_matrix(y_va, pred_zs), class_names,
                   "CLIP zero-shot confusion matrix",
                   args.out_dir / "confusion_matrix_zs.png")

    # --- Embedding viz -----------------------------------------------------
    print("\nt-SNE on CLIP embeddings (val)...")
    from sklearn.manifold import TSNE
    coords = TSNE(n_components=2, perplexity=30, init="pca",
                  learning_rate="auto", random_state=42).fit_transform(X_va)
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 7))
    cmap = plt.get_cmap("tab10", len(class_names))
    for c, name in enumerate(class_names):
        mask = y_va == c
        ax.scatter(coords[mask, 0], coords[mask, 1], s=12, alpha=0.7,
                   color=cmap(c), label=name, edgecolors="none")
    ax.legend(loc="upper right", fontsize=9, frameon=False)
    ax.set_title(f"t-SNE of CLIP {args.model} embeddings (val_set)")
    fig.tight_layout()
    fig.savefig(args.out_dir / "tsne_clip.png", dpi=140)
    plt.close(fig)

    # --- Comparison summary ------------------------------------------------
    summary = [
        {"method": "EfficientNet-B0 fine-tune (v3)", "accuracy": 0.726,
         "macro_f1": 0.718, "size_mb": 16,
         "training_required": "yes (2-phase fine-tune ~30 min T4)"},
        {"method": f"CLIP {args.model} linear probe", "accuracy": lp_metrics["accuracy"],
         "macro_f1": lp_metrics["macro_f1"], "size_mb": 350,
         "training_required": "only sklearn logreg (<1 min CPU)"},
        {"method": f"CLIP {args.model} zero-shot", "accuracy": zs_metrics["accuracy"],
         "macro_f1": zs_metrics["macro_f1"], "size_mb": 350,
         "training_required": "none"},
    ]
    import csv
    with (args.out_dir / "comparison_table.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    print("\n=== Comparison ===")
    for row in summary:
        print(f"  {row['method']:38s}  acc={row['accuracy']:.4f}  "
              f"macro_F1={row['macro_f1']:.4f}  size={row['size_mb']:>4}MB")
    print(f"\nDone. Artifacts in {args.out_dir.resolve()}")


if __name__ == "__main__":
    main()
