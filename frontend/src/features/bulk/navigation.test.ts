import {expect,it} from 'vitest';
import {normalizeBulkNavigation} from './navigation';
it('bulk navigation preserves opaque cursor and bigint identities without numeric conversion',()=>{
 const nav=normalizeBulkNavigation({view:'detail',batch_id:'9223372036854775807',round_id:'9007199254740993',cursor:'signed+/=token',result_state:'request_unknown'});
 expect(nav).toEqual({tab:'bulk',view:'detail',batch_id:'9223372036854775807',round_id:'9007199254740993',cursor:'signed+/=token',result_state:'failed'});
});
it('invalid detail links use list and detail legacy search cannot reuse its old cursor scope',()=>{
 expect(normalizeBulkNavigation({view:'detail',batch_id:'1.5'})).toEqual({tab:'bulk',view:'list'});
 expect(normalizeBulkNavigation({view:'detail',batch_id:'1',q:'old search',cursor:'wrong'})).toEqual({tab:'bulk',view:'detail',batch_id:'1'});
 expect(normalizeBulkNavigation({view:'detail',batch_id:'1',reason_code:'old_error',cursor:'wrong'})).toEqual({tab:'bulk',view:'detail',batch_id:'1'});
});
