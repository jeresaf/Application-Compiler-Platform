<script setup lang="ts">
import {ref,onMounted} from 'vue';import {call} from './api';import {reportContract as c} from './report-contract';
type Row={resourceId:string;version:number;state:string;values:Record<string,string>};
type Result={items:Row[];total:number;counts:{state:string;count:number}[]};
const filters=ref<Record<string,string>>(Object.fromEntries(c.filters.map(f=>[f.name,'']))),page=ref(0),data=ref<Result>({items:[],total:0,counts:[]}),busy=ref(false),error=ref(''),selected=ref(''),history=ref<{operation:string;occurredAt:string}[]>([]),historyError=ref(''),historyBusy=ref(false),sort=ref('IDENTITY');
let generation=0;
async function refresh(reset=false){if(reset)page.value=0;const run=++generation;busy.value=true;error.value='';selected.value='';history.value=[];try{
 const result=await call<Result>(c.path,{filters:Object.fromEntries(Object.entries(filters.value).filter(([,v])=>v!=='')),sort:{field:sort.value,direction:'ASC'},page:page.value,size:c.pagination.defaultSize});
 if(!result||!Array.isArray(result.items)||!Array.isArray(result.counts)||!Number.isSafeInteger(result.total)||result.total<0||result.items.some(r=>!r||typeof r.resourceId!=='string'||!r.values||typeof r.values!=='object'))throw new Error('REPORT_RESPONSE');
 if(run===generation)data.value=result;
}catch{if(run===generation){data.value={items:[],total:0,counts:[]};error.value='Reporting unavailable';}}finally{if(run===generation)busy.value=false;}}
async function select(row:Row){selected.value=row.resourceId;history.value=[];historyError.value='';historyBusy.value=true;try{
 const result=await call<{items:{operation:string;occurredAt:string}[]}>(c.path+'/history',{resourceId:row.resourceId,page:0,size:c.pagination.maximumSize});
 if(!result||!Array.isArray(result.items))throw new Error('REPORT_HISTORY_RESPONSE');
 if(selected.value===row.resourceId)history.value=result.items;
}catch{historyError.value='Audit history unavailable';}finally{historyBusy.value=false;}}
function move(delta:number){page.value+=delta;refresh();}
onMounted(()=>refresh());
</script>
<template><section aria-label="Reporting" class="report-panel"><h2>Reports and audit history</h2>
<form @submit.prevent="refresh(true)"><label v-for="f in c.filters" :key="f.name">Report {{f.name}}<select :aria-label="'Report '+f.name" v-if="f.type==='STATE'" v-model="filters[f.name]"><option value="">All states</option><option v-for="state in c.states" :key="state.id" :value="state.id">{{state.label}}</option></select><input v-else v-model="filters[f.name]" :maxlength="256" /></label>
<label>Report sort<select v-model="sort"><option value="IDENTITY">Identity</option><option value="STATE">Workflow state</option><option v-for="field in c.fields" :key="field.id" :value="field.id">{{field.label}}</option></select></label><button :disabled="busy">Refresh report</button></form>
<p v-if="busy" role="status">Loading report</p><p v-if="error" role="alert">{{error}}</p>
<div aria-label="State counts"><span v-for="count in data.counts" :key="count.state">{{count.state}}: {{count.count}} </span></div>
<p role="status">{{data.total}} permitted cases</p><p v-if="!busy&&!error&&data.items.length===0">No report results</p>
<div class="report-scroll"><table aria-label="Report results"><thead><tr><th v-for="field in c.fields" :key="field.id" scope="col">{{field.label}}</th><th scope="col">State</th><th scope="col">Audit history</th></tr></thead><tbody><tr v-for="row in data.items" :key="row.resourceId"><td v-for="field in c.fields" :key="field.id">{{row.values[field.id]}}</td><td>{{row.state}}</td><td><button @click="select(row)">History {{row.resourceId}}</button></td></tr></tbody></table></div>
<nav aria-label="Report pages"><button @click="move(-1)" :disabled="busy||page===0">Previous report page</button><span>Page {{page+1}}</span><button @click="move(1)" :disabled="busy||(page+1)*c.pagination.defaultSize>=data.total">Next report page</button></nav>
<section v-if="selected" aria-label="Selected audit history"><h3>Audit history</h3><p>{{selected}}</p><p v-if="historyBusy" role="status">Loading history</p><p v-if="historyError" role="alert">{{historyError}}</p><p v-if="!historyBusy&&!historyError&&history.length===0">No permitted history</p><ol><li v-for="(entry,i) in history" :key="i">{{entry.operation}} — <time>{{entry.occurredAt}}</time></li></ol></section>
</section></template>
<style scoped>.report-panel{margin-top:2rem;border-top:1px solid;padding-top:1rem}.report-panel form{display:flex;gap:.75rem;flex-wrap:wrap}.report-panel label{display:flex;flex-direction:column}.report-scroll{overflow:auto}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:.5rem}nav{display:flex;gap:.75rem;align-items:center;margin:1rem 0}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #185abc;outline-offset:2px}@media(max-width:40rem){.report-panel form>*{flex:1 1 100%}td{overflow-wrap:anywhere}}</style>
