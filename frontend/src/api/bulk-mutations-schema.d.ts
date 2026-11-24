// 由 contracts/bulk-mutations.openapi.json 生成，请运行 npm run generate:api。
export interface paths {
    "/api/bulk-mutations/{command_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["getBulkMutationReceipt"];
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
        BulkMutationItem: {
            key: unknown;
            /** @enum {string} */
            status: "updated" | "skipped" | "failed";
            reason_code: string | null;
            reason: string;
            data: unknown;
        };
        BulkMutationReceiptPage: {
            ok: boolean;
            command_id: string;
            task_id?: string | null;
            run_id?: string | null;
            operation: string;
            status: string;
            requested_count: number;
            unique_count: number;
            duplicate_count: number;
            updated_count: number;
            skipped_count: number;
            failed_count: number;
            item_count: number;
            offset: number;
            limit: number;
            next_offset: number | null;
            items: components["schemas"]["BulkMutationItem"][];
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
    getBulkMutationReceipt: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path: {
                command_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Bulk command status and a complete page of item receipts */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BulkMutationReceiptPage"];
                };
            };
            /** @description Invalid pagination */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unknown command */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
}
