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
 * 연 1회 인사평가 결과 (SAP 성과관리 모듈을 단순화).
 * Score: 1(미흡) ~ 5(탁월)
 */
@Entity
@Table(name = "ZAPPRAISAL", indexes = @Index(columnList = "pernr"))
@JsonNaming(PropertyNamingStrategies.UpperCamelCaseStrategy.class)
public class Appraisal {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @JsonIgnore
    private Long id;

    private String pernr;   // 사번
    private String zyear;   // 평가 연도
    private Integer score;  // 평가 점수 (1~5)

    public Appraisal() {
    }

    public Appraisal(String[] csv) {
        this.pernr = csv[0];
        this.zyear = csv[1];
        this.score = Integer.parseInt(csv[2]);
    }

    public Long getId() { return id; }
    public String getPernr() { return pernr; }
    public String getZyear() { return zyear; }
    public Integer getScore() { return score; }
}
