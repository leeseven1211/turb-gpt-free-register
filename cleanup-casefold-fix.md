# Cleanup 判定机械修正

针对 `root-run-5079fda704234d29` 的证据复核发现，Docker 返回 `error: no such object: <id>`，原 runner 只匹配首字母大写文本，导致真实已删除容器被记录为 `container=false`。已在本地 runner ART 单独修正为小写归一化后比较；没有修改既有失败结果、没有重跑、没有上传或覆盖 B5 package。

- 修正文件：`oracle_sandbox_acceptance.py`
- 修正后 SHA256：`7b95de2f83464eb2fcfb23bf2a5228a38f2da5b64a9376a7fa2e6d868c66ee92`
- `test_runner_offline.py`：9/9 PASS
- B5 冻结 runner SHA `fe15c1d6...`、package harness 与既有 evidence 保持原样；此修正若要再次运行，必须重新建立完整 harness/package 审查和 root GO。
