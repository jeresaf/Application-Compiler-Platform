package acp.domain;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ExactDecimalTest {
    @Test void preservesCurrencyAndExactScale() {
        var amount = ExactDecimal.parse("123.40", 18, 2, "UGX");
        assertEquals(new BigDecimal("123.40"), amount.value());
        assertEquals("UGX", amount.currency());
    }
    @Test void rejectsLossyRounding() {
        assertThrows(ArithmeticException.class, () -> ExactDecimal.parse("1.001", 18, 2, "UGX"));
    }
    @Test void rejectsPrecisionOverflow() {
        assertThrows(IllegalArgumentException.class, () -> ExactDecimal.parse("12345678901234567.00", 18, 2, "UGX"));
    }
}
