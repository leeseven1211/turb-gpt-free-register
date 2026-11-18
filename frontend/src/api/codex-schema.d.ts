// 由 contracts/codex.openapi.json 生成，请运行 npm run generate:api。
export interface paths {
    "/api/codex": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description 分页查询。plan/status/oauth_status 为单值；account_id 是 OAuth 字符串。facets 是全局计数，summary 是未归档全局计数。 */
        get: operations["listCodex"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["archiveCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/archive-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["archiveBulkCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/delete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["deleteCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/delete-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["deleteBulkCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/reset-export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["resetExportCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/refresh-token-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["refreshTokenBulkCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/retry-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["retryBulkCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/upload-sub2-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["uploadSub2BulkCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/download-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["downloadBulkCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/download-bulk-from-cpa": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post: operations["downloadBulkFromCpaCodex"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/download/{filename}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description 显式下载会增加导出计数；不得预取或自动重试。成功为 JSON attachment。 */
        get: operations["downloadCodex"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/codex/download-from-cpa/{filename}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description 显式下载会增加导出计数；不得预取或自动重试。成功为 JSON attachment。 */
        get: operations["downloadfromcpaCodex"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        CodexRow: {
            filename: string;
            email?: string;
            plan?: string;
            account_id?: string;
            type?: string;
            last_refresh?: string;
            expired?: string;
            oauth_status?: string;
            oauth_expires_at?: string;
            mtime?: string | null;
            exported_at?: string | null;
            sub2_uploaded_at?: string | null;
            sub2_sync_error?: string | null;
            sub2api_status?: string | null;
            oauth_refresh_attempted_at?: string | null;
            oauth_refresh_error?: string | null;
            oauth_account_status?: string | null;
            oauth_account_status_reason?: string | null;
            oauth_account_status_at?: string | null;
            archived_at?: string | null;
            size?: number;
            exported_count?: number;
            sub2_uploaded_count?: number;
            exported?: boolean;
            archived?: boolean;
            oauth_refreshable?: boolean;
            oauth_auto_refresh?: boolean;
            oauth_reauth_required?: boolean;
            sub2api_account_id?: number | string | null;
            sub2api_http_status?: number | string | null;
            oauth_seconds_left?: number | null;
            /** @enum {string} */
            access_token_preview?: "已保存" | "";
        };
        CodexFacet: {
            value: string;
            label?: string;
            count: number;
        };
        CodexFacets: {
            [key: string]: components["schemas"]["CodexFacet"][];
        };
        CodexListResponse: {
            ok?: boolean;
            accounts: components["schemas"]["CodexRow"][];
            total: number;
            page: number;
            page_size: number;
            offset?: number;
            limit?: number;
            revision?: string;
            facets: components["schemas"]["CodexFacets"];
            summary?: {
                total: number;
                exported: number;
                pending: number;
            };
        };
        CodexTaskReference: {
            filename?: string;
            accepted?: boolean;
            task_id?: number;
            run_id?: number | null;
            account_id?: number | string | null;
            email?: string;
            status?: string;
            busy?: boolean;
            reused?: boolean;
            source_system?: string;
            source_id?: number | string;
            trigger?: string;
        } & {
            [key: string]: unknown;
        };
        CodexSkipped: {
            filename?: string;
            reason?: string;
            error?: string;
            error_code?: string;
            task_id?: number;
            run_id?: number;
        } & {
            [key: string]: unknown;
        };
        CodexActionResponse: {
            ok: boolean;
            filename?: string;
            archived?: boolean;
            record?: {
                archived?: boolean;
                archived_at?: string | null;
            };
            deleted?: string | string[];
            deleted_count?: number;
            updated?: {
                filename: string;
                archived?: boolean;
            }[];
            updated_count?: number;
            message?: string;
            accepted?: boolean;
            status?: string;
            batch_id?: number | string | null;
            batch_uuid?: string;
            workers?: number;
            started?: components["schemas"]["CodexTaskReference"][];
            started_count?: number;
            queued?: components["schemas"]["CodexTaskReference"][];
            queued_count?: number;
            uploaded?: components["schemas"]["CodexTaskReference"][];
            uploaded_count?: number;
            failed?: components["schemas"]["CodexSkipped"][];
            failed_count?: number;
            skipped?: components["schemas"]["CodexSkipped"][];
            skipped_count?: number;
        };
        CodexError: {
            /** @constant */
            ok: false;
            error?: string | {
                message?: string;
                code?: string;
            };
            error_code?: string;
            message?: string;
            errors?: components["schemas"]["CodexSkipped"][];
            skipped?: components["schemas"]["CodexSkipped"][];
        } & {
            [key: string]: unknown;
        };
        CodexBulkDownload: {
            exported_at: string;
            count: number;
            credentials: {
                filename: string;
                data: {
                    [key: string]: unknown;
                };
            }[];
            errors?: components["schemas"]["CodexSkipped"][];
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listCodex: {
        parameters: {
            query?: {
                paged?: string;
                page?: number;
                page_size?: number;
                archived?: string;
                q?: string;
                plan?: string;
                status?: string;
                oauth_status?: string;
                account_id?: string;
                sub2api_id?: string;
                date_from?: string;
                date_to?: string;
                expired_date?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexListResponse"];
                };
            };
        };
    };
    archiveCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filename: string;
                    /** @default true */
                    archived?: boolean;
                };
            };
        };
        responses: {
            /** @description 成功 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexActionResponse"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    archiveBulkCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filenames: string[];
                    /** @default true */
                    archived?: boolean;
                };
            };
        };
        responses: {
            /** @description 成功 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexActionResponse"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    deleteCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filename: string;
                };
            };
        };
        responses: {
            /** @description 成功 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexActionResponse"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    deleteBulkCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filenames: string[];
                };
            };
        };
        responses: {
            /** @description 成功 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexActionResponse"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    resetExportCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filename: string;
                };
            };
        };
        responses: {
            /** @description 成功 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexActionResponse"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    refreshTokenBulkCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filenames: string[];
                };
            };
        };
        responses: {
            /** @description 成功 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexActionResponse"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    retryBulkCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filenames?: string[];
                    account_ids?: number[];
                    ids?: number[];
                } | unknown | unknown | unknown;
            };
        };
        responses: {
            /** @description 成功 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexActionResponse"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    uploadSub2BulkCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filenames: string[];
                };
            };
        };
        responses: {
            /** @description 成功 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexActionResponse"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    downloadBulkCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filenames: string[];
                };
            };
        };
        responses: {
            /** @description 成功 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexBulkDownload"];
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    downloadBulkFromCpaCodex: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    filenames: string[];
                };
            };
        };
        responses: {
            /** @description ZIP attachment；部分失败见 manifest.json，无逐文件外层回执 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/zip": string;
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    downloadCodex: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                filename: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 敏感凭证附件，仅供下载，不进入列表状态 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
    downloadfromcpaCodex: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                filename: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 敏感凭证附件，仅供下载，不进入列表状态 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description 业务错误 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CodexError"];
                };
            };
        };
    };
}
