package com.example.medical.controller;
import java.io.IOException;
import java.util.Map;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;


@RestController
@RequestMapping("/api")
public class MockPredictController {
    private final RestClient restClient;
    
    public MockPredictController(RestClient restClient) {
        this.restClient = restClient;
    }

    @PostMapping(value = "/mock-predict", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> mockPredict(@RequestPart("file") MultipartFile file) throws IOException {
        ByteArrayResource fileResource = new ByteArrayResource(file.getBytes()) {
            @Override
            public String getFilename() {
                return file.getOriginalFilename();
            }
        };

        MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();
        bodyBuilder.part("file", fileResource)
                .filename(file.getOriginalFilename())
                .contentType(MediaType.APPLICATION_OCTET_STREAM);

        MultiValueMap<String, org.springframework.http.HttpEntity<?>> body = bodyBuilder.build();

        Map pythonResult = restClient.post()
                .uri("http://localhost:8000/predict")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(Map.class);

        return Map.of(
                "code", 0,
                "message", "success",
                "data", pythonResult
        );
    }

}
