import type { Component } from 'vue';

export const components: Record<string, Component> = {};
export const formatters: Record<string, (value: unknown) => string> = {};
export const routes: ReadonlyArray<{ path: string; component: Component }> = [];
