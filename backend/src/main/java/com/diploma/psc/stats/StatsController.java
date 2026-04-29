package com.diploma.psc.stats;

import com.diploma.psc.auth.UserDetailsServiceImpl.AuthUser;
import com.diploma.psc.photo.PhotoRepository;
import com.diploma.psc.photo.PhotoStatus;
import com.diploma.psc.user.User;
import com.diploma.psc.user.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/stats")
@RequiredArgsConstructor
public class StatsController {

    private final UserRepository userRepository;
    private final PhotoRepository photoRepository;

    @GetMapping("/me")
    public ResponseEntity<StatsResponse> me(@AuthenticationPrincipal AuthUser principal) {
        User user = userRepository.findById(principal.getUserId())
                .orElseThrow(() -> new IllegalStateException("User not found"));

        long total = photoRepository.countByUserId(user.getId());

        Map<PhotoStatus, Long> byStatus = new EnumMap<>(PhotoStatus.class);
        for (PhotoStatus s : PhotoStatus.values()) byStatus.put(s, 0L);
        photoRepository.countByStatusForUser(user.getId())
                .forEach(r -> byStatus.put(r.getStatus(), r.getTotal()));

        List<StatsResponse.StyleCount> topStyles = photoRepository.topStylesByUser(user.getId()).stream()
                .map(r -> new StatsResponse.StyleCount(
                        r.getName(),
                        r.getTotal(),
                        r.getAvgConf() != null ? r.getAvgConf() : 0.0))
                .toList();

        return ResponseEntity.ok(new StatsResponse(
                user.getEmail(),
                user.getCreatedAt(),
                total,
                byStatus,
                topStyles
        ));
    }
}
