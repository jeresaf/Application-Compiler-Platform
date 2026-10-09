// @vitest-environment happy-dom
import { expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import App from './App.vue';
import { ui } from './task-ui-model';
import { call, ApiFailure } from './api';
import { identity } from './extensions/identity';
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), call: vi.fn() }));
vi.mock('./extensions/identity', () => ({ identity: vi.fn(), onIdentityChange: () => () => {}, accessToken: vi.fn() }));
it('retains the logical key and input during explicit recovery from rate denial', async () => {
 const row={resourceId:'selected',version:0,state:null,output:{[ui.outputField]:'old'}};
 vi.mocked(identity).mockReturnValue({actor:ui.boundary.data.actor.id,subject:'test',tenant:'test',permissions:new Set(ui.boundary.data.permissions.map(p=>p.id))});
 vi.mocked(call).mockResolvedValueOnce([row]).mockRejectedValueOnce(new ApiFailure('RATE_DENIED')).mockResolvedValueOnce(row).mockResolvedValueOnce([row]);
 const w=mount(App);await flushPromises();await w.find('tbody button').trigger('click');await w.find('textarea').setValue('exact note');
 vi.spyOn(w.find('dialog').element as HTMLDialogElement,'showModal').mockImplementation(()=>{});
 await w.find('form[data-semantic-id]').trigger('submit');await w.findAll('dialog button')[1].trigger('click');await flushPromises();
 const first=vi.mocked(call).mock.calls[1][1];expect(w.find('textarea').attributes()).toHaveProperty('disabled');
 await w.find('[role="alert"] button').trigger('click');await w.findAll('dialog button')[1].trigger('click');await flushPromises();
 expect(vi.mocked(call).mock.calls[2][1]).toEqual(first);w.unmount();
});
