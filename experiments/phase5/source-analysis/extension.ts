// Experiment fixture: human-owned extension.
import { settle as pay, type Payment } from './generated.js';
class Extension implements Payment { amount = 7; }
const resolved = pay(new Extension());
const missing = noSuchPayment(1);
