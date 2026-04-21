package com.diploma.psc.style;

import jakarta.persistence.Embeddable;
import lombok.*;

import java.io.Serializable;
import java.util.Objects;

@Embeddable
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class PhotoStyleId implements Serializable {

    private Long photoId;
    private Long styleId;

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof PhotoStyleId that)) return false;
        return Objects.equals(photoId, that.photoId) && Objects.equals(styleId, that.styleId);
    }

    @Override
    public int hashCode() {
        return Objects.hash(photoId, styleId);
    }
}
