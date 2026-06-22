package com.example.medical.dto;

import java.math.BigDecimal;

public class CreateTestRecordRequest {
    private String result;
    private BigDecimal confidence;
    private String remark;

    public String getResult() {
        return result;
    }

    public void setResult(String result) {
        this.result = result;
    }

    public BigDecimal getConfidence() {
        return confidence;
    }

    public void setConfidence(BigDecimal confidence) {
        this.confidence = confidence;
    }

    public String getRemark() {
        return remark;
    }

    public void setRemark(String remark) {
        this.remark = remark;
    }

}
