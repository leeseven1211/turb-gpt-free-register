import {h, render} from 'vue';
import BulkReportView from './BulkReportView.vue';
import type {BulkRecord} from './contracts';

export interface BulkReportState {
  operationKey: string;
  report: BulkRecord | null;
  error?: string;
  formatDateTime: (value: unknown) => string;
  onRetry: () => void;
}

/** The shell owns the request, scope, focus, and retry action. */
export function mountBulkReport(element: HTMLElement, initial: BulkReportState) {
  // The initial Vue render may replace the shell's fallback report.
  element.replaceChildren();
  function setView(state: BulkReportState) {
    render(h(BulkReportView, {...state}), element);
  }
  setView(initial);
  return {
    setView,
    destroy() {
      render(null, element);
    },
  };
}
