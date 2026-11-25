// 由 contracts/accounts.openapi.json 生成，请运行 npm run generate:api。
export interface paths {
    "/api/accounts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description 显式 paged/page/page_size 返回分页对象，否则保留旧数组。服务端最多 500 条，id DESC。 */
        get: operations["listAccounts"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/plan-check-status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description 本契约描述 compact=1；查询与列表相同，queue 不用于客户端重算并发。 */
        get: operations["accountStatuses"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/{account_id}/plan-details": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description 只按用户展开读取公开明细；响应不携带 revision，客户端以 owner 当前版本拒绝陈旧读取。 */
        get: operations["accountPlanDetails"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/operation-receipt": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** @description 查询已持久化的任务与其原始 Run 编号。批量提交仍在处理时可能只返回部分任务。每次查询读取当时已受理的任务。 */
        get: operations["findAccountOperationReceipt"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/check-live-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description 验证现有 AT。 */
        post: operations["queueAccountsLiveCheck"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/refresh-token-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description 刷新账号 AT。 */
        post: operations["queueAccountsTokenRefresh"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/check-plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description 查询单个账号的套餐。 */
        post: operations["queueAccountPlanCheck"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/check-plan-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description 查询多个账号的套餐。 */
        post: operations["queueAccountsPlanCheck"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/{acc_id}/check-deactivation-mail": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description 扫描单个账号的封号邮件。 */
        post: operations["queueAccountDeactivationMailCheck"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/accounts/check-deactivation-mail-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** @description 扫描多个账号的封号邮件。 */
        post: operations["queueAccountsDeactivationMailCheck"];
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
        AccountOperationRequestKey: string;
        AccountOperationReceipt: {
            task_id: string;
            run_id: string;
        };
        AccountOperationReceipts: {
            /** @constant */
            ok: true;
            found: boolean;
            items: components["schemas"]["AccountOperationReceipt"][];
        };
        AccountOperationBulkTargets: {
            account_ids?: (number | string)[];
            /** @description 保留兼容字段。 */
            ids?: (number | string)[];
        } | unknown | unknown;
        AccountOperationPlanTarget: {
            account_id?: number | string;
            /** @description 保留兼容字段。 */
            id?: number | string;
            email?: string;
            /** @description 客户端时区偏移（分钟）。省略时沿用服务端默认行为。 */
            timezone_offset_min?: string | number;
        } | unknown | unknown | unknown;
        AccountOperationAccepted: {
            /** @constant */
            ok: true;
            task_id?: number | string | null;
            run_id?: number | string | null;
        } & {
            [key: string]: unknown;
        };
        AccountOperationBulkAccepted: {
            /** @constant */
            ok: true;
            started: ({
                task_id?: number | string | null;
                run_id?: number | string | null;
            } & {
                [key: string]: unknown;
            })[];
            started_count: number;
            busy_count: number;
            failed_count?: number;
            skipped: Record<string, never>[];
        } & {
            [key: string]: unknown;
        };
        PublicScalar: string | number | boolean | null;
        AccountQueryFilters: {
            id: string;
            email: string;
            source: string[];
            registration_driver: string[];
            token: string[];
            password: string[];
            promotion: string[];
            totp: string[];
            risk: string[];
            codex: string[];
            account_status: string[];
            email_status: string[];
        };
        /** @description 由既有 window.AccountQuery 规范化。ID/email 保持文本，枚举只按现 JS 去重排序；limit 属于批次名单，不自动进入列表 URL。 */
        AccountQuerySpec: {
            /** @constant */
            schema_version: 1;
            /** @constant */
            entity: "account";
            archived: string;
            q: string;
            date_from: string;
            date_to: string;
            plan: string[];
            filters: components["schemas"]["AccountQueryFilters"];
            order: {
                /** @constant */
                field: "id";
                /** @constant */
                direction: "desc";
            }[];
            limit: number | null;
        };
        RegistrationRetry: {
            available: boolean | null;
            active: boolean | null;
            source_job_id: number | null;
            action: string | null;
            label: string | null;
            reason: string | null;
        };
        FingerprintSummary: {
            source?: string;
            profile_ref?: string;
            browser?: string;
            screen?: string;
            hardware?: string;
            language?: string;
            timezone?: string;
            geo_country?: string;
            proxy_mode?: string;
            observed_at?: string;
            device_pixel_ratio?: number;
        };
        CheckoutDetails: {
            checkout_status?: string | null;
            checkout_checked_at?: string | null;
            checkout_error?: string | null;
            session_type?: string | null;
            checkout_currency?: string | null;
            checkout_amount_source?: string | null;
            checkout_source?: string | null;
            checkout_country?: string | null;
            checkout_http_status?: number | null;
            checkout_amount_due_minor?: number | null;
            checkout_currency_exponent?: number | null;
            payment_method_types?: string[];
        };
        AccountPromotion: {
            plan?: components["schemas"]["PublicScalar"];
            kind?: components["schemas"]["PublicScalar"];
            eligible?: components["schemas"]["PublicScalar"];
            campaign_id?: components["schemas"]["PublicScalar"];
            title?: components["schemas"]["PublicScalar"];
            summary?: components["schemas"]["PublicScalar"];
            discount_percentage?: components["schemas"]["PublicScalar"];
            duration_num_periods?: components["schemas"]["PublicScalar"];
            duration_period?: components["schemas"]["PublicScalar"];
            promotion_type?: components["schemas"]["PublicScalar"];
            promotion_type_label?: components["schemas"]["PublicScalar"];
            country?: string;
            stale?: boolean;
            index?: number | null;
            checkout_status?: string | null;
            checkout_checked_at?: string | null;
            checkout_error?: string | null;
            session_type?: string | null;
            checkout_currency?: string | null;
            checkout_amount_source?: string | null;
            checkout_source?: string | null;
            checkout_country?: string | null;
            checkout_http_status?: number | null;
            checkout_amount_due_minor?: number | null;
            checkout_currency_exponent?: number | null;
            payment_method_types?: string[];
        };
        CampaignShape: {
            plan?: string;
            type?: string;
            metadata_type?: string;
            discount_type?: string;
            duration_type?: string;
            index?: number;
            length?: number;
            fields?: string[];
            metadata_fields?: string[];
            discount_fields?: string[];
            duration_fields?: string[];
        };
        /** @description 公开活动证据；不包含上游原始对象。普通列表不对已有可选结构做运行时删字段。 */
        PromotionQuerySnapshot: {
            version?: components["schemas"]["PublicScalar"];
            source?: components["schemas"]["PublicScalar"];
            container_type?: components["schemas"]["PublicScalar"];
            truncated?: components["schemas"]["PublicScalar"];
            campaign_keys?: string[];
            campaigns?: components["schemas"]["AccountPromotion"][];
            campaign_shapes?: components["schemas"]["CampaignShape"][];
        };
        QuotaWindow: {
            slot?: components["schemas"]["PublicScalar"];
            kind?: components["schemas"]["PublicScalar"];
            label?: components["schemas"]["PublicScalar"];
            used_percent?: components["schemas"]["PublicScalar"];
            remaining_percent?: components["schemas"]["PublicScalar"];
            reset_at?: components["schemas"]["PublicScalar"];
            window_seconds?: components["schemas"]["PublicScalar"];
            window_minutes?: components["schemas"]["PublicScalar"];
            reset_after_seconds?: components["schemas"]["PublicScalar"];
            allowed?: components["schemas"]["PublicScalar"];
            limit_reached?: components["schemas"]["PublicScalar"];
        };
        SafeCountryResult: {
            ok?: components["schemas"]["PublicScalar"];
            http_status?: components["schemas"]["PublicScalar"];
            checked_at?: components["schemas"]["PublicScalar"];
            current_plan_type?: components["schemas"]["PublicScalar"];
            subscription_plan?: components["schemas"]["PublicScalar"];
            has_active_subscription?: components["schemas"]["PublicScalar"];
            expires_at?: components["schemas"]["PublicScalar"];
            renews_at?: components["schemas"]["PublicScalar"];
            cancels_at?: components["schemas"]["PublicScalar"];
            billing_period?: components["schemas"]["PublicScalar"];
            billing_currency?: components["schemas"]["PublicScalar"];
            is_delinquent?: components["schemas"]["PublicScalar"];
            token_expired?: components["schemas"]["PublicScalar"];
            token_expires_at?: components["schemas"]["PublicScalar"];
            discount_type?: components["schemas"]["PublicScalar"];
            discount_amount?: components["schemas"]["PublicScalar"];
            discount_duration_num_periods?: components["schemas"]["PublicScalar"];
            discount_expires_at?: components["schemas"]["PublicScalar"];
            discount_cancellation_policy?: components["schemas"]["PublicScalar"];
            discount_promo_campaign_id?: components["schemas"]["PublicScalar"];
            last_purchase_origin_platform?: components["schemas"]["PublicScalar"];
            last_will_renew?: components["schemas"]["PublicScalar"];
            proxy_provider?: components["schemas"]["PublicScalar"];
            proxy_region?: components["schemas"]["PublicScalar"];
            network_route?: components["schemas"]["PublicScalar"];
            quota_status?: components["schemas"]["PublicScalar"];
            quota_checked_at?: components["schemas"]["PublicScalar"];
            quota_http_status?: components["schemas"]["PublicScalar"];
            quota_error?: components["schemas"]["PublicScalar"];
            quota_type?: components["schemas"]["PublicScalar"];
            plus_promo_eligible?: components["schemas"]["PublicScalar"];
            plus_promo_kind?: components["schemas"]["PublicScalar"];
            plus_discount_eligible?: components["schemas"]["PublicScalar"];
            plus_promo_campaign_id?: components["schemas"]["PublicScalar"];
            plus_promo_title?: components["schemas"]["PublicScalar"];
            plus_promo_summary?: components["schemas"]["PublicScalar"];
            plus_promo_discount_percentage?: components["schemas"]["PublicScalar"];
            plus_promo_duration_num_periods?: components["schemas"]["PublicScalar"];
            plus_promo_duration_period?: components["schemas"]["PublicScalar"];
            plus_promo_promotion_type?: components["schemas"]["PublicScalar"];
            plus_promo_promotion_type_label?: components["schemas"]["PublicScalar"];
            plus_trial_eligible?: components["schemas"]["PublicScalar"];
            plus_trial_campaign_id?: components["schemas"]["PublicScalar"];
            plus_trial_title?: components["schemas"]["PublicScalar"];
            plus_trial_summary?: components["schemas"]["PublicScalar"];
            plus_trial_discount_percentage?: components["schemas"]["PublicScalar"];
            plus_trial_duration_num_periods?: components["schemas"]["PublicScalar"];
            plus_trial_duration_period?: components["schemas"]["PublicScalar"];
            plus_trial_promotion_type_label?: components["schemas"]["PublicScalar"];
            account_promotions?: components["schemas"]["AccountPromotion"][];
            promotion_query_snapshot?: components["schemas"]["PromotionQuerySnapshot"];
            quota_windows?: components["schemas"]["QuotaWindow"][];
        };
        CountryResult: {
            country: string;
            status?: components["schemas"]["PublicScalar"];
            checked_at?: components["schemas"]["PublicScalar"];
            http_status?: components["schemas"]["PublicScalar"];
            error?: components["schemas"]["PublicScalar"];
            last_success_at?: components["schemas"]["PublicScalar"];
            token_expired?: components["schemas"]["PublicScalar"];
            token_expires_at?: components["schemas"]["PublicScalar"];
            result: components["schemas"]["SafeCountryResult"] | null;
        };
        /** @description 普通公开列表。可选字段保留省略/null/false/0；状态字符串允许未来值。无凭据、原始 JSON 或 secret。 */
        AccountRow: {
            account_promotions?: components["schemas"]["AccountPromotion"][];
            account_status?: string | null;
            account_status_at?: string | null;
            account_status_reason?: string | null;
            archived?: boolean | null;
            billing_currency?: string | null;
            billing_period?: string | null;
            codex_active_run_id?: number | null;
            codex_credential_state?: string | null;
            codex_error?: string | null;
            codex_execution_status?: string | null;
            codex_last_run_status?: string | null;
            codex_status?: string | null;
            created_at?: string | null;
            current_plan_type?: string | null;
            deactivation_mail_checked_at?: string | null;
            deactivation_mail_confidence?: components["schemas"]["PublicScalar"];
            deactivation_mail_detected?: boolean | null;
            deactivation_mail_error?: string | null;
            deactivation_mail_received_at?: string | null;
            deactivation_mail_scan_status?: string | null;
            deactivation_mail_scan_trigger?: string | null;
            deactivation_mail_sender?: string | null;
            deactivation_mail_subject?: string | null;
            discount_amount?: number | null;
            discount_expires_at?: string | null;
            discount_promo_campaign_id?: string | null;
            discount_type?: string | null;
            email: string | null;
            email_invalid: boolean;
            email_invalid_at: string | null;
            email_invalid_reason: string | null;
            email_invalid_source: string | null;
            email_source?: string | null;
            expires_at?: string | null;
            extract_link_copy_paste?: string | null;
            extract_link_error?: string | null;
            extract_link_expires_at?: string | null;
            extract_link_failed_types?: string[];
            extract_link_image_url_png?: string | null;
            extract_link_image_url_svg?: string | null;
            extract_link_last_failed_at?: string | null;
            extract_link_last_failed_type?: string | null;
            extract_link_long_url?: string | null;
            extract_link_message?: string | null;
            extract_link_ok?: boolean | null;
            extract_link_status?: string | null;
            extract_link_type?: string | null;
            fingerprint_summary?: components["schemas"]["FingerprintSummary"];
            has_access_token: boolean;
            has_account_password: boolean;
            id: number;
            last_auth_fallback_used?: boolean | null;
            last_auth_method?: string | null;
            /** @enum {string} */
            last_password_auth_status?: "verified" | "accepted" | "rejected" | "unknown" | "skipped";
            live_check_error?: string | null;
            live_check_http_status?: number | null;
            live_check_status?: string | null;
            live_checked_at?: string | null;
            note?: string | null;
            plan_check_countries?: string[];
            plan_check_country_results?: components["schemas"]["CountryResult"][];
            plan_check_error?: string | null;
            plan_check_ok?: boolean | null;
            plan_check_partial?: boolean | null;
            plan_check_queued_at?: string | null;
            plan_check_started_at?: string | null;
            plan_check_status?: string | null;
            plan_check_trigger?: string | null;
            plan_expires_at?: string | null;
            plan_last_success_at?: string | null;
            plan_promotion_country?: string | null;
            plan_renews_at?: string | null;
            plan_type?: string | null;
            plus_discount_eligible: boolean;
            plus_promo_campaign_id?: string | null;
            plus_promo_discount_percentage?: number | null;
            plus_promo_duration_num_periods?: number | null;
            plus_promo_duration_period?: string | null;
            plus_promo_eligible: boolean;
            plus_promo_kind: string;
            plus_promo_promotion_type?: string | null;
            plus_promo_promotion_type_label?: string | null;
            plus_promo_summary?: string | null;
            plus_promo_title?: string | null;
            plus_trial_campaign_id?: string | null;
            plus_trial_discount_percentage?: number | null;
            plus_trial_duration_num_periods?: number | null;
            plus_trial_duration_period?: string | null;
            plus_trial_eligible: boolean;
            plus_trial_promotion_type_label?: string | null;
            plus_trial_title?: string | null;
            promotion_query_snapshot?: components["schemas"]["PromotionQuerySnapshot"];
            quota_checked_at?: string | null;
            quota_error?: string | null;
            quota_http_status?: number | null;
            quota_last_success_at?: string | null;
            quota_status?: string | null;
            quota_type?: string | null;
            quota_windows?: components["schemas"]["QuotaWindow"][];
            registration_driver?: string | null;
            registration_proxy_provider?: string | null;
            registration_proxy_region?: string | null;
            registration_retry?: components["schemas"]["RegistrationRetry"];
            renews_at?: string | null;
            token_expired?: boolean | null;
            token_expires_at?: string | null;
            totp_enabled: boolean;
            updated_at?: string | null;
            user_name?: string | null;
        };
        AccountFacet: {
            value: string;
            count: number;
        };
        /** @description 联动分面：只排除自身列过滤，保留 q/archive/date/id/email 等范围。无 label。 */
        AccountFacets: {
            source?: components["schemas"]["AccountFacet"][];
            registration_driver?: components["schemas"]["AccountFacet"][];
            token?: components["schemas"]["AccountFacet"][];
            password?: components["schemas"]["AccountFacet"][];
            plan?: components["schemas"]["AccountFacet"][];
            promotion?: components["schemas"]["AccountFacet"][];
            totp?: components["schemas"]["AccountFacet"][];
            risk?: components["schemas"]["AccountFacet"][];
            codex?: components["schemas"]["AccountFacet"][];
            account_status?: components["schemas"]["AccountFacet"][];
            email_status?: components["schemas"]["AccountFacet"][];
        };
        AccountSearchTerm: {
            field: string;
            label: string;
            value: string;
            display_value: string;
            query_without: string;
        };
        AccountsListResponse: {
            /** @constant */
            ok: true;
            items: components["schemas"]["AccountRow"][];
            total: number;
            page: number;
            page_size: number;
            offset: number;
            limit: number;
            revision: string;
            /** @constant */
            compact: true;
            /** @description include_facets=0 时为空对象。 */
            facets: components["schemas"]["AccountFacets"];
            search_terms: components["schemas"]["AccountSearchTerm"][];
        };
        LegacyAccountsResponse: components["schemas"]["AccountRow"][];
        PlanSummaryPromotion: {
            plan?: string;
            kind?: components["schemas"]["PublicScalar"];
            country?: string;
            stale?: boolean;
            discount_percentage?: components["schemas"]["PublicScalar"];
            duration_num_periods?: components["schemas"]["PublicScalar"];
            duration_period?: components["schemas"]["PublicScalar"];
        };
        PlanSummaryCountry: {
            country?: string;
            status?: components["schemas"]["PublicScalar"];
            checked_at?: components["schemas"]["PublicScalar"];
            last_success_at?: components["schemas"]["PublicScalar"];
            http_status?: components["schemas"]["PublicScalar"];
            error?: components["schemas"]["PublicScalar"];
            promotions?: components["schemas"]["PlanSummaryPromotion"][] | null;
            result?: {
                plus_promo_eligible?: components["schemas"]["PublicScalar"];
                plus_promo_kind?: components["schemas"]["PublicScalar"];
                plus_discount_eligible?: components["schemas"]["PublicScalar"];
                plus_promo_campaign_id?: components["schemas"]["PublicScalar"];
                plus_promo_title?: components["schemas"]["PublicScalar"];
                plus_promo_summary?: components["schemas"]["PublicScalar"];
                plus_promo_discount_percentage?: components["schemas"]["PublicScalar"];
                plus_promo_duration_num_periods?: components["schemas"]["PublicScalar"];
                plus_promo_duration_period?: components["schemas"]["PublicScalar"];
                plus_promo_promotion_type?: components["schemas"]["PublicScalar"];
                plus_promo_promotion_type_label?: components["schemas"]["PublicScalar"];
                plus_trial_eligible?: components["schemas"]["PublicScalar"];
                plus_trial_campaign_id?: components["schemas"]["PublicScalar"];
                plus_trial_title?: components["schemas"]["PublicScalar"];
                plus_trial_summary?: components["schemas"]["PublicScalar"];
                plus_trial_discount_percentage?: components["schemas"]["PublicScalar"];
                plus_trial_duration_num_periods?: components["schemas"]["PublicScalar"];
                plus_trial_duration_period?: components["schemas"]["PublicScalar"];
                plus_trial_promotion_type_label?: components["schemas"]["PublicScalar"];
                plan_type?: string | null;
                current_plan_type?: string | null;
            };
        };
        PlanSummary: {
            promotions: components["schemas"]["PlanSummaryPromotion"][] | null;
            countries: components["schemas"]["PlanSummaryCountry"][];
        };
        /** @description compact=1 轮询投影。status_fields 缺失字段表示权威清空；完整明细独立按需读取。 */
        AccountStatusRow: {
            account_status?: string | null;
            account_status_at?: string | null;
            account_status_reason?: string | null;
            archived?: boolean | null;
            billing_currency?: string | null;
            billing_period?: string | null;
            codex_active_run_id?: number | null;
            codex_credential_state?: string | null;
            codex_error?: string | null;
            codex_execution_status?: string | null;
            codex_last_run_status?: string | null;
            codex_status?: string | null;
            current_plan_type?: string | null;
            discount_amount?: number | null;
            discount_expires_at?: string | null;
            discount_promo_campaign_id?: string | null;
            discount_type?: string | null;
            email?: string | null;
            email_invalid: boolean;
            email_invalid_at: string | null;
            email_invalid_reason: string | null;
            email_invalid_source: string | null;
            expires_at?: string | null;
            extract_link_copy_paste?: string | null;
            extract_link_error?: string | null;
            extract_link_expires_at?: string | null;
            extract_link_failed_types?: string[];
            extract_link_image_url_png?: string | null;
            extract_link_image_url_svg?: string | null;
            extract_link_last_failed_at?: string | null;
            extract_link_last_failed_type?: string | null;
            extract_link_long_url?: string | null;
            extract_link_message?: string | null;
            extract_link_ok?: boolean | null;
            extract_link_status?: string | null;
            extract_link_type?: string | null;
            has_access_token: boolean;
            has_account_password: boolean;
            id: number;
            last_auth_method?: string | null;
            last_password_auth_status: ("verified" | "accepted" | "rejected" | "unknown" | "skipped") | null;
            live_checked_at?: string | null;
            plan_check_completed_at?: string | null;
            plan_check_countries?: string[];
            plan_check_error?: string | null;
            plan_check_network_route?: string | null;
            plan_check_ok?: boolean | null;
            plan_check_partial?: boolean | null;
            plan_check_proxy_fallback_reason?: string | null;
            plan_check_proxy_used?: string | null;
            plan_check_queued_at?: string | null;
            plan_check_started_at?: string | null;
            plan_check_status?: string | null;
            plan_check_trigger?: string | null;
            plan_checked_at?: string | null;
            plan_expires_at?: string | null;
            plan_last_success_at?: string | null;
            plan_promotion_country: string | null;
            plan_renews_at?: string | null;
            plan_type?: string | null;
            plus_discount_eligible?: boolean;
            plus_promo_campaign_id?: string | null;
            plus_promo_discount_percentage?: number | null;
            plus_promo_duration_num_periods?: number | null;
            plus_promo_duration_period?: string | null;
            plus_promo_eligible?: boolean;
            plus_promo_kind?: string;
            plus_promo_promotion_type?: string | null;
            plus_promo_promotion_type_label?: string | null;
            plus_promo_summary?: string | null;
            plus_promo_title?: string | null;
            plus_trial_campaign_id?: string | null;
            plus_trial_discount_percentage?: number | null;
            plus_trial_duration_num_periods?: number | null;
            plus_trial_duration_period?: string | null;
            plus_trial_eligible?: boolean;
            plus_trial_promotion_type_label?: string | null;
            plus_trial_title?: string | null;
            quota_checked_at?: string | null;
            quota_error?: string | null;
            quota_http_status?: number | null;
            quota_last_success_at?: string | null;
            quota_status?: string | null;
            quota_type?: string | null;
            quota_windows?: components["schemas"]["QuotaWindow"][];
            renews_at?: string | null;
            updated_at?: string | null;
            plan_details_revision: string;
            plan_summary: components["schemas"]["PlanSummary"];
        };
        AccountQueueSettings: {
            workers: number;
            registration_workers: number;
            queue_limit: number;
            min_interval: number;
            jitter: number;
        };
        AccountStatusesResponse: {
            /** @constant */
            ok: true;
            items: components["schemas"]["AccountStatusRow"][];
            total: number;
            page: number;
            page_size: number;
            offset: number;
            limit: number;
            revision: string;
            queue: components["schemas"]["AccountQueueSettings"];
            status_fields: string[];
        };
        AccountPlanDetails: {
            account_promotions: components["schemas"]["AccountPromotion"][] | null;
            promotion_query_snapshot: components["schemas"]["PromotionQuerySnapshot"] | null;
            plan_check_country_results: components["schemas"]["CountryResult"][];
        };
        AccountPlanDetailsResponse: {
            /** @constant */
            ok: true;
            item: components["schemas"]["AccountPlanDetails"];
        };
        AccountSearchError: {
            /** @constant */
            ok: false;
            /** @constant */
            code: "account_search_invalid";
            error: string;
        };
        ApiError: {
            /** @constant */
            ok?: false;
            error?: string | {
                code?: string;
                message?: string;
            };
            message?: string;
            code?: string;
            error_code?: string;
        };
    };
    responses: never;
    parameters: {
        /** @description 标识一次账号操作意图。提交时生成请求编号，按相同编号查询该次提交已受理的任务。 */
        AccountOperationRequestKey: components["schemas"]["AccountOperationRequestKey"];
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listAccounts: {
        parameters: {
            query?: {
                /** @description 既有查询参数。 */
                paged?: string;
                /** @description 既有查询参数。 */
                page?: number;
                /** @description 既有查询参数。 */
                page_size?: number;
                /** @description 分页统计开关。默认为 1，传 0 跳过筛选统计，facets 返回空对象。 */
                include_facets?: 0 | 1;
                /** @description 既有查询参数。 */
                limit?: number;
                /** @description 既有查询参数。 */
                archived?: string;
                /** @description 高级搜索原文；语法错误使用顶层 code=account_search_invalid。 */
                q?: string;
                /** @description 既有查询参数。 */
                date_from?: string;
                /** @description 既有查询参数。 */
                date_to?: string;
                /** @description 文本子串，不转换成 JavaScript Number。 */
                id?: string;
                /** @description 既有查询参数。 */
                email?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                plan?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                source?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                registration_driver?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                token?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                password?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                promotion?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                totp?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                risk?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                codex?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                account_status?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                email_status?: string;
                /** @description 旧 promotion 别名，promotion 非空优先。 */
                trial?: string;
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
                    "application/json": components["schemas"]["AccountsListResponse"] | components["schemas"]["LegacyAccountsResponse"];
                };
            };
            /** @description 查询错误 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountSearchError"] | components["schemas"]["ApiError"];
                };
            };
            /** @description 登录失效；可能为非 JSON 登录页。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 读取失败 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 普通业务/网络服务端错误；保留原 HTTP 状态与错误消息。 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    accountStatuses: {
        parameters: {
            query?: {
                /** @description 既有查询参数。 */
                paged?: string;
                /** @description 既有查询参数。 */
                page?: number;
                /** @description 既有查询参数。 */
                page_size?: number;
                /** @description 既有查询参数。 */
                limit?: number;
                /** @description 既有查询参数。 */
                archived?: string;
                /** @description 高级搜索原文；语法错误使用顶层 code=account_search_invalid。 */
                q?: string;
                /** @description 既有查询参数。 */
                date_from?: string;
                /** @description 既有查询参数。 */
                date_to?: string;
                /** @description 文本子串，不转换成 JavaScript Number。 */
                id?: string;
                /** @description 既有查询参数。 */
                email?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                plan?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                source?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                registration_driver?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                token?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                password?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                promotion?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                totp?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                risk?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                codex?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                account_status?: string;
                /** @description 逗号多值，保留未知值，由服务端规范化。 */
                email_status?: string;
                /** @description 旧 promotion 别名，promotion 非空优先。 */
                trial?: string;
                compact?: string;
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
                    "application/json": components["schemas"]["AccountStatusesResponse"];
                };
            };
            /** @description 查询错误 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountSearchError"] | components["schemas"]["ApiError"];
                };
            };
            /** @description 登录失效；可能为非 JSON 登录页。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 读取失败 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 普通业务/网络服务端错误；保留原 HTTP 状态与错误消息。 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    accountPlanDetails: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                account_id: number;
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
                    "application/json": components["schemas"]["AccountPlanDetailsResponse"];
                };
            };
            /** @description 查询错误 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountSearchError"] | components["schemas"]["ApiError"];
                };
            };
            /** @description 登录失效；可能为非 JSON 登录页。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 账号不存在 */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 读取失败 */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 普通业务/网络服务端错误；保留原 HTTP 状态与错误消息。 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    findAccountOperationReceipt: {
        parameters: {
            query?: never;
            header: {
                /** @description 标识一次账号操作意图。提交时生成请求编号，按相同编号查询该次提交已受理的任务。 */
                "X-Account-Request-Key": components["schemas"]["AccountOperationRequestKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 回执查询成功。尚未查到任务时 found 为 false，items 为空。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountOperationReceipts"];
                };
            };
            /** @description 缺少请求编号或编号格式无效。 */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description 登录失效。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    queueAccountsLiveCheck: {
        parameters: {
            query?: never;
            header?: {
                /** @description 标识一次账号操作意图。提交时生成请求编号，按相同编号查询该次提交已受理的任务。 */
                "X-Account-Request-Key"?: components["parameters"]["AccountOperationRequestKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AccountOperationBulkTargets"] & {
                    driver?: string | null;
                };
            };
        };
        responses: {
            /** @description 提交已处理，批量接口按项目返回受理结果。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountOperationBulkAccepted"];
                };
            };
            /** @description 登录失效。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 提交失败或操作当前不可用。 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    queueAccountsTokenRefresh: {
        parameters: {
            query?: never;
            header?: {
                /** @description 标识一次账号操作意图。提交时生成请求编号，按相同编号查询该次提交已受理的任务。 */
                "X-Account-Request-Key"?: components["parameters"]["AccountOperationRequestKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AccountOperationBulkTargets"];
            };
        };
        responses: {
            /** @description 提交已处理，批量接口按项目返回受理结果。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountOperationBulkAccepted"];
                };
            };
            /** @description 登录失效。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 提交失败或操作当前不可用。 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    queueAccountPlanCheck: {
        parameters: {
            query?: never;
            header?: {
                /** @description 标识一次账号操作意图。提交时生成请求编号，按相同编号查询该次提交已受理的任务。 */
                "X-Account-Request-Key"?: components["parameters"]["AccountOperationRequestKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AccountOperationPlanTarget"];
            };
        };
        responses: {
            /** @description 任务已受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountOperationAccepted"];
                };
            };
            /** @description 登录失效。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 提交失败或操作当前不可用。 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    queueAccountsPlanCheck: {
        parameters: {
            query?: never;
            header?: {
                /** @description 标识一次账号操作意图。提交时生成请求编号，按相同编号查询该次提交已受理的任务。 */
                "X-Account-Request-Key"?: components["parameters"]["AccountOperationRequestKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AccountOperationBulkTargets"] & {
                    /** @description 客户端时区偏移（分钟）。省略时沿用服务端默认行为。 */
                    timezone_offset_min?: string | number;
                };
            };
        };
        responses: {
            /** @description 提交已处理，批量接口按项目返回受理结果。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountOperationBulkAccepted"];
                };
            };
            /** @description 登录失效。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 提交失败或操作当前不可用。 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    queueAccountDeactivationMailCheck: {
        parameters: {
            query?: never;
            header?: {
                /** @description 标识一次账号操作意图。提交时生成请求编号，按相同编号查询该次提交已受理的任务。 */
                "X-Account-Request-Key"?: components["parameters"]["AccountOperationRequestKey"];
            };
            path: {
                acc_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 任务已受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountOperationAccepted"];
                };
            };
            /** @description 登录失效。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 提交失败或操作当前不可用。 */
            default: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    queueAccountsDeactivationMailCheck: {
        parameters: {
            query?: never;
            header?: {
                /** @description 标识一次账号操作意图。提交时生成请求编号，按相同编号查询该次提交已受理的任务。 */
                "X-Account-Request-Key"?: components["parameters"]["AccountOperationRequestKey"];
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AccountOperationBulkTargets"];
            };
        };
        responses: {
            /** @description 提交已处理，批量接口按项目返回受理结果。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AccountOperationBulkAccepted"];
                };
            };
            /** @description 登录失效。 */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description 提交失败或操作当前不可用。 */
            default: {
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
