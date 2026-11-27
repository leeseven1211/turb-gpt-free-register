// 由 contracts/teams.openapi.json 生成，请运行 npm run generate:api。
export interface paths {
    "/api/teams/binding-probes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 异步探测管理账号
         * @description 持久 Task/Run 后异步认证和读取远端。归档母号可探测；target_workspace_id 仅限制或预选，不创建 Team。
         */
        post: operations["createTeamBindingProbe"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/binding-probes/{probe_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 读取绑定探测证据
         * @description stage 可轮询，详细进度通过已有 Task/Run 读取；普通 GET 不触发新探测。
         */
        get: operations["getTeamBindingProbe"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 分页读取 Team
         * @description 本地 id 降序；role/last_sync_status 为唯一 facet 维度。
         */
        get: operations["listTeams"];
        put?: never;
        /**
         * 创建 Team 绑定并受理首轮同步
         * @description 同一事务保存 Team、管理关联、首轮同步。首次未知数量为 null、last_sync_status=queued。不同键重复 workspace 返回 team_already_bound 及 details.existing_team_id；相同键复用原 201。
         */
        post: operations["createTeam"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 读取 Team 详情和动作能力
         * @description 仅读取现有快照，不触发同步或权限核验。
         */
        get: operations["getTeam"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * 修改 Team 本地配置或管理账号
         * @description expected_revision 冲突为 409 revision_conflict，details.revision 为当前版本。换母号沿用路径 Team 的 workspace，不丢弃旧执行真实回执，旧执行不能覆盖新配置。降低本地上限不删除成员或撤回已发邀请。
         */
        patch: operations["updateTeam"];
        trace?: never;
    };
    "/api/teams/{team_id}/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 受理 Team 快照同步
         * @description 同步成员、邀请、订阅和数量快照；同 Team 同类未终态同步任务复用，reused=true。
         */
        post: operations["syncTeam"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/sync-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 批量受理 Team 同步
         * @description 1–100 个 Team ID；每项独立受理，acceptance_status 与 execution_status 分开。
         */
        post: operations["syncTeamsBulk"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/reverify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 单独受理管理权限核验
         * @description 只更新权限证据及角色，不冒充完整成员/邀请同步。同 Team 同类未终态核验任务复用。
         */
        post: operations["reverifyTeam"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/members": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 分页读取 Team 成员
         * @description 默认 membership_state=joined，本地 id 升序；历史 left/unconfirmed 需显式筛选。读取失败、不完整或单次缺项不把 joined 改成 left。
         */
        get: operations["listTeamMembers"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/invitations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 分页读取邀请与加入意图
         * @description 不传状态时包含全部本地意图和远端邀请，updated_at、id 降序；邀请事实与成员事实分别读取。
         */
        get: operations["listTeamInvitations"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/invitations/{invitation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 读取单条邀请与加入意图
         * @description 邀请不存在或不属于路径 Team 均按 404，不返回其他 Team 材料。
         */
        get: operations["getTeamInvitation"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/candidates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 分页读取本地候选账号
         * @description 纯本地读取，账号 id 降序；默认 scope=unassigned、archived=0。unassigned 排除任何本地 Team 母号/成员/未决占用，含本 Team pending；all 可查看续接。材料布尔筛选仅代表本地存在性，不在线认证。include_facets=1 返回 {}。
         */
        get: operations["listTeamCandidates"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/candidates/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 按邮箱或本地 ID 精确解析候选
         * @description 纯读 POST，无幂等键要求；1–10,000 输入，trim 去重后精确匹配。不因归档跳过，不创建任务/名单/邀请/占位，不访问远端。
         */
        post: operations["resolveTeamCandidates"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/join-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 纯本地评估加入名单与容量
         * @description 显式 ID 或冻结 selection 二选一，不消费 selection，不创建任何执行或占位，不认证、不取 OTP、不访问上游。can_submit=false 仍为 HTTP 200。缺已购席位与本地上限为 team_limit_required；已具备上限但需同步或名额不足可受理后等待。P95<50ms 是尚未验收的性能目标。
         */
        post: operations["previewTeamJoin"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/join": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 持久受理集合加入请求
         * @description 固定目标、父 Task/Run 与回执先持久化，后台窗口受理。先取得/复用唯一账号 Team 业务占用，跨 Team 项 skipped/already_in_another_team。同 Team 活跃意图复用；已是成员跳过；未知认证材料仍可检查。缺上限返回 409，不创建新邀请/席位；待同步或待容量允许 202。默认普通成员、接受指定 workspace、保留个人工作区、不自动合并个人数据；成功需远端成员与本地保存均确认。已消费 selection 返回 selection_consumed，details.existing_join_request_id 定位原请求。
         */
        post: operations["joinTeam"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/join-requests/{join_request_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * 分页读取集合加入逐项回执
         * @description 固定目标 ordinal 升序；接受状态仅代表逐项受理，后台业务成果通过邀请与 Task/Run 读取。列表、total 使用同一筛选；include_facets=1 返回 {}。请求不属于路径 Team 时 404。
         */
        get: operations["getTeamJoinRequest"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/invitations/{invitation_id}/continue": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 继续邀请未完成阶段
         * @description operation=continue，唯一目标；邀请须属于路径 Team。未终态执行复用原 Task/Run；终态需要执行则新建 Run 并保留原邀请与成果，不强制重发信。已加入且本地保存完整 skipped/already_member。纯接受/核验/保存无需新增占位时允许上限暂缺；需重新邀请再核验上限与容量，必要时等待。回执缺失或结果待确认不永久阻止重跑。
         */
        post: operations["continueTeamInvitation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/invitations/continue-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 批量继续邀请
         * @description operation=continue；1–10,000 邀请 ID，先按邀请再按同 Team 目标身份去重。不存在或不属于该 Team 的项逐项 skipped/invitation_not_found，其余继续；同目标未终态执行复用。纯接受/核验/保存无需新增占位时保留缺上限例外。
         */
        post: operations["continueTeamInvitationsBulk"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/invitations/{invitation_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 人工重跑邀请终态执行
         * @description operation=retry，唯一目标；邀请须属于路径 Team。未终态执行复用原 Task/Run；终态需要执行则新建 Run 并保留原邀请与成果，不强制重发信。已加入且本地保存完整 skipped/already_member。纯接受/核验/保存无需新增占位时允许上限暂缺；需重新邀请再核验上限与容量，必要时等待。回执缺失或结果待确认不永久阻止重跑。
         */
        post: operations["retryTeamInvitation"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/teams/{team_id}/invitations/retry-bulk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * 批量人工重跑邀请
         * @description operation=retry；1–10,000 邀请 ID，先按邀请再按同 Team 目标身份去重。不存在或不属于该 Team 的项逐项 skipped/invitation_not_found，其余继续；同目标未终态执行复用。纯接受/核验/保存无需新增占位时保留缺上限例外。
         */
        post: operations["retryTeamInvitationsBulk"];
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
        /** @description 本地正整数十进制 ID；始终使用字符串，禁止转换为 JavaScript Number，不自动去除空格。 */
        LocalId: string;
        /** @description 远端不透明标识，保留原字符串，不能与本地 ID 互换。 */
        RemoteId: string;
        /** @description 正整数业务/证据版本；与列表读模型修订字符串分开。 */
        Revision: number;
        /** @description 读模型修订标识，不可作为 expected_revision 使用。 */
        ReadModelRevision: string;
        Count: number;
        PositiveInteger: number;
        /**
         * Format: date-time
         * @description 带时区的 ISO 8601 时间；未知时间使用 null。
         */
        Timestamp: string;
        /**
         * Format: email
         * @description 非空邮箱；不携带认证材料。
         */
        Email: string;
        /** @description 本地备注名，最多 120 个字符；去除首尾空白后为空时按 null 清空。 */
        DisplayName: string | null;
        /** @description 去除首尾空白后 16–128 个字符，推荐 UUID。允许头或 JSON 字段提供，两处均提供时规范化后必须完全相同。 */
        IdempotencyKey: string;
        /**
         * @description 仅依据实际远端权限归一化，未知不推断。
         * @enum {string}
         */
        Role: "owner" | "admin" | "member" | "unknown";
        /**
         * @description 成员关系独立于邀请状态保存；缺项或同步失败不能推断已离开。
         * @enum {string}
         */
        MembershipState: "joined" | "left" | "unconfirmed";
        /**
         * @description 邀请事实独立保存；已有邀请属于可续接事实。
         * @enum {string}
         */
        InvitationState: "not_sent" | "pending" | "accepted" | "revoked" | "expired" | "unconfirmed";
        /**
         * @description 仅表达本次认证材料能力；unknown 不能视作已确认缺少。
         * @enum {string}
         */
        AuthCapability: "available" | "missing" | "unknown";
        /** @enum {string} */
        TaskStatus: "queued" | "running" | "waiting" | "cancelling" | "settling" | "stopping" | "success" | "partial_success" | "failed" | "stopped" | "cancelled" | "interrupted" | "deactivated" | "unsupported";
        /**
         * @description none 表示尚无执行；waiting 仍是执行状态。
         * @enum {string}
         */
        ExecutionStatus: "none" | "queued" | "running" | "waiting" | "cancelling" | "settling" | "stopping" | "success" | "partial_success" | "failed" | "stopped" | "cancelled" | "interrupted" | "deactivated" | "unsupported";
        /** @enum {string} */
        JoinStage: "queued" | "manager_verify" | "state_check" | "invite" | "member_auth" | "accept" | "member_verify" | "persist" | "complete";
        /** @enum {string} */
        WaitingReasonCode: "waiting_account" | "waiting_sync" | "waiting_capacity" | "waiting_child" | "waiting_remote";
        /** @enum {string} */
        LastSyncStatus: "never" | "queued" | "running" | "success" | "partial_success" | "failed" | "interrupted";
        /** @enum {string} */
        ProbeStatus: "queued" | "running" | "success" | "failed" | "cancelled" | "interrupted";
        /** @enum {string} */
        ProbeStage: "queued" | "manager_auth" | "workspace_discovery" | "permission_check" | "complete";
        /**
         * @description 逐目标受理状态，不代表已加入；reused 属于 accepted 统计子集。
         * @enum {string}
         */
        AcceptanceStatus: "pending" | "accepted" | "reused" | "skipped" | "failed";
        /** @enum {string} */
        SyncAcceptanceStatus: "accepted" | "reused" | "skipped" | "failed";
        /** @enum {string} */
        JoinRequestStatus: "preparing" | "queued" | "running" | "waiting" | "success" | "partial_success" | "failed" | "stopped" | "cancelled" | "interrupted";
        /**
         * @description 按枚举所列顺序互斥分类；unknown 认证能力不能归入 missing_auth。
         * @enum {string}
         */
        CandidateCategory: "unavailable" | "another_team" | "already_member" | "same_team_active" | "missing_auth" | "resume_invite" | "new";
        /**
         * @description unmarked 只表示未标记失效，不宣称邮箱健康。
         * @enum {string}
         */
        EmailStatus: "invalid" | "unmarked";
        /** @enum {string} */
        WorkspaceType: "personal" | "team" | "unknown";
        /** @enum {string} */
        MatchStatus: "matched" | "not_found" | "ambiguous";
        /** @enum {string} */
        JoinOperation: "join" | "continue" | "retry";
        /** @enum {string} */
        CapacityBasis: "purchased_seats" | "planned_member_limit" | "unavailable";
        /** @enum {string} */
        CapacityBlockingReason: "team_limit_required" | "no_eligible_targets";
        /** @enum {string} */
        LinkedFilter: "all" | "linked" | "unlinked";
        /** @enum {string} */
        CandidateScope: "unassigned" | "all";
        /** @enum {string} */
        ArchivedFilter: "0" | "only" | "all";
        /**
         * @description 只接受字面字符串 true 或 false，不接受 0/1、空字符串或逗号拼接。
         * @enum {string}
         */
        BooleanQuery: "true" | "false";
        /**
         * @description 公开业务原因码；以下常用值固定，认证、OTP、TOTP、网络与存储细分继续复用既有错误目录，不合并为 unknown。
         * @example already_in_another_team
         * @example already_member
         * @example missing_auth_materials
         * @example account_not_found
         * @example account_unavailable
         * @example account_identity_changed
         * @example invitation_not_found
         * @example waiting_sync
         * @example waiting_capacity
         */
        BusinessReasonCode: string;
        /** @description 账号窄引用，允许已归档账号；不返回完整账号行或认证材料。 */
        AccountRef: {
            id: components["schemas"]["LocalId"];
            email: components["schemas"]["Email"] | null;
            archived: boolean;
        };
        TeamRef: {
            id: components["schemas"]["LocalId"];
            workspace_id: components["schemas"]["RemoteId"];
            name: string | null;
            display_name: components["schemas"]["DisplayName"];
        };
        /** @description 尚未创建的对应 Task/Run 引用为 null，不能编造任务。 */
        TaskRef: {
            task_id: components["schemas"]["LocalId"] | null;
            run_id: components["schemas"]["LocalId"] | null;
            status: components["schemas"]["TaskStatus"];
        };
        /** @description 公开简短错误；完整证据通过 TaskCenter 读取。正常等待与跳过不自动产生失败 ErrorInfo。 */
        ErrorInfo: {
            code: components["schemas"]["BusinessReasonCode"];
            /** @description 中文原因。 */
            message: string;
            stage: components["schemas"]["JoinStage"] | components["schemas"]["ProbeStage"] | null;
            retryable: boolean;
        };
        /** @description 持久任务受理回执；accepted=true 仅表示已持久受理。相同 Team 同类未终态任务复用原引用。 */
        ActionReceipt: {
            /** @constant */
            accepted: true;
            reused: boolean;
            team_id: components["schemas"]["LocalId"];
            task_id: components["schemas"]["LocalId"];
            run_id: components["schemas"]["LocalId"];
            status: components["schemas"]["TaskStatus"];
        };
        /** @description 只描述当前读取快照的动作能力；无禁用原因时 reason_code=null，执行仍需核验。 */
        AllowedAction: {
            enabled: boolean;
            reason_code: components["schemas"]["BusinessReasonCode"] | null;
        };
        /** @description 固定窄 DTO。未知数量为 null；purchased_seats=0 是明确零席位；三种摘要数量不能相加当成占位。失败保留上次成功快照与时间。 */
        TeamDTO: {
            id: components["schemas"]["LocalId"];
            workspace_id: components["schemas"]["RemoteId"];
            name: string | null;
            display_name: components["schemas"]["DisplayName"];
            manager_account: components["schemas"]["AccountRef"];
            role: components["schemas"]["Role"];
            purchased_seats: components["schemas"]["Count"] | null;
            planned_member_limit: components["schemas"]["PositiveInteger"] | null;
            confirmed_member_count: components["schemas"]["Count"] | null;
            pending_invite_count: components["schemas"]["Count"] | null;
            processing_count: components["schemas"]["Count"] | null;
            last_synced_at: components["schemas"]["Timestamp"] | null;
            last_sync_status: components["schemas"]["LastSyncStatus"];
            revision: components["schemas"]["Revision"];
        };
        /** @description 未匹配本地账号的远端成员仍返回，不自动创建账号；本地关联与远端身份分别保存。 */
        MemberDTO: {
            id: components["schemas"]["LocalId"];
            team_id: components["schemas"]["LocalId"];
            remote_user_id: components["schemas"]["RemoteId"] | null;
            email: components["schemas"]["Email"] | null;
            account: components["schemas"]["AccountRef"] | null;
            role: components["schemas"]["Role"];
            membership_state: components["schemas"]["MembershipState"];
            joined_at: components["schemas"]["Timestamp"] | null;
            last_verified_at: components["schemas"]["Timestamp"] | null;
            latest_task: components["schemas"]["TaskRef"] | null;
        };
        /** @description 无执行时 task_id/run_id=null、status=none；尚无可知阶段时 stage=null。等待时使用 status=waiting，原因另列。 */
        InvitationExecution: {
            task_id: components["schemas"]["LocalId"] | null;
            run_id: components["schemas"]["LocalId"] | null;
            status: components["schemas"]["ExecutionStatus"];
            stage: components["schemas"]["JoinStage"] | null;
            waiting_reason_code: components["schemas"]["WaitingReasonCode"] | null;
            error_info: components["schemas"]["ErrorInfo"] | null;
        } & unknown;
        InvitationActions: {
            continue: components["schemas"]["AllowedAction"];
            retry: components["schemas"]["AllowedAction"];
            view_task: components["schemas"]["AllowedAction"];
        };
        /** @description 本地邀请与加入意图；尚未发送远端邀请时仍可存在，remote_invitation_id=null 不表示失败。 */
        InvitationDTO: {
            id: components["schemas"]["LocalId"];
            team_id: components["schemas"]["LocalId"];
            remote_invitation_id: components["schemas"]["RemoteId"] | null;
            account: components["schemas"]["AccountRef"] | null;
            email_snapshot: components["schemas"]["Email"] | null;
            invitation_state: components["schemas"]["InvitationState"];
            membership_state: components["schemas"]["MembershipState"];
            latest_execution: components["schemas"]["InvitationExecution"];
            updated_at: components["schemas"]["Timestamp"];
            last_verified_at: components["schemas"]["Timestamp"] | null;
            actions: components["schemas"]["InvitationActions"];
        };
        /** @description 未确认能力用 null。 */
        ProbeCapabilities: {
            read_members: boolean | null;
            read_invitations: boolean | null;
            invite_members: boolean | null;
        };
        /** @description 远端工作区窄证据；未确认远端事实使用 null，绑定要求 can_manage=true。 */
        ProbeWorkspace: {
            workspace_id: components["schemas"]["RemoteId"];
            workspace_type: components["schemas"]["WorkspaceType"];
            name: string | null;
            role: components["schemas"]["Role"];
            can_manage: boolean | null;
            capabilities: components["schemas"]["ProbeCapabilities"];
            purchased_seats: components["schemas"]["Count"] | null;
        };
        /** @description 成功证据自完成起 10 分钟有效；排队或失败无有效期。仅唯一、已确认非个人且可管理的 Team 候选可被建议，不自动绑定。 */
        BindingProbeDTO: {
            id: components["schemas"]["LocalId"];
            revision: components["schemas"]["Revision"];
            manager_account: components["schemas"]["AccountRef"];
            status: components["schemas"]["ProbeStatus"];
            stage: components["schemas"]["ProbeStage"];
            task_id: components["schemas"]["LocalId"];
            run_id: components["schemas"]["LocalId"];
            workspaces: components["schemas"]["ProbeWorkspace"][];
            suggested_workspace_id: components["schemas"]["RemoteId"] | null;
            completed_at: components["schemas"]["Timestamp"] | null;
            expires_at: components["schemas"]["Timestamp"] | null;
            error_info: components["schemas"]["ErrorInfo"] | null;
        };
        BindingProbeReceipt: {
            probe_id: components["schemas"]["LocalId"];
            status: components["schemas"]["ProbeStatus"];
            task_id: components["schemas"]["LocalId"];
            run_id: components["schemas"]["LocalId"];
        };
        TeamActions: {
            sync: components["schemas"]["AllowedAction"];
            reverify: components["schemas"]["AllowedAction"];
            join: components["schemas"]["AllowedAction"];
        };
        TeamDetail: {
            team: components["schemas"]["TeamDTO"];
            actions: components["schemas"]["TeamActions"];
            permission_verified_at: components["schemas"]["Timestamp"] | null;
        };
        /** @description Team、母号关联与首轮同步任务同事务受理，不能部分成功。 */
        TeamCreated: {
            team: components["schemas"]["TeamDTO"];
            sync: components["schemas"]["ActionReceipt"];
        };
        TeamUpdated: {
            team: components["schemas"]["TeamDTO"];
        };
        InvitationDetail: {
            invitation: components["schemas"]["InvitationDTO"];
        };
        /** @description 材料存在性不等于在线认证成功；other_teams 仅指其他本地 Team 业务归属。归档或 auth_capability=unknown 本身不禁用。 */
        CandidateDTO: {
            account: components["schemas"]["AccountRef"];
            category: components["schemas"]["CandidateCategory"];
            auth_capability: components["schemas"]["AuthCapability"];
            has_access_token: boolean;
            has_password: boolean;
            totp_enabled: boolean;
            email_status: components["schemas"]["EmailStatus"];
            other_teams: components["schemas"]["TeamRef"][];
            disabled: boolean;
            reason_code: components["schemas"]["BusinessReasonCode"] | null;
        };
        /** @description 按 trim 后输入去重；邮箱按已有规范精确匹配，只有唯一匹配可自动成为候选，ambiguous 不能默认取第一条。 */
        CandidateResolveItem: {
            input: string;
            match_status: components["schemas"]["MatchStatus"];
            candidates: components["schemas"]["CandidateDTO"][];
            reason_code: components["schemas"]["BusinessReasonCode"] | null;
        };
        /** @description requested_count=unique_count+duplicate_count；明确 ID/邮箱解析不因归档跳过。 */
        CandidateResolveResult: {
            requested_count: components["schemas"]["Count"];
            unique_count: components["schemas"]["Count"];
            duplicate_count: components["schemas"]["Count"];
            items: components["schemas"]["CandidateResolveItem"][];
        };
        /** @description requested=unique+duplicate；七类互斥桶之和为 unique；eligible=new+resume_invite+same_team_active，不能作为额外互斥桶相加。 */
        PreviewCounts: {
            requested_count: components["schemas"]["Count"];
            unique_count: components["schemas"]["Count"];
            duplicate_count: components["schemas"]["Count"];
            unavailable_count: components["schemas"]["Count"];
            another_team_count: components["schemas"]["Count"];
            already_member_count: components["schemas"]["Count"];
            same_team_active_count: components["schemas"]["Count"];
            missing_auth_count: components["schemas"]["Count"];
            resume_invite_count: components["schemas"]["Count"];
            new_count: components["schemas"]["Count"];
            eligible_count: components["schemas"]["Count"];
        };
        /** @description 已购已知时取已购与本地上限较小值，已购为 0 不回退；已购未知时用本地正整数上限。占用为成员/邀请/有效占位按身份去重并集，未知为 null；available=max(0,limit-occupied)。additional_required 为净新增预留数。缺上限或无合格目标阻断 POST join；已有上限但待同步/容量可受理等待。预览不预占、不授权、不承诺零计费。 */
        Capacity: {
            basis: components["schemas"]["CapacityBasis"];
            purchased_seats: components["schemas"]["Count"] | null;
            planned_member_limit: components["schemas"]["PositiveInteger"] | null;
            effective_limit: components["schemas"]["Count"] | null;
            occupied_count: components["schemas"]["Count"] | null;
            available_count: components["schemas"]["Count"] | null;
            additional_required: components["schemas"]["Count"] | null;
            can_submit: boolean;
            blocking_reason_code: components["schemas"]["CapacityBlockingReason"] | null;
        };
        /** @description 纯本地评估；显式 ID 模式 selection 字段均为 null，snapshot_revision 为读模型修订字符串；未知快照事实为 null。不创建 Task/Run、邀请、名单或席位占位。 */
        JoinPreviewDTO: {
            team_id: components["schemas"]["LocalId"];
            selection_id: components["schemas"]["LocalId"] | null;
            selection_revision: components["schemas"]["Revision"] | null;
            snapshot_revision: components["schemas"]["ReadModelRevision"] | null;
            snapshot_at: components["schemas"]["Timestamp"] | null;
            team_last_synced_at: components["schemas"]["Timestamp"] | null;
            requires_sync: boolean;
            counts: components["schemas"]["PreviewCounts"];
            capacity: components["schemas"]["Capacity"];
        };
        /** @description requested/unique/duplicate 受理后固定；pending+accepted+skipped+failed=unique；reused 为 accepted 子集。failed 仅为逐项受理失败。 */
        JoinRequestCounts: {
            requested_count: components["schemas"]["Count"];
            unique_count: components["schemas"]["Count"];
            duplicate_count: components["schemas"]["Count"];
            pending_count: components["schemas"]["Count"];
            accepted_count: components["schemas"]["Count"];
            reused_count: components["schemas"]["Count"];
            skipped_count: components["schemas"]["Count"];
            failed_count: components["schemas"]["Count"];
        };
        /** @description 持久集合请求及父 Task/Run；accepted=true 和 HTTP 202 不表示所有目标已受理或已加入。固定目标先保存，后台窗口受理；待处理项保持 pending。 */
        JoinRequestDTO: {
            id: components["schemas"]["LocalId"];
            team_id: components["schemas"]["LocalId"];
            operation: components["schemas"]["JoinOperation"];
            /** @constant */
            accepted: true;
            reused: boolean;
            status: components["schemas"]["JoinRequestStatus"];
            waiting_reason_code: components["schemas"]["WaitingReasonCode"] | null;
            selection_id: components["schemas"]["LocalId"] | null;
            selection_revision: components["schemas"]["Revision"] | null;
            batch_id: components["schemas"]["LocalId"];
            task_id: components["schemas"]["LocalId"];
            run_id: components["schemas"]["LocalId"];
            created_at: components["schemas"]["Timestamp"];
            counts: components["schemas"]["JoinRequestCounts"];
            capacity: components["schemas"]["Capacity"];
            /** @description 本请求逐项回执读取路径。 */
            items_url: string;
        };
        /** @description 固定目标 ordinal 升序；未创建或不能定位的引用为 null（如无效 invitation_id 无法定位 account_id）。无执行引用时 execution_status=none；已有精确引用可保留。 */
        JoinItemDTO: {
            ordinal: components["schemas"]["Count"];
            account_id: components["schemas"]["LocalId"] | null;
            invitation_id: components["schemas"]["LocalId"] | null;
            acceptance_status: components["schemas"]["AcceptanceStatus"];
            task_id: components["schemas"]["LocalId"] | null;
            run_id: components["schemas"]["LocalId"] | null;
            execution_status: components["schemas"]["ExecutionStatus"];
            reason_code: components["schemas"]["BusinessReasonCode"] | null;
            message: string | null;
        };
        SyncBulkItem: {
            team_id: components["schemas"]["LocalId"];
            task_id: components["schemas"]["LocalId"] | null;
            run_id: components["schemas"]["LocalId"] | null;
            acceptance_status: components["schemas"]["SyncAcceptanceStatus"];
            execution_status: components["schemas"]["ExecutionStatus"];
            reason_code: components["schemas"]["BusinessReasonCode"] | null;
        };
        /** @description requested=unique+duplicate；accepted+skipped+failed=unique；reused 已包含在 accepted 中，不重复相加。 */
        SyncBulkReceipt: {
            /** @constant */
            accepted: true;
            batch_id: components["schemas"]["LocalId"];
            requested_count: components["schemas"]["Count"];
            unique_count: components["schemas"]["Count"];
            duplicate_count: components["schemas"]["Count"];
            reused_count: components["schemas"]["Count"];
            accepted_count: components["schemas"]["Count"];
            skipped_count: components["schemas"]["Count"];
            failed_count: components["schemas"]["Count"];
            items: components["schemas"]["SyncBulkItem"][];
        };
        /** @description 没有其他业务字段；幂等键也可仅放请求头。 */
        IdempotentRequest: {
            idempotency_key?: components["schemas"]["IdempotencyKey"];
        };
        /** @description target_workspace_id 仅限制或预选探测，不能代替创建时明确绑定。归档管理账号允许探测。 */
        BindingProbeRequest: {
            manager_account_id: components["schemas"]["LocalId"];
            target_workspace_id?: components["schemas"]["RemoteId"];
            idempotency_key?: components["schemas"]["IdempotencyKey"];
        };
        /** @description 必须提交准确工作区与匹配的有效成功探测证据，can_manage=true；不能绑定个人工作区。同部署 workspace 唯一。 */
        TeamCreateRequest: {
            manager_account_id: components["schemas"]["LocalId"];
            workspace_id: components["schemas"]["RemoteId"];
            probe_id: components["schemas"]["LocalId"];
            probe_revision: components["schemas"]["Revision"];
            display_name?: components["schemas"]["DisplayName"];
            planned_member_limit?: components["schemas"]["PositiveInteger"] | null;
            idempotency_key?: components["schemas"]["IdempotencyKey"];
        };
        /** @description 至少一个可编辑字段；换母号需同一已保存 workspace 的有效 Probe。不能修改 workspace、角色、已购席位或远端名称；未更换母号不得通过无关 Probe 修改权限事实。只更换执行管理身份，不转移所有权或改变成员角色。 */
        TeamPatchRequest: {
            expected_revision: components["schemas"]["Revision"];
            display_name?: components["schemas"]["DisplayName"];
            planned_member_limit?: components["schemas"]["PositiveInteger"] | null;
            manager_account_id?: components["schemas"]["LocalId"];
            probe_id?: components["schemas"]["LocalId"];
            probe_revision?: components["schemas"]["Revision"];
            idempotency_key?: components["schemas"]["IdempotencyKey"];
        } & ({
            display_name: components["schemas"]["DisplayName"];
        } | {
            planned_member_limit: components["schemas"]["PositiveInteger"] | null;
        } | {
            manager_account_id: components["schemas"]["LocalId"];
        });
        /** @description 按 team_id 去重；重复输入合法，保留 requested/unique/duplicate 统计。 */
        SyncBulkRequest: {
            team_ids: components["schemas"]["LocalId"][];
            idempotency_key?: components["schemas"]["IdempotencyKey"];
        };
        /** @description 纯读 POST；不要求也不接受 JSON idempotency_key；不登录、不访问上游、不持久名单或创建任务。 */
        CandidateResolveRequest: {
            values: string[];
        };
        /** @description 可选账号 ID→非空邮箱快照映射；每个键必须属于同请求 account_ids。账号来源应提交完整已选邮箱快照。 */
        ExpectedEmailSnapshots: {
            [key: string]: components["schemas"]["Email"];
        };
        /** @description 按账号 ID 去重并保留首次顺序；重复输入合法。核对固定邮箱快照，不把换绑后邮箱静默替换为本次目标。 */
        ExplicitPreviewTargets: {
            account_ids: components["schemas"]["LocalId"][];
            expected_emails?: components["schemas"]["ExpectedEmailSnapshots"];
        };
        /** @description 必须为已冻结、最多 100,000 账号的 team_join/version=1 集合，Team 与修订匹配；沿用名单固定邮箱快照，不接受 account_ids 或 expected_emails。preview 不消费，join 原子消费。 */
        SelectionPreviewTargets: {
            selection_id: components["schemas"]["LocalId"];
            selection_revision: components["schemas"]["Revision"];
        };
        /** @description 显式账号或冻结集合严格二选一；不接受任意角色、workspace 替换或个人数据合并选项。 */
        JoinPreviewRequest: {
            account_ids?: components["schemas"]["LocalId"][];
            expected_emails?: components["schemas"]["ExpectedEmailSnapshots"];
            selection_id?: components["schemas"]["LocalId"];
            selection_revision?: components["schemas"]["Revision"];
        } & (components["schemas"]["ExplicitPreviewTargets"] | components["schemas"]["SelectionPreviewTargets"]);
        /** @description 按账号 ID 去重并保留首次顺序；重复输入合法。核对固定邮箱快照，不把换绑后邮箱静默替换为本次目标。 */
        ExplicitJoinTargets: {
            account_ids: components["schemas"]["LocalId"][];
            expected_emails?: components["schemas"]["ExpectedEmailSnapshots"];
            idempotency_key?: components["schemas"]["IdempotencyKey"];
        };
        /** @description 必须为已冻结、最多 100,000 账号的 team_join/version=1 集合，Team 与修订匹配；沿用名单固定邮箱快照，不接受 account_ids 或 expected_emails。preview 不消费，join 原子消费。 */
        SelectionJoinTargets: {
            selection_id: components["schemas"]["LocalId"];
            selection_revision: components["schemas"]["Revision"];
            idempotency_key?: components["schemas"]["IdempotencyKey"];
        };
        /** @description 显式账号或冻结集合严格二选一；不接受任意角色、workspace 替换或个人数据合并选项。 */
        JoinRequest: {
            account_ids?: components["schemas"]["LocalId"][];
            expected_emails?: components["schemas"]["ExpectedEmailSnapshots"];
            idempotency_key?: components["schemas"]["IdempotencyKey"];
            selection_id?: components["schemas"]["LocalId"];
            selection_revision?: components["schemas"]["Revision"];
        } & (components["schemas"]["ExplicitJoinTargets"] | components["schemas"]["SelectionJoinTargets"]);
        /** @description 先按 invitation_id、再按同 Team 目标身份去重。不存在或属于其他 Team 的项 skipped/invitation_not_found，其余继续，不返回其他 Team 材料。 */
        InvitationBulkRequest: {
            invitation_ids: components["schemas"]["LocalId"][];
            idempotency_key?: components["schemas"]["IdempotencyKey"];
        };
        /** @description 仅接受列出的单值参数；未知字段、非法枚举或分页越界返回 422，不接受逗号拼接。q 只匹配公开名称、邮箱或本地 ID，不替代精确 ID 筛选。 */
        TeamListQuery: {
            /** @default 1 */
            page: number;
            /** @default 20 */
            page_size: number;
            /**
             * @default 0
             * @enum {string}
             */
            include_facets: "0" | "1";
            q?: string;
            manager_account_id?: components["schemas"]["LocalId"];
            role?: components["schemas"]["Role"];
            last_sync_status?: components["schemas"]["LastSyncStatus"];
        };
        /** @description 仅接受列出的单值参数；未知字段、非法枚举或分页越界返回 422，不接受逗号拼接。q 只匹配公开名称、邮箱或本地 ID，不替代精确 ID 筛选。 */
        MemberListQuery: {
            /** @default 1 */
            page: number;
            /** @default 20 */
            page_size: number;
            /**
             * @default 0
             * @enum {string}
             */
            include_facets: "0" | "1";
            q?: string;
            /** @default joined */
            membership_state: components["schemas"]["MembershipState"];
            role?: components["schemas"]["Role"];
            linked?: components["schemas"]["LinkedFilter"];
        };
        /** @description 仅接受列出的单值参数；未知字段、非法枚举或分页越界返回 422，不接受逗号拼接。q 只匹配公开名称、邮箱或本地 ID，不替代精确 ID 筛选。 */
        InvitationListQuery: {
            /** @default 1 */
            page: number;
            /** @default 20 */
            page_size: number;
            /**
             * @default 0
             * @enum {string}
             */
            include_facets: "0" | "1";
            q?: string;
            invitation_state?: components["schemas"]["InvitationState"];
            membership_state?: components["schemas"]["MembershipState"];
            execution_status?: components["schemas"]["ExecutionStatus"];
            stage?: components["schemas"]["JoinStage"];
            join_request_id?: components["schemas"]["LocalId"];
        };
        /** @description 仅接受列出的单值参数；未知字段、非法枚举或分页越界返回 422，不接受逗号拼接。q 只匹配公开名称、邮箱或本地 ID，不替代精确 ID 筛选。 */
        CandidateListQuery: {
            /** @default 1 */
            page: number;
            /** @default 20 */
            page_size: number;
            /**
             * @default 0
             * @enum {string}
             */
            include_facets: "0" | "1";
            q?: string;
            /** @default unassigned */
            scope: components["schemas"]["CandidateScope"];
            /** @default 0 */
            archived: components["schemas"]["ArchivedFilter"];
            has_access_token?: components["schemas"]["BooleanQuery"];
            has_password?: components["schemas"]["BooleanQuery"];
            totp_enabled?: components["schemas"]["BooleanQuery"];
            email_status?: components["schemas"]["EmailStatus"];
        };
        /** @description 仅接受列出的单值参数；未知字段、非法枚举或分页越界返回 422，不接受逗号拼接。q 只匹配公开名称、邮箱或本地 ID，不替代精确 ID 筛选。 */
        JoinRequestItemsQuery: {
            /** @default 1 */
            page: number;
            /** @default 20 */
            page_size: number;
            /**
             * @default 0
             * @enum {string}
             */
            include_facets: "0" | "1";
            acceptance_status?: components["schemas"]["AcceptanceStatus"];
            execution_status?: components["schemas"]["ExecutionStatus"];
            reason_code?: components["schemas"]["BusinessReasonCode"];
        };
        /** @description 该列表不提供业务 facets；include_facets=1 时返回严格空对象。 */
        EmptyFacets: Record<string, never>;
        TeamRoleFacet: {
            value: components["schemas"]["Role"];
            count: components["schemas"]["Count"];
        };
        TeamLastSyncStatusFacet: {
            value: components["schemas"]["LastSyncStatus"];
            count: components["schemas"]["Count"];
        };
        /** @description 仅在 include_facets=1 时返回；列表、total、facets 使用相同业务范围。 */
        TeamFacets: {
            role: components["schemas"]["TeamRoleFacet"][];
            last_sync_status: components["schemas"]["TeamLastSyncStatusFacet"][];
        };
        MemberMembershipStateFacet: {
            value: components["schemas"]["MembershipState"];
            count: components["schemas"]["Count"];
        };
        MemberRoleFacet: {
            value: components["schemas"]["Role"];
            count: components["schemas"]["Count"];
        };
        MemberLinkedFacet: {
            /** @enum {string} */
            value: "linked" | "unlinked";
            count: components["schemas"]["Count"];
        };
        /** @description 仅在 include_facets=1 时返回；列表、total、facets 使用相同业务范围。 */
        MemberFacets: {
            membership_state: components["schemas"]["MemberMembershipStateFacet"][];
            role: components["schemas"]["MemberRoleFacet"][];
            linked: components["schemas"]["MemberLinkedFacet"][];
        };
        InvitationInvitationStateFacet: {
            value: components["schemas"]["InvitationState"];
            count: components["schemas"]["Count"];
        };
        InvitationMembershipStateFacet: {
            value: components["schemas"]["MembershipState"];
            count: components["schemas"]["Count"];
        };
        InvitationExecutionStatusFacet: {
            value: components["schemas"]["ExecutionStatus"];
            count: components["schemas"]["Count"];
        };
        InvitationStageFacet: {
            value: components["schemas"]["JoinStage"];
            count: components["schemas"]["Count"];
        };
        /** @description 仅在 include_facets=1 时返回；列表、total、facets 使用相同业务范围。 */
        InvitationFacets: {
            invitation_state: components["schemas"]["InvitationInvitationStateFacet"][];
            membership_state: components["schemas"]["InvitationMembershipStateFacet"][];
            execution_status: components["schemas"]["InvitationExecutionStatusFacet"][];
            stage: components["schemas"]["InvitationStageFacet"][];
        };
        TeamList: {
            items: components["schemas"]["TeamDTO"][];
            total: components["schemas"]["Count"];
            page: number;
            page_size: number;
            revision: components["schemas"]["ReadModelRevision"];
            facets?: components["schemas"]["TeamFacets"];
        };
        MemberList: {
            items: components["schemas"]["MemberDTO"][];
            total: components["schemas"]["Count"];
            page: number;
            page_size: number;
            revision: components["schemas"]["ReadModelRevision"];
            facets?: components["schemas"]["MemberFacets"];
        };
        InvitationList: {
            items: components["schemas"]["InvitationDTO"][];
            total: components["schemas"]["Count"];
            page: number;
            page_size: number;
            revision: components["schemas"]["ReadModelRevision"];
            facets?: components["schemas"]["InvitationFacets"];
        };
        CandidateList: {
            items: components["schemas"]["CandidateDTO"][];
            total: components["schemas"]["Count"];
            page: number;
            page_size: number;
            revision: components["schemas"]["ReadModelRevision"];
            facets?: components["schemas"]["EmptyFacets"];
        };
        JoinRequestItems: {
            request: components["schemas"]["JoinRequestDTO"];
            items: components["schemas"]["JoinItemDTO"][];
            total: components["schemas"]["Count"];
            page: number;
            page_size: number;
            revision: components["schemas"]["ReadModelRevision"];
            facets?: components["schemas"]["EmptyFacets"];
        };
        /** @description 允许空对象或白名单业务详情。契约明确定位字段：existing_team_id、existing_join_request_id、revision；其余仅安全资源/版本/字段名/上下限。禁止完整账号、AT、Cookie、密码、OTP、Session、恢复材料及原始上游响应。 */
        ErrorDetails: {
            existing_team_id?: components["schemas"]["LocalId"];
            existing_join_request_id?: components["schemas"]["LocalId"];
            team_id?: components["schemas"]["LocalId"];
            account_id?: components["schemas"]["LocalId"];
            probe_id?: components["schemas"]["LocalId"];
            invitation_id?: components["schemas"]["LocalId"];
            join_request_id?: components["schemas"]["LocalId"];
            selection_id?: components["schemas"]["LocalId"];
            revision?: components["schemas"]["Revision"];
            expected_revision?: components["schemas"]["Revision"];
            probe_revision?: components["schemas"]["Revision"];
            selection_revision?: components["schemas"]["Revision"];
            workspace_id?: components["schemas"]["RemoteId"];
            fields?: string[];
            unsupported_fields?: string[];
            allowed_fields?: string[];
            minimum?: number;
            maximum?: number;
        };
        /** @enum {string} */
        HttpErrorCode: "invalid_json" | "authentication_required" | "access_denied" | "team_not_found" | "account_not_found" | "probe_not_found" | "invitation_not_found" | "join_request_not_found" | "selection_not_found" | "idempotency_conflict" | "revision_conflict" | "probe_not_ready" | "probe_expired" | "probe_revision_conflict" | "probe_identity_mismatch" | "manager_permission_unconfirmed" | "team_already_bound" | "already_in_another_team" | "selection_not_ready" | "selection_revision_mismatch" | "selection_operation_mismatch" | "selection_team_mismatch" | "selection_consumed" | "team_limit_required" | "selection_expired" | "parameter_invalid" | "field_not_supported" | "idempotency_key_required" | "idempotency_key_invalid" | "idempotency_key_mismatch" | "team_store_unavailable";
        ApiError: {
            code: components["schemas"]["HttpErrorCode"];
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            retryable: boolean;
            details: components["schemas"]["ErrorDetails"];
        };
        /** @description HTTP 状态与错误一致，不使用 HTTP 200 包装输入错误。request_id 仅跟踪本次请求，不是幂等键；无单一字段时 field=null。 */
        ErrorResponse: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["ApiError"];
        };
        Http400Error: {
            /** @enum {string} */
            code: "invalid_json";
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            retryable: boolean;
            details: components["schemas"]["ErrorDetails"];
        };
        Http400Response: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["Http400Error"];
        };
        Http401Error: {
            /** @enum {string} */
            code: "authentication_required";
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            retryable: boolean;
            details: components["schemas"]["ErrorDetails"];
        };
        Http401Response: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["Http401Error"];
        };
        Http403Error: {
            /** @enum {string} */
            code: "access_denied";
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            retryable: boolean;
            details: components["schemas"]["ErrorDetails"];
        };
        Http403Response: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["Http403Error"];
        };
        Http404Error: {
            /** @enum {string} */
            code: "team_not_found" | "account_not_found" | "probe_not_found" | "invitation_not_found" | "join_request_not_found" | "selection_not_found";
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            retryable: boolean;
            details: components["schemas"]["ErrorDetails"];
        };
        Http404Response: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["Http404Error"];
        };
        Http409Error: {
            /** @enum {string} */
            code: "idempotency_conflict" | "revision_conflict" | "probe_not_ready" | "probe_expired" | "probe_revision_conflict" | "probe_identity_mismatch" | "manager_permission_unconfirmed" | "team_already_bound" | "already_in_another_team" | "selection_not_ready" | "selection_revision_mismatch" | "selection_operation_mismatch" | "selection_team_mismatch" | "selection_consumed" | "team_limit_required";
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            retryable: boolean;
            details: components["schemas"]["ErrorDetails"];
        };
        Http409Response: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["Http409Error"];
        };
        Http410Error: {
            /** @enum {string} */
            code: "selection_expired";
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            retryable: boolean;
            details: components["schemas"]["ErrorDetails"];
        };
        Http410Response: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["Http410Error"];
        };
        Http422Error: {
            /** @enum {string} */
            code: "parameter_invalid" | "field_not_supported" | "idempotency_key_required" | "idempotency_key_invalid" | "idempotency_key_mismatch";
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            retryable: boolean;
            details: components["schemas"]["ErrorDetails"];
        };
        Http422Response: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["Http422Error"];
        };
        Http503Error: {
            /** @enum {string} */
            code: "team_store_unavailable";
            /** @description 公开中文原因。 */
            message: string;
            field: string | null;
            /** @constant */
            retryable: true;
            details: components["schemas"]["ErrorDetails"];
        };
        Http503Response: {
            /** @constant */
            ok: false;
            request_id: string;
            error: components["schemas"]["Http503Error"];
        };
        BindingProbeReceiptResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["BindingProbeReceipt"];
        };
        BindingProbeDTOResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["BindingProbeDTO"];
        };
        TeamCreatedResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["TeamCreated"];
        };
        TeamListResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["TeamList"];
        };
        TeamDetailResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["TeamDetail"];
        };
        TeamUpdatedResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["TeamUpdated"];
        };
        ActionReceiptResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["ActionReceipt"];
        };
        SyncBulkReceiptResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["SyncBulkReceipt"];
        };
        MemberListResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["MemberList"];
        };
        InvitationListResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["InvitationList"];
        };
        InvitationDetailResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["InvitationDetail"];
        };
        CandidateListResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["CandidateList"];
        };
        CandidateResolveResultResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["CandidateResolveResult"];
        };
        JoinPreviewDTOResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["JoinPreviewDTO"];
        };
        JoinRequestDTOResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["JoinRequestDTO"];
        };
        JoinRequestItemsResponse: {
            /** @constant */
            ok: true;
            /** @description 本次 HTTP 追踪编号，不是幂等键。 */
            request_id: string;
            data: components["schemas"]["JoinRequestItems"];
        };
    };
    responses: {
        /** @description invalid_json */
        Error400: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Http400Response"];
            };
        };
        /** @description authentication_required */
        Error401: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Http401Response"];
            };
        };
        /** @description access_denied */
        Error403: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Http403Response"];
            };
        };
        /** @description team_not_found；account_not_found；probe_not_found；invitation_not_found；join_request_not_found；selection_not_found */
        Error404: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Http404Response"];
            };
        };
        /** @description idempotency_conflict；revision_conflict；probe_not_ready；probe_expired；probe_revision_conflict；probe_identity_mismatch；manager_permission_unconfirmed；team_already_bound；already_in_another_team；selection_not_ready；selection_revision_mismatch；selection_operation_mismatch；selection_team_mismatch；selection_consumed；team_limit_required */
        Error409: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Http409Response"];
            };
        };
        /** @description selection_expired */
        Error410: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Http410Response"];
            };
        };
        /** @description parameter_invalid；field_not_supported；idempotency_key_required；idempotency_key_invalid；idempotency_key_mismatch */
        Error422: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Http422Response"];
            };
        };
        /** @description team_store_unavailable */
        Error503: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Http503Response"];
            };
        };
    };
    parameters: {
        /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
        IdempotencyKey: components["schemas"]["IdempotencyKey"];
        /** @description 精确本地 ID，正整数十进制字符串。 */
        team_id: components["schemas"]["LocalId"];
        /** @description 精确本地 ID，正整数十进制字符串。 */
        probe_id: components["schemas"]["LocalId"];
        /** @description 精确本地 ID，正整数十进制字符串。 */
        invitation_id: components["schemas"]["LocalId"];
        /** @description 精确本地 ID，正整数十进制字符串。 */
        join_request_id: components["schemas"]["LocalId"];
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    createTeamBindingProbe: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["BindingProbeRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BindingProbeReceiptResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    getTeamBindingProbe: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                probe_id: components["parameters"]["probe_id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BindingProbeDTOResponse"];
                };
            };
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    listTeams: {
        parameters: {
            query?: {
                /** @description 页码，默认 1。 */
                page?: number;
                /** @description 每页数量，默认 20，范围 1–100。 */
                page_size?: number;
                /** @description 默认 0；1 时返回该列表契约限定的 facets。 */
                include_facets?: "0" | "1";
                /** @description 精确单值筛选；未传时不限定。 */
                q?: string;
                /** @description 精确单值筛选；未传时不限定。 */
                manager_account_id?: components["schemas"]["LocalId"];
                /** @description 精确单值筛选；未传时不限定。 */
                role?: components["schemas"]["Role"];
                /** @description 精确单值筛选；未传时不限定。 */
                last_sync_status?: components["schemas"]["LastSyncStatus"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeamListResponse"];
                };
            };
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    createTeam: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["TeamCreateRequest"];
            };
        };
        responses: {
            /** @description 成功。 */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeamCreatedResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    getTeam: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeamDetailResponse"];
                };
            };
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    updateTeam: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["TeamPatchRequest"];
            };
        };
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TeamUpdatedResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    syncTeam: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody?: {
            content: {
                "application/json": components["schemas"]["IdempotentRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionReceiptResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    syncTeamsBulk: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path?: never;
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["SyncBulkRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SyncBulkReceiptResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    reverifyTeam: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody?: {
            content: {
                "application/json": components["schemas"]["IdempotentRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActionReceiptResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    listTeamMembers: {
        parameters: {
            query?: {
                /** @description 页码，默认 1。 */
                page?: number;
                /** @description 每页数量，默认 20，范围 1–100。 */
                page_size?: number;
                /** @description 默认 0；1 时返回该列表契约限定的 facets。 */
                include_facets?: "0" | "1";
                /** @description 精确单值筛选；未传时不限定。 */
                q?: string;
                /** @description 精确单值筛选；未传时不限定。 */
                membership_state?: components["schemas"]["MembershipState"];
                /** @description 精确单值筛选；未传时不限定。 */
                role?: components["schemas"]["Role"];
                /** @description 精确单值筛选；未传时不限定。 */
                linked?: components["schemas"]["LinkedFilter"];
            };
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MemberListResponse"];
                };
            };
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    listTeamInvitations: {
        parameters: {
            query?: {
                /** @description 页码，默认 1。 */
                page?: number;
                /** @description 每页数量，默认 20，范围 1–100。 */
                page_size?: number;
                /** @description 默认 0；1 时返回该列表契约限定的 facets。 */
                include_facets?: "0" | "1";
                /** @description 精确单值筛选；未传时不限定。 */
                q?: string;
                /** @description 精确单值筛选；未传时不限定。 */
                invitation_state?: components["schemas"]["InvitationState"];
                /** @description 精确单值筛选；未传时不限定。 */
                membership_state?: components["schemas"]["MembershipState"];
                /** @description 精确单值筛选；未传时不限定。 */
                execution_status?: components["schemas"]["ExecutionStatus"];
                /** @description 精确单值筛选；未传时不限定。 */
                stage?: components["schemas"]["JoinStage"];
                /** @description 精确单值筛选；未传时不限定。 */
                join_request_id?: components["schemas"]["LocalId"];
            };
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvitationListResponse"];
                };
            };
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    getTeamInvitation: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
                /** @description 精确本地 ID，正整数十进制字符串。 */
                invitation_id: components["parameters"]["invitation_id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvitationDetailResponse"];
                };
            };
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    listTeamCandidates: {
        parameters: {
            query?: {
                /** @description 页码，默认 1。 */
                page?: number;
                /** @description 每页数量，默认 20，范围 1–100。 */
                page_size?: number;
                /** @description 默认 0；1 时返回该列表契约限定的 facets。 */
                include_facets?: "0" | "1";
                /** @description 精确单值筛选；未传时不限定。 */
                q?: string;
                /** @description 精确单值筛选；未传时不限定。 */
                scope?: components["schemas"]["CandidateScope"];
                /** @description 精确单值筛选；未传时不限定。 */
                archived?: components["schemas"]["ArchivedFilter"];
                /** @description 精确单值筛选；未传时不限定。 */
                has_access_token?: components["schemas"]["BooleanQuery"];
                /** @description 精确单值筛选；未传时不限定。 */
                has_password?: components["schemas"]["BooleanQuery"];
                /** @description 精确单值筛选；未传时不限定。 */
                totp_enabled?: components["schemas"]["BooleanQuery"];
                /** @description 精确单值筛选；未传时不限定。 */
                email_status?: components["schemas"]["EmailStatus"];
            };
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CandidateListResponse"];
                };
            };
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    resolveTeamCandidates: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["CandidateResolveRequest"];
            };
        };
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CandidateResolveResultResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    previewTeamJoin: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["JoinPreviewRequest"];
            };
        };
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JoinPreviewDTOResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            410: components["responses"]["Error410"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    joinTeam: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["JoinRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JoinRequestDTOResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            410: components["responses"]["Error410"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    getTeamJoinRequest: {
        parameters: {
            query?: {
                /** @description 页码，默认 1。 */
                page?: number;
                /** @description 每页数量，默认 20，范围 1–100。 */
                page_size?: number;
                /** @description 默认 0；1 时返回该列表契约限定的 facets。 */
                include_facets?: "0" | "1";
                /** @description 精确单值筛选；未传时不限定。 */
                acceptance_status?: components["schemas"]["AcceptanceStatus"];
                /** @description 精确单值筛选；未传时不限定。 */
                execution_status?: components["schemas"]["ExecutionStatus"];
                /** @description 精确单值筛选；未传时不限定。 */
                reason_code?: components["schemas"]["BusinessReasonCode"];
            };
            header?: never;
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
                /** @description 精确本地 ID，正整数十进制字符串。 */
                join_request_id: components["parameters"]["join_request_id"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description 成功。 */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JoinRequestItemsResponse"];
                };
            };
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    continueTeamInvitation: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
                /** @description 精确本地 ID，正整数十进制字符串。 */
                invitation_id: components["parameters"]["invitation_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody?: {
            content: {
                "application/json": components["schemas"]["IdempotentRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JoinRequestDTOResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    continueTeamInvitationsBulk: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["InvitationBulkRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JoinRequestDTOResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    retryTeamInvitation: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
                /** @description 精确本地 ID，正整数十进制字符串。 */
                invitation_id: components["parameters"]["invitation_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody?: {
            content: {
                "application/json": components["schemas"]["IdempotentRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JoinRequestDTOResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
    retryTeamInvitationsBulk: {
        parameters: {
            query?: never;
            header?: {
                /** @description 写请求至少从此头或 JSON idempotency_key 提供一份；两处均提供时 trim 后必须完全相同，否则 422。request_id 不能代替本键。 */
                "Idempotency-Key"?: components["parameters"]["IdempotencyKey"];
            };
            path: {
                /** @description 精确本地 ID，正整数十进制字符串。 */
                team_id: components["parameters"]["team_id"];
            };
            cookie?: never;
        };
        /** @description 必须为 JSON 对象，只接受本文列出的字段。也可仅通过请求头提供幂等键。 */
        requestBody: {
            content: {
                "application/json": components["schemas"]["InvitationBulkRequest"];
            };
        };
        responses: {
            /** @description 已持久受理。 */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JoinRequestDTOResponse"];
                };
            };
            400: components["responses"]["Error400"];
            401: components["responses"]["Error401"];
            403: components["responses"]["Error403"];
            404: components["responses"]["Error404"];
            409: components["responses"]["Error409"];
            422: components["responses"]["Error422"];
            503: components["responses"]["Error503"];
        };
    };
}
