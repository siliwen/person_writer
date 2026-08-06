# 评测与训练数据获取规则

## 结论

MVP 评测集不能默认通过爬虫抓取仍在版权保护期内的作者作品。爬虫只能用于获取授权清晰的数据，或用于下载我们已经确认可合法使用的数据源。

## 可接受来源

| 来源 | 是否可用于 MVP 评测 | 是否可用于未来 Personal LoRA |
|---|---|---|
| 用户本人上传并确认拥有权利的作品 | 可以 | 需要单独训练授权 |
| 组织内作者授权提供的作品 | 可以 | 需要作者单独训练授权 |
| 团队自写样本 | 可以 | 可以，按内部授权记录 |
| 明确开放许可文本 | 可以，需遵守许可条件 | 取决于许可是否允许训练/商业使用 |
| 已进入公共领域的作品 | 可以用于技术流程测试 | 不建议包装成“个人作家服务”卖点 |
| 未授权抓取的现代作者作品 | 不可以 | 不可以 |
| 付费平台、会员站、App 内作品 | 不可以，除非取得平台和权利人许可 | 不可以 |

## 爬虫允许范围

允许做：

- 抓取自有网站或已获授权网站的文本。
- 抓取明确开放许可或公共领域文本。
- 抓取作品元数据、URL、作者、标题、许可声明和采集时间。
- 遵守 robots、网站条款、频率限制和反爬规则。

不允许做：

- 绕过登录、付费、会员、验证码、DRM 或反爬限制。
- 批量抓取在版权保护期内的现代作者全文。
- 把未授权作品导入 RAG、评测集、微调集或演示环境。
- 用未授权作者名字对外展示“模仿某某作家风格”。

## 元数据要求

每份 Material 必须记录：

- `source_type`：user_upload / organization_authorized / internal_original / open_license / public_domain。
- `source_url`
- `source_site`
- `author_name`
- `title`
- `license_name`
- `license_url`
- `rights_status`
- `collected_at`
- `collector`
- `content_hash`
- `allowed_for_eval`
- `allowed_for_rag`
- `allowed_for_training`
- `authorization_document_id`

## MVP 推荐做法

第一版评测集优先采用：

1. 团队内部自写样本。
2. 真实作者授权提供样本。
3. 作协或组织成员自愿提供样本。
4. 公共领域作品只作为系统流程测试，不作为商业效果宣传。

如果要写爬虫，先写“授权来源白名单”，再按白名单采集。采集脚本必须输出元数据清单，不能只输出正文。

具体执行流程见：

- `D:\AI_talk\personal_writing_agent_saas\07_ops_compliance_运维合规\sample_acquisition_crawler_workflow.md`

## 样本状态流转

所有通过网页采集器得到的作品，默认先进入 `candidate_materials`，不能直接进入 RAG、评测集或训练集。

状态流转：

```text
candidate_materials
  -> rights_reviewed
  -> approved_for_eval / approved_for_rag / approved_for_training
  -> imported
```

任何缺少授权记录、来源许可或使用范围的样本，都只能停留在 `candidate_materials`。

## 法律依据提示

这不是法律意见。正式上线前应由律师确认。

需要重点关注：

- 《中华人民共和国著作权法》保护文字作品，著作权包括复制权、信息网络传播权、改编权、汇编权等。
- 《生成式人工智能服务管理暂行办法》要求训练数据和基础模型具有合法来源，涉及知识产权的不得侵害他人依法享有的知识产权。
- 面向公众提供生成式 AI 服务时，还应关注 AI 生成合成内容标识、隐私、投诉举报和内容治理要求。
