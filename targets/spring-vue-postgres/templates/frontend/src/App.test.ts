// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import App from './App.vue';
import { model } from './model';
import { call } from './api';
import { permissions } from './extensions/identity';

vi.mock('./api', () => ({ call: vi.fn() }));
vi.mock('./extensions/identity', () => ({ permissions: vi.fn(), accessToken: vi.fn() }));

describe('semantic task screen', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(call).mockResolvedValue([]);
    vi.mocked(permissions).mockReturnValue(new Set(model.nodes.filter(node => node.kind === 'Permission').map(node => node.id)));
  });

  it('renders empty and loading outcomes', async () => {
    const wrapper = mount(App);
    await flushPromises();
    expect(wrapper.text()).toContain('No tasks are available.');
    expect(wrapper.find('nav[aria-label="Tasks"]').exists()).toBe(true);
  });

  it('shows safe server errors with an accessible summary', async () => {
    vi.mocked(call).mockRejectedValue(new Error('Permission denied.'));
    const wrapper = mount(App);
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('Permission denied.');
  });

  it('hides workflow actions without permission', async () => {
    vi.mocked(permissions).mockReturnValue(new Set());
    const wrapper = mount(App);
    await flushPromises();
    expect(wrapper.find('[data-component-role="WorkflowAction"]').exists()).toBe(false);
  });

  it('links missing required fields to the error summary', async () => {
    const wrapper = mount(App);
    await flushPromises();
    const button = wrapper.get('[data-component-role="WorkflowAction"]');
    await button.element.closest('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain('Choose a task');
    expect(wrapper.find('textarea[aria-invalid="true"]').exists()).toBe(true);
  });
});
