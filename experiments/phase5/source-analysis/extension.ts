// acp-owner: HUMAN id=EXT-PAYMENT
// Experiment fixture: human-owned extension.
import { settle as pay, PaymentBase, type Payment } from './generated.js';
class Extension extends PaymentBase implements Payment { amount = 7; }
const resolved = pay(new Extension());
const missing = noSuchPayment(1);
