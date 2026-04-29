package com.diploma.psc.photo;

import com.diploma.psc.auth.UserDetailsServiceImpl.AuthUser;
import com.diploma.psc.photo.dto.PhotoResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

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

    @GetMapping
    public ResponseEntity<Page<PhotoResponse>> list(@AuthenticationPrincipal AuthUser principal,
                                                    @RequestParam(defaultValue = "0") int page,
                                                    @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(photoService.list(principal, page, size));
    }

    @GetMapping("/search")
    public ResponseEntity<Page<PhotoResponse>> search(@AuthenticationPrincipal AuthUser principal,
                                                      @RequestParam String style,
                                                      @RequestParam(defaultValue = "0.2") double minConfidence,
                                                      @RequestParam(defaultValue = "0") int page,
                                                      @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(photoService.searchByStyle(principal, style, minConfidence, page, size));
    }
}
