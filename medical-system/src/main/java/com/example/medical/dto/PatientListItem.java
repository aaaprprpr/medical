package com.example.medical.dto;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class PatientListItem {

    private Long id;
    private String name;
    private String gender;
    private Integer age;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private String latestResult;
    private BigDecimal latestConfidence;
    private LocalDateTime latestTestedAt;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getGender() {
        return gender;
    }

    public void setGender(String gender) {
        this.gender = gender;
    }

    public Integer getAge() {
        return age;
    }

    public void setAge(Integer age) {
        this.age = age;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }

    public String getLatestResult() {
        return latestResult;
    }

    public void setLatestResult(String latestResult) {
        this.latestResult = latestResult;
    }

    public BigDecimal getLatestConfidence() {
        return latestConfidence;
    }

    public void setLatestConfidence(BigDecimal latestConfidence) {
        this.latestConfidence = latestConfidence;
    }

    public LocalDateTime getLatestTestedAt() {
        return latestTestedAt;
    }

    public void setLatestTestedAt(LocalDateTime latestTestedAt) {
        this.latestTestedAt = latestTestedAt;
    }
}
