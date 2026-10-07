package experiment;
// acp-owner: GENERATED id=ENT-PAYMENT
interface Payment { int amount(); }
class PaymentBase implements Payment { public int amount() { return 0; } }
// acp-owner: GENERATED id=SERVICE-SETTLE
class GeneratedPayment {
 static int settle(int amount) { return amount; }
 static int settle(Payment payment) { return payment.amount(); }
}
