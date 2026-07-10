package com.portfolio.sapmock.odata;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * OData v2 $filter 식의 부분 집합을 파싱한다.
 * 지원 문법:  Field eq 'value'  |  Field ge 12.5  |  절들을 and 로 연결
 * 예) $filter=Stat2 eq '3' and Orgeh eq '40001000'
 *     $filter=Othrs ge 20
 *
 * (실제 SAP Gateway는 or/그룹핑/함수까지 지원하지만,
 *  이 프로젝트에서 소비하는 질의 범위에 맞춰 의도적으로 부분 구현했다.)
 */
public final class ODataFilterParser {

    private static final Pattern CLAUSE =
            Pattern.compile("^\\s*(\\w+)\\s+(eq|ne|gt|ge|lt|le)\\s+(?:'([^']*)'|([-\\d.]+))\\s*$");

    private ODataFilterParser() {
    }

    /** $filter 식을 "필드맵 → 통과 여부" Predicate 로 컴파일한다. */
    public static Predicate<Map<String, Object>> parse(String filter) {
        List<Predicate<Map<String, Object>>> clauses = new ArrayList<>();
        for (String raw : filter.split("(?i)\\s+and\\s+")) {
            Matcher m = CLAUSE.matcher(raw);
            if (!m.matches()) {
                throw new IllegalArgumentException("지원하지 않는 $filter 절: " + raw);
            }
            String field = m.group(1);
            String op = m.group(2);
            String strVal = m.group(3);
            String numVal = m.group(4);
            clauses.add(row -> {
                Object actual = row.get(field);
                if (actual == null) {
                    return false;
                }
                if (strVal != null) {
                    int cmp = String.valueOf(actual).compareTo(strVal);
                    return evaluate(op, cmp);
                }
                double target = Double.parseDouble(numVal);
                double value = Double.parseDouble(String.valueOf(actual));
                return evaluate(op, Double.compare(value, target));
            });
        }
        return clauses.stream().reduce(row -> true, Predicate::and);
    }

    private static boolean evaluate(String op, int cmp) {
        return switch (op) {
            case "eq" -> cmp == 0;
            case "ne" -> cmp != 0;
            case "gt" -> cmp > 0;
            case "ge" -> cmp >= 0;
            case "lt" -> cmp < 0;
            case "le" -> cmp <= 0;
            default -> false;
        };
    }
}
