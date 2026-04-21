package com.diploma.psc.style;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PhotoStyleRepository extends JpaRepository<PhotoStyle, PhotoStyleId> {
    List<PhotoStyle> findByPhotoId(Long photoId);
    void deleteByPhotoId(Long photoId);
}
