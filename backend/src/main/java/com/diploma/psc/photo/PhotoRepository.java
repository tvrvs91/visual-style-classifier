package com.diploma.psc.photo;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface PhotoRepository extends JpaRepository<Photo, Long> {

    Page<Photo> findByUserId(Long userId, Pageable pageable);

    Optional<Photo> findByIdAndUserId(Long id, Long userId);

    @Query("""
           SELECT DISTINCT p FROM Photo p
             JOIN p.styles ps
             JOIN ps.style s
           WHERE p.user.id = :userId
             AND s.name = :styleName
             AND ps.confidence >= :minConfidence
           """)
    Page<Photo> searchByStyle(@Param("userId") Long userId,
                              @Param("styleName") String styleName,
                              @Param("minConfidence") double minConfidence,
                              Pageable pageable);

    long countByUserId(Long userId);

    @Query("""
           SELECT p.status AS status, COUNT(p) AS total
           FROM Photo p
           WHERE p.user.id = :userId
           GROUP BY p.status
           """)
    List<StatusCount> countByStatusForUser(@Param("userId") Long userId);

    @Query(value = """
           SELECT s.name AS name,
                  COUNT(*) AS total,
                  AVG(ps.confidence) AS avg_conf
           FROM photo_styles ps
           JOIN photos p ON p.id = ps.photo_id
           JOIN styles s ON s.id = ps.style_id
           WHERE p.user_id = :userId
           GROUP BY s.name
           ORDER BY total DESC, avg_conf DESC
           """, nativeQuery = true)
    List<StyleStat> topStylesByUser(@Param("userId") Long userId);

    interface StatusCount {
        PhotoStatus getStatus();
        long getTotal();
    }

    interface StyleStat {
        String getName();
        long getTotal();
        Double getAvgConf();
    }
}
