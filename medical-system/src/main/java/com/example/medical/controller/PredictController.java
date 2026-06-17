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
public class PredictController {
    private final RestClient restClient;

    public PredictController(RestClient restClient) {
        this.restClient = restClient;
    }

    @PostMapping(value = "/predict", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> predict(@RequestPart("files") MultipartFile[] files) throws IOException {
        MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();
        for (MultipartFile file : files) {
            String filename = file.getOriginalFilename();
            ByteArrayResource fileResource = new ByteArrayResource(file.getBytes()) {
                @Override
                public String getFilename() {
                    return filename;
                }
            };
            bodyBuilder.part("files", fileResource)
                    .filename(filename)
                    .contentType(MediaType.APPLICATION_OCTET_STREAM);

        }

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
                "data", pythonResult);
    }

}
