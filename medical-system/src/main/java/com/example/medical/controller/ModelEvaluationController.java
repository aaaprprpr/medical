package com.example.medical.controller;

import java.io.IOException;
import java.util.Map;

import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api")
public class ModelEvaluationController {
    private final RestClient restClient;

    public ModelEvaluationController(RestClient restClient) {
        this.restClient = restClient;
    }

    @PostMapping(value = "/model-evaluation", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> evaluate(@RequestPart("files") MultipartFile[] files) throws IOException {
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
                .uri("http://localhost:8000/evaluate")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(Map.class);

        return Map.of(
                "code", 0,
                "message", "success",
                "data", pythonResult);
    }

    @PostMapping(value = "/model-evaluation-path", consumes = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Object> evaluatePath(@RequestBody Map<String, String> request) {
        String dataPath = request.get("dataPath");
        if (dataPath == null || dataPath.isBlank()) {
            throw new IllegalArgumentException("dataPath is required");
        }

        Map<String, String> pythonRequest = Map.of("data_path", dataPath);
        Map pythonResult = restClient.post()
                .uri("http://localhost:8000/evaluate-path")
                .contentType(MediaType.APPLICATION_JSON)
                .body(pythonRequest)
                .retrieve()
                .body(Map.class);

        return Map.of(
                "code", 0,
                "message", "success",
                "data", pythonResult);
    }
}
