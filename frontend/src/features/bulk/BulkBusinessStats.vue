<script setup lang="ts">
import {computed} from 'vue';
import {businessGroups,number,type BusinessGroup} from './bulkReportPresentation';
const props=defineProps<{metrics?:unknown;groups?:BusinessGroup[]}>();
const groups=computed(()=>props.groups??businessGroups(props.metrics));
</script>
<template>
  <div v-if="groups.length" class="bulk-business-groups">
    <section v-for="group in groups" :key="group.title" class="bulk-business-group">
      <header class="bulk-business-heading">
        <h4>{{group.title}}</h4>
        <span>{{group.title==='国家查询项'?'项':'账号数'}}</span>
      </header>
      <dl class="bulk-business-metrics">
        <div v-for="item in group.items" :key="item.title">
          <dt>{{item.title}}</dt>
          <dd>{{number(item.value)}}</dd>
        </div>
      </dl>
    </section>
  </div>
  <p v-else class="bulk-report-empty">暂无已确认的功能统计。</p>
</template>
