package com.diploma.psc.photo;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface PhotoFeaturesRepository extends JpaRepository<PhotoFeatures, Long> {

    Optional<PhotoFeatures> findByPhotoId(Long photoId);

    /**
     * Все features фотографий конкретного пользователя — для построения
     * embedding-индекса при поиске похожих. Возвращаем только пары
     * (photoId, embedding) — palette и scores не нужны для similarity.
     */
    @Query("""
           SELECT pf.photoId AS photoId, pf.embedding AS embedding
           FROM PhotoFeatures pf
           JOIN pf.photo p
           WHERE p.user.id = :userId AND p.status = com.diploma.psc.photo.PhotoStatus.DONE
           """)
    List<EmbeddingRow> findEmbeddingsByUserId(@Param("userId") Long userId);

    interface EmbeddingRow {
        Long getPhotoId();
        String getEmbedding();
    }
}
