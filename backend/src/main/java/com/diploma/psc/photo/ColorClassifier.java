package com.diploma.psc.photo;

import java.awt.Color;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Маппинг hex-цвета в одну из 9 цветовых семей через HSV.
 *
 * Семьи (по убыванию частоты в типичной фотографии):
 *   neutral (gray/black/white при S < 0.15)
 *   brown   (тёмный red/orange при V < 0.5)
 *   red, orange, yellow, green, blue, purple, pink — по hue-региону
 *
 * Используется для фильтрации фотографий в галерее по доминирующему цвету.
 * Принцип: на классификацию подаётся палитра (5 hex'ов) → каждый
 * маппится в семью → дубликаты убираются → результирующий список
 * хранится в photo_features.color_tags для быстрого поиска.
 */
public final class ColorClassifier {

    private ColorClassifier() {}

    public static final List<String> FAMILIES = List.of(
            "red", "orange", "yellow", "green", "blue",
            "purple", "pink", "brown", "neutral"
    );

    /** Маппит палитру в множество цветовых семей (по одной на каждый hex). */
    public static Set<String> classifyPalette(List<String> palette) {
        if (palette == null) return Set.of();
        Set<String> out = new LinkedHashSet<>();
        for (String hex : palette) {
            String family = classifyHex(hex);
            if (family != null) out.add(family);
        }
        return out;
    }

    /** Преобразует строку "#aabbcc" в одну из {@link #FAMILIES}. */
    public static String classifyHex(String hex) {
        if (hex == null || hex.length() < 7 || hex.charAt(0) != '#') return null;
        int r, g, b;
        try {
            r = Integer.parseInt(hex.substring(1, 3), 16);
            g = Integer.parseInt(hex.substring(3, 5), 16);
            b = Integer.parseInt(hex.substring(5, 7), 16);
        } catch (NumberFormatException e) {
            return null;
        }
        float[] hsv = Color.RGBtoHSB(r, g, b, null);
        float h = hsv[0] * 360f;
        float s = hsv[1];
        float v = hsv[2];

        // Низкая насыщенность — серый/чёрный/белый
        if (s < 0.15f) return "neutral";

        // Brown — тёмный warm hue (red/orange) с пониженной светлотой
        if (v < 0.55f && (h < 50f || h >= 350f)) return "brown";
        if (v < 0.45f && h < 70f) return "brown";

        if (h < 15f || h >= 345f) return "red";
        if (h < 45f) return "orange";
        if (h < 70f) return "yellow";
        if (h < 165f) return "green";
        if (h < 255f) return "blue";
        if (h < 290f) return "purple";
        if (h < 330f) return "pink";
        return "red";
    }
}
