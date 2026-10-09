<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
import { ui } from './task-ui-model';
import { queryTasks, submitTask, type TaskCompletion, type TaskInput } from './task-contract';
import { ApiFailure } from './api';
import { identity, onIdentityChange } from './extensions/identity';
const rows=ref<TaskCompletion[]>([]), selected=ref<TaskCompletion|null>(null), search=ref('');
const input=ref<Partial<TaskInput>>({}), busy=ref(false), error=ref(false), invalid=ref(false), success=ref(''), empty=ref(false);
const snapshot=ref(identity());
const allowed=computed(()=>snapshot.value.actor===ui.boundary.data.actor.id && ui.boundary.data.permissions.every(p=>snapshot.value.permissions.has(p.id)));
const actionAllowed=computed(()=>allowed.value && ui.action.data.permissions.every(p=>snapshot.value.permissions.has(p.id)));
const dialog=ref<HTMLDialogElement|null>(null), actionButton=ref<HTMLButtonElement|null>(null), stateElement=ref<HTMLElement|null>(null), searchElement=ref<HTMLInputElement|null>(null);
type Pending={ key:string; row:TaskCompletion; values:Partial<TaskInput> };
const pending=ref<Pending|null>(null);let epoch=0;
const resourceError=computed(()=>invalid.value && (!selected.value || input.value[ui.resourceInputField]!==selected.value.resourceId));
const textError=computed(()=>invalid.value && (input.value[ui.textInputField]===undefined || input.value[ui.textInputField]===''));
async function focusState(){await nextTick();stateElement.value?.focus();}
function reset(){epoch++;rows.value=[];selected.value=null;input.value={};pending.value=null;success.value='';error.value=false;invalid.value=false;empty.value=false;busy.value=false;dialog.value?.close();snapshot.value=identity();}
const unsubscribe=onIdentityChange(reset);onUnmounted(unsubscribe);
function select(row:TaskCompletion){if(busy.value||pending.value)return;selected.value=row;input.value[ui.resourceInputField]=row.resourceId;}
function fail(failure:unknown){error.value=true;success.value='';if(failure instanceof ApiFailure && ['UNAUTHENTICATED','DENIED'].includes(failure.outcome)){rows.value=[];selected.value=null;input.value={};pending.value=null;}
 else if(failure instanceof ApiFailure && failure.outcome==='STALE'){selected.value=null;input.value={};pending.value=null;rows.value=[];}}
async function load(preserveSuccess=false){if(!allowed.value||busy.value||pending.value)return;const ticket=epoch;busy.value=true;error.value=false;if(!preserveSuccess)success.value='';
 try{const result=await queryTasks(search.value);if(ticket!==epoch)return;rows.value=result;selected.value=null;input.value={};empty.value=result.length===0;}
 catch(f){if(ticket===epoch){fail(f);await focusState();}}finally{if(ticket===epoch)busy.value=false;}}
async function confirm(){if(!actionAllowed.value||busy.value)return;invalid.value=true;error.value=false;success.value='';
 if(!pending.value && (resourceError.value||textError.value)){error.value=true;await focusState();return;}
 dialog.value?.showModal();await nextTick();dialog.value?.querySelector<HTMLButtonElement>('button')?.focus();}
async function cancel(){dialog.value?.close();await nextTick();actionButton.value?.focus();}
async function submit(){if(busy.value||!actionAllowed.value)return;
 if(!pending.value){if(!selected.value)return;pending.value={key:crypto.randomUUID(),row:{...selected.value},values:{...input.value}};}
 const logical=pending.value,ticket=epoch;busy.value=true;dialog.value?.close();error.value=false;
 try{const result=await submitTask(logical.values,logical.row.resourceId,logical.row.version,logical.key);if(ticket!==epoch)return;
 pending.value=null;selected.value=null;input.value={};invalid.value=false;success.value=result.output[ui.outputField];
 try{const refreshed=await queryTasks(search.value);if(ticket!==epoch)return;rows.value=refreshed;empty.value=rows.value.length===0;}catch(f){if(ticket!==epoch)return;rows.value=[];fail(f);}
 if(ticket===epoch)await focusState();}
 catch(f){if(ticket===epoch){fail(f);if(f instanceof ApiFailure && !['NETWORK','IN_PROGRESS','INTERNAL','RATE_DENIED','SEMANTIC_FAILURE'].includes(f.outcome))pending.value=null;await focusState();}}
 finally{if(ticket===epoch)busy.value=false;}}
function recovery(){if(pending.value||selected.value)void confirm();else{error.value=false;invalid.value=false;void nextTick().then(()=>searchElement.value?.focus());}}
onMounted(()=>{if(allowed.value)void load();else error.value=true;});
</script>
<template>
 <main :aria-busy="busy">
  <h1>{{ ui.screen.name }}</h1>
  <p v-if="busy" role="status" aria-live="polite">{{ ui.states.LOADING.data.message }}</p>
  <section v-if="error || !allowed" ref="stateElement" role="alert" tabindex="-1" class="error-summary">
   <h2>{{ ui.states.ERROR.data.message }}</h2>
   <p v-if="resourceError">{{ ui.controls[0].data.errorMessage }}</p><p v-if="textError">{{ ui.controls[1].data.errorMessage }}</p>
   <button v-if="allowed && !busy" type="button" @click="recovery">{{ ui.action.data.label }} — recovery</button>
   <button v-if="allowed && !busy && !pending" type="button" @click="load()">Retry search</button>
  </section>
  <section v-if="success" ref="stateElement" role="status" tabindex="-1"><h2>{{ ui.states.SUCCESS.data.message }}</h2><p>{{ success }}</p></section>
  <template v-if="allowed">
   <section :data-semantic-id="ui.search.id">
    <form @submit.prevent="load()"><label :for="ui.search.id">{{ ui.search.data.label }}</label><input ref="searchElement" :id="ui.search.id" v-model="search" type="search" :disabled="busy || !!pending"><button :disabled="busy || !!pending">Search</button></form>
   </section>
   <section :data-semantic-id="ui.table.id">
    <p v-if="empty && !busy">{{ ui.states.EMPTY.data.message }}</p><p v-if="empty && !busy">{{ ui.table.data.emptyMessage }}</p>
    <table v-if="rows.length"><caption>{{ ui.search.data.label }}</caption><thead><tr><th v-for="column in ui.columns" :key="column.id" scope="col">{{ column.name }}</th><th scope="col">Selection</th></tr></thead>
     <tbody><tr v-for="row in rows" :key="row.resourceId"><td v-for="column in ui.columns" :key="column.id">{{ row.output[column.id] }}</td><td><button type="button" :disabled="busy || !!pending" :aria-pressed="selected?.resourceId===row.resourceId" @click="select(row)">Select {{ row.resourceId }}</button></td></tr></tbody>
    </table>
   </section>
   <section :data-semantic-id="ui.wizard.id" :aria-label="ui.wizard.name">
    <form :data-semantic-id="ui.form.id" @submit.prevent="confirm" novalidate>
     <p v-if="selected">Selected resource: {{ selected.resourceId }}; version {{ selected.version }}</p>
     <div v-for="(control,index) in ui.controls" :key="control.id">
      <label :for="control.id">{{ control.data.label }}</label>
      <input v-if="control.data.purpose==='TEXT'" :id="control.id" v-model="input[control.data.field.id]" type="text" required readonly :aria-invalid="resourceError" :aria-describedby="control.id+'-error'">
      <textarea v-else :id="control.id" v-model="input[control.data.field.id]" required :disabled="busy || !!pending" :aria-invalid="textError" :aria-describedby="control.id+'-error'"/>
      <p :id="control.id+'-error'">{{ (index===0?resourceError:textError)?control.data.errorMessage:'' }}</p>
     </div>
     <button v-if="actionAllowed && selected" ref="actionButton" :disabled="busy" data-component-role="WorkflowAction">{{ ui.action.data.label }}</button>
    </form>
   </section>
  </template>
  <dialog ref="dialog" aria-labelledby="confirm-title" @cancel.prevent="cancel"><h2 id="confirm-title">{{ ui.action.data.label }}</h2><p>Confirm this action for {{ pending?.row.resourceId || selected?.resourceId }}?</p><button type="button" :disabled="busy" @click="cancel">Cancel</button><button type="button" :disabled="busy" @click="submit">Confirm</button></dialog>
  <slot name="extensions"/>
 </main>
</template>
