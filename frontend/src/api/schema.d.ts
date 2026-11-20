// 由 contracts/task-center.openapi.json 生成，请运行 npm run generate:api。
export interface paths {
    "/api/operations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 分页查询任务；默认返回筛选计数与最近批次 */
        get: operations["listOperations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/receipts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 批量查询指定任务和执行实例的回执 */
        get: operations["listOperationReceipts"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{task_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 查询任务及运行历史 */
        get: operations["getOperation"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{task_id}/runs/{run_id}/progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 查询选定运行的完整进度 */
        get: operations["getOperationProgress"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{task_id}/runs/{run_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 分页读取运行事件
         * @description 沿用既有行为：任务不存在返回 404；Run 不属于任务或不存在时返回空页，不暴露其他任务的事件。
         */
        get: operations["getOperationEvents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{task_id}/runs/{run_id}/logs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 增量读取运行日志 */
        get: operations["getOperationLogs"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{task_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** 重跑任务，复用现有动作边界 */
        post: operations["retryOperation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{task_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** 取消任务，复用现有动作边界 */
        post: operations["cancelOperation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{task_id}/terminate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** 终止任务，复用现有动作边界 */
        post: operations["terminateOperation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/{task_id}/delete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** 隐藏任务，复用现有动作边界 */
        post: operations["deleteOperation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/operations/bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** 批量执行现有任务操作 */
        post: operations["bulkOperations"];
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
        ErrorInfo: {
            code?: string | null;
            display_code?: string | null;
            summary?: string | null;
            cause_code?: string | null;
            cause_display_code?: string | null;
            cause_summary?: string | null;
            category?: string | null;
            stage?: string | null;
            detail?: string | null;
            suggestion?: string | null;
        } & {
            [key: string]: unknown;
        };
        NextAction: {
            action: string;
            label?: string;
            source_job_id?: number | null;
            enabled?: boolean;
            reason?: string | null;
        } & {
            [key: string]: unknown;
        };
        AdmissionReason: {
            code?: string;
            message?: string | null;
            label?: string | null;
            limit?: number | null;
            used?: number | null;
        } & {
            [key: string]: unknown;
        };
        DebugArtifacts: {
            available?: boolean;
            page_state_available?: boolean;
            screenshot_available?: boolean;
            har_url?: string;
            page_state_url?: string;
            screenshot_url?: string;
        } & {
            [key: string]: unknown;
        };
        OperationRun: {
            source_system?: string | null;
            source_id?: string | null;
            status?: string | null;
            internal_status?: string | null;
            error_message?: string | null;
            error_code?: string | null;
            error_category?: string | null;
            failure_stage?: string | null;
            failure_stage_label?: string | null;
            created_at?: string | null;
            updated_at?: string | null;
            started_at?: string | null;
            completed_at?: string | null;
            current_stage?: string | null;
            progress_stage?: string | null;
            admission_wait_reason?: string | null;
            id: number;
            result_summary?: {
                [key: string]: unknown;
            } | null;
            data?: {
                [key: string]: unknown;
            } | null;
            error_info?: components["schemas"]["ErrorInfo"] | null;
            duration_ms?: number | null;
            admission_wait_reasons?: components["schemas"]["AdmissionReason"][];
            task_id?: number;
            run_uuid?: string;
            run_no?: number;
            trigger?: string | null;
            config_snapshot?: {
                [key: string]: unknown;
            };
            debug_artifacts?: components["schemas"]["DebugArtifacts"];
            execution_id?: string | null;
            log_file?: string | null;
            bulk_context?: {
                [key: string]: unknown;
            };
            debug_pause?: {
                [key: string]: unknown;
            } | null;
        } & {
            [key: string]: unknown;
        };
        OperationEvent: {
            id: number;
            task_id?: number;
            run_id?: number | null;
            run_no?: number | null;
            event_uuid?: string | null;
            event_type?: string;
            level?: string;
            stage?: string | null;
            main_step_id?: string | null;
            step_id?: string | null;
            stage_label?: string | null;
            message?: string | null;
            created_at?: string | null;
            detail?: {
                [key: string]: unknown;
            };
            fields?: {
                [key: string]: unknown;
            };
            source_system?: string | null;
        } & {
            [key: string]: unknown;
        };
        OperationLog: {
            ts?: string | null;
            task_id?: number | null;
            run_id?: number | null;
            event_id?: number | string | null;
            event_uuid?: string | null;
            event_type?: string | null;
            level?: string | null;
            stage?: string | null;
            stage_label?: string | null;
            main_step_id?: string | null;
            message?: string | null;
            fields?: {
                [key: string]: unknown;
            };
        } & {
            [key: string]: unknown;
        };
        OperationTask: {
            source_system?: string | null;
            source_id?: string | null;
            status?: string | null;
            internal_status?: string | null;
            error_message?: string | null;
            error_code?: string | null;
            error_category?: string | null;
            failure_stage?: string | null;
            failure_stage_label?: string | null;
            created_at?: string | null;
            updated_at?: string | null;
            started_at?: string | null;
            completed_at?: string | null;
            current_stage?: string | null;
            progress_stage?: string | null;
            admission_wait_reason?: string | null;
            id: number;
            result_summary?: {
                [key: string]: unknown;
            } | null;
            data?: {
                [key: string]: unknown;
            } | null;
            error_info?: components["schemas"]["ErrorInfo"] | null;
            duration_ms?: number | null;
            admission_wait_reasons?: components["schemas"]["AdmissionReason"][];
            task_uuid?: string;
            task_type: string;
            target_type?: string | null;
            target_id?: number | null;
            email?: string | null;
            account_id?: number | null;
            target_status?: string | null;
            internal_target_status?: string | null;
            batch_id?: number | null;
            batch_uuid?: string | null;
            batch_title?: string | null;
            batch_type?: string | null;
            parent_task_id?: number | null;
            attempt_id?: number | null;
            retryable?: boolean;
            retry_reason?: string | null;
            next_actions?: components["schemas"]["NextAction"][];
            current_run_id?: number | null;
            last_run_id?: number | null;
            last_run_no?: number | null;
            run_count?: number;
            runs?: components["schemas"]["OperationRun"][];
            events?: components["schemas"]["OperationEvent"][];
            resources?: {
                [key: string]: unknown;
            }[];
            attempt?: {
                [key: string]: unknown;
            } | null;
            parent?: components["schemas"]["OperationTask"] | null;
            flow?: {
                [key: string]: unknown;
            }[];
            bulk_context?: {
                [key: string]: unknown;
            };
            latest_legacy_job_id?: number | null;
            debug_pause?: {
                [key: string]: unknown;
            } | null;
            email_snapshot?: string | null;
            trigger?: string | null;
            current_stage_label?: string | null;
            bulk_batch_id?: string | null;
            bulk_round_id?: string | null;
        } & {
            [key: string]: unknown;
        };
        FacetOption: {
            value: string;
            count: number;
            label?: string;
        } & {
            [key: string]: unknown;
        };
        OperationBatch: {
            id: number;
            batch_uuid?: string;
            title?: string | null;
            batch_type?: string | null;
            status?: string | null;
            created_at?: string | null;
        } & {
            [key: string]: unknown;
        };
        OperationList: {
            ok: boolean;
            items: components["schemas"]["OperationTask"][];
            total: number;
            page: number;
            page_size: number;
            revision: string;
            facets?: {
                [key: string]: components["schemas"]["FacetOption"][];
            };
            batches?: components["schemas"]["OperationBatch"][];
        } & {
            [key: string]: unknown;
        };
        OperationDetail: {
            ok: boolean;
            task: components["schemas"]["OperationTask"];
        } & {
            [key: string]: unknown;
        };
        OperationReceipts: {
            ok: boolean;
            items: {
                task_id: string;
                run_id: string | null;
                status: string;
                message: string;
            }[];
        };
        ProgressStep: {
            id: string;
            step_id?: string;
            label: string;
            name?: string;
            state: string;
            display_status?: string;
            status?: string;
            reason?: string | null;
            message?: string | null;
            started_at?: string | null;
            completed_at?: string | null;
            duration_ms?: number | null;
            /** @description 本 Run/所选线路内按已记录开始时间与首条阶段证据得到的观察排序，不能据此推断严格先后或并行。 */
            observed_order?: number | null;
            raw_stages?: string[];
            attempts?: {
                [key: string]: unknown;
            }[];
            children?: components["schemas"]["ProgressStep"][];
            evidence?: string | {
                [key: string]: unknown;
            } | null;
            group?: string;
            depends_on?: string[];
            execution?: components["schemas"]["ProgressExecution"];
            step_instances?: {
                [key: string]: unknown;
            }[];
        } & {
            [key: string]: unknown;
        };
        ProgressFailure: {
            step_id?: string | null;
            label?: string | null;
            stage?: string | null;
            message?: string | null;
            event_id?: number | string | null;
            error_info?: components["schemas"]["ErrorInfo"] | null;
            inferred?: boolean;
            reconcile_required?: boolean;
            country_failures?: {
                [key: string]: unknown;
            }[];
            evidence?: string | {
                [key: string]: unknown;
            } | null;
        } & {
            [key: string]: unknown;
        };
        ProgressOutcome: {
            status?: string;
            internal_status?: string;
            message?: string | null;
            label?: string | null;
            child_tasks?: ({
                task_id: number | string;
                run_id?: number | string | null;
                task_type?: string | null;
                status?: string | null;
                error_message?: string | null;
            } & {
                [key: string]: unknown;
            })[];
        } & {
            [key: string]: unknown;
        };
        OperationProgress: {
            task_id: number;
            run_id: number;
            revision: string;
            flow_version?: number;
            source?: string;
            main_steps: components["schemas"]["ProgressStep"][];
            current?: {
                [key: string]: unknown;
            } | null;
            outcome: components["schemas"]["ProgressOutcome"];
            failure?: components["schemas"]["ProgressFailure"] | null;
            history_unknown?: {
                [key: string]: unknown;
            }[];
            route_attempts?: {
                [key: string]: unknown;
            }[];
            structure?: components["schemas"]["ProgressStructure"];
        } & {
            [key: string]: unknown;
        };
        ProgressResponse: {
            ok: boolean;
            progress: components["schemas"]["OperationProgress"];
        } & {
            [key: string]: unknown;
        };
        EventsResponse: {
            ok: boolean;
            items: components["schemas"]["OperationEvent"][];
            next_after_id: number;
            has_more: boolean;
        } & {
            [key: string]: unknown;
        };
        LogsResponse: {
            ok: boolean;
            items: components["schemas"]["OperationLog"][];
            next_cursor: number;
            has_more: boolean;
            available: boolean;
            size?: number;
            run_terminal: boolean;
        } & {
            [key: string]: unknown;
        };
        ApiError: {
            /** @constant */
            ok: false;
            error: string;
            error_code?: string;
        } & {
            [key: string]: unknown;
        };
        ActionResult: {
            task_id: number;
            run_id?: number | null;
            state?: string | null;
            status?: string | null;
            message?: string | null;
            error?: string | null;
            error_code?: string | null;
            result?: {
                [key: string]: unknown;
            };
        } & {
            [key: string]: unknown;
        };
        ActionResponse: {
            ok?: boolean;
            accepted?: boolean | components["schemas"]["ActionResult"][];
            accepted_count?: number;
            skipped?: components["schemas"]["ActionResult"][];
            skipped_count?: number;
            deleted?: boolean | number[];
            deleted_count?: number;
            task_id?: number;
            run_id?: number;
            action?: string;
            state?: string | null;
            message?: string | null;
            error?: string | null;
            error_code?: string | null;
            busy?: boolean;
            reused?: boolean;
            status?: string | null;
        } & {
            [key: string]: unknown;
        };
        ProgressCondition: {
            label: string;
            /** @enum {string} */
            state: "met" | "not_met" | "unknown";
            evidence: string;
        } & {
            [key: string]: unknown;
        };
        ProgressWaitTarget: {
            task_id?: number | string | null;
            run_id?: number | string | null;
            task_type?: string | null;
            status?: string | null;
            evidence: string;
        } & {
            [key: string]: unknown;
        };
        ProgressRetry: {
            /** @enum {string} */
            state: "observed" | "recovered" | "unknown";
            attempt_count: number | null;
            event_ids: string[];
        } & {
            [key: string]: unknown;
        };
        /** @description 只读展示语义。runtime_contract 仅表示已有展示定义，不代表实际执行证据；依赖、条件、子任务等待和重试分别表达。 */
        ProgressExecution: {
            /** @enum {string} */
            kind: "stage" | "conditional" | "child_task" | "result" | "unknown";
            condition: components["schemas"]["ProgressCondition"] | null;
            /** @enum {string} */
            dependency_state: "waiting" | "blocked" | "satisfied" | "unknown";
            waits_for: components["schemas"]["ProgressWaitTarget"][];
            parallel_group: string | null;
            retry: components["schemas"]["ProgressRetry"];
            /** @enum {string} */
            source: "runtime_contract" | "event" | "unknown";
        } & {
            [key: string]: unknown;
        };
        /** @description 观察顺序不是严格执行顺序；未提供明确并行组时不得从排列或时间重叠推断并行。 */
        ProgressStructure: {
            version: number;
            /** @enum {string} */
            order_basis: "observed_events";
            /** @enum {string} */
            parallelism: "explicit" | "unknown";
            note: string;
        } & {
            [key: string]: unknown;
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
    listOperations: {
        parameters: {
            query?: {
                /** @description 页码，从 1 开始 */
                page?: number;
                /** @description 每页数量 */
                page_size?: number;
                /** @description 任务类型，可用逗号组合 */
                type?: string;
                /** @description 公开执行状态，仅支持单个状态值，不支持逗号组合 */
                status?: string;
                /** @description 任务来源 */
                source?: string;
                /** @description 全文搜索 */
                q?: string;
                /** @description 任务编号筛选 */
                task_id?: string;
                /** @description 目标邮箱或标识 */
                target?: string;
                /** @description 公开目标状态 */
                target_status?: string;
                /** @description 批次标题或标识 */
                batch?: string;
                /** @description 运行次数，可用 4+ */
                run_count?: string;
                /** @description 执行阶段 */
                stage?: string;
                /** @description 创建日期起点 */
                created_from?: string;
                /** @description 创建日期终点 */
                created_to?: string;
                /** @description 结果文本 */
                result?: string;
                /** @description 指定批次 ID */
                batch_id?: number;
                /** @description 0/false/no 表示省略筛选计数；轮询使用 0 */
                include_facets?: string;
                /** @description 0/false/no 表示省略最近批次；轮询使用 0 */
                include_batches?: string;
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
                    "application/json": components["schemas"]["OperationList"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    listOperationReceipts: {
        parameters: {
            query: {
                /** @description 任务 ID 或以冒号连接的任务 ID 与执行实例 ID。重复参数最多传入 20 项。 */
                ref: string[];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 返回已找到的回执 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OperationReceipts"];
                };
            };
            /** @description 回执查询参数无效 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getOperation: {
        parameters: {
            query?: {
                /** @description 0/false/no/off 省略全历史事件；新前端显式传 0 */
                include_events?: string;
            };
            header?: never;
            path: {
                /** @description 任务 ID */
                task_id: number;
            };
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
                    "application/json": components["schemas"]["OperationDetail"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getOperationProgress: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 任务 ID */
                task_id: number;
                /** @description 执行实例 ID */
                run_id: number;
            };
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
                    "application/json": components["schemas"]["ProgressResponse"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getOperationEvents: {
        parameters: {
            query?: {
                /** @description 省略读取最新一页；0 从头读取；其余值读取更大的事件 ID */
                after_id?: number;
                /** @description 单页上限 */
                limit?: number;
            };
            header?: never;
            path: {
                /** @description 任务 ID */
                task_id: number;
                /** @description 执行实例 ID */
                run_id: number;
            };
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
                    "application/json": components["schemas"]["EventsResponse"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    getOperationLogs: {
        parameters: {
            query?: {
                /** @description 日志字节游标；省略读尾部，0 从头读取 */
                cursor?: number;
                /** @description 单页行数上限 */
                limit?: number;
            };
            header?: never;
            path: {
                /** @description 任务 ID */
                task_id: number;
                /** @description 执行实例 ID */
                run_id: number;
            };
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
                    "application/json": components["schemas"]["LogsResponse"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    retryOperation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 任务 ID */
                task_id: number;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": {
                    /** @enum {string} */
                    driver?: "roxy" | "protocol";
                } & {
                    [key: string]: unknown;
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
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 已受理 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 参数无效 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 当前任务状态不支持操作 */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 执行入口暂不可用 */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    cancelOperation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 任务 ID */
                task_id: number;
            };
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
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 已受理 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 参数无效 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 当前任务状态不支持操作 */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 执行入口暂不可用 */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    terminateOperation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 任务 ID */
                task_id: number;
            };
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
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 已受理 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 参数无效 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 当前任务状态不支持操作 */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 执行入口暂不可用 */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    deleteOperation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 任务 ID */
                task_id: number;
            };
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
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 已受理 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 参数无效 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 当前任务状态不支持操作 */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 执行入口暂不可用 */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    bulkOperations: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    /** @enum {string} */
                    action: "retry" | "cancel" | "terminate" | "delete";
                    task_ids: number[];
                } & {
                    [key: string]: unknown;
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
                    "application/json": components["schemas"]["ActionResponse"];
                };
            };
            /** @description 参数无效 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 任务或执行实例不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
}
