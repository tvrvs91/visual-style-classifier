package com.diploma.psc.photo;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

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
}
