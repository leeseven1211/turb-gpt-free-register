"""私有密码恢复的固定失败原因须形成明确展示，不推断远端改密结果。"""
import pytest

from core.operations.errors import classify_task_error


STORE_CASES = [
    ('encryption_key_missing', 'configuration.missing', 'CFG-PWD-REC-001', '密码恢复主密钥未配置'),
    ('encryption_key_invalid', 'configuration.invalid', 'CFG-PWD-REC-002', '密码恢复主密钥格式无效'),
    ('credential_context_invalid', 'internal.storage', 'SYS-PWD-REC-001', '密码恢复私有凭据格式无效'),
    ('credential_decryption_failed', 'internal.storage', 'SYS-PWD-REC-002', '密码恢复私有凭据解密失败'),
    ('candidate_generation_failed', 'internal.code', 'SYS-PWD-REC-003', '密码恢复候选密码生成失败'),
    ('candidate_invalid', 'internal.code', 'SYS-PWD-REC-004', '密码恢复候选密码不符合保存要求'),
    ('recovery_intent_invalid', 'internal.code', 'SYS-PWD-REC-006', '密码检查点的操作类型无效'),
    ('owner_invalid', 'workflow.password_recovery.owner_invalid', 'FLOW-PWD-REC-001', '密码恢复执行归属参数无效'),
    ('operation_inactive', 'workflow.password_recovery.operation_inactive', 'FLOW-PWD-REC-002', '密码恢复操作已不在执行中'),
    ('operation_execution_mismatch', 'workflow.password_recovery.operation_execution_mismatch', 'FLOW-PWD-REC-003', '密码恢复操作执行身份不匹配'),
    ('operation_identity_mismatch', 'workflow.password_recovery.operation_identity_mismatch', 'FLOW-PWD-REC-004', '密码恢复操作与账号或邮箱不匹配'),
    ('registration_identity_mismatch', 'workflow.password_recovery.registration_identity_mismatch', 'FLOW-PWD-REC-005', '密码恢复原注册任务身份不匹配'),
    ('registration_execution_mismatch', 'workflow.password_recovery.registration_execution_mismatch', 'FLOW-PWD-REC-006', '密码恢复注册执行身份不匹配'),
    ('registration_operation_mapping_mismatch', 'workflow.password_recovery.registration_operation_mapping_mismatch', 'FLOW-PWD-REC-007', '密码恢复注册任务与操作 Run 映射不匹配'),
    ('manual_operation_mismatch', 'workflow.password_recovery.manual_operation_mismatch', 'FLOW-PWD-REC-008', '密码恢复手动操作归属不匹配'),
    ('account_identity_mismatch', 'workflow.password_recovery.account_identity_mismatch', 'FLOW-PWD-REC-009', '密码恢复账号与原邮箱不匹配'),
    ('account_deactivated', 'workflow.password_recovery.account_deactivated', 'FLOW-PWD-REC-010', '本地账号已停用，密码恢复身份检查未通过'),
    ('operation_lease_invalid', 'workflow.password_recovery.operation_lease_invalid', 'FLOW-PWD-REC-011', '密码恢复当前账号租约无效'),
    ('owner_active', 'workflow.password_recovery.owner_active', 'FLOW-PWD-REC-012', '密码恢复检查点仍由其他执行持有'),
    ('registration_attempt_conflict', 'workflow.password_recovery.registration_attempt_conflict', 'FLOW-PWD-REC-013', '密码恢复检查点与当前注册 Attempt 冲突'),
    ('password_conflict', 'workflow.password_recovery.password_conflict', 'FLOW-PWD-REC-014', '密码恢复时账号密码版本冲突'),
    ('recovery_not_found', 'workflow.password_recovery.recovery_not_found', 'FLOW-PWD-REC-015', '密码恢复私有检查点不存在'),
    ('recovery_owner_mismatch', 'workflow.password_recovery.recovery_owner_mismatch', 'FLOW-PWD-REC-016', '密码恢复检查点执行归属不匹配'),
    ('attempt_password_conflict', 'workflow.password_recovery.attempt_password_conflict', 'FLOW-PWD-REC-017', '密码恢复时原注册 Attempt 密码版本冲突'),
    ('recovery_intent_conflict', 'workflow.password_recovery.recovery_intent_conflict', 'FLOW-PWD-REC-028', '存在另一种密码操作的待确认候选，请继续原操作'),
    ('password_add_context_invalid', 'workflow.password_recovery.password_add_context_invalid', 'FLOW-PWD-REC-029', '添加密码回执与当前补密码候选不匹配'),
    ('state_invalid', 'workflow.password_recovery.state_invalid', 'FLOW-PWD-REC-018', '密码恢复目标状态无效'),
    ('confirmation_invalid', 'workflow.password_recovery.confirmation_invalid', 'FLOW-PWD-REC-019', '密码恢复缺少有效的明确确认类型'),
    ('version_conflict', 'workflow.password_recovery.version_conflict', 'FLOW-PWD-REC-020', '密码恢复检查点版本冲突'),
    ('state_transition_invalid', 'workflow.password_recovery.state_transition_invalid', 'FLOW-PWD-REC-021', '密码恢复检查点不允许本次状态推进'),
    ('checkpoint_missing', 'workflow.password_recovery.checkpoint_missing', 'FLOW-PWD-REC-022', '密码恢复尚未建立私有检查点'),
    ('candidate_login_context_invalid', 'workflow.password_recovery.candidate_login_context_invalid', 'FLOW-PWD-REC-025', '候选密码认证上下文或私有候选与当前注册续跑不匹配，请保留候选并核对执行归属'),
    ('candidate_login_receipt_invalid', 'workflow.password_recovery.candidate_login_receipt_invalid', 'FLOW-PWD-REC-026', '候选密码认证回执缺少有效配对成功证据，请保留候选并核对本次密码提交回执'),
    ('candidate_login_fact_invalid', 'workflow.password_recovery.candidate_login_fact_invalid', 'FLOW-PWD-REC-027', '候选密码认证的持久化提交事实不匹配，请保留候选并核对同 Run 提交记录'),
]


@pytest.mark.parametrize('suffix,code,display,summary', STORE_CASES)
@pytest.mark.parametrize('surface', ['exception', 'structured'])
def test_every_current_private_recovery_failure_has_fact_specific_chinese_classification(suffix, code, display, summary, surface):
    result_summary = {'cause_code': f'password_recovery_{suffix}', 'outcome': 'request_unknown'} if surface == 'structured' else {}
    raw = 'PasswordRecoveryError: 密码恢复失败：' + suffix if surface == 'exception' else '注册执行未完成'
    info = classify_task_error(raw, task_type='registration_resume', stage='login_password', result_summary=result_summary)
    assert info['code'] == code
    assert info['display_code'] == display
    assert info['summary'] == summary
    assert info['cause_code'] == f'password_recovery_{suffix}'
    assert info['source'] in {'internal', 'configuration', 'workflow'}
    if surface == 'structured':
        assert info['reconcile_required'] is True
        assert info['next_action'] == 'manual_reconcile'
        assert result_summary == {'cause_code': f'password_recovery_{suffix}', 'outcome': 'request_unknown'}


@pytest.mark.parametrize('suffix', ['candidate_login_context_invalid', 'candidate_login_receipt_invalid', 'candidate_login_fact_invalid'])
def test_candidate_confirmation_error_display_uses_registered_reason_without_private_context(suffix):
    from core.storage.accounts.password_recovery import PasswordRecoveryError

    private = {'email': 'private-account@example.test', 'password': 'private-candidate-password',
               'request_id': 'private-request-id'}
    result_summary = {'cause_code': f'password_recovery_{suffix}', 'outcome': 'request_unknown',
                      'private_context': private}
    info = classify_task_error(PasswordRecoveryError(suffix), task_type='registration_resume',
                               stage='login_password', result_summary=result_summary)
    assert info['code'] == f'workflow.password_recovery.{suffix}'
    assert info['cause_code'] == f'password_recovery_{suffix}'
    assert info['source'] == 'workflow'
    assert info['next_action'] == 'manual_reconcile'
    assert info['remote_state_impact'] == 'unknown'
    assert info['reconcile_required'] is True
    assert '请保留候选并核对' in info['summary']
    assert all(value not in str(info) for value in private.values())
    assert result_summary['private_context'] == private


@pytest.mark.parametrize('database_code', ['database_23505', 'database_08006', 'database_OperationalError', 'database_PoolTimeout'])
def test_database_failures_are_local_storage_errors_without_inventing_remote_password_failure(database_code):
    info = classify_task_error('PasswordRecoveryError: 密码恢复失败：' + database_code, task_type='password_change')
    assert info['code'] == 'internal.storage'
    assert info['display_code'] == 'SYS-DB-PWD-REC'
    assert info['summary'] == '密码恢复私有检查点数据库操作失败'
    assert info['cause_code'] == 'password_recovery_database_error'
    assert info['source'] == 'internal'
    assert '远端' not in info['summary']


@pytest.mark.parametrize('cause,code,display,summary', [
    ('password_recovery_owner_missing', 'workflow.password_recovery.owner_missing', 'FLOW-PWD-REC-023', '密码恢复缺少当前操作执行或原账号归属'),
    ('password_recovery_unconfirmed', 'request_unknown', 'AUTH-PWD-REC-001', '密码恢复候选尚未完成认证确认，已保留私有检查点'),
    ('password_recovery_identity_unconfirmed', 'workflow.password_recovery.identity_unconfirmed', 'FLOW-PWD-REC-024', '密码恢复尚未确认原邮箱登录入口，候选已保留且未提交重置'),
])
def test_browser_and_adapter_failures_are_stable_without_overwriting_original_outcome(cause, code, display, summary):
    original = {'cause_code': cause, 'outcome': 'request_unknown', 'reconcile_required': True}
    info = classify_task_error(cause + ': 已保留原任务', task_type='registration', error_code='request_unknown', result_summary=original)
    assert info['code'] == code
    assert info['display_code'] == display
    assert info['summary'] == summary
    assert info['reconcile_required'] is True
    assert original == {'cause_code': cause, 'outcome': 'request_unknown', 'reconcile_required': True}


def test_candidate_login_proof_unknown_keeps_password_recovery_reason():
    info = classify_task_error(
        'PasswordResetTransitionUnknown: request_unknown: 候选密码认证未取得本次配对成功响应，保留恢复检查点',
        task_type='registration_resume', error_code='request_unknown', stage='login_password',
    )
    assert info['code'] == 'request_unknown'
    assert info['cause_code'] == 'password_recovery_candidate_login_unconfirmed'
    assert info['display_code'] == 'AUTH-PWD-REC-002'
    assert info['summary'] == '密码恢复候选认证缺少本次配对成功响应，已保留私有检查点'
    assert info['reconcile_required'] is True


def test_unscoped_version_conflict_is_not_assigned_to_password_recovery():
    info = classify_task_error('version_conflict', task_type='account_update')
    assert not str(info.get('cause_code', '')).startswith('password_recovery_')
