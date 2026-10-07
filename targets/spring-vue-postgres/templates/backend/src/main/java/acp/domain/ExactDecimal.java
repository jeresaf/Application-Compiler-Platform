package acp.domain;

import java.math.BigDecimal;
import java.math.RoundingMode;

/** Semantic decimal boundary: precision and scale are validated before JDBC. */
public record ExactDecimal(BigDecimal value, int precision, int scale, String currency) {
    public ExactDecimal {
        if (value == null || precision < 1 || scale < 0 || scale > precision) {
            throw new IllegalArgumentException("DECIMAL_CONSTRAINT");
        }
        value = value.setScale(scale, RoundingMode.UNNECESSARY);
        if (value.precision() > precision) {
            throw new IllegalArgumentException("DECIMAL_PRECISION");
        }
        if (currency != null && !currency.matches("[A-Z]{3}")) {
            throw new IllegalArgumentException("CURRENCY");
        }
    }

    public static ExactDecimal parse(String text, int precision, int scale, String currency) {
        return new ExactDecimal(new BigDecimal(text), precision, scale, currency);
    }
}
