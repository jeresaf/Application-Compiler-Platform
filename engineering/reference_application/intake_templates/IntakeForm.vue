<script setup lang="ts">
import {ref} from 'vue';
import {call} from './api';
const contract=${CONTRACT};
const values=ref<Record<string,string>>(Object.fromEntries(Object.keys(contract.inputs).map(n=>[n,''])));
const busy=ref(false),message=ref(''),created=ref('');let key=crypto.randomUUID();
function valid(){return Object.entries(contract.inputs).every(([name,field])=>{const n=Array.from(values.value[name]??'').length;return n>=1&&n<=field.maxLength;});}
async function submit(){if(busy.value)return;if(!valid()){message.value='Invalid intake input';return;}busy.value=true;message.value='Creating';try{
 const result=await call<{resourceId:string}>(contract.path,{...values.value,idempotencyKey:key});
 created.value=result.resourceId;message.value='Case created';key=crypto.randomUUID();
}catch{message.value='Creation failed';}finally{busy.value=false;}}
</script>
<template><section aria-label="Synthetic case intake"><h2>Create case — synthetic preview</h2>
<form @submit.prevent="submit"><label v-for="(field,name) in contract.inputs" :key="name">{{ name }}<input v-model="values[name]" :name="name" required :disabled="busy" /></label><button :disabled="busy" type="submit">Create case</button></form>
<p role="status">{{ message }}</p><p v-if="created">Created resource: <output>{{ created }}</output></p>
</section></template>
