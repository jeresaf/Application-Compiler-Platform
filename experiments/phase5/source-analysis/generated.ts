// Experiment fixture: generator-owned.
export interface Payment { amount: number; }
export function settle(value: number): number;
export function settle(value: Payment): number;
export function settle(value: number | Payment): number {
    return typeof value === 'number' ? value : value.amount;
}
