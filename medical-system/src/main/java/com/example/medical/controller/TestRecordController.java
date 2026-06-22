package com.example.medical.controller;

import com.example.medical.model.TestRecord;
import com.example.medical.repository.TestRecordRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import com.example.medical.dto.CreateTestRecordRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import java.util.List;
import java.util.Map;

@RestController
public class TestRecordController {
    private final TestRecordRepository testRecordRepository;

    public TestRecordController(TestRecordRepository testRecordRepository) {
        this.testRecordRepository = testRecordRepository;
    }

    @GetMapping("/api/patients/{patientId}/records")
    public Map<String, Object> listRecordsByPatientId(@PathVariable Long patientId) {
        List<TestRecord> records = testRecordRepository.findByPatientId(patientId);
        return Map.of("code", 0, "message", "success", "data", records);
    }

    @PostMapping("/api/patients/{patientId}/records")
    public Map<String, Object> createRecord(
            @PathVariable Long patientId,
            @RequestBody CreateTestRecordRequest request) {
        int affectedRows = testRecordRepository.create(
                patientId,
                request.getResult(),
                request.getConfidence(),
                request.getRemark());

        return Map.of(
                "code", 0,
                "message", "success",
                "data", Map.of("affectedRows", affectedRows));
    }
}
