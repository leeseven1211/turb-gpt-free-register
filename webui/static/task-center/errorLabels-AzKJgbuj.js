var e = {
	version: 1,
	maxLength: 10,
	lookupFields: [
		"cause_display_code",
		"cause_code",
		"code",
		"error_code",
		"display_code"
	],
	codeLabels: {
		"account.deactivated": "账号已停用",
		"account.email_already_used": "邮箱已被使用",
		"account.email_matches_current": "邮箱未变化",
		"account.target_unavailable": "目标不可用",
		browser_unavailable_on_deployment: "浏览器未配置",
		"configuration.invalid": "配置无效",
		"configuration.missing": "配置缺失",
		"external.c2a.auth": "集成鉴权失败",
		"external.c2a.configuration": "集成配置无效",
		"external.c2a.confirmation": "集成回执未确认",
		"external.c2a.contract": "集成回执异常",
		"external.c2a.credential": "集成凭据异常",
		"external.c2a.http": "集成接口异常",
		"external.c2a.identity": "集成身份不符",
		"external.c2a.local_execution": "本地执行异常",
		"external.c2a.local_policy": "本地策略限制",
		"external.c2a.local_writeback": "本地写回未完成",
		"external.c2a.remote_rejected": "集成请求被拒",
		"external.c2a.safety": "远端策略待核验",
		"external.c2a.transport": "集成网络异常",
		"external.email": "邮箱服务异常",
		"external.email.account_missing": "邮箱账号不存在",
		"external.email.email_butler_prepare": "邮箱准备失败",
		"external.email.service_unavailable": "邮箱服务不可用",
		"external.extract_link.rejected": "提链请求被拒",
		"external.network": "网络服务异常",
		"external.network.mfa_transport": "双重验证网络异常",
		"external.network.registration_timeout": "注册认证超时",
		"external.openai": "上游服务异常",
		"external.openai.account_creation_rejected": "账号创建被拒",
		"external.openai.auth_reauth_required": "需要重新登录",
		"external.openai.auth_route_rejected": "授权路由被拒",
		"external.openai.credential_expired": "授权已失效",
		"external.openai.email_change_account_too_new": "账号注册时间不足",
		"external.openai.email_change_failed": "邮箱换绑失败",
		"external.openai.email_change_forbidden": "当前会话禁止换绑",
		"external.openai.email_change_incomplete": "邮箱换绑未完成",
		"external.openai.email_change_recent_login": "换绑认证失败",
		"external.openai.email_change_rejected": "邮箱换绑被拒",
		"external.openai.email_domain_rejected": "邮箱域名被拒",
		"external.openai.plan_forbidden": "套餐请求被拒",
		"external.openai.registration_rejected": "注册请求被拒",
		"external.proxy": "代理获取失败",
		"external.roxy": "浏览器服务异常",
		"external.roxy_capacity": "浏览器额度不足",
		"external.sub2api.auth": "集成鉴权失败",
		"external.sub2api.configuration": "集成配置无效",
		"external.sub2api.confirmation": "集成回执未确认",
		"external.sub2api.contract": "集成回执异常",
		"external.sub2api.credential": "集成凭据异常",
		"external.sub2api.http": "集成接口异常",
		"external.sub2api.identity": "集成身份不符",
		"external.sub2api.local_execution": "本地执行异常",
		"external.sub2api.local_policy": "本地策略限制",
		"external.sub2api.local_writeback": "本地写回未完成",
		"external.sub2api.remote_rejected": "集成请求被拒",
		"external.sub2api.safety": "远端策略待核验",
		"external.sub2api.transport": "集成网络异常",
		"internal.browser": "浏览器自动化异常",
		"internal.code": "本地代码错误",
		"internal.request_prepare": "请求准备失败",
		"internal.storage": "数据存储异常",
		"service.interrupted": "服务重启中断",
		"task.pending": "等待执行",
		"unknown.unclassified": "诊断证据不足",
		"user.interrupted": "任务已取消",
		"workflow.page_state": "页面未推进",
		"workflow.password_entry_not_hydrated": "密码页未加载",
		"workflow.password_entry_not_offered": "密码入口缺失",
		"workflow.password_entry_recovery_exhausted": "密码页恢复失败",
		"workflow.password_settings_entry_unavailable": "密码设置入口缺失",
		"workflow.retry_blocked": "原邮箱无法重试",
		"workflow.unsupported": "功能不支持",
		"workflow.verification": "验证流程失败"
	},
	causeCodeLabels: /* @__PURE__ */ JSON.parse("{\"access_token_expired\":\"返回凭据已过期\",\"access_token_missing\":\"账号凭据缺失\",\"account_action_http_rejected\":\"账号请求被拒\",\"account_action_rate_limited\":\"账号请求受限流\",\"account_action_request_unknown\":\"账号请求待确认\",\"account_action_route_exhausted\":\"账号换线次数耗尽\",\"account_action_route_unavailable\":\"账号线路不可用\",\"account_busy\":\"账号正被占用\",\"account_create_invalid_state\":\"账号创建会话失效\",\"account_create_registration_disallowed\":\"注册被上游禁止\",\"account_create_user_already_exists\":\"账号已存在会话未完成\",\"account_profile_required\":\"账号资料待补全\",\"account_reference_mismatch\":\"本地账号邮箱不符\",\"account_setup_local_commit_failed\":\"账号配置写回未完成\",\"account_setup_step_not_completed\":\"账号配置尚未完成\",\"account_setup_step_not_executed\":\"账号配置尚未执行\",\"active_lease_limit\":\"邮箱租约已达上限\",\"adapter_operation_unmapped\":\"任务操作未登记\",\"adapter_status_unmapped\":\"任务状态未登记\",\"allocation_busy\":\"邮箱分配繁忙\",\"api_version_retired\":\"邮箱接口已退役\",\"at_refresh_failed\":\"自动刷新凭据失败\",\"at_refresh_network_budget_exhausted\":\"刷新网络恢复超时\",\"auth_challenge_loop\":\"认证挑战重复\",\"auth_cloudflare_challenge\":\"认证挑战受阻\",\"auth_context_ambiguous\":\"认证上下文冲突\",\"auth_context_missing\":\"登录上下文缺失\",\"auth_navigation_failed\":\"认证页面请求未完成\",\"auth_operation_timeout\":\"认证页面操作超时\",\"auth_page_unknown\":\"认证页面未识别\",\"auth_redirect_invalid\":\"认证跳转目标无效\",\"auth_redirect_limit\":\"认证跳转超限\",\"auth_route_rejected\":\"授权路由被拒\",\"batch_capacity\":\"等待批次空位\",\"batch_paused\":\"批次已暂停\",\"browser_auth_navigation_failed\":\"认证页面导航失败\",\"browser_http2_ping_failed\":\"浏览器连接保活失败\",\"browser_stage_timeout\":\"浏览器阶段超时\",\"butler_availability_response_invalid\":\"库存回执无效\",\"butler_client_response_invalid\":\"邮箱客户端回执无效\",\"butler_code_response_invalid\":\"验证码回执无效\",\"butler_configuration_invalid\":\"邮箱连接配置无效\",\"butler_credentials_missing\":\"邮箱连接凭据缺失\",\"butler_endpoint_redirect\":\"邮箱接口发生跳转\",\"butler_lease_id_invalid\":\"邮箱租约编号无效\",\"butler_lease_identity_mismatch\":\"返回租约身份不符\",\"butler_lease_response_invalid\":\"邮箱租约回执无效\",\"butler_pagination_invalid\":\"邮箱分页回执无效\",\"butler_release_response_invalid\":\"退租回执无效\",\"butler_request_invalid\":\"邮箱请求参数无效\",\"butler_response_invalid\":\"邮箱响应格式无效\",\"butler_response_not_json\":\"邮箱响应解析失败\",\"butler_since_invalid\":\"验证码时间边界无效\",\"butler_transport_connection\":\"邮箱服务连接失败\",\"butler_transport_failed\":\"邮箱网络传输失败\",\"butler_transport_timeout\":\"邮箱服务请求超时\",\"butler_wait_invalid\":\"取码等待参数无效\",\"c2a_account_ambiguous\":\"远端同邮箱账号不唯一\",\"c2a_account_deactivated\":\"关联账号已停用\",\"c2a_account_identity_invalid\":\"账号邮箱身份无效\",\"c2a_account_missing\":\"远端同邮箱账号缺失\",\"c2a_auth_rejected\":\"凭据导入鉴权失败\",\"c2a_backend_changed\":\"凭据导入目标已变化\",\"c2a_client_error\":\"凭据导入客户端异常\",\"c2a_config_invalid\":\"凭据导入配置无效\",\"c2a_connection_failed\":\"凭据导入连接失败\",\"c2a_create_rejected\":\"远端账号新建被拒\",\"c2a_create_unconfirmed\":\"账号新建待确认\",\"c2a_http_error\":\"凭据导入接口异常\",\"c2a_local_access_token_missing\":\"本地同步凭据缺失\",\"c2a_local_account_id_invalid\":\"本地账号编号无效\",\"c2a_local_account_identity_invalid\":\"本地邮箱身份无效\",\"c2a_local_account_missing\":\"本地账号不存在\",\"c2a_local_at_expired\":\"本地凭据已过期\",\"c2a_local_at_identity_mismatch\":\"本地凭据身份不符\",\"c2a_local_at_missing\":\"本地导入凭据缺失\",\"c2a_local_at_unverified\":\"本地凭据未核验\",\"c2a_local_identity_changed\":\"本地账号邮箱已变化\",\"c2a_local_receipt_writeback_failed\":\"远端已更新写回失败\",\"c2a_manual_execution_failed\":\"凭据导入执行异常\",\"c2a_manual_queue_busy\":\"凭据导入任务已存在\",\"c2a_manual_queue_deferred\":\"凭据导入尚未入队\",\"c2a_manual_queue_failed\":\"凭据导入入队失败\",\"c2a_pagination_limit\":\"凭据导入分页超限\",\"c2a_rate_limited\":\"凭据导入请求受限流\",\"c2a_remote_account_id_invalid\":\"远端账号编号无效\",\"c2a_remote_account_disabled\":\"远端账号已禁用\",\"c2a_remote_account_identity_changed\":\"远端邮箱已变化\",\"c2a_remote_account_missing\":\"远端账号不存在\",\"c2a_remote_at_invalid\":\"远端凭据仍失效\",\"c2a_remote_auto_removal_enabled\":\"远端自动清理已开启\",\"c2a_remote_policy_unverified\":\"远端清理策略未确认\",\"c2a_repair_request_invalid\":\"修复请求标识缺失\",\"c2a_remote_token_conflict\":\"远端凭据归属冲突\",\"c2a_scan_queue_failed\":\"巡检任务入队失败\",\"c2a_scan_storage_unavailable\":\"巡检存储不可用\",\"c2a_status_unavailable\":\"巡检状态读取失败\",\"c2a_scan_response_invalid\":\"巡检响应无效\",\"c2a_remote_diagnostic_missing\":\"远端诊断缺失\",\"c2a_local_account_ambiguous\":\"本地账号匹配不唯一\",\"c2a_local_account_archived\":\"本地账号已归档\",\"c2a_remote_account_deactivated\":\"远端账号已停用\",\"c2a_remote_rate_limited\":\"远端账号限流中\",\"c2a_remote_quota_exhausted\":\"远端账号额度不足\",\"c2a_remote_temporarily_unavailable\":\"远端账号暂不可用\",\"c2a_refresh_selection_failed\":\"刷新名单准备失败\",\"c2a_refresh_batch_failed\":\"批量刷新受理失败\",\"c2a_refresh_result_missing\":\"刷新结果缺失\",\"c2a_refresh_token_unchanged\":\"新凭据未确认保存\",\"c2a_refresh_attempts_exhausted\":\"刷新失败已达上限\",\"c2a_upload_queue_failed\":\"回传任务入队失败\",\"c2a_upload_result_missing\":\"回传结果缺失\",\"c2a_upload_request_unknown\":\"上传回执未确认\",\"c2a_repair_cancelled\":\"修复已取消\",\"c2a_scan_in_progress\":\"巡检进行中\",\"c2a_repair_cooldown\":\"等待修复冷却\",\"c2a_scan_cycle_limit\":\"本轮调度已达上限\",\"c2a_sync_complete\":\"远端同步已完成\",\"c2a_remote_at_newer\":\"远端凭据已更新\",\"c2a_remote_access_token_missing\":\"远端凭据读取缺失\",\"c2a_remote_verification_pending\":\"远端核验进行中\",\"c2a_request_failed\":\"凭据导入网络失败\",\"c2a_response_invalid\":\"凭据导入响应无效\",\"c2a_server_error\":\"凭据导入服务不可用\",\"c2a_timeout\":\"凭据导入请求超时\",\"c2a_update_rejected\":\"凭据更新被拒\",\"c2a_update_unconfirmed\":\"凭据更新回执缺失\",\"cached_session_http_failed\":\"会话复用请求异常\",\"cached_session_invalid_response\":\"会话复用响应无效\",\"cached_session_network_failed\":\"会话复用网络失败\",\"cf_proxy_new_ip_unverified\":\"新出口地址未确认\",\"codex_consent_unverifiable\":\"授权确认页受阻\",\"codex_credential_confirmation_missing\":\"授权凭据确认缺失\",\"codex_phone_verification_disabled\":\"手机接码已关闭\",\"completion_confirmation_missing\":\"账号补全结果缺失\",\"concurrency_policy_invalid\":\"并发策略无效\",\"concurrency_policy_migration_required\":\"并发策略待迁移\",\"concurrency_policy_missing\":\"并发策略缺失\",\"config_revision_changed\":\"配置版本已变化\",\"country_attempts_exhausted\":\"国家查询次数耗尽\",\"country_deadline_exhausted\":\"国家查询期限已到\",\"detail_incomplete\":\"套餐诊断证据不足\",\"diagnostic_cause_unresolved\":\"失败原因未记录\",\"email_change_verify_prepare_failed\":\"新邮箱验证准备失败\",\"email_cutover_route_changed\":\"收件路由已变化\",\"email_cutover_target_invalid\":\"邮箱迁移目标无效\",\"email_derivation_address_collision\":\"子地址重复\",\"email_derivation_address_invalid\":\"母邮箱地址无效\",\"email_derivation_capacity_exhausted\":\"子地址额度不足\",\"email_derivation_identity_conflict\":\"子地址身份不符\",\"email_derivation_inventory_empty\":\"子地址库存不足\",\"email_derivation_parent_unavailable\":\"母邮箱不可用\",\"email_derivation_profile_unavailable\":\"子地址收件配置无效\",\"email_derivation_request_conflict\":\"子地址请求冲突\",\"email_derivation_source_disabled\":\"子地址来源未启用\",\"email_derivation_source_unsupported\":\"子地址来源不支持\",\"email_entry_not_ready\":\"邮箱入口未就绪\",\"email_otp_code_rejected\":\"邮箱验证码被拒\",\"email_otp_evidence_missing\":\"邮箱验证证据不足\",\"email_otp_failed\":\"邮箱验证未完成\",\"email_otp_invalid\":\"邮箱验证码无效\",\"email_otp_mailbox_failed\":\"验证码邮箱读取失败\",\"email_otp_no_mail\":\"验证码等待超时\",\"email_otp_send_failed\":\"验证码发送失败\",\"email_otp_send_no_response\":\"发码请求无响应\",\"email_otp_send_rejected\":\"验证码发送被拒\",\"email_otp_send_unconfirmed\":\"发码回执缺失\",\"email_otp_send_unknown\":\"发码响应记录缺失\",\"email_otp_timeout\":\"验证码等待超时\",\"email_otp_validate_failed\":\"邮箱验证码提交未完成\",\"email_otp_validate_invalid_response\":\"邮箱验证码响应无效\",\"email_resource_expired\":\"邮箱资源已过期\",\"email_resource_expiry_invalid\":\"邮箱有效期无效\",\"email_resource_read_failed\":\"邮箱取码不可用\",\"email_scan_connector_unsupported\":\"收件连接器不支持\",\"email_submit_unconfirmed\":\"邮箱提交未确认\",\"email_transition_timeout\":\"邮箱认证跳转超时\",\"email_verification_required\":\"仍需邮箱验证\",\"execution_active\":\"等待上次执行退出\",\"executor_capacity\":\"等待执行空位\",\"executor_submit_failed\":\"执行器未接收任务\",\"extract_approval_query_failed\":\"支付结果查询失败\",\"extract_cdk_invalid\":\"提链兑换码无效\",\"extract_certificate_error\":\"提链证书校验失败\",\"extract_checkout_blocked\":\"结账审批受阻\",\"extract_checkout_risk_blocked\":\"结账被风控拦截\",\"extract_checkout_token_revoked\":\"结账凭据已撤销\",\"extract_checkout_unusual_activity\":\"结账异常活动\",\"extract_connection_failed\":\"提链连接失败\",\"extract_country_mismatch\":\"账单国家不符\",\"extract_create_http_unknown\":\"提链接口异常\",\"extract_create_invalid_json\":\"提链响应解析失败\",\"extract_create_missing_job_id\":\"提链任务编号缺失\",\"extract_create_transport_error\":\"提链网络中断\",\"extract_nonzero_amount\":\"应付金额非零\",\"extract_order_no_progress\":\"提链原单无进展\",\"extract_order_not_found\":\"提链原单未找到\",\"extract_order_polling_timeout\":\"提链续查超时\",\"extract_order_query_failures\":\"提链原单查询失败\",\"extract_payment_approval_blocked\":\"支付审批受阻\",\"extract_payment_blocked\":\"支付确认受阻\",\"extract_payment_method_failed\":\"支付方式设置失败\",\"extract_payment_submit_failed\":\"支付提交失败\",\"extract_promotion_not_applied\":\"优惠未生效\",\"extract_provider_connection_error\":\"提链平台连接失败\",\"extract_provider_dns_error\":\"提链域名解析失败\",\"extract_provider_failed\":\"平台提链失败\",\"extract_provider_request_error\":\"提链请求异常\",\"extract_provider_response_error\":\"提链响应无效\",\"extract_provider_response_missing\":\"提链请求无响应\",\"extract_provider_task_failed\":\"平台任务失败\",\"extract_request_timeout\":\"提链请求超时\",\"extract_sentinel_failed\":\"安全校验异常\",\"extract_tls_error\":\"提链加密连接失败\",\"extract_token_revoked\":\"提链凭据已失效\",\"extract_upi_rejected\":\"支付确认被拒\",\"fairness_turn\":\"等待调度轮转\",\"global_capacity\":\"等待全局空位\",\"icloud_identity_not_found\":\"原邮箱身份不存在\",\"icloud_result_conflict\":\"邮箱上报结果冲突\",\"idempotency_conflict\":\"幂等请求冲突\",\"idempotency_key_invalid\":\"幂等键无效\",\"idempotency_key_required\":\"幂等键缺失\",\"idempotency_result_expired\":\"原幂等结果已过期\",\"identity_mismatch\":\"认证账号身份不符\",\"identity_unconfirmed\":\"认证账号身份未确认\",\"inbound_code_ambiguous\":\"验证码投递存在歧义\",\"inbound_code_timeout\":\"验证码等待超时\",\"inbound_request_failed\":\"入站取码请求失败\",\"inbound_storage_error\":\"入站邮件存储异常\",\"invalid_api_key\":\"邮箱密钥无效\",\"invalid_code_cursor\":\"验证码游标无效\",\"invalid_key\":\"邮箱密钥校验失败\",\"invalid_since\":\"验证码时间边界被拒\",\"inventory_exhausted\":\"邮箱库存不足\",\"lease_client_mismatch\":\"租约客户端不符\",\"lease_expired\":\"邮箱租约已到期\",\"lease_expiry_invalid\":\"租约到期时间无效\",\"lease_identity_mismatch\":\"邮箱租约身份不符\",\"lease_mapping_ambiguous\":\"邮箱租约归属不明\",\"lease_not_found\":\"原租约无法读取\",\"lease_original_mapping_required\":\"原租约映射缺失\",\"lease_released\":\"邮箱租约已退租\",\"lease_restore_required\":\"原邮箱租约待恢复\",\"lease_revoked\":\"邮箱租约已回收\",\"local_browser_submission_conflict\":\"浏览器提交上下文冲突\",\"local_config_schema_mismatch\":\"配置结构不匹配\",\"local_email_inventory_empty\":\"本地邮箱库存为空\",\"mailbox_mismatch\":\"验证码收件箱不符\",\"mfa_activation_unconfirmed\":\"双重验证激活未确认\",\"mfa_code_missing\":\"双重验证码缺失\",\"mfa_enrollment_page_error\":\"双重验证页面错误\",\"mfa_enrollment_step_changed\":\"双重验证步骤已变化\",\"mfa_enrollment_unsupported\":\"双重验证步骤不支持\",\"mfa_factor_missing\":\"双重验证方式缺失\",\"mfa_issue_challenge_failed\":\"双重验证发起失败\",\"mfa_issue_challenge_invalid_response\":\"双重验证挑战无效\",\"mfa_network_error\":\"双重验证网络失败\",\"mfa_otp_provider_not_cooperative\":\"验证码适配器不支持\",\"mfa_rejected\":\"双重验证被拒\",\"mfa_secret_invalid\":\"双重验证密钥无效\",\"mfa_secret_missing\":\"双重验证密钥缺失\",\"mfa_verify_failed\":\"双重验证未完成\",\"mfa_verify_invalid_response\":\"双重验证响应无效\",\"network_connection_failed\":\"套餐网络连接失败\",\"network_dns_failed\":\"套餐域名解析失败\",\"network_preflight_failed\":\"认证线路预检失败\",\"network_tls_failed\":\"套餐加密连接失败\",\"not_due\":\"等待计划时间\",\"oauth_callback_failed\":\"授权回调未完成\",\"oauth_callback_rejected\":\"授权回调被拒\",\"otp_before_challenge\":\"验证码早于挑战\",\"otp_format_invalid\":\"验证码格式无效\",\"otp_network_connection_closed\":\"验证码连接被关闭\",\"otp_network_connection_reset\":\"验证码连接被重置\",\"otp_network_failed_to_fetch\":\"验证码页面读取失败\",\"otp_network_http2_ping_failed\":\"验证码连接保活失败\",\"otp_network_name_not_resolved\":\"验证码域名解析失败\",\"otp_network_proxy_connection_failed\":\"验证码代理连接失败\",\"otp_network_tunnel_connection_failed\":\"验证码代理隧道失败\",\"password_change_required\":\"需要修改密码\",\"password_change_session_required\":\"需先刷新登录态\",\"password_reset_send_otp_failed\":\"重置发码失败\",\"password_reset_otp_rejected\":\"重置验证码被拒\",\"password_reset_otp_timeout\":\"重置验证码超时\",\"password_reset_rejected\":\"重置请求被拒\",\"password_reset_rate_limited\":\"重置被限流\",\"password_reset_unconfirmed\":\"重置未确认\",\"password_reset_checkpoint_failed\":\"新密码未保存\",\"password_reset_request_unknown\":\"重置结果未知\",\"password_entry_navigation_failed\":\"密码入口进入失败\",\"password_entry_navigation_timeout\":\"密码入口导航超时\",\"password_entry_not_offered\":\"认证入口缺失\",\"password_login_unavailable\":\"密码登录不可用\",\"password_missing\":\"本地密码缺失\",\"password_page_error\":\"密码登录页错误\",\"password_recovery_account_deactivated\":\"本地账号已停用\",\"password_recovery_account_identity_mismatch\":\"账号邮箱身份不符\",\"password_recovery_attempt_password_conflict\":\"原注册密码冲突\",\"password_recovery_candidate_generation_failed\":\"候选密码生成失败\",\"password_recovery_candidate_invalid\":\"候选密码无效\",\"password_recovery_candidate_login_context_invalid\":\"候选认证上下文不符\",\"password_recovery_candidate_login_fact_invalid\":\"候选认证事实不符\",\"password_recovery_candidate_login_receipt_invalid\":\"候选认证回执不足\",\"password_recovery_candidate_login_unconfirmed\":\"候选认证未确认\",\"password_recovery_cause_unregistered\":\"恢复原因未登记\",\"password_recovery_checkpoint_missing\":\"恢复检查点缺失\",\"password_recovery_confirmation_invalid\":\"恢复确认缺失\",\"password_recovery_credential_context_invalid\":\"恢复凭据无效\",\"password_recovery_credential_decryption_failed\":\"恢复凭据解密失败\",\"password_recovery_database_error\":\"恢复检查点存储失败\",\"password_recovery_encryption_key_invalid\":\"恢复密钥无效\",\"password_recovery_encryption_key_missing\":\"恢复密钥缺失\",\"password_recovery_identity_unconfirmed\":\"原邮箱身份未确认\",\"password_recovery_manual_operation_mismatch\":\"手动操作归属不符\",\"password_recovery_operation_execution_mismatch\":\"恢复执行身份不符\",\"password_recovery_operation_identity_mismatch\":\"恢复操作身份不符\",\"password_recovery_operation_inactive\":\"恢复操作未执行\",\"password_recovery_operation_lease_invalid\":\"恢复租约无效\",\"password_recovery_owner_active\":\"恢复检查点被占用\",\"password_recovery_owner_invalid\":\"恢复归属无效\",\"password_recovery_owner_missing\":\"恢复执行归属缺失\",\"password_recovery_password_add_context_invalid\":\"添加密码回执不符\",\"password_recovery_password_conflict\":\"密码版本冲突\",\"password_recovery_password_login_confirmation_mismatch\":\"原密码版本不符\",\"password_recovery_password_login_confirmation_not_prepared\":\"候选密码待确认\",\"password_recovery_password_login_confirmation_unverified\":\"密码验证证据不足\",\"password_recovery_recovery_intent_conflict\":\"密码恢复操作冲突\",\"password_recovery_recovery_intent_invalid\":\"恢复操作类型无效\",\"password_recovery_recovery_not_found\":\"恢复检查点不存在\",\"password_recovery_recovery_owner_mismatch\":\"检查点执行归属不符\",\"password_recovery_registration_attempt_conflict\":\"注册检查点冲突\",\"password_recovery_registration_execution_mismatch\":\"注册执行身份不符\",\"password_recovery_registration_identity_mismatch\":\"原注册身份不符\",\"password_recovery_registration_operation_mapping_mismatch\":\"注册任务映射不符\",\"password_recovery_reset_result_unknown\":\"密码重置结果未确认\",\"password_recovery_session_context_invalid\":\"恢复会话身份不符\",\"password_recovery_state_invalid\":\"恢复目标状态无效\",\"password_recovery_state_transition_invalid\":\"恢复状态不可推进\",\"password_recovery_unconfirmed\":\"候选密码未确认\",\"password_recovery_version_conflict\":\"恢复检查点版本冲突\",\"password_rejected\":\"账号密码被拒\",\"password_rejected_email_fallback_failed\":\"密码与邮箱登录失败\",\"password_result_unknown\":\"密码提交未确认\",\"password_sentinel_failed\":\"密码认证预检失败\",\"password_setup_access_token_missing\":\"补密码凭据缺失\",\"password_setup_already_set\":\"账号已有密码\",\"password_setup_auth_failed\":\"补密码认证未完成\",\"password_setup_csrf_missing\":\"补密码认证状态缺失\",\"password_setup_email_otp_failed\":\"补密码邮箱验证未完成\",\"password_setup_execution_fence_missing\":\"补密码执行租约缺失\",\"password_setup_http_rejected\":\"补密码请求被拒\",\"password_setup_input_invalid\":\"补密码输入无效\",\"password_setup_mfa_factor_missing\":\"补密码验证挑战缺失\",\"password_setup_mfa_rejected\":\"补密码双重验证被拒\",\"password_setup_mfa_secret_invalid\":\"补密码验证密钥无效\",\"password_setup_mfa_secret_missing\":\"补密码需双重验证\",\"password_setup_network_failed\":\"补密码网络失败\",\"password_setup_oauth_callback_failed\":\"补密码回调未完成\",\"password_setup_otp_context_changed\":\"补密码验证码会话变化\",\"password_setup_otp_context_invalid\":\"补密码验证码会话不符\",\"password_setup_otp_invalid\":\"补密码验证码无效\",\"password_setup_otp_rejected\":\"补密码验证码被拒\",\"password_setup_otp_send_unconfirmed\":\"补密码发码回执缺失\",\"password_setup_otp_unavailable\":\"补密码验证码未取得\",\"password_setup_page_not_ready\":\"密码设置页未就绪\",\"password_setup_page_unexpected\":\"补密码页面不符\",\"password_setup_password_rejected\":\"补密码原密码被拒\",\"password_setup_password_reset_required\":\"需要重置密码\",\"password_setup_previous_result_unknown\":\"上次密码回执缺失\",\"password_setup_protocol_network_error\":\"补密码登录网络失败\",\"password_setup_rate_limited\":\"补密码请求受限流\",\"password_setup_redirect_invalid\":\"补密码跳转无效\",\"password_setup_redirect_limit\":\"补密码跳转超限\",\"password_setup_request_unknown\":\"补密码结果未确认\",\"password_setup_response_invalid\":\"补密码响应无效\",\"password_setup_result_unconfirmed\":\"密码设置未确认\",\"password_setup_runtime_failed\":\"补密码执行异常\",\"password_setup_security_check\":\"补密码安全校验失败\",\"password_setup_sentinel_failed\":\"补密码预检失败\",\"password_setup_session_cooling_down\":\"补密码会话冷却中\",\"password_setup_session_expired\":\"补密码会话已失效\",\"password_setup_session_missing\":\"补密码会话缺失\",\"password_setup_unconfirmed\":\"补密码回执缺失\",\"password_setup_unsupported\":\"添加密码未完成\",\"password_setup_untrusted_redirect\":\"补密码跳转不可信\",\"password_verify_failed\":\"密码验证未完成\",\"password_verify_invalid_response\":\"密码验证响应无效\",\"passwordless_fallback_unavailable\":\"邮箱免密兜底不可用\",\"payment_provider_response_missing\":\"支付请求无响应\",\"permission_denied\":\"邮箱操作权限不足\",\"permit_owner_lost\":\"执行许可归属已变化\",\"plan_config_invalid\":\"套餐查询配置异常\",\"plan_country_mixed_failures\":\"多类套餐查询失败\",\"plan_country_queries_failed\":\"逐国套餐证据不足\",\"plan_http_error\":\"套餐接口异常\",\"plan_http_forbidden\":\"套餐请求被拒\",\"plan_http_rate_limited\":\"套餐请求受限流\",\"plan_http_server_error\":\"套餐服务端异常\",\"plan_result_confirmation_missing\":\"套餐结果确认缺失\",\"post_register_failure\":\"注册后流程失败\",\"profile_auth_error\":\"资料认证页面错误\",\"profile_completion_required\":\"账号资料待补全\",\"profile_session_read_failed\":\"资料后会话读取失败\",\"profile_session_unconfirmed\":\"资料后会话未确认\",\"protocol_auth_http_failed\":\"协议认证接口异常\",\"protocol_auth_rejected_before_password\":\"认证请求被拒\",\"protocol_auth_transport_failed\":\"协议认证传输失败\",\"protocol_failure_evidence_missing\":\"协议失败证据不足\",\"protocol_network_error\":\"协议认证网络失败\",\"protocol_post_otp_transport_failed\":\"验证码后认证网络失败\",\"protocol_preauth_transport_failed\":\"协议前置网络失败\",\"protocol_session_incomplete\":\"注册后登录态未取得\",\"protocol_unmapped_request_transport_failed\":\"未映射请求传输失败\",\"protocol_v2_unknown_error\":\"协议认证证据不足\",\"protocol_v3_unknown_error\":\"协议认证证据不足\",\"protocol_rust_unknown_error\":\"Rust 认证未确认\",\"provider_capacity\":\"等待平台空位\",\"provider_not_supported\":\"邮箱来源不支持\",\"provider_unavailable\":\"邮箱来源不可用\",\"proxy_connect_failed\":\"代理连接失败\",\"proxy_country_mismatch\":\"代理出口国家不符\",\"proxy_supply_exhausted\":\"查询国代理库存不足\",\"proxy_tunnel_failed\":\"代理隧道连接失败\",\"rate_limited\":\"邮箱请求受限流\",\"recipient_ambiguous\":\"验证码收件存在歧义\",\"recipient_contract_unsupported\":\"收件校验不支持\",\"recipient_evidence_missing\":\"验证码收件证据不足\",\"recipient_mismatch\":\"验证码收件地址不符\",\"refresh_cancelled\":\"凭据刷新已取消\",\"refresh_confirmation_missing\":\"凭据刷新确认缺失\",\"refresh_driver_exception\":\"凭据刷新执行异常\",\"refresh_local_commit_failed\":\"凭据刷新写回未完成\",\"refresh_result_invalid\":\"凭据刷新结果无效\",\"registration_auth_state_unrecognized\":\"注册页面未识别\",\"registration_checkpoint_failed\":\"注册检查点写入失败\",\"registration_completion_dispatch_failed\":\"补密码入队失败\",\"registration_completion_incomplete\":\"自动补密码未完成\",\"registration_identity_verification_required\":\"仍需身份验证\",\"registration_password_create_rejected\":\"注册密码创建被拒\",\"registration_password_entry_unavailable\":\"注册密码入口缺失\",\"registration_password_unconfirmed\":\"注册密码回执缺失\",\"registration_profile_submission_unresolved\":\"资料提交待确认\",\"registration_route_close_failed\":\"旧连接关闭失败\",\"registration_session_invalid_response\":\"注册会话无效\",\"remote_order_capacity\":\"等待远端订单名额\",\"remote_response_missing\":\"远端响应缺失\",\"request_unknown\":\"请求结果未确认\",\"resource_capacity\":\"等待资源空位\",\"response_invalid\":\"套餐响应格式无效\",\"response_missing\":\"套餐响应缺失\",\"roxy_authenticated_callback_failed\":\"登录后账号处理失败\",\"roxy_driver_attach_failed\":\"浏览器调试连接失败\",\"roxy_login_failed\":\"浏览器登录未完成\",\"roxy_login_page_not_ready\":\"浏览器登录页未就绪\",\"roxy_login_page_timeout\":\"浏览器登录页超时\",\"roxy_login_preflight_failed\":\"浏览器登录预检失败\",\"roxy_login_preflight_timeout\":\"浏览器登录预检超时\",\"roxy_navigation_failed\":\"浏览器登录页加载失败\",\"roxy_not_configured\":\"浏览器连接配置缺失\",\"roxy_password_prepare_timeout\":\"密码表单准备超时\",\"roxy_profile_open_failed\":\"浏览器环境启动失败\",\"roxy_proxy_tunnel_failed\":\"浏览器代理隧道失败\",\"roxy_session_fetch_failed\":\"浏览器会话读取失败\",\"scheduler_store_unavailable\":\"调度存储不可用\",\"selection_expired\":\"批量名单已过期\",\"service_not_allowed\":\"邮箱服务未授权\",\"service_not_authorized\":\"邮箱服务未授权\",\"service_not_found\":\"目标邮箱服务未配置\",\"service_unavailable\":\"邮箱暂停新租用\",\"sentinel_rs_binary_unavailable\":\"内核不可用\",\"sentinel_rs_otp_timeout\":\"内核验证码超时\",\"sentinel_rs_remote_account_exists\":\"远端已有账号\",\"sentinel_rs_twofa_failed\":\"内核 2FA 失败\",\"sentinel_rs_registration_failed\":\"内核注册失败\",\"sentinel_rs_result_invalid\":\"内核结果无效\",\"session_fetch_failed\":\"登录会话读取失败\",\"session_identity_mismatch\":\"认证会话身份不符\",\"session_invalid_response\":\"登录会话响应无效\",\"setup_confirmation_missing\":\"账号配置回执缺失\",\"signal_scan_unsupported\":\"封号扫描不支持\",\"source_authentication_failed\":\"验证码来源认证失败\",\"source_untrusted\":\"验证码来源未确认\",\"sub2api_account_ambiguous\":\"远端账号不唯一\",\"sub2api_account_deactivated\":\"关联账号已停用\",\"sub2api_account_id_invalid\":\"远端账号编号无效\",\"sub2api_account_identity_mismatch\":\"远端账号身份不符\",\"sub2api_account_missing\":\"远端账号未找到\",\"sub2api_auth_rejected\":\"凭据同步鉴权失败\",\"sub2api_backend_changed\":\"凭据同步目标已变化\",\"sub2api_client_error\":\"凭据同步客户端异常\",\"sub2api_config_invalid\":\"凭据同步配置无效\",\"sub2api_connection_failed\":\"凭据同步连接失败\",\"sub2api_credential_generation_changed\":\"本地凭据版本已变化\",\"sub2api_credential_identity_mismatch\":\"本地凭据身份不符\",\"sub2api_credential_identity_missing\":\"凭据身份缺失\",\"sub2api_credential_invalid\":\"本地凭据无效\",\"sub2api_credential_missing\":\"本地凭据不存在\",\"sub2api_credential_reauthorization_required\":\"凭据需重新授权\",\"sub2api_http_error\":\"凭据同步接口异常\",\"sub2api_import_result_invalid\":\"凭据导入回执无效\",\"sub2api_local_confirmation_conflict\":\"同步回执写回冲突\",\"sub2api_manual_execution_failed\":\"凭据上传执行异常\",\"sub2api_manual_local_writeback_failed\":\"上传本地写回未完成\",\"sub2api_oauth_incomplete\":\"账号授权未完成\",\"sub2api_operation_rejected\":\"凭据同步操作被拒\",\"sub2api_pagination_limit\":\"凭据同步分页超限\",\"sub2api_request_failed\":\"凭据同步网络失败\",\"sub2api_response_invalid\":\"凭据同步响应无效\",\"sub2api_sync_execution_error\":\"凭据补传执行异常\",\"sub2api_sync_failed\":\"凭据同步未完成\",\"sub2api_sync_unconfirmed\":\"凭据同步回执缺失\",\"sub2api_target_archived\":\"关联账号已归档\",\"sub2api_timeout\":\"凭据同步请求超时\",\"sub2api_upload_rejected\":\"凭据导入被拒\",\"timeout\":\"套餐查询超时\",\"token_expired_or_rejected\":\"凭据失效原因未确认\",\"token_http_401\":\"套餐凭据未通过验证\",\"token_local_expired\":\"本地凭据已过期\",\"token_missing\":\"套餐凭据缺失\",\"totp_rejected\":\"动态验证码被拒\",\"ttl_out_of_range\":\"邮箱租约时长越界\",\"twofa_setup_failed\":\"双重验证设置未完成\",\"type_capacity\":\"等待本类空位\",\"untrusted_auth_url\":\"认证地址不可信\",\"user_register_continue_url_missing\":\"后续验证地址缺失\",\"user_register_result_unknown\":\"账号创建结果未确认\",\"worker_interrupted\":\"执行进程中断\",\"workspace_ambiguous\":\"目标工作区不明确\",\"workspace_missing\":\"可用工作区缺失\",\"workspace_select_failed\":\"工作区选择未完成\",\"workspace_select_invalid_response\":\"工作区选择响应无效\"}"),
	displayCodeLabels: /* @__PURE__ */ JSON.parse("{\"ACCT-001\":\"账号已停用\",\"ACCT-002\":\"目标不可用\",\"ACCT-003\":\"邮箱已被使用\",\"ACCT-004\":\"邮箱未变化\",\"AUTH-001\":\"授权已失效\",\"AUTH-002\":\"需要重新登录\",\"AUTH-ACCOUNT-UNKNOWN-001\":\"账号请求待确认\",\"AUTH-AT-001\":\"账号凭据缺失\",\"AUTH-CALLBACK-001\":\"授权回调未完成\",\"AUTH-CALLBACK-002\":\"授权回调被拒\",\"AUTH-CHALLENGE-001\":\"认证挑战重复\",\"AUTH-IDENTITY-001\":\"认证账号身份不符\",\"AUTH-IDENTITY-002\":\"认证账号身份未确认\",\"AUTH-IDENTITY-003\":\"本地账号邮箱不符\",\"AUTH-IDENTITY-004\":\"认证会话身份不符\",\"AUTH-MFA-001\":\"双重验证码缺失\",\"AUTH-MFA-002\":\"双重验证方式缺失\",\"AUTH-MFA-003\":\"双重验证发起失败\",\"AUTH-MFA-004\":\"双重验证挑战无效\",\"AUTH-MFA-005\":\"双重验证被拒\",\"AUTH-MFA-006\":\"双重验证密钥无效\",\"AUTH-MFA-007\":\"双重验证密钥缺失\",\"AUTH-MFA-008\":\"双重验证未完成\",\"AUTH-MFA-009\":\"双重验证响应无效\",\"AUTH-MFA-CONFIRM\":\"双重验证激活未确认\",\"AUTH-MFA-PAGE\":\"双重验证页面错误\",\"AUTH-MFA-SETUP-001\":\"双重验证设置未完成\",\"AUTH-MFA-TOTP-REJECTED\":\"动态验证码被拒\",\"AUTH-OTP-VALIDATE-001\":\"邮箱验证码提交未完成\",\"AUTH-OTP-VALIDATE-002\":\"邮箱验证码响应无效\",\"AUTH-PAGE-001\":\"认证页面未识别\",\"AUTH-PAGE-AMBIGUOUS\":\"认证上下文冲突\",\"AUTH-PAGE-CONTEXT\":\"登录上下文缺失\",\"AUTH-PAGE-TIMEOUT\":\"认证页面操作超时\",\"AUTH-PROFILE-001\":\"账号资料待补全\",\"AUTH-PROTOCOL-001\":\"协议认证证据不足\",\"AUTH-PROTOCOL-003\":\"协议认证证据不足\",\"AUTH-PROTOCOL-004\":\"Rust 认证未确认\",\"AUTH-PWD-001\":\"本地密码缺失\",\"AUTH-PWD-002\":\"账号密码被拒\",\"AUTH-PWD-003\":\"密码与邮箱登录失败\",\"AUTH-PWD-004\":\"密码提交未确认\",\"AUTH-PWD-005\":\"密码认证预检失败\",\"AUTH-PWD-006\":\"密码验证未完成\",\"AUTH-PWD-007\":\"密码验证响应无效\",\"AUTH-PWD-008\":\"邮箱免密兜底不可用\",\"AUTH-PWD-009\":\"密码登录不可用\",\"AUTH-PWD-010\":\"仍需邮箱验证\",\"AUTH-PWD-PAGE\":\"密码登录页错误\",\"AUTH-PWD-PREPARE\":\"密码表单准备超时\",\"AUTH-PWD-REC-001\":\"候选密码未确认\",\"AUTH-PWD-REC-002\":\"候选认证未确认\",\"AUTH-PWD-REC-003\":\"密码重置结果未确认\",\"AUTH-PWD-RESET\":\"需要修改密码\",\"AUTH-PWD-RESET-001\":\"需先刷新登录态\",\"AUTH-PWD-RESET-002\":\"重置发码失败\",\"AUTH-PWD-RESET-003\":\"重置验证码被拒\",\"AUTH-PWD-RESET-004\":\"重置验证码超时\",\"AUTH-PWD-RESET-005\":\"重置请求被拒\",\"AUTH-PWD-RESET-006\":\"重置被限流\",\"AUTH-PWD-RESET-007\":\"重置未确认\",\"AUTH-PWD-RESET-008\":\"新密码未保存\",\"AUTH-PWD-RESET-009\":\"重置结果未知\",\"AUTH-PWD-SETUP-001\":\"密码设置未确认\",\"AUTH-PWD-SETUP-002\":\"账号已有密码\",\"AUTH-PWD-SETUP-003\":\"补密码回执缺失\",\"AUTH-PWD-SETUP-004\":\"补密码会话缺失\",\"AUTH-PWD-SETUP-005\":\"补密码认证未完成\",\"AUTH-PWD-SETUP-006\":\"补密码会话已失效\",\"AUTH-PWD-SETUP-007\":\"补密码会话冷却中\",\"AUTH-PWD-SETUP-008\":\"补密码需双重验证\",\"AUTH-PWD-SETUP-009\":\"补密码结果未确认\",\"AUTH-PWD-SETUP-010\":\"补密码响应无效\",\"AUTH-PWD-SETUP-011\":\"上次密码回执缺失\",\"AUTH-PWD-SETUP-012\":\"补密码原密码被拒\",\"AUTH-PWD-SETUP-013\":\"补密码凭据缺失\",\"AUTH-PWD-SETUP-014\":\"添加密码未完成\",\"AUTH-PWD-SETUP-CALLBACK\":\"补密码回调未完成\",\"AUTH-PWD-SETUP-MFA-001\":\"补密码双重验证被拒\",\"AUTH-PWD-SETUP-MFA-002\":\"补密码验证挑战缺失\",\"AUTH-PWD-SETUP-OTP-001\":\"补密码验证码会话不符\",\"AUTH-PWD-SETUP-OTP-002\":\"补密码验证码会话变化\",\"AUTH-PWD-SETUP-RESET\":\"需要重置密码\",\"AUTH-REG-IDENTITY-001\":\"仍需身份验证\",\"AUTH-REG-PWD-001\":\"注册密码回执缺失\",\"AUTH-REG-SESSION-001\":\"注册会话无效\",\"AUTH-SESSION-001\":\"会话复用响应无效\",\"AUTH-SESSION-002\":\"登录会话响应无效\",\"AUTH-SESSION-003\":\"返回凭据已过期\",\"AUTH-URL-001\":\"认证地址不可信\",\"AUTH-URL-002\":\"认证跳转目标无效\",\"AUTH-URL-003\":\"认证跳转超限\",\"AUTH-WORKSPACE-001\":\"目标工作区不明确\",\"AUTH-WORKSPACE-002\":\"可用工作区缺失\",\"AUTH-WORKSPACE-003\":\"工作区选择未完成\",\"AUTH-WORKSPACE-004\":\"工作区选择响应无效\",\"C2A-AUTH-001\":\"凭据导入鉴权失败\",\"C2A-CONFIG-001\":\"凭据导入配置无效\",\"C2A-CONFIG-002\":\"凭据导入目标已变化\",\"C2A-CONFIRM-001\":\"凭据更新回执缺失\",\"C2A-CONFIRM-002\":\"账号新建待确认\",\"C2A-CONFIRM-003\":\"上传回执未确认\",\"C2A-CONTRACT-001\":\"凭据导入响应无效\",\"C2A-CONTRACT-002\":\"凭据导入分页超限\",\"C2A-CONTRACT-003\":\"远端同邮箱账号缺失\",\"C2A-CONTRACT-004\":\"远端同邮箱账号不唯一\",\"C2A-CONTRACT-005\":\"远端账号编号无效\",\"C2A-CONTRACT-006\":\"巡检响应无效\",\"C2A-CONTRACT-007\":\"远端诊断缺失\",\"C2A-CONTRACT-008\":\"刷新结果缺失\",\"C2A-CONTRACT-009\":\"回传结果缺失\",\"C2A-CRED-001\":\"本地同步凭据缺失\",\"C2A-CRED-002\":\"本地导入凭据缺失\",\"C2A-CRED-003\":\"本地凭据已过期\",\"C2A-CRED-004\":\"本地凭据未核验\",\"C2A-CRED-005\":\"远端凭据仍失效\",\"C2A-CRED-006\":\"新凭据未确认保存\",\"C2A-CRED-007\":\"远端凭据读取缺失\",\"C2A-HTTP-001\":\"凭据导入接口异常\",\"C2A-ID-001\":\"本地凭据身份不符\",\"C2A-ID-002\":\"本地账号邮箱已变化\",\"C2A-ID-003\":\"远端邮箱已变化\",\"C2A-ID-004\":\"远端凭据归属冲突\",\"C2A-ID-005\":\"本地账号匹配不唯一\",\"C2A-LOCAL-001\":\"账号邮箱身份无效\",\"C2A-LOCAL-002\":\"本地账号不存在\",\"C2A-LOCAL-003\":\"本地邮箱身份无效\",\"C2A-LOCAL-004\":\"远端已更新写回失败\",\"C2A-LOCAL-005\":\"凭据导入执行异常\",\"C2A-LOCAL-006\":\"凭据导入客户端异常\",\"C2A-LOCAL-007\":\"凭据导入入队失败\",\"C2A-LOCAL-008\":\"本地账号编号无效\",\"C2A-LOCAL-009\":\"凭据导入任务已存在\",\"C2A-LOCAL-010\":\"凭据导入尚未入队\",\"C2A-LOCAL-011\":\"修复请求标识缺失\",\"C2A-LOCAL-012\":\"巡检任务入队失败\",\"C2A-LOCAL-013\":\"巡检存储不可用\",\"C2A-LOCAL-014\":\"巡检状态读取失败\",\"C2A-LOCAL-015\":\"刷新名单准备失败\",\"C2A-LOCAL-016\":\"批量刷新受理失败\",\"C2A-LOCAL-017\":\"回传任务入队失败\",\"C2A-NET-001\":\"凭据导入请求超时\",\"C2A-NET-002\":\"凭据导入连接失败\",\"C2A-NET-003\":\"凭据导入网络失败\",\"C2A-NET-004\":\"凭据导入请求受限流\",\"C2A-NET-005\":\"凭据导入服务不可用\",\"C2A-NET-006\":\"远端账号暂不可用\",\"C2A-POLICY-001\":\"关联账号已停用\",\"C2A-POLICY-002\":\"远端账号已禁用\",\"C2A-POLICY-003\":\"本地账号已归档\",\"C2A-POLICY-004\":\"远端账号已停用\",\"C2A-POLICY-005\":\"修复已取消\",\"C2A-POLICY-008\":\"刷新失败已达上限\",\"C2A-POLICY-006\":\"巡检进行中\",\"C2A-POLICY-007\":\"远端核验进行中\",\"C2A-REMOTE-001\":\"凭据更新被拒\",\"C2A-REMOTE-002\":\"远端账号不存在\",\"C2A-REMOTE-003\":\"远端账号新建被拒\",\"C2A-REMOTE-004\":\"远端账号限流中\",\"C2A-REMOTE-005\":\"远端账号额度不足\",\"C2A-SAFE-001\":\"远端清理策略未确认\",\"C2A-SAFE-002\":\"远端自动清理已开启\",\"CFG-001\":\"配置缺失\",\"CFG-CODEX-PHONE-001\":\"手机接码已关闭\",\"CFG-CONC-001\":\"并发策略无效\",\"CFG-CONC-002\":\"并发策略缺失\",\"CFG-PWD-REC-001\":\"恢复密钥缺失\",\"CFG-PWD-REC-002\":\"恢复密钥无效\",\"CFG-PWD-SETUP-MFA-001\":\"补密码验证密钥无效\",\"DEPLOY-BROWSER-001\":\"浏览器未配置\",\"FLOW-EMAIL-001\":\"邮箱提交未确认\",\"FLOW-EMAIL-002\":\"邮箱认证跳转超时\",\"FLOW-EMAIL-003\":\"邮箱入口未就绪\",\"FLOW-MFA-CHANGED\":\"双重验证步骤已变化\",\"FLOW-MFA-STEP\":\"双重验证步骤不支持\",\"FLOW-PAGE-001\":\"页面未推进\",\"FLOW-PROFILE-001\":\"资料后会话读取失败\",\"FLOW-PROFILE-002\":\"资料后会话未确认\",\"FLOW-PROFILE-003\":\"资料认证页面错误\",\"FLOW-PWD-001\":\"密码页未加载\",\"FLOW-PWD-002\":\"密码入口缺失\",\"FLOW-PWD-003\":\"密码页恢复失败\",\"FLOW-PWD-004\":\"密码设置入口缺失\",\"FLOW-PWD-005\":\"密码入口导航超时\",\"FLOW-PWD-006\":\"密码入口进入失败\",\"FLOW-PWD-007\":\"认证入口缺失\",\"FLOW-PWD-REC-001\":\"恢复归属无效\",\"FLOW-PWD-REC-002\":\"恢复操作未执行\",\"FLOW-PWD-REC-003\":\"恢复执行身份不符\",\"FLOW-PWD-REC-004\":\"恢复操作身份不符\",\"FLOW-PWD-REC-005\":\"原注册身份不符\",\"FLOW-PWD-REC-006\":\"注册执行身份不符\",\"FLOW-PWD-REC-007\":\"注册任务映射不符\",\"FLOW-PWD-REC-008\":\"手动操作归属不符\",\"FLOW-PWD-REC-009\":\"账号邮箱身份不符\",\"FLOW-PWD-REC-010\":\"本地账号已停用\",\"FLOW-PWD-REC-011\":\"恢复租约无效\",\"FLOW-PWD-REC-012\":\"恢复检查点被占用\",\"FLOW-PWD-REC-013\":\"注册检查点冲突\",\"FLOW-PWD-REC-014\":\"密码版本冲突\",\"FLOW-PWD-REC-015\":\"恢复检查点不存在\",\"FLOW-PWD-REC-016\":\"检查点执行归属不符\",\"FLOW-PWD-REC-017\":\"原注册密码冲突\",\"FLOW-PWD-REC-018\":\"恢复目标状态无效\",\"FLOW-PWD-REC-019\":\"恢复确认缺失\",\"FLOW-PWD-REC-020\":\"恢复检查点版本冲突\",\"FLOW-PWD-REC-021\":\"恢复状态不可推进\",\"FLOW-PWD-REC-022\":\"恢复检查点缺失\",\"FLOW-PWD-REC-023\":\"恢复执行归属缺失\",\"FLOW-PWD-REC-024\":\"原邮箱身份未确认\",\"FLOW-PWD-REC-025\":\"候选认证上下文不符\",\"FLOW-PWD-REC-026\":\"候选认证回执不足\",\"FLOW-PWD-REC-027\":\"候选认证事实不符\",\"FLOW-PWD-REC-028\":\"密码恢复操作冲突\",\"FLOW-PWD-REC-029\":\"添加密码回执不符\",\"FLOW-PWD-REC-030\":\"候选密码待确认\",\"FLOW-PWD-REC-031\":\"原密码版本不符\",\"FLOW-PWD-REC-032\":\"密码验证证据不足\",\"FLOW-PWD-REC-033\":\"恢复会话身份不符\",\"FLOW-PWD-SETUP-001\":\"补密码执行租约缺失\",\"FLOW-PWD-SETUP-002\":\"补密码输入无效\",\"FLOW-PWD-SETUP-003\":\"补密码认证状态缺失\",\"FLOW-PWD-SETUP-004\":\"补密码页面不符\",\"FLOW-PWD-SETUP-005\":\"补密码跳转无效\",\"FLOW-PWD-SETUP-006\":\"补密码跳转超限\",\"FLOW-PWD-SETUP-007\":\"补密码跳转不可信\",\"FLOW-PWD-SETUP-008\":\"密码设置页未就绪\",\"FLOW-REG-AUTH-001\":\"注册页面未识别\",\"FLOW-REG-COMPLETE-001\":\"补密码入队失败\",\"FLOW-REG-COMPLETE-002\":\"自动补密码未完成\",\"FLOW-REG-EVIDENCE\":\"协议失败证据不足\",\"FLOW-REG-PROFILE-001\":\"资料提交待确认\",\"FLOW-REG-PWD-001\":\"注册密码入口缺失\",\"FLOW-REG-ROUTE-CLOSE\":\"旧连接关闭失败\",\"FLOW-REG-SESSION\":\"注册后登录态未取得\",\"FLOW-RETRY-001\":\"原邮箱无法重试\",\"FLOW-SETUP-001\":\"账号配置尚未执行\",\"FLOW-SETUP-002\":\"账号配置尚未完成\",\"FLOW-STAGE-001\":\"浏览器阶段超时\",\"FLOW-UNSUPPORTED-001\":\"功能不支持\",\"FLOW-VERIFY-001\":\"验证流程失败\",\"LINK-APPROVAL-QUERY\":\"支付结果查询失败\",\"LINK-CDK-INVALID\":\"提链兑换码无效\",\"LINK-CHECKOUT-ACTIVITY\":\"结账异常活动\",\"LINK-CHECKOUT-BLOCKED\":\"结账审批受阻\",\"LINK-CHECKOUT-RISK\":\"结账被风控拦截\",\"LINK-CHECKOUT-TOKEN\":\"结账凭据已撤销\",\"LINK-COUNTRY-400\":\"账单国家不符\",\"LINK-FAILED\":\"平台提链失败\",\"LINK-HTTP-000\":\"提链请求被拒\",\"LINK-ORDER-404\":\"提链原单未找到\",\"LINK-ORDER-PROGRESS\":\"提链原单无进展\",\"LINK-ORDER-QUERY\":\"提链原单查询失败\",\"LINK-ORDER-TIMEOUT\":\"提链续查超时\",\"LINK-PAYMENT-APPROVAL\":\"支付审批受阻\",\"LINK-PAYMENT-BLOCKED\":\"支付确认受阻\",\"LINK-PAYMENT-METHOD\":\"支付方式设置失败\",\"LINK-PAYMENT-SUBMIT\":\"支付提交失败\",\"LINK-PROMO-AMOUNT\":\"应付金额非零\",\"LINK-PROMO-MISSING\":\"优惠未生效\",\"LINK-REQUEST-ERROR\":\"提链请求异常\",\"LINK-RESPONSE-ERROR\":\"提链响应无效\",\"LINK-RESPONSE-MISSING\":\"提链请求无响应\",\"LINK-SENTINEL\":\"安全校验异常\",\"LINK-TASK-FAILED\":\"平台任务失败\",\"LINK-TOKEN-REVOKED\":\"提链凭据已失效\",\"LINK-UPI-REJECTED\":\"支付确认被拒\",\"MAIL-001\":\"邮箱服务异常\",\"MAIL-002\":\"邮箱服务不可用\",\"MAIL-003\":\"邮箱账号不存在\",\"MAIL-004\":\"邮箱准备失败\",\"MAIL-BUTLER-AUTH-001\":\"邮箱密钥校验失败\",\"MAIL-BUTLER-AUTH-002\":\"邮箱服务未授权\",\"MAIL-BUTLER-REQUEST-001\":\"入站取码请求失败\",\"MAIL-BUTLER-STORAGE-001\":\"入站邮件存储异常\",\"MAIL-BUTLER-V2-001\":\"邮箱客户端回执无效\",\"MAIL-BUTLER-V2-002\":\"邮箱请求参数无效\",\"MAIL-BUTLER-V2-003\":\"邮箱租约编号无效\",\"MAIL-BUTLER-V2-004\":\"取码等待参数无效\",\"MAIL-BUTLER-V2-005\":\"验证码时间边界无效\",\"MAIL-BUTLER-V2-006\":\"退租回执无效\",\"MAIL-BUTLER-V2-007\":\"库存回执无效\",\"MAIL-BUTLER-V2-008\":\"幂等键无效\",\"MAIL-BUTLER-V2-009\":\"幂等键缺失\",\"MAIL-BUTLER-V2-010\":\"邮箱来源不支持\",\"MAIL-BUTLER-V2-011\":\"目标邮箱服务未配置\",\"MAIL-BUTLER-V2-012\":\"邮箱租约时长越界\",\"MAIL-BUTLER-V2-013\":\"邮箱分配繁忙\",\"MAIL-BUTLER-V2-014\":\"验证码游标无效\",\"MAIL-BUTLER-V2-015\":\"验证码时间边界被拒\",\"MAIL-BUTLER-V2-AMBIGUOUS\":\"验证码投递存在歧义\",\"MAIL-BUTLER-V2-API\":\"邮箱接口已退役\",\"MAIL-BUTLER-V2-AUTH\":\"邮箱密钥无效\",\"MAIL-BUTLER-V2-CLIENT\":\"租约客户端不符\",\"MAIL-BUTLER-V2-CODE\":\"验证码回执无效\",\"MAIL-BUTLER-V2-CONFIG\":\"邮箱连接配置无效\",\"MAIL-BUTLER-V2-CONNECT\":\"邮箱服务连接失败\",\"MAIL-BUTLER-V2-EMPTY\":\"邮箱库存不足\",\"MAIL-BUTLER-V2-EXPIRED\":\"邮箱租约已到期\",\"MAIL-BUTLER-V2-EXPIRY\":\"租约到期时间无效\",\"MAIL-BUTLER-V2-FORMAT\":\"验证码格式无效\",\"MAIL-BUTLER-V2-IDENTITY\":\"邮箱租约身份不符\",\"MAIL-BUTLER-V2-INTENT\":\"幂等请求冲突\",\"MAIL-BUTLER-V2-INTENT-EXPIRED\":\"原幂等结果已过期\",\"MAIL-BUTLER-V2-JSON\":\"邮箱响应解析失败\",\"MAIL-BUTLER-V2-KEY\":\"邮箱连接凭据缺失\",\"MAIL-BUTLER-V2-LIMIT\":\"邮箱租约已达上限\",\"MAIL-BUTLER-V2-MAPPING\":\"邮箱租约归属不明\",\"MAIL-BUTLER-V2-NETWORK\":\"邮箱网络传输失败\",\"MAIL-BUTLER-V2-NOTFOUND\":\"原租约无法读取\",\"MAIL-BUTLER-V2-ORIGINAL\":\"原租约映射缺失\",\"MAIL-BUTLER-V2-PAGE\":\"邮箱分页回执无效\",\"MAIL-BUTLER-V2-PERMISSION\":\"邮箱操作权限不足\",\"MAIL-BUTLER-V2-PROVIDER\":\"邮箱来源不可用\",\"MAIL-BUTLER-V2-RATE\":\"邮箱请求受限流\",\"MAIL-BUTLER-V2-RECEIPT\":\"邮箱租约回执无效\",\"MAIL-BUTLER-V2-RECEIPT-ID\":\"返回租约身份不符\",\"MAIL-BUTLER-V2-REDIRECT\":\"邮箱接口发生跳转\",\"MAIL-BUTLER-V2-RELEASED\":\"邮箱租约已退租\",\"MAIL-BUTLER-V2-RESPONSE\":\"邮箱响应格式无效\",\"MAIL-BUTLER-V2-RESTORE\":\"原邮箱租约待恢复\",\"MAIL-BUTLER-V2-REVOKED\":\"邮箱租约已回收\",\"MAIL-BUTLER-V2-SCAN\":\"封号扫描不支持\",\"MAIL-BUTLER-V2-SERVICE\":\"邮箱服务未授权\",\"MAIL-BUTLER-V2-TIME\":\"验证码早于挑战\",\"MAIL-BUTLER-V2-TIMEOUT\":\"邮箱服务请求超时\",\"MAIL-BUTLER-V2-UNAVAILABLE\":\"邮箱暂停新租用\",\"MAIL-LOCAL-STOCK-001\":\"本地邮箱库存为空\",\"MAIL-OTP-001\":\"邮箱验证未完成\",\"MAIL-OTP-002\":\"验证码等待超时\",\"MAIL-OTP-004\":\"邮箱验证码无效\",\"MAIL-OTP-005\":\"验证码等待超时\",\"MAIL-OTP-EVIDENCE\":\"邮箱验证证据不足\",\"MAIL-OTP-READ\":\"验证码邮箱读取失败\",\"MAIL-PWD-SETUP-001\":\"补密码验证码无效\",\"MAIL-PWD-SETUP-002\":\"补密码验证码被拒\",\"MAIL-PWD-SETUP-003\":\"补密码验证码未取得\",\"MAIL-PWD-SETUP-004\":\"补密码发码回执缺失\",\"MAIL-PWD-SETUP-005\":\"补密码邮箱验证未完成\",\"MAIL-RECIPIENT-001\":\"收件校验不支持\",\"MAIL-RECIPIENT-002\":\"验证码收件证据不足\",\"MAIL-RECIPIENT-003\":\"验证码收件存在歧义\",\"MAIL-RECIPIENT-004\":\"验证码收件地址不符\",\"MAIL-RECIPIENT-005\":\"验证码收件箱不符\",\"MAIL-RECIPIENT-006\":\"验证码等待超时\",\"MAIL-REPORT-001\":\"邮箱上报结果冲突\",\"MAIL-REPORT-002\":\"原邮箱身份不存在\",\"MAIL-RESOURCE-001\":\"邮箱资源已过期\",\"MAIL-RESOURCE-002\":\"邮箱有效期无效\",\"MAIL-RESOURCE-003\":\"邮箱取码不可用\",\"MAIL-ROUTE-001\":\"邮箱迁移目标无效\",\"MAIL-ROUTE-002\":\"收件路由已变化\",\"MAIL-SCAN-001\":\"收件连接器不支持\",\"MAIL-SEND-001\":\"验证码发送失败\",\"MAIL-SEND-002\":\"验证码发送被拒\",\"MAIL-SEND-003\":\"发码回执缺失\",\"MAIL-SEND-004\":\"发码请求无响应\",\"MAIL-SEND-005\":\"发码响应记录缺失\",\"MAIL-SOURCE-001\":\"验证码来源未确认\",\"MAIL-SOURCE-002\":\"验证码来源认证失败\",\"MAIL-STOCK-001\":\"子地址库存不足\",\"MAIL-STOCK-002\":\"子地址身份不符\",\"MAIL-STOCK-003\":\"子地址来源不支持\",\"MAIL-STOCK-004\":\"子地址收件配置无效\",\"MAIL-STOCK-005\":\"子地址额度不足\",\"MAIL-STOCK-006\":\"子地址请求冲突\",\"MAIL-STOCK-007\":\"子地址来源未启用\",\"MAIL-STOCK-008\":\"母邮箱不可用\",\"MAIL-STOCK-009\":\"母邮箱地址无效\",\"MAIL-STOCK-010\":\"子地址重复\",\"NET-001\":\"网络服务异常\",\"NET-002\":\"双重验证网络异常\",\"NET-003\":\"注册认证超时\",\"NET-ACCOUNT-ROUTE-001\":\"账号换线次数耗尽\",\"NET-ACCOUNT-ROUTE-002\":\"账号线路不可用\",\"NET-AT-BUDGET-001\":\"刷新网络恢复超时\",\"NET-AUTH-001\":\"协议认证网络失败\",\"NET-AUTH-002\":\"认证页面请求未完成\",\"NET-AUTH-NAVIGATION\":\"认证页面导航失败\",\"NET-EXTRACT-001\":\"提链网络中断\",\"NET-HTTP2-001\":\"浏览器连接保活失败\",\"NET-LINK-CERT\":\"提链证书校验失败\",\"NET-LINK-CLIENT-CONNECT\":\"提链平台连接失败\",\"NET-LINK-CONNECT\":\"提链连接失败\",\"NET-LINK-DNS\":\"提链域名解析失败\",\"NET-LINK-TIMEOUT\":\"提链请求超时\",\"NET-LINK-TLS\":\"提链加密连接失败\",\"NET-MFA-PAGE\":\"双重验证网络失败\",\"NET-OTP-CLOSED\":\"验证码连接被关闭\",\"NET-OTP-DNS\":\"验证码域名解析失败\",\"NET-OTP-FETCH\":\"验证码页面读取失败\",\"NET-OTP-HTTP2\":\"验证码连接保活失败\",\"NET-OTP-PROXY\":\"验证码代理连接失败\",\"NET-OTP-RESET\":\"验证码连接被重置\",\"NET-OTP-TUNNEL\":\"验证码代理隧道失败\",\"NET-PWD-SETUP-001\":\"补密码网络失败\",\"NET-PWD-SETUP-002\":\"补密码预检失败\",\"NET-PWD-SETUP-003\":\"补密码登录网络失败\",\"NET-REG-AUTH\":\"协议认证传输失败\",\"NET-REG-OTP\":\"验证码后认证网络失败\",\"NET-REG-PREAUTH\":\"协议前置网络失败\",\"NET-REG-UNMAPPED\":\"未映射请求传输失败\",\"NET-ROUTE-001\":\"认证线路预检失败\",\"NET-ROXY-001\":\"浏览器代理隧道失败\",\"NET-ROXY-CF-001\":\"新出口地址未确认\",\"NET-SESSION-001\":\"会话复用网络失败\",\"NET-SESSION-002\":\"会话复用请求异常\",\"NET-SESSION-003\":\"登录会话读取失败\",\"OA-000\":\"上游服务异常\",\"OA-ACCOUNT-HTTP-001\":\"账号请求被拒\",\"OA-ACCOUNT-RATE-001\":\"账号请求受限流\",\"OA-AUTH-000\":\"授权路由被拒\",\"OA-AUTH-CF-CHALLENGE\":\"认证挑战受阻\",\"OA-CODEX-CONSENT-001\":\"授权确认页受阻\",\"OA-EMAIL-000\":\"邮箱换绑失败\",\"OA-EMAIL-001\":\"邮箱换绑未完成\",\"OA-EMAIL-002\":\"账号注册时间不足\",\"OA-EMAIL-003\":\"当前会话禁止换绑\",\"OA-EMAIL-004\":\"换绑认证失败\",\"OA-EMAIL-005\":\"邮箱换绑被拒\",\"OA-EMAIL-006\":\"邮箱域名被拒\",\"OA-EMAIL-VERIFY-001\":\"新邮箱验证准备失败\",\"OA-EXTRACT-001\":\"提链响应解析失败\",\"OA-EXTRACT-002\":\"提链任务编号缺失\",\"OA-EXTRACT-HTTP\":\"提链接口异常\",\"OA-OTP-CODE-001\":\"邮箱验证码被拒\",\"OA-PLAN-403\":\"套餐请求被拒\",\"OA-PLAN-COUNTRIES\":\"逐国套餐证据不足\",\"OA-PWD-SETUP-001\":\"补密码请求被拒\",\"OA-PWD-SETUP-002\":\"补密码安全校验失败\",\"OA-PWD-SETUP-003\":\"补密码请求受限流\",\"OA-REG-000\":\"注册请求被拒\",\"OA-REG-001\":\"账号创建被拒\",\"OA-REG-AUTH-HTTP\":\"协议认证接口异常\",\"OA-REG-AUTH-PWD\":\"认证请求被拒\",\"OA-REG-CHECKPOINT-001\":\"注册检查点写入失败\",\"OA-REG-DISALLOWED-001\":\"注册被上游禁止\",\"OA-REG-EXISTS-001\":\"账号已存在会话未完成\",\"OA-REG-POST-001\":\"注册后流程失败\",\"OA-REG-PWD-001\":\"注册密码创建被拒\",\"OA-REG-REQUEST-001\":\"账号创建结果未确认\",\"OA-REG-RESPONSE-001\":\"后续验证地址缺失\",\"OA-REG-SESSION-001\":\"账号创建会话失效\",\"PAYMENT-RESPONSE-MISSING\":\"支付请求无响应\",\"PROXY-001\":\"代理获取失败\",\"REQ-RESPONSE-001\":\"远端响应缺失\",\"ROXY-001\":\"浏览器服务异常\",\"ROXY-002\":\"浏览器额度不足\",\"ROXY-REFRESH-000\":\"浏览器连接配置缺失\",\"ROXY-REFRESH-001\":\"浏览器环境启动失败\",\"ROXY-REFRESH-002\":\"浏览器调试连接失败\",\"ROXY-REFRESH-003\":\"浏览器登录页加载失败\",\"ROXY-REFRESH-004\":\"浏览器登录未完成\",\"ROXY-REFRESH-005\":\"浏览器会话读取失败\",\"ROXY-REFRESH-006\":\"登录后账号处理失败\",\"ROXY-REFRESH-007\":\"浏览器登录页未就绪\",\"ROXY-REFRESH-008\":\"浏览器登录页超时\",\"ROXY-REFRESH-009\":\"浏览器登录预检超时\",\"ROXY-REFRESH-010\":\"浏览器登录预检失败\",\"ROXY-REFRESH-011\":\"密码入口进入失败\",\"ROXY-REFRESH-012\":\"账号资料待补全\",\"STATE-001\":\"等待执行\",\"SUB2-AUTH-001\":\"凭据同步鉴权失败\",\"SUB2-CONFIG-001\":\"凭据同步配置无效\",\"SUB2-CONFIG-002\":\"凭据同步目标已变化\",\"SUB2-CONFIRM-001\":\"凭据同步回执缺失\",\"SUB2-CONFIRM-002\":\"凭据同步未完成\",\"SUB2-CONTRACT-001\":\"远端账号未找到\",\"SUB2-CONTRACT-002\":\"远端账号编号无效\",\"SUB2-CONTRACT-003\":\"凭据导入回执无效\",\"SUB2-CONTRACT-004\":\"凭据同步响应无效\",\"SUB2-CONTRACT-005\":\"凭据同步分页超限\",\"SUB2-CRED-001\":\"本地凭据无效\",\"SUB2-CRED-002\":\"本地凭据不存在\",\"SUB2-CRED-003\":\"账号授权未完成\",\"SUB2-CRED-004\":\"凭据需重新授权\",\"SUB2-HTTP-001\":\"凭据同步接口异常\",\"SUB2-ID-001\":\"凭据身份缺失\",\"SUB2-ID-002\":\"本地凭据身份不符\",\"SUB2-ID-003\":\"远端账号身份不符\",\"SUB2-ID-004\":\"远端账号不唯一\",\"SUB2-LOCAL-001\":\"上传本地写回未完成\",\"SUB2-LOCAL-002\":\"凭据上传执行异常\",\"SUB2-LOCAL-003\":\"凭据同步客户端异常\",\"SUB2-LOCAL-004\":\"凭据补传执行异常\",\"SUB2-LOCAL-005\":\"同步回执写回冲突\",\"SUB2-NET-001\":\"凭据同步请求超时\",\"SUB2-NET-002\":\"凭据同步连接失败\",\"SUB2-NET-003\":\"凭据同步网络失败\",\"SUB2-POLICY-001\":\"关联账号已停用\",\"SUB2-POLICY-002\":\"关联账号已归档\",\"SUB2-POLICY-003\":\"本地凭据版本已变化\",\"SUB2-REMOTE-001\":\"凭据导入被拒\",\"SUB2-REMOTE-002\":\"凭据同步操作被拒\",\"SYS-002\":\"服务重启中断\",\"SYS-BROWSER-001\":\"浏览器自动化异常\",\"SYS-BULK-ADAPTER-OPERATION\":\"任务操作未登记\",\"SYS-BULK-ADAPTER-STATUS\":\"任务状态未登记\",\"SYS-BULK-AT-RECEIPT\":\"凭据刷新确认缺失\",\"SYS-BULK-CODEX-CREDENTIAL\":\"授权凭据确认缺失\",\"SYS-BULK-COMPLETION-RESULT\":\"账号补全结果缺失\",\"SYS-BULK-DIAGNOSTICS\":\"失败原因未记录\",\"SYS-BULK-PLAN-RESULT\":\"套餐结果确认缺失\",\"SYS-BULK-SETUP-RECEIPT\":\"账号配置回执缺失\",\"SYS-CODE-001\":\"本地代码错误\",\"SYS-CONC-001\":\"调度存储不可用\",\"SYS-CONC-002\":\"执行器未接收任务\",\"SYS-CONC-003\":\"执行许可归属已变化\",\"SYS-CONFIG-SCHEMA\":\"配置结构不匹配\",\"SYS-DB-001\":\"数据存储异常\",\"SYS-DB-PWD-REC\":\"恢复检查点存储失败\",\"SYS-MFA-OTP\":\"验证码适配器不支持\",\"SYS-KERNEL-001\":\"内核不可用\",\"SYS-KERNEL-002\":\"内核结果无效\",\"SYS-KERNEL-003\":\"内核验证码超时\",\"SYS-KERNEL-004\":\"内核注册失败\",\"SYS-KERNEL-005\":\"远端已有账号\",\"SYS-KERNEL-006\":\"内核 2FA 失败\",\"SYS-PWD-REC-001\":\"恢复凭据无效\",\"SYS-PWD-REC-002\":\"恢复凭据解密失败\",\"SYS-PWD-REC-003\":\"候选密码生成失败\",\"SYS-PWD-REC-004\":\"候选密码无效\",\"SYS-PWD-REC-005\":\"恢复原因未登记\",\"SYS-PWD-REC-006\":\"恢复操作类型无效\",\"SYS-PWD-SETUP-001\":\"补密码执行异常\",\"SYS-REFRESH-001\":\"凭据刷新执行异常\",\"SYS-REFRESH-RESULT\":\"凭据刷新结果无效\",\"SYS-REFRESH-WRITEBACK\":\"凭据刷新写回未完成\",\"SYS-REQ-001\":\"请求准备失败\",\"SYS-SETUP-WRITEBACK\":\"账号配置写回未完成\",\"SYS-SUBMISSION-001\":\"浏览器提交上下文冲突\",\"SYS-WORKER-001\":\"执行进程中断\",\"TASK-CONC-WAIT\":\"等待执行\",\"UNK-000\":\"诊断证据不足\",\"USR-001\":\"任务已取消\",\"USR-REFRESH-001\":\"凭据刷新已取消\"}"),
	categoryLabels: {
		account: "账号异常",
		auth: "认证异常",
		browser: "浏览器异常",
		c2a: "凭据导入异常",
		configuration: "配置异常",
		email: "邮箱验证异常",
		external: "外部服务异常",
		internal: "本地执行异常",
		network: "网络异常",
		payment: "支付未完成",
		sub2api: "凭据同步异常",
		system: "任务协调异常",
		unknown: "原因未分类",
		user: "用户已停止",
		workflow: "流程未完成"
	},
	rules: [
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_proxy_dns$",
			label: "预检代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-005$",
			label: "预检代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_dns$",
			label: "预检域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-006$",
			label: "预检域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_connect$",
			label: "预检连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-007$",
			label: "预检连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_partial_response$",
			label: "预检响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-018$",
			label: "预检响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_timeout$",
			label: "预检请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-001$",
			label: "预检请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_tls$",
			label: "预检加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-002$",
			label: "预检加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_empty_response$",
			label: "预检响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-052$",
			label: "预检响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_send$",
			label: "预检发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-055$",
			label: "预检发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_connection$",
			label: "预检连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-003$",
			label: "预检连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_certificate$",
			label: "预检证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-004$",
			label: "预检证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_proxy$",
			label: "预检代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-097$",
			label: "预检代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_transport_error$",
			label: "预检网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PREFLIGHT-000$",
			label: "预检网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_http_rejected$",
			label: "预检请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^network_preflight_http_error$",
			label: "预检接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_proxy_dns$",
			label: "密码预检代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-005$",
			label: "密码预检代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_dns$",
			label: "密码预检域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-006$",
			label: "密码预检域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_connect$",
			label: "密码预检连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-007$",
			label: "密码预检连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_partial_response$",
			label: "密码预检响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-018$",
			label: "密码预检响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_timeout$",
			label: "密码预检请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-001$",
			label: "密码预检请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_tls$",
			label: "密码预检加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-002$",
			label: "密码预检加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_empty_response$",
			label: "密码预检响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-052$",
			label: "密码预检响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_send$",
			label: "密码预检发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-055$",
			label: "密码预检发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_connection$",
			label: "密码预检连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-003$",
			label: "密码预检连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_certificate$",
			label: "密码预检证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-004$",
			label: "密码预检证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_proxy$",
			label: "密码预检代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-097$",
			label: "密码预检代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_transport_error$",
			label: "密码预检网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SENTINEL-000$",
			label: "密码预检网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_http_rejected$",
			label: "密码预检请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_sentinel_http_error$",
			label: "密码预检接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_proxy_dns$",
			label: "密码代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-005$",
			label: "密码代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_dns$",
			label: "密码域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-006$",
			label: "密码域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_connect$",
			label: "密码连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-007$",
			label: "密码连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_partial_response$",
			label: "密码响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-018$",
			label: "密码响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_timeout$",
			label: "密码请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-001$",
			label: "密码请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_tls$",
			label: "密码加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-002$",
			label: "密码加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_empty_response$",
			label: "密码响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-052$",
			label: "密码响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_send$",
			label: "密码发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-055$",
			label: "密码发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_connection$",
			label: "密码连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-003$",
			label: "密码连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_certificate$",
			label: "密码证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-004$",
			label: "密码证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_proxy$",
			label: "密码代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-097$",
			label: "密码代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_transport_error$",
			label: "密码网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-PWD-000$",
			label: "密码网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_http_rejected$",
			label: "密码请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_verify_http_error$",
			label: "密码接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_proxy_dns$",
			label: "双重验证代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-005$",
			label: "双重验证代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_dns$",
			label: "双重验证域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-006$",
			label: "双重验证域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_connect$",
			label: "双重验证连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-007$",
			label: "双重验证连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_partial_response$",
			label: "双重验证响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-018$",
			label: "双重验证响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_timeout$",
			label: "双重验证请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-001$",
			label: "双重验证请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_tls$",
			label: "双重验证加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-002$",
			label: "双重验证加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_empty_response$",
			label: "双重验证响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-052$",
			label: "双重验证响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_send$",
			label: "双重验证发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-055$",
			label: "双重验证发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_connection$",
			label: "双重验证连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-003$",
			label: "双重验证连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_certificate$",
			label: "双重验证证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-004$",
			label: "双重验证证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_proxy$",
			label: "双重验证代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-097$",
			label: "双重验证代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_transport_error$",
			label: "双重验证网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MFA-000$",
			label: "双重验证网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_http_rejected$",
			label: "双重验证请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^mfa_verify_http_error$",
			label: "双重验证接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_proxy_dns$",
			label: "回调代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-005$",
			label: "回调代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_dns$",
			label: "回调域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-006$",
			label: "回调域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_connect$",
			label: "回调连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-007$",
			label: "回调连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_partial_response$",
			label: "回调响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-018$",
			label: "回调响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_timeout$",
			label: "回调请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-001$",
			label: "回调请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_tls$",
			label: "回调加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-002$",
			label: "回调加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_empty_response$",
			label: "回调响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-052$",
			label: "回调响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_send$",
			label: "回调发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-055$",
			label: "回调发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_connection$",
			label: "回调连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-003$",
			label: "回调连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_certificate$",
			label: "回调证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-004$",
			label: "回调证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_proxy$",
			label: "回调代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-097$",
			label: "回调代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_transport_error$",
			label: "回调网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-CALLBACK-000$",
			label: "回调网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_http_rejected$",
			label: "回调请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^oauth_callback_http_error$",
			label: "回调接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_proxy_dns$",
			label: "会话代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-005$",
			label: "会话代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_dns$",
			label: "会话域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-006$",
			label: "会话域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_connect$",
			label: "会话连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-007$",
			label: "会话连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_partial_response$",
			label: "会话响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-018$",
			label: "会话响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_timeout$",
			label: "会话请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-001$",
			label: "会话请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_tls$",
			label: "会话加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-002$",
			label: "会话加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_empty_response$",
			label: "会话响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-052$",
			label: "会话响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_send$",
			label: "会话发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-055$",
			label: "会话发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_connection$",
			label: "会话连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-003$",
			label: "会话连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_certificate$",
			label: "会话证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-004$",
			label: "会话证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_proxy$",
			label: "会话代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-097$",
			label: "会话代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_transport_error$",
			label: "会话网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-SESSION-READ-000$",
			label: "会话网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_http_rejected$",
			label: "会话请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^session_fetch_http_error$",
			label: "会话接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_proxy_dns$",
			label: "收件代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-005$",
			label: "收件代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_dns$",
			label: "收件域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-006$",
			label: "收件域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_connect$",
			label: "收件连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-007$",
			label: "收件连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_partial_response$",
			label: "收件响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-018$",
			label: "收件响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_timeout$",
			label: "收件请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-001$",
			label: "收件请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_tls$",
			label: "收件加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-002$",
			label: "收件加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_empty_response$",
			label: "收件响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-052$",
			label: "收件响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_send$",
			label: "收件发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-055$",
			label: "收件发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_connection$",
			label: "收件连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-003$",
			label: "收件连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_certificate$",
			label: "收件证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-004$",
			label: "收件证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_proxy$",
			label: "收件代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-097$",
			label: "收件代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_transport_error$",
			label: "收件网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-MAILBOX-000$",
			label: "收件网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_http_rejected$",
			label: "收件请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_http_error$",
			label: "收件接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_proxy_dns$",
			label: "发码代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-005$",
			label: "发码代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_dns$",
			label: "发码域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-006$",
			label: "发码域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_connect$",
			label: "发码连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-007$",
			label: "发码连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_partial_response$",
			label: "发码响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-018$",
			label: "发码响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_timeout$",
			label: "发码请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-001$",
			label: "发码请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_tls$",
			label: "发码加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-002$",
			label: "发码加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_empty_response$",
			label: "发码响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-052$",
			label: "发码响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_send$",
			label: "发码发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-055$",
			label: "发码发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_connection$",
			label: "发码连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-003$",
			label: "发码连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_certificate$",
			label: "发码证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-004$",
			label: "发码证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_proxy$",
			label: "发码代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-097$",
			label: "发码代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_transport_error$",
			label: "发码网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-SEND-000$",
			label: "发码网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_http_rejected$",
			label: "发码请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_send_http_error$",
			label: "发码接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_proxy_dns$",
			label: "验码代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-005$",
			label: "验码代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_dns$",
			label: "验码域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-006$",
			label: "验码域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_connect$",
			label: "验码连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-007$",
			label: "验码连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_partial_response$",
			label: "验码响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-018$",
			label: "验码响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_timeout$",
			label: "验码请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-001$",
			label: "验码请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_tls$",
			label: "验码加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-002$",
			label: "验码加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_empty_response$",
			label: "验码响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-052$",
			label: "验码响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_send$",
			label: "验码发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-055$",
			label: "验码发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_connection$",
			label: "验码连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-003$",
			label: "验码连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_certificate$",
			label: "验码证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-004$",
			label: "验码证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_proxy$",
			label: "验码代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-097$",
			label: "验码代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_transport_error$",
			label: "验码网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-OTP-VALIDATE-000$",
			label: "验码网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_http_rejected$",
			label: "验码请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^email_otp_validate_http_error$",
			label: "验码接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_proxy_dns$",
			label: "浏览器代理解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-005$",
			label: "浏览器代理解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_dns$",
			label: "浏览器域名解析失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-006$",
			label: "浏览器域名解析失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_connect$",
			label: "浏览器连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-007$",
			label: "浏览器连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_partial_response$",
			label: "浏览器响应不完整"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-018$",
			label: "浏览器响应不完整"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_timeout$",
			label: "浏览器请求超时"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-001$",
			label: "浏览器请求超时"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_tls$",
			label: "浏览器加密连接失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-002$",
			label: "浏览器加密连接失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_empty_response$",
			label: "浏览器响应缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-052$",
			label: "浏览器响应缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_send$",
			label: "浏览器发送中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-055$",
			label: "浏览器发送中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_connection$",
			label: "浏览器连接中断"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-003$",
			label: "浏览器连接中断"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_certificate$",
			label: "浏览器证书校验失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-004$",
			label: "浏览器证书校验失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_proxy$",
			label: "浏览器代理隧道失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-097$",
			label: "浏览器代理隧道失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_transport_error$",
			label: "浏览器网络请求失败"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^NET-ROXY-AT-000$",
			label: "浏览器网络请求失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_http_rejected$",
			label: "浏览器请求被拒"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^roxy_at_http_error$",
			label: "浏览器接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PREFLIGHT-401$",
			label: "预检请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PREFLIGHT-403$",
			label: "预检请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PREFLIGHT-429$",
			label: "预检请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PREFLIGHT-5[0-9]{2}$",
			label: "预检服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PREFLIGHT-4[0-9]{2}$",
			label: "预检接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SENTINEL-401$",
			label: "密码预检请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SENTINEL-403$",
			label: "密码预检请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SENTINEL-429$",
			label: "密码预检请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SENTINEL-5[0-9]{2}$",
			label: "密码预检服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SENTINEL-4[0-9]{2}$",
			label: "密码预检接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PWD-401$",
			label: "密码请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PWD-403$",
			label: "密码请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PWD-429$",
			label: "密码请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PWD-5[0-9]{2}$",
			label: "密码服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-PWD-4[0-9]{2}$",
			label: "密码接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-MFA-401$",
			label: "双重验证请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-MFA-403$",
			label: "双重验证请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-MFA-429$",
			label: "双重验证请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-MFA-5[0-9]{2}$",
			label: "双重验证服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-MFA-4[0-9]{2}$",
			label: "双重验证接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-CALLBACK-401$",
			label: "回调请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-CALLBACK-403$",
			label: "回调请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-CALLBACK-429$",
			label: "回调请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-CALLBACK-5[0-9]{2}$",
			label: "回调服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-CALLBACK-4[0-9]{2}$",
			label: "回调接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SESSION-401$",
			label: "会话请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SESSION-403$",
			label: "会话请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SESSION-429$",
			label: "会话请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SESSION-5[0-9]{2}$",
			label: "会话服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-SESSION-4[0-9]{2}$",
			label: "会话接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^MAIL-OTP-HTTP-401$",
			label: "收件请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^MAIL-OTP-HTTP-403$",
			label: "收件请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^MAIL-OTP-HTTP-429$",
			label: "收件请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^MAIL-OTP-HTTP-5[0-9]{2}$",
			label: "收件服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^MAIL-OTP-HTTP-4[0-9]{2}$",
			label: "收件接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-SEND-401$",
			label: "发码请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-SEND-403$",
			label: "发码请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-SEND-429$",
			label: "发码请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-SEND-5[0-9]{2}$",
			label: "发码服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-SEND-4[0-9]{2}$",
			label: "发码接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-VALIDATE-401$",
			label: "验码请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-VALIDATE-403$",
			label: "验码请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-VALIDATE-429$",
			label: "验码请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-VALIDATE-5[0-9]{2}$",
			label: "验码服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-OTP-VALIDATE-4[0-9]{2}$",
			label: "验码接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-ROXY-AT-401$",
			label: "浏览器请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-ROXY-AT-403$",
			label: "浏览器请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-ROXY-AT-429$",
			label: "浏览器请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-ROXY-AT-5[0-9]{2}$",
			label: "浏览器服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-ROXY-AT-4[0-9]{2}$",
			label: "浏览器接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-REG-401$",
			label: "注册请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-REG-403$",
			label: "注册请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-REG-429$",
			label: "注册请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-REG-5[0-9]{2}$",
			label: "注册服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-REG-4[0-9]{2}$",
			label: "注册接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-AUTH-401$",
			label: "授权请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-AUTH-403$",
			label: "授权请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-AUTH-429$",
			label: "授权请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-AUTH-5[0-9]{2}$",
			label: "授权服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-AUTH-4[0-9]{2}$",
			label: "授权接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-EXTRACT-401$",
			label: "提链请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-EXTRACT-403$",
			label: "提链请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-EXTRACT-429$",
			label: "提链请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-EXTRACT-5[0-9]{2}$",
			label: "提链服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^OA-EXTRACT-4[0-9]{2}$",
			label: "提链接口异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^LINK-HTTP-401$",
			label: "提链请求未授权"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^LINK-HTTP-403$",
			label: "提链请求被禁止"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^LINK-HTTP-429$",
			label: "提链请求受限流"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^LINK-HTTP-5[0-9]{2}$",
			label: "提链服务端异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^LINK-HTTP-4[0-9]{2}$",
			label: "提链接口异常"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^[a-z][a-z0-9_]*_failure_diagnostics_missing$",
			label: "失败诊断缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^[a-z][a-z0-9_]*_receipt_missing$",
			label: "执行回执缺失"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^password_recovery_database_[a-z0-9_]+$",
			label: "恢复检查点存储失败"
		},
		{
			fields: [
				"cause_code",
				"code",
				"error_code"
			],
			pattern: "^workflow\\.password_recovery\\.[a-z0-9_]+$",
			label: "密码恢复流程异常"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^SYS-DIAG-[A-Z0-9-]+$",
			label: "失败诊断缺失"
		},
		{
			fields: ["cause_display_code", "display_code"],
			pattern: "^[A-Z][A-Z0-9-]*-RECEIPT(?:-[0-9]+)?$",
			label: "执行回执缺失"
		}
	],
	fallback: "原因未分类"
}, t = {
	...e.codeLabels,
	...e.causeCodeLabels
}, n = e.displayCodeLabels, r = e.categoryLabels, i = e.rules.map((e) => ({
	...e,
	match: new RegExp(e.pattern)
})), a = (e, t) => Object.hasOwn(e, t) ? e[t] : void 0;
function o(o) {
	if (!o) return e.fallback;
	for (let r of e.lookupFields) {
		let e = String(o[r] ?? "").trim();
		if (!e) continue;
		let s = a(r.includes("display") ? n : t, e);
		if (s) return s;
		let c = i.find((t) => t.fields.includes(r) && t.match.test(e));
		if (c) return c.label;
	}
	return a(r, String(o.category ?? "")) || a(r, String(o.source ?? "")) || e.fallback;
}
export { o as t };
