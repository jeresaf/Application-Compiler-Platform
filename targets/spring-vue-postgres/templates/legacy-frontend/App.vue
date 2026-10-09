<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { model } from './model';
import { call } from './api';
import { permissions } from './extensions/identity';

type Row = Record<string, unknown> & { resourceId: string; version: number; state: string | null };
const nodes: ReadonlyArray<{ id: string; kind: string; name: string; data: any }> = model.nodes;
const screen = nodes.find(node => node.kind === 'Screen');
const task = nodes.find(node => node.id === screen?.data.task.id);
const inputFields = nodes.filter(node => node.kind === 'Field' && node.data.owner.id === task?.data.input.id);
const query = model.api.find(operation => operation.role === 'Query');
const submitOperation = model.api.find(operation => operation.origin.id === task?.id);
const input = ref<Record<string, string>>({});
const rows = ref<Row[]>([]);
const selected = ref<Row | null>(null);
const search = ref('');
const busy = ref(false);
const error = ref('');
const success = ref('');
const dialog = ref<HTMLDialogElement | null>(null);
const errorSummary = ref<HTMLElement | null>(null);
const action = nodes.find(node => node.kind === 'Action' && node.data.useCase?.id === task?.id);
const allowed = computed(() => !!action && action.data.permissions.every((permission: { id: string }) => permissions().has(permission.id)));
const invalid = computed(() => inputFields.filter(field => !field.data.optional && !input.value[field.id]?.trim()));

async function load() {
  if (!query) return;
  busy.value = true; error.value = '';
  try { rows.value = await call<Row[]>(`${query.path}?search=${encodeURIComponent(search.value)}`); }
  catch (failure) { error.value = failure instanceof Error ? failure.message : 'Unable to load tasks.'; }
  finally { busy.value = false; }
}

async function confirm() {
  error.value = ''; success.value = '';
  if (invalid.value.length || !selected.value) {
    error.value = 'Choose a task and complete the required fields.';
    await nextTick(); errorSummary.value?.focus(); return;
  }
  dialog.value?.showModal();
}

async function submit() {
  dialog.value?.close();
  if (!submitOperation || !selected.value) return;
  busy.value = true;
  try {
    await call(submitOperation.path, { resourceId: selected.value.resourceId, expectedVersion: selected.value.version, input: input.value });
    success.value = 'Task completed.'; selected.value = null; await load();
  } catch (failure) { error.value = failure instanceof Error ? failure.message : 'Unable to complete task.'; }
  finally { busy.value = false; }
}

onMounted(load);
</script>

<template>
  <main>
    <nav aria-label="Tasks"><a :href="`#/${screen?.id}`">{{ screen?.name }}</a></nav>
    <h1>{{ screen?.name }}</h1>
    <section v-if="error" ref="errorSummary" role="alert" tabindex="-1" class="error-summary"><h2>Task errors</h2><p>{{ error }}</p><ul><li v-for="field in invalid" :key="field.id"><a :href="`#${field.id}`">Complete {{ field.name }}</a></li></ul></section>
    <p v-if="success" role="status">{{ success }}</p>
    <form @submit.prevent="load"><label for="search">Search tasks</label><input id="search" v-model="search" type="search"><button :disabled="busy">Search</button></form>
    <p v-if="busy" role="status">Loading tasks…</p>
    <p v-else-if="!rows.length">No tasks are available.</p>
    <table v-else><caption>Available tasks</caption><thead><tr><th scope="col">Task</th><th scope="col">Status</th><th scope="col">Selection</th></tr></thead><tbody><tr v-for="row in rows" :key="row.resourceId"><th scope="row">{{ row.resourceId }}</th><td>{{ row.state || 'Initial' }}</td><td><button type="button" :aria-pressed="selected?.resourceId === row.resourceId" @click="selected = row">Select {{ row.resourceId }}</button></td></tr></tbody></table>
    <section v-if="selected" aria-label="Task details"><h2>Task {{ selected.resourceId }}</h2><p>Status: {{ selected.state || 'Initial' }}</p></section>
    <form v-if="allowed" @submit.prevent="confirm" novalidate>
      <div v-for="field in inputFields" :key="field.id"><label :for="field.id">{{ field.name }}</label><textarea :id="field.id" v-model="input[field.id]" :required="!field.data.optional" :aria-invalid="invalid.some(item => item.id === field.id) && !!error" :aria-describedby="`${field.id}-error`"/><p :id="`${field.id}-error`">{{ error && invalid.some(item => item.id === field.id) ? 'This field is required.' : '' }}</p></div>
      <button :disabled="busy" data-component-role="WorkflowAction">{{ action?.name || 'Complete task' }}</button>
    </form>
    <dialog ref="dialog" aria-labelledby="confirm-title"><h2 id="confirm-title">Confirm task action</h2><p>Continue with the selected task?</p><button type="button" autofocus @click="dialog?.close()">Cancel</button><button type="button" @click="submit">Confirm</button></dialog>
    <slot name="extensions"/>
  </main>
</template>
