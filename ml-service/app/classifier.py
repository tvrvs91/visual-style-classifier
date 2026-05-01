"""
Style classifier on EfficientNet-B0 with a 8-class fine-tuned head.

При старте сервис ищет дообученные веса:
1. По каноничному пути ``settings.model_weights_path``
   (``/app/weights/efficientnet_b0_styles.pth`` по умолчанию).
2. Если файла нет — берёт первый ``*.pth`` в ``settings.weights_dir``,
   с приоритетом имён, содержащих ``efficientnet_b0_styles``.
3. Если не нашлось ничего — переходит в эвристический режим (image-stats
   эвристика по яркости/контрасту/насыщенности/теплоте).

Важно: индекс класса в выходе модели соответствует порядку
``settings.styles`` (алфавитный — airy, dark, dramatic, golden_hour,
minimalist, moody, street, vintage). При обучении на стороне Colab
порядок классов должен быть таким же.
"""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

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
        self.model: Optional[nn.Module] = None
        self.use_heuristic: bool = True
        self.weights_path: Optional[str] = None

        self._build_model()
        self._load_weights()

        # Жёсткий resize 224x224 (без CenterCrop), нормализация ImageNet.
        # Совпадает с тем, что используется в training-скрипте.
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])

    def _build_model(self) -> None:
        model = efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features  # 1280
        model.classifier[1] = nn.Linear(in_features, len(self.styles))
        self.model = model.to(self.device).eval()

    def _resolve_weights_path(self) -> Optional[str]:
        """Найти .pth-файл с весами. Возвращает абсолютный путь или None."""
        canonical = settings.model_weights_path
        if canonical and os.path.exists(canonical):
            return canonical

        weights_dir = Path(settings.weights_dir)
        if not weights_dir.is_dir():
            return None

        candidates = sorted(weights_dir.glob("*.pth"))
        if not candidates:
            return None

        # Приоритет именам, начинающимся с "efficientnet_b0_styles".
        prioritized = [p for p in candidates if p.name.startswith("efficientnet_b0_styles")]
        chosen = (prioritized or candidates)[0]
        return str(chosen)

    def _load_weights(self) -> None:
        path = self._resolve_weights_path()
        if not path:
            log.warning(
                "Fallback: heuristic mode (no .pth in %s)",
                settings.weights_dir,
            )
            return

        try:
            # weights_only=False нужен, если в .pth сохранён весь объект модели,
            # а не только state_dict. Файл локальный и доверенный — допустимо.
            state = torch.load(path, map_location=self.device, weights_only=False)

            if isinstance(state, nn.Module):
                state = state.state_dict()
            elif isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]

            missing, unexpected = self.model.load_state_dict(state, strict=False)
            self.use_heuristic = False
            self.weights_path = path

            log.info("Model loaded: EfficientNet-B0 (weights from %s)", path)
            if missing:
                log.info("  missing keys (random-init): %s", list(missing))
            if unexpected:
                log.info("  unexpected keys (ignored): %s", list(unexpected))
        except Exception as e:
            log.exception("Failed to load weights from %s — staying in heuristic mode: %s", path, e)

    def predict(self, image_bytes: bytes) -> List[Tuple[str, float]]:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        scores = self._heuristic_scores(img) if self.use_heuristic else self._nn_scores(img)
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
        """Hand-crafted scoring — fallback, когда нет fine-tuned весов."""
        thumb = img.resize((224, 224))
        arr = np.asarray(thumb).astype(np.float32) / 255.0
        r, _, b = arr[..., 0], arr[..., 1], arr[..., 2]

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
            "street":      0.4 * contrast + 0.3 * (0.5 - abs(0.5 - brightness)) + 0.3 * (1.0 - max(warmth, 0.0)),
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

    def info(self) -> dict:
        return {
            "model": "efficientnet_b0" if not self.use_heuristic else "heuristic",
            "weights_path": self.weights_path,
            "device": str(self.device),
            "styles": self.styles,
            "top_k": settings.top_k,
        }
