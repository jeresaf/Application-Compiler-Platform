// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises,mount } from '@vue/test-utils';
import App from './App.vue';
import { ui } from './task-ui-model';
import { call,ApiFailure } from './api';
import { identity } from './extensions/identity';
vi.mock('./api',async original=>({...await original<typeof import('./api')>(),call:vi.fn()}));
vi.mock('./extensions/identity',()=>({identity:vi.fn(),onIdentityChange:()=>()=>{},accessToken:vi.fn()}));
describe('validated task interface',()=>{
 beforeEach(()=>{vi.resetAllMocks();vi.mocked(identity).mockReturnValue({actor:ui.boundary.data.actor.id,subject:'test',tenant:'test',permissions:new Set(ui.boundary.data.permissions.map(p=>p.id))});vi.mocked(call).mockResolvedValue([]);});
 it('preserves exact search label, semantic order and empty state',async()=>{const w=mount(App);await flushPromises();expect(w.text()).toContain(ui.states.EMPTY.data.message);expect(w.find('label').text()).toBe(ui.search.data.label);expect(w.findAll('[data-semantic-id]').slice(0,3).map(x=>x.attributes('data-semantic-id'))).toEqual(ui.screen.data.content.map(x=>x.id));expect(w.find('[data-component-role]').exists()).toBe(false);});
 it('sends exact typed empty String query with bounded pagination',async()=>{mount(App);await flushPromises();expect(call).toHaveBeenCalledWith(ui.queryPath+'?offset=0&limit='+ui.page.limit,{[ui.queryInputField]:''});});
 it('denies presentation before loading without boundary permissions',async()=>{vi.mocked(identity).mockReturnValue({actor:ui.boundary.data.actor.id,subject:'test',tenant:'test',permissions:new Set()});const w=mount(App);await flushPromises();expect(call).not.toHaveBeenCalled();expect(w.find('[role="alert"]').text()).toContain(ui.states.ERROR.data.message);});
 it('shows safe declared errors, never exception content',async()=>{vi.mocked(call).mockRejectedValue(new ApiFailure('INTERNAL'));const w=mount(App);await flushPromises();expect(w.find('[role="alert"]').text()).toContain(ui.states.ERROR.data.message);expect(w.text()).not.toContain('INTERNAL');});
 it('renders declared projection only and explicit selected resource control',async()=>{vi.mocked(call).mockResolvedValue([{resourceId:'selected',version:0,state:'SECRET_STATE',output:{[ui.outputField]:'visible'}}]);const w=mount(App);await flushPromises();expect(w.find('tbody').text()).toContain('visible');expect(w.find('tbody').text()).not.toContain('SECRET_STATE');await w.find('tbody button').trigger('click');expect((w.find('input[readonly]').element as HTMLInputElement).value).toBe('selected');expect(w.find('[data-component-role]').text()).toBe(ui.action.data.label);});
});
