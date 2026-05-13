"""
E2 — Извлечение embedding'ов + t-SNE/UMAP + метрики разделимости.

Прогоняет всю validation выборку через `model.features → avgpool → flatten`,
получает (N, 1280) embedding'ы. Считает silhouette / Davies-Bouldin / kNN-acc,
строит 2D-проекции (t-SNE, UMAP), считает матрицу cosine similarity между
центроидами классов.

Запуск:
  python embed_viz.py \\
    --weights ./out/efficientnet_b0_styles.pth \\
    --data-dir ./dataset \\
    --out-dir ./out/embed \\
    --split val \\
    --umap        # опционально (если стоит пакет umap-learn)

Артефакты:
  out/embed/embeddings.npy           — сырые векторы (N, 1280)
  out/embed/labels.npy               — метки (N,)
  out/embed/tsne.png                 — t-SNE 2D
  out/embed/umap.png                 — UMAP 2D (если запрошен)
  out/embed/metrics.json             — silhouette, Davies-Bouldin, kNN-acc
  out/embed/centroid_similarity.csv  — 8×8 cosine между центроидами
  out/embed/centroid_similarity.png  — её heatmap
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torchvision import datasets, transforms
from torchvision.models import efficientnet_b0

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_eval_transform():
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def load_model(weights_path: Path, num_classes: int, device: torch.device) -> nn.Module:
    m = efficientnet_b0(weights=None)
    in_f = m.classifier[1].in_features
    m.classifier[1] = nn.Linear(in_f, num_classes)
    state = torch.load(weights_path, map_location=device)
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    m.load_state_dict(state)
    m.eval().to(device)
    return m


def extract_embeddings(model: nn.Module, dataset, device: torch.device,
                       batch_size: int = 32):
    """Forward через features → avgpool → flatten; возвращает (N, 1280), (N,)."""
    from torch.utils.data import DataLoader
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=2)
    all_emb, all_y = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            feat = model.features(x)
            pooled = model.avgpool(feat).flatten(1)  # (B, 1280)
            all_emb.append(pooled.cpu().numpy())
            all_y.append(y.numpy())
    return np.concatenate(all_emb), np.concatenate(all_y)


def compute_metrics(emb: np.ndarray, y: np.ndarray) -> dict:
    """Silhouette + Davies-Bouldin + kNN-accuracy (cosine, k=5)."""
    from sklearn.metrics import silhouette_score, davies_bouldin_score
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.model_selection import cross_val_score

    # Нормируем для cosine
    emb_n = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12)

    sil = float(silhouette_score(emb_n, y, metric="cosine", sample_size=min(2000, len(emb))))
    db = float(davies_bouldin_score(emb_n, y))

    knn = KNeighborsClassifier(n_neighbors=5, metric="cosine")
    # 5-fold CV для честной оценки kNN-точности на этих эмбеддингах
    scores = cross_val_score(knn, emb_n, y, cv=5, scoring="accuracy")
    knn_acc = float(scores.mean())
    knn_std = float(scores.std())

    return {
        "silhouette_cosine": sil,
        "davies_bouldin": db,
        "knn5_accuracy_mean": knn_acc,
        "knn5_accuracy_std": knn_std,
        "n_samples": int(len(emb)),
        "embedding_dim": int(emb.shape[1]),
    }


def compute_centroid_similarity(emb: np.ndarray, y: np.ndarray,
                                class_names: list[str]) -> np.ndarray:
    """Cosine similarity между центроидами классов."""
    centroids = []
    for c in range(len(class_names)):
        centroids.append(emb[y == c].mean(axis=0))
    centroids = np.stack(centroids)
    norm = centroids / (np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-12)
    return norm @ norm.T


def plot_centroid_heatmap(sim: np.ndarray, class_names: list[str], out_path: Path):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(sim, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(class_names)))
    ax.set_yticks(range(len(class_names)))
    ax.set_xticklabels(class_names, rotation=45, ha="right")
    ax.set_yticklabels(class_names)
    for i in range(len(class_names)):
        for j in range(len(class_names)):
            ax.text(j, i, f"{sim[i, j]:.2f}", ha="center", va="center",
                    color="black" if abs(sim[i, j]) < 0.5 else "white", fontsize=8)
    fig.colorbar(im, ax=ax, fraction=0.046)
    ax.set_title("Cosine similarity между центроидами классов в embedding space")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_2d_scatter(coords: np.ndarray, y: np.ndarray,
                    class_names: list[str], title: str, out_path: Path):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 7))
    cmap = plt.get_cmap("tab10", len(class_names))
    for c in range(len(class_names)):
        mask = y == c
        ax.scatter(coords[mask, 0], coords[mask, 1], s=12, alpha=0.7,
                   color=cmap(c), label=class_names[c], edgecolors="none")
    ax.legend(loc="upper right", fontsize=9, frameon=False)
    ax.set_title(title)
    ax.set_xlabel("dim 1")
    ax.set_ylabel("dim 2")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True, type=Path)
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--out-dir", default=Path("./out/embed"), type=Path)
    p.add_argument("--split", default="val", choices=["train", "val"])
    p.add_argument("--umap", action="store_true",
                   help="Дополнительно посчитать UMAP (нужен пакет umap-learn)")
    p.add_argument("--tsne-perplexity", type=float, default=30.0)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    eval_tf = build_eval_transform()
    ds = datasets.ImageFolder(args.data_dir / args.split, transform=eval_tf)
    class_names = ds.classes
    print(f"Classes: {class_names}")
    print(f"Split '{args.split}': {len(ds)} images")

    model = load_model(args.weights, len(class_names), device)

    print("Extracting embeddings...")
    emb, y = extract_embeddings(model, ds, device)
    np.save(args.out_dir / "embeddings.npy", emb)
    np.save(args.out_dir / "labels.npy", y)
    print(f"  emb shape: {emb.shape}, labels: {y.shape}")

    print("Computing separability metrics...")
    metrics = compute_metrics(emb, y)
    metrics["class_names"] = class_names
    (args.out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"  silhouette={metrics['silhouette_cosine']:.3f}, "
          f"DB={metrics['davies_bouldin']:.3f}, "
          f"kNN5-acc={metrics['knn5_accuracy_mean']:.3f}±{metrics['knn5_accuracy_std']:.3f}")

    print("Computing centroid similarity matrix...")
    sim = compute_centroid_similarity(emb, y, class_names)
    np.savetxt(args.out_dir / "centroid_similarity.csv", sim, fmt="%.4f",
               delimiter=",", header=",".join(class_names), comments="")
    plot_centroid_heatmap(sim, class_names, args.out_dir / "centroid_similarity.png")

    print("Running t-SNE...")
    from sklearn.manifold import TSNE
    tsne = TSNE(n_components=2, perplexity=args.tsne_perplexity,
                init="pca", learning_rate="auto", random_state=args.seed)
    tsne_xy = tsne.fit_transform(emb)
    plot_2d_scatter(tsne_xy, y, class_names,
                    f"t-SNE (perplexity={args.tsne_perplexity:g}) — fine-tuned EfficientNet-B0 embeddings",
                    args.out_dir / "tsne.png")

    if args.umap:
        try:
            import umap  # noqa
            print("Running UMAP...")
            reducer = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1,
                                random_state=args.seed)
            umap_xy = reducer.fit_transform(emb)
            plot_2d_scatter(umap_xy, y, class_names,
                            "UMAP (n_neighbors=15, min_dist=0.1) — fine-tuned EfficientNet-B0",
                            args.out_dir / "umap.png")
        except ImportError:
            print("  umap-learn не установлен, пропускаю (pip install umap-learn)")

    print(f"\nDone. Artifacts in {args.out_dir.resolve()}")


if __name__ == "__main__":
    main()
