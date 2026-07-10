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
 * SAP HCM 인포타입 PA2001(결근/휴가)을 단순화한 근태 이벤트.
 * AWART(근태유형): 0100=연차, 0200=병가
 */
@Entity
@Table(name = "PA2001", indexes = @Index(columnList = "pernr"))
@JsonNaming(PropertyNamingStrategies.UpperCamelCaseStrategy.class)
public class Absence {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @JsonIgnore
    private Long id;

    private String pernr;   // 사번
    private String awart;   // 근태 유형 (0100=연차, 0200=병가)
    private String begda;   // 시작일
    private String endda;   // 종료일
    private Integer abwtg;  // 근태 일수

    public Absence() {
    }

    public Absence(String[] csv) {
        this.pernr = csv[0];
        this.awart = csv[1];
        this.begda = csv[2];
        this.endda = csv[3];
        this.abwtg = Integer.parseInt(csv[4]);
    }

    public Long getId() { return id; }
    public String getPernr() { return pernr; }
    public String getAwart() { return awart; }
    public String getBegda() { return begda; }
    public String getEndda() { return endda; }
    public Integer getAbwtg() { return abwtg; }
}
