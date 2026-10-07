package experiment;
import static experiment.GeneratedPayment.settle;
// acp-owner: HUMAN id=EXT-PAYMENT
class HumanExtension extends PaymentBase implements Payment {
 public int amount() { return 7; }
 int resolved() { return settle(this); }
 int unresolved() { return noSuchPayment(); }
}
