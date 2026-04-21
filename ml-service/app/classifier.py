"""
Style classifier built on EfficientNet-B0 with a fine-tuned 8-class head.

If fine-tuned weights are available at settings.model_weights_path, they're
loaded into the model. Otherwise, the service falls back to a heuristic that
computes basic image statistics (brightness, saturation, contrast, warmth,
etc.) and maps them to the 8 style classes via hand-tuned rules — enough to
produce plausible outputs end-to-end while the real model is being trained.

Replace the heuristic by dropping a trained `.pth` into the weights dir.
"""
from __future__ import annotations

import io
import logging
import os
from typing import List, Tuple

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms
from torchvision.models import efficientnet_b0

from .config import settings

log = logging.getLogger(__name__)


class StyleClassifier:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.styles: List[str] = list(settings.styles)
        self.model: nn.Module | None = None
        self.use_heuristic: bool = True

        self._build_model()
        self._load_weights()

        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])

    def _build_model(self) -> None:
        model = efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Linear(in_features, len(self.styles))
        self.model = model.to(self.device).eval()

    def _load_weights(self) -> None:
        path = settings.model_weights_path
        if not path or not os.path.exists(path):
            log.warning(
                "Fine-tuned weights not found at %s — running in heuristic mode.",
                path,
            )
            return
        try:
            state = torch.load(path, map_location=self.device)
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            self.model.load_state_dict(state, strict=False)
            self.use_heuristic = False
            log.info("Loaded fine-tuned weights from %s", path)
        except Exception as e:
            log.exception("Failed to load weights (%s); staying in heuristic mode.", e)

    def predict(self, image_bytes: bytes) -> List[Tuple[str, float]]:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        if self.use_heuristic:
            scores = self._heuristic_scores(img)
        else:
            scores = self._nn_scores(img)

        pairs = list(zip(self.styles, scores))
        pairs.sort(key=lambda p: p[1], reverse=True)
        return pairs[: settings.top_k]

    def _nn_scores(self, img: Image.Image) -> List[float]:
        with torch.no_grad():
            x = self.transform(img).unsqueeze(0).to(self.device)
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()
        return [float(p) for p in probs]

    def _heuristic_scores(self, img: Image.Image) -> List[float]:
        """Hand-crafted scoring from basic image statistics.

        Returns a softmax-normalized score per style in `self.styles` order:
        [moody, minimalist, street, golden_hour, dark, airy, vintage, dramatic]
        """
        thumb = img.resize((224, 224))
        arr = np.asarray(thumb).astype(np.float32) / 255.0
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]

        brightness = float(arr.mean())
        contrast = float(arr.std())
        saturation = float((arr.max(axis=2) - arr.min(axis=2)).mean())
        warmth = float((r.mean() - b.mean()))
        max_channel = float(arr.max(axis=2).mean())
        min_channel = float(arr.min(axis=2).mean())
        dynamic_range = max_channel - min_channel

        raw = {
            "moody":       0.6 * (1.0 - brightness) + 0.4 * (1.0 - saturation),
            "minimalist":  0.5 * (1.0 - contrast) + 0.3 * (1.0 - saturation) + 0.2 * brightness,
            "street":      0.4 * contrast + 0.3 * (0.5 - abs(0.5 - brightness)) + 0.3 * (1.0 - warmth if warmth > 0 else 0.5),
            "golden_hour": 0.5 * max(warmth, 0.0) + 0.3 * brightness + 0.2 * saturation,
            "dark":        0.7 * (1.0 - brightness) + 0.3 * (1.0 - max_channel),
            "airy":        0.5 * brightness + 0.3 * (1.0 - contrast) + 0.2 * min_channel,
            "vintage":     0.4 * max(warmth, 0.0) + 0.3 * (1.0 - saturation) + 0.3 * (1.0 - contrast),
            "dramatic":    0.6 * contrast + 0.4 * dynamic_range,
        }

        vec = np.array([raw[name] for name in self.styles], dtype=np.float32)
        vec = vec - vec.max()
        exp = np.exp(vec * 3.0)
        probs = exp / exp.sum()
        return probs.tolist()
