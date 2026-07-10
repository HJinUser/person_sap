package com.portfolio.sapmock.odata;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.UUID;

/**
 * SAP Gateway 의 X-CSRF-Token 핸드셰이크를 재현한다.
 *
 * 실제 SAP OData 서비스는 변경 요청(POST/PUT) 전에 클라이언트가
 * GET 요청 헤더에 "X-CSRF-Token: Fetch" 를 보내 토큰을 발급받아야 한다.
 * 이 mock 은 조회 전용이지만, SAP 클라이언트의 표준 동작을 그대로
 * 수용할 수 있도록 토큰 발급 동작을 구현해 두었다.
 */
@Component
public class CsrfTokenFilter extends OncePerRequestFilter {

    private static final String TOKEN = UUID.randomUUID().toString();

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        if ("Fetch".equalsIgnoreCase(request.getHeader("X-CSRF-Token"))) {
            response.setHeader("X-CSRF-Token", TOKEN);
        }
        filterChain.doFilter(request, response);
    }
}
