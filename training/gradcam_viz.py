"""
E1 — Grad-CAM визуализация attention обученной модели.

Самодостаточная реализация Grad-CAM (Selvaraju et al., 2017) через PyTorch
hooks. Не требует `pytorch-grad-cam`.

Для каждого класса берёт N случайных изображений из val_set, считает
heatmap по последнему свёрточному блоку EfficientNet-B0, накладывает на
оригинал. Дополнительно — топ-K «уверенно неправильных» предсказаний.

Запуск:
  python gradcam_viz.py \\
    --weights ./out/efficientnet_b0_styles.pth \\
    --data-dir ./dataset \\
    --out-dir ./out/gradcam \\
    --per-class 6 \\
    --errors 10

Артефакты:
  out/gradcam/gradcam_{class}.png  — collage по 6 примеров на класс
  out/gradcam/gradcam_grid.png      — общий 8×6 grid
  out/gradcam/gradcam_errors.png    — топ-10 уверенно неправильных
  out/gradcam/notes.json            — метаданные по каждому изображению
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
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


class GradCAM:
    """Grad-CAM на произвольном свёрточном слое.

    Использование:
        cam = GradCAM(model, target_layer=model.features[-1])
        heatmap = cam(input_tensor, class_idx)   # (H, W) в [0, 1]
    """

    def __init__(self, model: nn.Module, target_layer: nn.Module):
        self.model = model
        self.activations: torch.Tensor | None = None
        self.gradients: torch.Tensor | None = None
        target_layer.register_forward_hook(self._save_activation)
        target_layer.register_full_backward_hook(self._save_gradient)

    def _save_activation(self, module, inp, out):
        self.activations = out.detach()

    def _save_gradient(self, module, grad_in, grad_out):
        self.gradients = grad_out[0].detach()

    def __call__(self, x: torch.Tensor, class_idx: int) -> np.ndarray:
        self.model.zero_grad()
        logits = self.model(x)
        score = logits[0, class_idx]
        score.backward()

        # Глобальное усреднение градиентов по пространственным осям -> веса каналов
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)   # (1, C, 1, 1)
        cam = (weights * self.activations).sum(dim=1, keepdim=True)  # (1, 1, H, W)
        cam = F.relu(cam)
        # До исходного размера изображения
        cam = F.interpolate(cam, size=x.shape[-2:], mode="bilinear", align_corners=False)
        cam = cam.squeeze().cpu().numpy()
        # Нормализация в [0, 1]
        if cam.max() > 0:
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
        return cam


def overlay_heatmap(image_pil: Image.Image, cam: np.ndarray, alpha: float = 0.45) -> Image.Image:
    """Накладывает Grad-CAM heatmap на исходное изображение."""
    import matplotlib.cm as mcm
    img = np.array(image_pil.convert("RGB").resize((224, 224))) / 255.0
    colored = mcm.get_cmap("jet")(cam)[:, :, :3]
    blended = (1 - alpha) * img + alpha * colored
    blended = np.clip(blended, 0, 1)
    return Image.fromarray((blended * 255).astype(np.uint8))


def build_collage(panels: list[tuple[Image.Image, str]], cols: int = 6,
                  cell_w: int = 224, cell_h: int = 224,
                  title_h: int = 24, gap: int = 8) -> Image.Image:
    """Собирает collage из (image, caption) панелей."""
    import math
    from PIL import ImageDraw, ImageFont
    rows = math.ceil(len(panels) / cols)
    W = cols * cell_w + (cols + 1) * gap
    H = rows * (cell_h + title_h) + (rows + 1) * gap
    canvas = Image.new("RGB", (W, H), (20, 20, 20))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    for i, (img, caption) in enumerate(panels):
        r, c = divmod(i, cols)
        x = gap + c * (cell_w + gap)
        y = gap + r * (cell_h + title_h + gap)
        canvas.paste(img.resize((cell_w, cell_h)), (x, y))
        draw.text((x + 4, y + cell_h + 4), caption, fill=(220, 220, 220), font=font)
    return canvas


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True, type=Path)
    p.add_argument("--data-dir", required=True, type=Path,
                   help="Корень датасета с подпапкой val/")
    p.add_argument("--out-dir", default=Path("./out/gradcam"), type=Path)
    p.add_argument("--per-class", type=int, default=6,
                   help="Сколько изображений визуализировать на каждый класс")
    p.add_argument("--errors", type=int, default=10,
                   help="Сколько топ-уверенно-неправильных предсказаний показать")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    eval_tf = build_eval_transform()
    val_ds = datasets.ImageFolder(args.data_dir / "val", transform=eval_tf)
    class_names = val_ds.classes
    print(f"Classes ({len(class_names)}): {class_names}")
    print(f"Val set: {len(val_ds)} images")

    model = load_model(args.weights, len(class_names), device)
    target_layer = model.features[-1]  # последний MBConv-блок
    cam_engine = GradCAM(model, target_layer)

    # --- 1. По N изображений на каждый класс ---
    by_class: dict[int, list[int]] = defaultdict(list)
    for idx, (_, label) in enumerate(val_ds.samples):
        by_class[label].append(idx)

    per_class_panels: dict[str, list[tuple[Image.Image, str]]] = {}
    all_notes = []

    for cls_idx, cls_name in enumerate(class_names):
        indices = by_class.get(cls_idx, [])
        sample = random.sample(indices, min(args.per_class, len(indices)))
        panels: list[tuple[Image.Image, str]] = []
        for img_idx in sample:
            img_path = val_ds.samples[img_idx][0]
            x_t = eval_tf(Image.open(img_path).convert("RGB")).unsqueeze(0).to(device)
            x_t.requires_grad_(True)
            heatmap = cam_engine(x_t, cls_idx)
            with torch.no_grad():
                probs = F.softmax(model(x_t), dim=1).cpu().numpy()[0]
            pred_idx = int(np.argmax(probs))
            overlay = overlay_heatmap(Image.open(img_path), heatmap)
            caption = (f"true={cls_name}  pred={class_names[pred_idx]}  "
                       f"conf={probs[pred_idx]:.2f}")
            panels.append((overlay, caption))
            all_notes.append({
                "image": str(Path(img_path).relative_to(args.data_dir)),
                "true_class": cls_name,
                "pred_class": class_names[pred_idx],
                "confidence": float(probs[pred_idx]),
                "kind": "per_class",
            })
        per_class_panels[cls_name] = panels
        collage = build_collage(panels, cols=args.per_class)
        out_path = args.out_dir / f"gradcam_{cls_name}.png"
        collage.save(out_path)
        print(f"  saved {out_path}")

    # Сводный 8×per_class grid
    flat_panels = []
    for cls_name in class_names:
        flat_panels.extend(per_class_panels[cls_name])
    grid = build_collage(flat_panels, cols=args.per_class)
    grid.save(args.out_dir / "gradcam_grid.png")
    print(f"  saved {args.out_dir / 'gradcam_grid.png'}")

    # --- 2. Топ-K «уверенно неправильных» предсказаний ---
    print("\nScanning for high-confidence misclassifications...")
    model.eval()
    misclassified: list[tuple[float, int, int, int]] = []  # (conf, idx, true, pred)
    with torch.no_grad():
        for img_idx in range(len(val_ds)):
            img_path, true_label = val_ds.samples[img_idx]
            x_t = eval_tf(Image.open(img_path).convert("RGB")).unsqueeze(0).to(device)
            probs = F.softmax(model(x_t), dim=1).cpu().numpy()[0]
            pred_idx = int(np.argmax(probs))
            if pred_idx != true_label:
                misclassified.append((float(probs[pred_idx]), img_idx, true_label, pred_idx))

    misclassified.sort(reverse=True)
    print(f"  found {len(misclassified)} misclassifications "
          f"(top conf: {misclassified[0][0]:.3f} if any)")

    error_panels: list[tuple[Image.Image, str]] = []
    for conf, img_idx, true_label, pred_idx in misclassified[: args.errors]:
        img_path = val_ds.samples[img_idx][0]
        x_t = eval_tf(Image.open(img_path).convert("RGB")).unsqueeze(0).to(device)
        x_t.requires_grad_(True)
        # heatmap по предсказанному классу — куда смотрела модель,
        # делая ОШИБКУ. Это и есть интересный артефакт.
        heatmap = cam_engine(x_t, pred_idx)
        overlay = overlay_heatmap(Image.open(img_path), heatmap)
        caption = (f"true={class_names[true_label]}  "
                   f"pred={class_names[pred_idx]}  conf={conf:.2f}")
        error_panels.append((overlay, caption))
        all_notes.append({
            "image": str(Path(img_path).relative_to(args.data_dir)),
            "true_class": class_names[true_label],
            "pred_class": class_names[pred_idx],
            "confidence": conf,
            "kind": "error",
        })

    if error_panels:
        err_collage = build_collage(error_panels, cols=min(5, args.errors))
        err_collage.save(args.out_dir / "gradcam_errors.png")
        print(f"  saved {args.out_dir / 'gradcam_errors.png'}")

    # --- 3. Метаданные ---
    (args.out_dir / "notes.json").write_text(
        json.dumps(all_notes, indent=2, ensure_ascii=False)
    )
    print(f"\nDone. Artifacts in {args.out_dir.resolve()}")


if __name__ == "__main__":
    main()
