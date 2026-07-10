package com.portfolio.sapmock.entity;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * SAP HCM 인포타입 PA0000(인사조치) + PA0001(조직배치)을 단순화한 사원 마스터.
 * 필드명은 실제 SAP 필드명을 따른다 (PERNR=사번, ORGEH=조직단위, PLANS=직위 등).
 */
@Entity
@Table(name = "PA0001")
@JsonNaming(PropertyNamingStrategies.UpperCamelCaseStrategy.class)
public class Employee {

    @Id
    private String pernr;      // 사번
    private String ename;      // 성명
    private String gesch;      // 성별 (1=남, 2=여)
    private String gbdat;      // 생년월일
    private String hidat;      // 입사일
    private String orgeh;      // 조직단위 코드
    private String orgehTxt;   // 조직단위 명
    private String plans;      // 직위 코드
    private String plansTxt;   // 직위 명
    private String stat2;      // 재직상태 (3=재직, 0=퇴직)
    private String massn;      // 인사조치 유형 (01=입사, 10=퇴사)
    private String terdt;      // 퇴사일 (재직 중이면 빈 값)

    public Employee() {
    }

    public Employee(String[] csv) {
        this.pernr = csv[0];
        this.ename = csv[1];
        this.gesch = csv[2];
        this.gbdat = csv[3];
        this.hidat = csv[4];
        this.orgeh = csv[5];
        this.orgehTxt = csv[6];
        this.plans = csv[7];
        this.plansTxt = csv[8];
        this.stat2 = csv[9];
        this.massn = csv[10];
        this.terdt = csv[11];
    }

    public String getPernr() { return pernr; }
    public String getEname() { return ename; }
    public String getGesch() { return gesch; }
    public String getGbdat() { return gbdat; }
    public String getHidat() { return hidat; }
    public String getOrgeh() { return orgeh; }
    public String getOrgehTxt() { return orgehTxt; }
    public String getPlans() { return plans; }
    public String getPlansTxt() { return plansTxt; }
    public String getStat2() { return stat2; }
    public String getMassn() { return massn; }
    public String getTerdt() { return terdt; }
}
