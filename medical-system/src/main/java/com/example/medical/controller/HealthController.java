package com.example.medical.controller;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;


@RestController
@RequestMapping("/api")
public class HealthController {
    
    @GetMapping("/health")
    public Map<String, Object> healthCheck() {
        return Map.of(
            "code",0,
            "message","success",
            "data", Map.of("status","UP")
        );
    }


}
