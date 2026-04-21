package com.diploma.psc.style;

import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/styles")
@RequiredArgsConstructor
public class StyleController {

    private final StyleRepository styleRepository;

    @GetMapping
    public ResponseEntity<List<String>> list() {
        return ResponseEntity.ok(styleRepository.findAll().stream().map(Style::getName).sorted().toList());
    }
}
