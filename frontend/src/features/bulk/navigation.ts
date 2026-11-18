import type {BulkNavigation} from './contracts';
const fields=['batch_id','round_id','result_state','cursor','q','operation','state','created_from','created_to'] as const;
const aliases=new Set(['attention_required','request_unknown','manual_reconcile','unknown','unconfirmed']);
export function normalizeBulkNavigation(value:Partial<BulkNavigation>={}):BulkNavigation {
  const view=['list','create','detail'].includes(value.view||'')?value.view!:'list';
  const result:BulkNavigation={tab:'bulk',view};
  for(const field of fields)if(typeof value[field]==='string'&&value[field])result[field]=value[field];
  if(view==='detail'){
    if(!/^[1-9]\d*$/.test(result.batch_id||''))return{tab:'bulk',view:'list'};
    // Older detail links carried list-only fields and an incompatible cursor scope.
    if(result.q||value.reason_code){delete result.q;delete result.cursor;}
    if(result.result_state&&aliases.has(result.result_state))result.result_state='failed';
  }
  return result;
}
