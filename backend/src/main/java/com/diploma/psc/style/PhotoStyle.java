package com.diploma.psc.style;

import com.diploma.psc.photo.Photo;
import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "photo_styles")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class PhotoStyle {

    @EmbeddedId
    private PhotoStyleId id;

    @MapsId("photoId")
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "photo_id")
    private Photo photo;

    @MapsId("styleId")
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "style_id")
    private Style style;

    @Column(nullable = false)
    private double confidence;
}
