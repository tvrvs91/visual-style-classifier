package com.diploma.psc.auth;

import com.diploma.psc.user.User;
import com.diploma.psc.user.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class UserDetailsServiceImpl implements UserDetailsService {

    private final UserRepository userRepository;

    @Override
    public UserDetails loadUserByUsername(String email) throws UsernameNotFoundException {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UsernameNotFoundException("User not found: " + email));
        return new AuthUser(user);
    }

    public record AuthUser(User user) implements UserDetails {
        @Override public String getUsername() { return user.getEmail(); }
        @Override public String getPassword() { return user.getPassword(); }
        @Override public java.util.Collection<? extends org.springframework.security.core.GrantedAuthority>
                getAuthorities() { return List.of(new SimpleGrantedAuthority("ROLE_USER")); }
        @Override public boolean isAccountNonExpired() { return true; }
        @Override public boolean isAccountNonLocked() { return true; }
        @Override public boolean isCredentialsNonExpired() { return true; }
        @Override public boolean isEnabled() { return true; }
        public Long getUserId() { return user.getId(); }
    }
}
