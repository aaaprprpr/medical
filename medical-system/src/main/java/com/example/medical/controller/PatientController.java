package com.example.medical.controller;

import com.example.medical.model.Patient;
import com.example.medical.repository.PatientRepository;
import com.example.medical.dto.CreatePatientRequest;
import com.example.medical.dto.PatientListItem;
import com.example.medical.dto.UpdatePatientRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.RequestParam;
import java.util.List;
import java.util.Map;

@RestController
public class PatientController {
    private final PatientRepository patientRepository;

    public PatientController(PatientRepository patientRepository) {
        this.patientRepository = patientRepository;
    }

    @GetMapping("/api/patients")
    public Map<String, Object> listPatients(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String gender,
            @RequestParam(required = false) String result,
            @RequestParam(required = false) String sortBy,
            @RequestParam(required = false) String order) {
        List<PatientListItem> patients = patientRepository.searchWithLatestRecord(keyword, gender, result, sortBy,
                order);
        return Map.of(
                "code", 0,
                "message", "success",
                "data", patients);
    }

    @GetMapping("/api/patients/{id}")
    public Map<String, Object> getPatientById(@PathVariable Long id) {
        Patient patient = patientRepository.findById(id);

        return Map.of(
                "code", 0,
                "message", "success",
                "data", patient);
    }

    @PostMapping("/api/patients")
    public Map<String, Object> createPatient(@RequestBody CreatePatientRequest request) {

        int affectedRows = patientRepository.create(
                request.getName(),
                request.getGender(),
                request.getAge());
        return Map.of(
                "code", 0,
                "message", "success",
                "data", Map.of("affectedRows", affectedRows));
    }

    @PutMapping("/api/patients/{id}")
    public Map<String, Object> updatePatient(@PathVariable Long id, @RequestBody UpdatePatientRequest request) {
        int affectedRows = patientRepository.update(id, request.getName(), request.getGender(), request.getAge());
        return Map.of(
                "code", 0,
                "message", "success",
                "data", Map.of("affectedRows", affectedRows));
    }

    @DeleteMapping("/api/patients/{id}")
    public Map<String, Object> deletePatient(@PathVariable Long id) {
        int affectedRows = patientRepository.deleteById(id);
        return Map.of(
                "code", 0,
                "message", "success",
                "data", Map.of("affectedRows", affectedRows));
    }
}
