<script setup lang="ts">
import {computed} from 'vue';
import {label} from '../presentation';
import {phaseRelations} from './flowPresentation';
import {progressLabel, type Step} from './model';
const props = defineProps<{step: Step; siblings?: Step[]}>();
const relations = computed(() => phaseRelations(props.step, props.siblings));
</script>

<template>
  <dl class="tc-step-relations">
    <div v-for="item in relations" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></div>
    <div v-for="(child, index) in step.execution?.waits_for || []" :key="`${child.task_id}:${child.run_id}:${index}`"><dt>关联子任务</dt><dd><template v-if="child.task_id">{{ label('task_type', child.task_type) }} #{{ child.task_id }}<template v-if="child.run_id"> · 运行 #{{ child.run_id }}</template><template v-if="child.status"> · {{ progressLabel(child.status) }}</template></template><template v-else>子任务关联标识未记录<template v-if="child.status"> · {{ progressLabel(child.status) }}</template></template></dd></div>
  </dl>
</template>

<style scoped>
.tc-step-relations {display:flex;gap:4px 18px;flex-wrap:wrap;margin:6px 0;font-size:12px;color:var(--ui-color-text-secondary)}
.tc-step-relations>div {display:flex;gap:5px;min-width:0}
dt {flex:none}dd {margin:0;overflow-wrap:anywhere;color:var(--ui-color-text)}
</style>
