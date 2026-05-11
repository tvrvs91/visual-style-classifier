"""
Style classifier на EfficientNet-B0 + расширенный визуальный анализ.

КЛЮЧЕВАЯ ML-ФИЧА — извлечение 1280-мерных эмбеддингов из предпоследнего
слоя (после global average pooling, перед классифицирующей головой).
Эти векторные представления используются backend'ом для поиска визуально
похожих фотографий через cosine similarity — это значительно точнее, чем
поиск по совпадению тегов: модель оценивает не категорию, а полное
вложение изображения в выученное пространство визуальных стилей.

Дополнительно (без обучения, чисто детерминированный анализ пикселей):
- Color palette: 5 доминирующих цветов через k-means над пиксельным простр.
- Score card: brightness / contrast / saturation / warmth / sharpness — 5
  количественных метрик для расширенной семантической характеристики кадра.
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
from sklearn.cluster import KMeans
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

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])
        self.tta_transform = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.RandomCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225]),
        ])

    # ---------- model setup ------------------------------------------------

    def _build_model(self) -> None:
        model = efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features  # 1280
        model.classifier[1] = nn.Linear(in_features, len(self.styles))
        self.model = model.to(self.device).eval()

    def _resolve_weights_path(self) -> Optional[str]:
        canonical = settings.model_weights_path
        if canonical and os.path.exists(canonical):
            return canonical
        weights_dir = Path(settings.weights_dir)
        if not weights_dir.is_dir():
            return None
        candidates = sorted(weights_dir.glob("*.pth"))
        if not candidates:
            return None
        prioritized = [p for p in candidates if p.name.startswith("efficientnet_b0_styles")]
        return str((prioritized or candidates)[0])

    def _load_weights(self) -> None:
        path = self._resolve_weights_path()
        if not path:
            log.warning("Fallback: heuristic mode (no .pth in %s)", settings.weights_dir)
            return
        try:
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

    # ---------- основной публичный API ------------------------------------

    def analyze(self, image_bytes: bytes) -> dict:
        """Полный анализ изображения: стили + embedding + палитра + scores."""
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        if self.use_heuristic:
            style_scores = self._heuristic_scores(img)
            embedding: Optional[List[float]] = None
        else:
            style_scores, embedding = self._nn_inference(img)

        pairs = sorted(zip(self.styles, style_scores), key=lambda p: p[1], reverse=True)
        top_styles = [(name, conf) for name, conf in pairs[: settings.top_k]]

        return {
            "styles": top_styles,
            "embedding": embedding,
            "palette": self._extract_palette(img),
            "scores": self._compute_scores(img),
        }

    def predict(self, image_bytes: bytes) -> List[Tuple[str, float]]:
        """Backward-compat: только top-k стилей."""
        return self.analyze(image_bytes)["styles"]

    # ---------- нейросетевой проход с эмбеддингом -------------------------

    def _nn_inference(self, img: Image.Image) -> Tuple[List[float], List[float]]:
        """Прогон через EfficientNet с извлечением эмбеддинга предпоследнего слоя.

        Возвращает (softmax-вероятности по классам, 1280-мерный embedding).
        В TTA-режиме softmax усредняется по аугментациям; embedding берётся
        с основного прохода без аугментаций (детерминированно).
        """
        with torch.no_grad():
            x = self.transform(img).unsqueeze(0).to(self.device)

            # Расщепляем forward на backbone + head, чтобы извлечь pooled features.
            # EfficientNet structure: features → avgpool → classifier (Dropout + Linear)
            feats = self.model.features(x)
            pooled = self.model.avgpool(feats)
            pooled_flat = torch.flatten(pooled, 1)        # [1, 1280] — это эмбеддинг
            logits = self.model.classifier(pooled_flat)   # [1, num_classes]

            if settings.use_tta and settings.tta_passes > 1:
                probs = self._tta_softmax(img, base_logits=logits)
            else:
                probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()

            embedding = pooled_flat.squeeze(0).cpu().numpy()

        return [float(p) for p in probs], [float(v) for v in embedding]

    def _tta_softmax(self, img: Image.Image, base_logits: torch.Tensor) -> np.ndarray:
        """Усреднение softmax по N аугментациям. Используется только если включён TTA."""
        passes = [torch.softmax(base_logits, dim=1)]
        x = self.transform(img).unsqueeze(0).to(self.device)
        passes.append(torch.softmax(self.model(torch.flip(x, dims=[3])), dim=1))
        for _ in range(max(0, settings.tta_passes - 2)):
            x_aug = self.tta_transform(img).unsqueeze(0).to(self.device)
            passes.append(torch.softmax(self.model(x_aug), dim=1))
        return torch.stack(passes).mean(dim=0).squeeze(0).cpu().numpy()

    # ---------- цветовая палитра через k-means ---------------------------

    def _extract_palette(self, img: Image.Image, k: int = 5) -> List[str]:
        """K-means кластеризация в RGB-пространстве, возврат k доминирующих цветов в hex.

        Кластеры отсортированы по размеру (самый частый цвет первым).
        """
        small = img.resize((100, 100))
        arr = np.asarray(small).reshape(-1, 3).astype(np.float32)
        try:
            km = KMeans(n_clusters=k, n_init=3, random_state=42).fit(arr)
            centers = km.cluster_centers_.astype(int)
            counts = np.bincount(km.labels_, minlength=k)
            order = np.argsort(-counts)
            return ["#{:02x}{:02x}{:02x}".format(*centers[i]) for i in order]
        except Exception as e:
            log.warning("Palette extraction failed: %s", e)
            return []

    # ---------- score card (5 количественных метрик) ---------------------

    def _compute_scores(self, img: Image.Image) -> dict:
        """Детерминированные характеристики изображения, дополняющие стили.

        Все значения в [0, 1].
        - brightness: средняя яркость по perceptual luma (Y' = 0.299R + 0.587G + 0.114B)
        - contrast: std яркости, нормированный к [0,1] (выше = больше тоновой динамики)
        - saturation: средняя насыщенность как (max-min)/max в RGB
        - warmth: смещение R относительно B; >0.5 — тёплый, <0.5 — холодный
        - sharpness: средняя величина градиента яркости — proxy для детализации/резкости
        """
        arr = np.asarray(img.resize((224, 224))).astype(np.float32) / 255.0
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        luma = 0.299 * r + 0.587 * g + 0.114 * b

        brightness = float(luma.mean())
        contrast = float(min(luma.std() * 2.0, 1.0))

        mx = arr.max(axis=2)
        mn = arr.min(axis=2)
        sat = np.where(mx > 1e-6, (mx - mn) / mx, 0.0)
        saturation = float(sat.mean())

        warmth = float(np.clip(((r - b).mean() + 1.0) / 2.0, 0.0, 1.0))

        gx = float(np.abs(np.diff(luma, axis=1)).mean())
        gy = float(np.abs(np.diff(luma, axis=0)).mean())
        sharpness = float(min((gx + gy) * 5.0, 1.0))

        return {
            "brightness": round(brightness, 3),
            "contrast": round(contrast, 3),
            "saturation": round(saturation, 3),
            "warmth": round(warmth, 3),
            "sharpness": round(sharpness, 3),
        }

    # ---------- эвристика (fallback когда нет .pth) ----------------------

    def _heuristic_scores(self, img: Image.Image) -> List[float]:
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
            "golden_hour": 0.5 * max(warmth, 0.0) + 0.3 * brightness + 0.2 * saturation,
            "dark":        0.7 * (1.0 - brightness) + 0.3 * (1.0 - max_channel),
            "airy":        0.5 * brightness + 0.3 * (1.0 - contrast) + 0.2 * min_channel,
            "vintage":     0.4 * max(warmth, 0.0) + 0.3 * (1.0 - saturation) + 0.3 * (1.0 - contrast),
            "dramatic":    0.6 * contrast + 0.4 * dynamic_range,
        }
        # Заполняем нулями для классов которых нет в эвристике
        vec = np.array([raw.get(name, 0.0) for name in self.styles], dtype=np.float32)
        vec = vec - vec.max()
        exp = np.exp(vec * 3.0)
        probs = exp / exp.sum()
        return probs.tolist()

    # ---------- service info ---------------------------------------------

    def info(self) -> dict:
        return {
            "model": "efficientnet_b0" if not self.use_heuristic else "heuristic",
            "weights_path": self.weights_path,
            "device": str(self.device),
            "styles": self.styles,
            "top_k": settings.top_k,
            "tta": settings.use_tta and settings.tta_passes > 1,
            "tta_passes": settings.tta_passes if settings.use_tta else 1,
            "embedding_dim": 1280 if not self.use_heuristic else None,
        }
