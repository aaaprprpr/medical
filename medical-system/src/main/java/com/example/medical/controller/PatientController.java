package com.example.medical.controller;

import com.example.medical.model.Patient;
import com.example.medical.repository.PatientRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.PathVariable;
import java.util.List;
import java.util.Map;

@RestController
public class PatientController {
    private final PatientRepository patientRepository;

    public PatientController(PatientRepository patientRepository) {
        this.patientRepository = patientRepository;
    }

    @GetMapping("/api/patients")
    public Map<String, Object> listPatients() {
        List<Patient> patients = patientRepository.findAll();
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

}
