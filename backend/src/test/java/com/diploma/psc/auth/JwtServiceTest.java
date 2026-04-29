package com.diploma.psc.auth;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class JwtServiceTest {

    private static final String SECRET = "test-secret-must-be-at-least-32-bytes-long-for-hs512-signing";
    private static final long ONE_HOUR = 60 * 60 * 1000L;

    private final JwtService service = new JwtService(SECRET, ONE_HOUR);

    private UserDetails user(String email) {
        return new User(email, "password",
                List.of(new SimpleGrantedAuthority("ROLE_USER")));
    }

    @Test
    void generated_token_carries_email_as_subject() {
        String token = service.generateToken(user("alice@example.com"));
        assertThat(service.extractUsername(token)).isEqualTo("alice@example.com");
    }

    @Test
    void valid_token_for_same_user_passes_validation() {
        UserDetails u = user("bob@example.com");
        String token = service.generateToken(u);
        assertThat(service.isTokenValid(token, u)).isTrue();
    }

    @Test
    void valid_token_for_different_user_fails_validation() {
        String token = service.generateToken(user("alice@example.com"));
        assertThat(service.isTokenValid(token, user("mallory@example.com"))).isFalse();
    }

    @Test
    void token_signed_with_different_secret_is_rejected() {
        JwtService other = new JwtService(
                "different-secret-must-be-at-least-32-bytes-long-also-strong",
                ONE_HOUR);
        String alienToken = other.generateToken(user("alice@example.com"));

        assertThatThrownBy(() -> service.extractUsername(alienToken))
                .isInstanceOf(io.jsonwebtoken.security.SignatureException.class);
    }

    @Test
    void expired_token_fails_validation() throws InterruptedException {
        JwtService shortLived = new JwtService(SECRET, 50); // 50ms
        UserDetails u = user("alice@example.com");
        String token = shortLived.generateToken(u);
        Thread.sleep(120);
        assertThatThrownBy(() -> shortLived.isTokenValid(token, u))
                .isInstanceOf(io.jsonwebtoken.ExpiredJwtException.class);
    }
}
