import type {components} from '../../api/accounts-schema';

export type AccountQuerySpec = components['schemas']['AccountQuerySpec'] & {
  team_scope?: string;
};
export interface AccountQueryAdapter {
  normalize(raw?: object): AccountQuerySpec;
  fromLegacy(params: URLSearchParams | string): AccountQuerySpec;
  toLegacy(raw: AccountQuerySpec, paging?: Record<string, string | number>): URLSearchParams;
}

/** The shared legacy AccountQuery remains the only normalizer/serializer. */
export function createAccountQueryAdapter(legacy: AccountQueryAdapter): AccountQueryAdapter {
  return {
    normalize: raw => legacy.normalize(raw),
    fromLegacy: params => legacy.fromLegacy(params),
    toLegacy: (raw, paging) => legacy.toLegacy(raw, paging),
  };
}
