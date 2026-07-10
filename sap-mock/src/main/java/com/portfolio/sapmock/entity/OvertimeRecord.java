package com.portfolio.sapmock.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

/**
 * SAP 근무시간관리(PT)의 월별 초과근무 집계를 단순화한 테이블.
 * (실제 SAP에서는 CATS/PT 테이블에서 집계하지만, 여기서는 월 단위 요약으로 제공)
 */
@Entity
@Table(name = "ZOVERTIME", indexes = @Index(columnList = "pernr"))
@JsonNaming(PropertyNamingStrategies.UpperCamelCaseStrategy.class)
public class OvertimeRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @JsonIgnore
    private Long id;

    private String pernr;    // 사번
    private String zmonth;   // 대상 월 (YYYY-MM)
    private Double othrs;    // 초과근무 시간

    public OvertimeRecord() {
    }

    public OvertimeRecord(String[] csv) {
        this.pernr = csv[0];
        this.zmonth = csv[1];
        this.othrs = Double.parseDouble(csv[2]);
    }

    public Long getId() { return id; }
    public String getPernr() { return pernr; }
    public String getZmonth() { return zmonth; }
    public Double getOthrs() { return othrs; }
}
