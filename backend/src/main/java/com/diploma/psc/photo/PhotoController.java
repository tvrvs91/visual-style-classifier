package com.diploma.psc.photo;

import com.diploma.psc.auth.UserDetailsServiceImpl.AuthUser;
import com.diploma.psc.photo.dto.PhotoResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/photos")
@RequiredArgsConstructor
public class PhotoController {

    private final PhotoService photoService;

    @PostMapping(consumes = "multipart/form-data")
    public ResponseEntity<PhotoResponse> upload(@RequestPart("file") MultipartFile file,
                                                @AuthenticationPrincipal AuthUser principal) {
        return ResponseEntity.ok(photoService.upload(file, principal));
    }

    @GetMapping("/{id}")
    public ResponseEntity<PhotoResponse> get(@PathVariable Long id,
                                             @AuthenticationPrincipal AuthUser principal) {
        return ResponseEntity.ok(photoService.get(id, principal));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id,
                                       @AuthenticationPrincipal AuthUser principal) {
        photoService.delete(id, principal);
        return ResponseEntity.noContent().build();
    }

    /**
     * Embedding-based поиск похожих фотографий — использует cosine similarity
     * в 1280-мерном пространстве признаков EfficientNet-B0. Точнее чем
     * tag-based search (которая всё ещё доступна через /search?style=...).
     */
    @GetMapping("/{id}/similar")
    public ResponseEntity<List<PhotoResponse>> similar(@PathVariable Long id,
                                                       @RequestParam(defaultValue = "6") int limit,
                                                       @AuthenticationPrincipal AuthUser principal) {
        return ResponseEntity.ok(photoService.similar(id, principal, limit));
    }

    @GetMapping
    public ResponseEntity<Page<PhotoResponse>> list(@AuthenticationPrincipal AuthUser principal,
                                                    @RequestParam(defaultValue = "0") int page,
                                                    @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(photoService.list(principal, page, size));
    }

    @GetMapping("/search")
    public ResponseEntity<Page<PhotoResponse>> search(@AuthenticationPrincipal AuthUser principal,
                                                      @RequestParam(required = false) String style,
                                                      @RequestParam(required = false) String color,
                                                      @RequestParam(defaultValue = "0.2") double minConfidence,
                                                      @RequestParam(defaultValue = "0") int page,
                                                      @RequestParam(defaultValue = "20") int size) {
        // Один эндпоинт-универсал: либо style, либо color (приоритет: style).
        // Для фильтра по обоим одновременно нужен JPA-Specification — оставлено
        // как future work, на текущем UI используются как взаимоисключающие.
        if (style != null && !style.isBlank()) {
            return ResponseEntity.ok(photoService.searchByStyle(principal, style, minConfidence, page, size));
        }
        if (color != null && !color.isBlank()) {
            return ResponseEntity.ok(photoService.searchByColor(principal, color, page, size));
        }
        throw new IllegalArgumentException("Either 'style' or 'color' query parameter is required");
    }

    /** Доступные цветовые семьи для фильтра — фронт строит из этого UI. */
    @GetMapping("/colors")
    public ResponseEntity<List<String>> colors() {
        return ResponseEntity.ok(ColorClassifier.FAMILIES);
    }
}
