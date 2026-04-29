package com.diploma.psc.auth;

import com.diploma.psc.IntegrationTestBase;
import com.diploma.psc.auth.dto.AuthResponse;
import com.diploma.psc.auth.dto.LoginRequest;
import com.diploma.psc.auth.dto.RegisterRequest;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;

class AuthFlowTest extends IntegrationTestBase {

    @Autowired
    TestRestTemplate rest;

    @Test
    void register_then_login_returns_jwt() {
        RegisterRequest req = new RegisterRequest("alice@example.com", "password123");
        ResponseEntity<AuthResponse> reg = rest.postForEntity("/api/auth/register", req, AuthResponse.class);

        assertThat(reg.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(reg.getBody()).isNotNull();
        assertThat(reg.getBody().token()).isNotBlank();
        assertThat(reg.getBody().email()).isEqualTo("alice@example.com");

        ResponseEntity<AuthResponse> login = rest.postForEntity(
                "/api/auth/login", new LoginRequest("alice@example.com", "password123"), AuthResponse.class);

        assertThat(login.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(login.getBody().token()).isNotBlank();
    }

    @Test
    void duplicate_email_registration_rejected() {
        RegisterRequest req = new RegisterRequest("bob@example.com", "password123");
        rest.postForEntity("/api/auth/register", req, AuthResponse.class);

        ResponseEntity<String> dup = rest.postForEntity("/api/auth/register", req, String.class);
        assertThat(dup.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
    }

    @Test
    void login_with_wrong_password_returns_401() {
        rest.postForEntity("/api/auth/register",
                new RegisterRequest("carol@example.com", "password123"), AuthResponse.class);

        ResponseEntity<String> bad = rest.postForEntity(
                "/api/auth/login",
                new LoginRequest("carol@example.com", "wrong-password"),
                String.class);

        assertThat(bad.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void protected_endpoint_without_jwt_is_rejected() {
        ResponseEntity<String> r = rest.getForEntity("/api/photos", String.class);
        assertThat(r.getStatusCode()).isIn(HttpStatus.UNAUTHORIZED, HttpStatus.FORBIDDEN);
    }
}
