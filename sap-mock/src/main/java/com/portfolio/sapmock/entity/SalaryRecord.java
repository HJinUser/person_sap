package com.portfolio.sapmock.entity;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import com.fasterxml.jackson.annotation.JsonIgnore;

/**
 * SAP HCM 인포타입 PA0008(기본급)을 단순화한 급여 이력.
 * SAP의 기간 유효(period-effective) 레코드 방식을 그대로 따른다:
 * 한 사람의 급여 이력이 BEGDA~ENDDA 구간 레코드 여러 개로 표현되며,
 * 현재 유효 레코드는 ENDDA='9999-12-31' 이다.
 */
@Entity
@Table(name = "PA0008")
@JsonNaming(PropertyNamingStrategies.UpperCamelCaseStrategy.class)
public class SalaryRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @JsonIgnore
    private Long id;

    private String pernr;   // 사번
    private String begda;   // 유효 시작일
    private String endda;   // 유효 종료일 (9999-12-31 = 현재 유효)
    private Double bet01;   // 월 기본급 (만원)

    public SalaryRecord() {
    }

    public SalaryRecord(String[] csv) {
        this.pernr = csv[0];
        this.begda = csv[1];
        this.endda = csv[2];
        this.bet01 = Double.parseDouble(csv[3]);
    }

    public Long getId() { return id; }
    public String getPernr() { return pernr; }
    public String getBegda() { return begda; }
    public String getEndda() { return endda; }
    public Double getBet01() { return bet01; }
}
