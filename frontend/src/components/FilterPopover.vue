<script setup lang="ts">
import {PopoverClose, PopoverContent, PopoverPortal, PopoverRoot, PopoverTrigger} from 'reka-ui';

defineProps<{label: string; triggerLabel?: string; active?: boolean; summary?: string; open: boolean}>();
const emit = defineEmits<{'update:open': [boolean]}>();
</script>

<template>
  <PopoverRoot :open="open" :modal="false" @update:open="emit('update:open', $event)">
    <PopoverTrigger as-child>
      <button type="button" class="tc-column-filter-trigger" :class="{'is-active': active}"
        :data-active="active ? '' : undefined" :aria-label="`筛选${label}`"
        :title="active ? `${label}：${summary || '已筛选'}` : `筛选${label}`">
        <span class="tc-column-filter-label">{{ triggerLabel || label }}</span>
        <svg class="tc-column-filter-icon" viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true" focusable="false">
          <path d="M2 3h12L9.5 8.3V13l-3-1.5V8.3L2 3Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
        </svg>
      </button>
    </PopoverTrigger>
    <PopoverPortal>
      <PopoverContent class="tc-filter-popover list-filter-popover" :aria-label="`筛选${label}`" side="bottom" align="start" :side-offset="6" :collision-padding="10" hide-when-detached>
        <div class="tc-filter-popover-heading list-filter-popover__heading">筛选{{ label }}</div>
        <slot />
        <PopoverClose class="tc-filter-popover-close list-filter-popover__close" :aria-label="`关闭${label}筛选`" title="关闭筛选">
          <svg viewBox="0 0 16 16" width="16" height="16" fill="none" aria-hidden="true" focusable="false">
            <path d="m4 4 8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          </svg>
        </PopoverClose>
      </PopoverContent>
    </PopoverPortal>
  </PopoverRoot>
</template>

<style scoped>
/* 浮层由 Portal 挂到 body，基础样式随组件提供，不依赖使用方页面。 */
.tc-column-filter-trigger {display:inline-flex;align-items:center;gap:6px;max-width:100%;min-height:32px;padding:3px 0;border:0;background:transparent;color:inherit;font:inherit;text-align:left;cursor:pointer}
.tc-column-filter-trigger svg {width:14px;height:14px;flex:none;fill:none;stroke:currentColor;stroke-width:1.5}
.tc-column-filter-trigger:hover,.tc-column-filter-trigger[data-state=open],.tc-column-filter-trigger.is-active {color:var(--ui-color-brand)}
.tc-column-filter-trigger.is-active {font-weight:650}
.tc-column-filter-trigger.is-active svg {fill:var(--ui-color-brand-soft);stroke-width:2}
.tc-column-filter-trigger:focus-visible {outline:2px solid var(--ui-color-brand);outline-offset:3px}
/* Reka 的 Portal 根节点不透传 SFC scope 属性，使用组件专属全局类定位真实 DOM。 */
:global(.list-filter-popover) {display:flex;flex-direction:column;box-sizing:border-box;z-index:1200;width:280px;max-width:calc(100vw - 20px);max-height:min(440px,var(--reka-popover-content-available-height));overflow:auto;padding:14px;border:1px solid var(--ui-color-border-strong);border-radius:10px;background:var(--ui-color-surface);color:var(--ui-color-text);box-shadow:0 8px 28px rgb(23 32 51 / 16%);font:13px/1.5 var(--ui-font-sans)}
:global(.list-filter-popover *) {box-sizing:border-box}
:global(.list-filter-popover button),:global(.list-filter-popover input),:global(.list-filter-popover select) {font:inherit}
:global(.list-filter-popover button) {cursor:pointer}
:global(.list-filter-popover :is(button,input,select):focus-visible) {outline:2px solid var(--ui-color-brand);outline-offset:2px}
:global(.list-filter-popover__heading) {flex:0 0 auto;font-size:13px;font-weight:650;margin:0 32px 12px 0}
:global(.list-filter-popover__close) {position:absolute;top:10px;right:10px;display:grid;place-items:center;width:28px;height:28px;padding:0;border:0;border-radius:4px;background:transparent;color:var(--ui-color-text-secondary)}
:global(.list-filter-popover__close:hover) {background:var(--ui-color-surface-subtle)}
@media(max-width:680px) {
  :global(.list-filter-popover) {width:300px}
  :global(.list-filter-popover__close) {width:36px;height:36px}
}
</style>
