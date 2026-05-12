# qwen3.5-397b-a17b nanobot GUI-only failure analysis

Analyzed runs:
- `traj_logs/GUI_only_nanobot_qwen35_397b_a17b`
- `traj_logs/GUI_only_nanobot_qwen35_397b_a17b_calls50_timeout1200_rerun`

## Aggregate

| run | tasks | failures | timeout | GUI call cap | early/wrong completion | runtime error |
|---|---:|---:|---:|---:|---:|---:|
| `GUI_only_nanobot_qwen35_397b_a17b` | 116 | 74 | 28 | 11 | 35 | 0 |
| `GUI_only_nanobot_qwen35_397b_a17b_calls50_timeout1200_rerun` | 45 | 30 | 6 | 4 | 19 | 1 |


## Direct answers

| question | answer | evidence |
|---|---|---|
| 是否主要是任务执行中 memory 缺陷？ | 不是主要原因，但存在少量疑似 cross-task memory/history 污染。 | traces 中 `memory_retrieval` 主要注入固定安全策略；thread log 多数是 `Token consolidation idle ... /65536`，没有明显上下文压缩丢失。疑似污染体现在若干错误内容，如 `Which country has the largest land area?`、`Hello from Owner`。 |
| 是否主要是最大步数/限制？ | 第一轮很重要，重跑后显著下降但没有消失。 | base 失败 74 个，其中 timeout 28、GUI call cap 11；rerun 失败 30 个，其中 timeout 6、GUI call cap 4。 |
| 是否主要是幻觉/提前结束？ | 是重跑后最大的失败类别，也是整体最稳定的问题。 | base 35/74；rerun 19/30。典型模式是 `nanobot_success=true` 或 final action `done`，但 MobileWorld native score 为 0。 |

## Per-task failure table

| task | base score/reason | base diagnosis | rerun score/reason | rerun diagnosis | conclusion |
|---|---|---|---|---|---|
| `AdjustBrightnessMaximumTask` | 0.0: Brightness is not at maximum level, current: 252/255 | 提前/错误完成; gui_steps=7, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `BidFileRenameTask` | 0.0: Bid files not renamed (missed): ['bid_catering_menu_2024.doc', 'bid_menu_design_contract.pdf', 'bid_food_supplier_quote.txt'] | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=104, calls=2 | 0.0: Expected renamed file not found: bid_1.txt. Found: ['bid_001.txt', 'bid_002.doc', 'bid_003.pdf', 'bid_004.txt'] | 提前/错误完成; gui_steps=50, calls=1 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `CVEmailTask` | 0.0: No email sent | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=106, calls=3 | 1.0: success | 成功; score=1.0 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `ChangeWallpaperTask` | 0.0: Wallpaper has not changed | 提前/错误完成; gui_steps=12, calls=1 | 1.0: Success | 成功; score=1.0 | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `CheckConferenceAndSendSmsTask1` | 0.0: SMS to +14058298746 with correct dates not found | 提前/错误完成; gui_steps=16, calls=1 | 1.0: Success | 成功; score=1.0 | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `CheckConferenceAndSendSmsTask2` | 0.0: SMS to +14058298746 with correct dates not found | 提前/错误完成; gui_steps=25, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `CheckConferenceLocationTask` | 0.0: no answer or not a number | 提前/错误完成; gui_steps=45, calls=3 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `CheckDeduplicatedEventsTask` | 0.0: Incorrect answer , expected 9 | 提前/错误完成; gui_steps=10, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `CheckGithubInfoTask` | 0.0: No email found | 提前/错误完成; gui_steps=0, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `CheckInterviewTimesTask` | 0.0: incorrect calendar events | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=101, calls=3 | 0.0: incorrect calendar events | 提前/错误完成; gui_steps=126, calls=3 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `CheckInvoiceTask2` | 0.0: No email sent | GUI 调用次数上限; calls=3/3, gui_steps=17 | 1.0: success | 成功; score=1.0 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `CheckInvoiceTask3` | 0.0: No SMS found to Mia Scott (14058298746) with correct answer: 0 | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=88, calls=2 | 1.0: success | 成功; score=1.0 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `CheckRegistrationTask` | 0.0: No email found | 提前/错误完成; gui_steps=6, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `CheckSetMeetTimeTask` | 0.0: incorrect calendar event | 提前/错误完成; gui_steps=17, calls=2 | 1.0: success | 成功; score=1.0 | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `DownloadSendReceiptTask` | 0.0: No email found | GUI 调用次数上限; calls=3/3, gui_steps=48 | 1.0: success | 成功; score=1.0 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `GraduationMassEmailTask` | 0.0: No email found | GUI 调用次数上限; calls=3/3, gui_steps=82 | 0.0: No email found | 提前/错误完成; gui_steps=0, calls=2 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `InvoiceReceiptCopyAskUserTask` | 0.0: Target folder 'Documents/expense/invoice' does not exist | GUI 调用次数上限; calls=3/3, gui_steps=104 | 0.0: Target folder 'Documents/expense/invoice' does not exist | 提前/错误完成; gui_steps=50, calls=1 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `InvoiceReceiptCopyTask` | 0.0: Expected 1 files in folder, found 0. Expected: ['invoice_2025_001.pdf'], Found: [] | 提前/错误完成; gui_steps=61, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `ItemCheckoutTask` | 0.0: No callback data found | 提前/错误完成; gui_steps=61, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `LocalFileManagementTask` | 0.0: File 06_music_collection_20240929.zip is not deleted | 提前/错误完成; gui_steps=0, calls=3 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `LocalFileManagementTask2` | 0.0: File 06_music_collection_20240929.zip is not deleted | 提前/错误完成; gui_steps=0, calls=0 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MastodonAddBookmarkTask` | 0.0: Expected status id {115359670141158913, 115342692663348018} not found in bookmarks for user 'test' | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=97, calls=2 | 0.0: Expected status id {115359670141158913, 115342692663348018} not found in bookmarks for user 'test' | 最大运行时间/长程搜索耗尽; timeout=1200s, gui_steps=156, calls=3 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonAddFeaturedHashtagsTask` | 0.0: Featured tags for user test not found | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=104, calls=2 | 0.0: Featured tags for user test not found | 提前/错误完成; gui_steps=100, calls=2 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonAdjustTootsTask` | 0.0: Expected status ids are still in bookmarks. Still bookmarked: {115410836820181445, 115348102480027134, 115410818912936581} | GUI 调用次数上限; calls=3/3, gui_steps=63 | 0.0: Expected status ids are still in bookmarks. Still bookmarked: {115410836820181445, 115348102480027134, 115410818912936581} | 最大运行时间/长程搜索耗尽; timeout=1200s, gui_steps=176, calls=4 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonCalendarMultiMemosTask` | 0.0: Event not found: 1761318000 - 1761323400 | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=93, calls=2 | 0.0: Event not found: 1761318000 - 1761323400 | 最大运行时间/长程搜索耗尽; timeout=1200s, gui_steps=173, calls=5 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonChangeLanguageTask` | 0.0: User language mismatch: actual_language=en != expected_language=zh-CN | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=105, calls=3 | 0.0: User language mismatch: actual_language=en != expected_language=zh-CN | 提前/错误完成; gui_steps=65, calls=2 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonConditionalFavoTask` | 0.0: Not all expected toots are favorited. Expected: {115410810887077411, 115410813905484454}, Missing: {115410810887077411, 115410813905484454} | 提前/错误完成（含疑似陈旧上下文或搜索误判）; gui_steps=27, calls=1 | 0.0: No favorites found for user 'test' | GUI 调用次数上限; calls=5/5, gui_steps=63 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `MastodonCreateMemoTask` | 0.0: Event not found: 1761318000 - 1761323400 | 提前/错误完成; gui_steps=58, calls=2 | 1.0: No reason provided for MastodonCreateMemoTask | 成功; score=1.0 | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MastodonExportFollowsTask` | 0.0: Export file 'my_following.csv' not found in /storage/emulated/0/Download | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=96, calls=3 | 0.0: Export file 'my_following.csv' not found in /storage/emulated/0/Download | 提前/错误完成; gui_steps=103, calls=3 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonFavoriteTootsTask` | 0.0: No favorites found for user 'test' | 提前/错误完成（含疑似陈旧上下文或搜索误判）; gui_steps=14, calls=1 | 未运行 | - | 主要是提前确信或陈旧上下文/搜索误判，不是外层 step 上限。 |
| `MastodonFilterLanguageTask` | 0.0: Chosen languages for user test not found | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=94, calls=3 | 0.0: Chosen languages for user test not found | 提前/错误完成; gui_steps=41, calls=1 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonGetServerInfoTask` | 0.0: The database size info not correct, expected: 15.6 MB, actual: Hello from Owner 👋 | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=89, calls=2 | 0.0: The database size info not correct, expected: 15.6 MB, actual: Hello from Owner 👋 | 最大运行时间/长程搜索耗尽; timeout=1200s, gui_steps=196, calls=5 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonImportMutedUsersTask` | 0.0: No muted users found for user 'test' | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=98, calls=2 | 1.0: No reason provided for MastodonImportMutedUsersTask | 成功; score=1.0 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonInviteTask` | 0.0: SMS content mismatch. | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=93, calls=2 | 1.0: No reason provided for MastodonInviteTask | 成功; score=1.0 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonMallShareOrderTask` | 0.0: Perceptual hash does not match, image not matched | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=73, calls=3 | 1.0: No reason provided for MastodonMallShareOrderTask | 成功; score=1.0 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonManageHashtagsTask` | 0.0: Expected no followed hashtags dogs found in followed hashtags ['hummus', 'chinesecuisine', 'cats', 'flavorburst', 'foodperfection', 'foodgoals', 'careertransition', 'careergrowth', 'newbeginnings', 'newgoals', 'lookingahead', 'professionalgrowth', 'projectsucc | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=89, calls=2 | 0.0: Expected no followed hashtags dogs found in followed hashtags ['hummus', 'chinesecuisine', 'cats', 'flavorburst', 'foodperfection', 'foodgoals', 'careertransition', 'careergrowth', 'newbeginnings', 'newgoals', 'lookingahead', 'professionalgrowth', 'projectsucc | GUI 调用次数上限; calls=5/5, gui_steps=166 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonManageMultiListTask` | 0.0: List 'open' not found | GUI 调用次数上限; calls=3/3, gui_steps=72 | 0.0: List 'open' members mismatch. Expected: {'openUniversity', 'openCompany'}, Got: {'gourmet', 'openCompany'} | 提前/错误完成; gui_steps=112, calls=4 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `MastodonMattermostPostNoticeTask` | 0.0: Toot text mismatch: Which country has the largest land area? != Security: rotated API keys; check 1Password vault for updated entries. | 提前/错误完成（含疑似陈旧上下文或搜索误判）; gui_steps=10, calls=1 | 未运行 | - | 主要是提前确信或陈旧上下文/搜索误判，不是外层 step 上限。 |
| `MastodonMultiInviteTask` | 0.0: Leonard's invite not found or doesn't match expected parameters. | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=92, calls=2 | 0.0: Leonard's invite not found or doesn't match expected parameters. | 最大运行时间/长程搜索耗尽; timeout=1200s, gui_steps=169, calls=4 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonNewFilterTask` | 0.0: Filter not found: phrase=Anti-Spoiler-BCS, username=test | 提前/错误完成; gui_steps=74, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MastodonOpenAutomatedDeletionTask` | 0.0: No automated post deletions setting found for user: test | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=75, calls=2 | 0.0: No automated post deletions setting found for user: test | 提前/错误完成; gui_steps=125, calls=5 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonPostEditedPhotoTask` | 0.0: No images found for toot: 115433627788463436 | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=91, calls=2 | 0.0: No images found for toot: 115433627788463436 | 提前/错误完成; gui_steps=25, calls=1 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonRemoveBookmarkTask` | 0.0: Expected status id {115410836820181445, 115410818912936581} found in bookmarks for user 'test' | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=91, calls=2 | 1.0: No reason provided for MastodonRemoveBookmarkTask | 成功; score=1.0 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonReportTask` | 0.0: The report reason is not the same as the toot content: toot_content=Just got a message from my cousin in the fire department — there’s a gas leak near the city mall, they’re covering it up! Leave the area NOW before it explodes! != report_reason=Just got a mes | 提前/错误完成; gui_steps=25, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MastodonRevisePollTask` | 0.0: Expected 3 options, but found 4 | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=93, calls=3 | 1.0: No reason provided for MastodonRevisePollTask | 成功; score=1.0 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonSavePhotosTask` | 0.0: Image not found on device: 3a0cba7a548347d5.jpg | GUI 调用次数上限; calls=3/3, gui_steps=59 | 0.0: Image not found on device: 9233a784e5525d0c.jpg | 最大运行时间/长程搜索耗尽; timeout=1200s, gui_steps=176, calls=4 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonServerInfoReportTask` | 0.0: No email found | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=94, calls=2 | 0.0: Report count mismatch. Expected: 2, Got in email: 0 | 提前/错误完成（含疑似陈旧上下文或搜索误判）; gui_steps=145, calls=4 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MastodonShareLocationTask` | 0.0: URL mismatch: Which country has the largest land area? does not contain https://maps.app.goo.gl/xxxxxx | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=104, calls=2 | 0.0: URL mismatch: Which country has the largest land area? does not contain https://maps.app.goo.gl/xxxxxx | 提前/错误完成（含疑似陈旧上下文或搜索误判）; gui_steps=123, calls=3 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MattermostBudgetApprovalPipelineTask` | 0.0: Budget summary table not posted in channel (missing departments, ROI info, or table format) | 提前/错误完成; gui_steps=5, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostCreateChannelTask` | 0.0: Channel not created | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=97, calls=2 | 0.0: Channel not created | 运行时错误; RuntimeError: SystemExit: NOTE: You must install tkinter on Linux to use MouseInfo. Run the following: sudo apt-get inst | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MattermostCustomerFeedbackAnalysisTask` | 0.0: No summary email sent | 提前/错误完成; gui_steps=9, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostDeadlineReconciliationTask` | 0.0: Untracked event 'Team Building Event' not mentioned in email | 提前/错误完成; gui_steps=12, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostEmailTask` | 0.0: No email sent: None | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=93, calls=2 | 0.0: No email sent: None | GUI 调用次数上限; calls=5/5, gui_steps=69 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MattermostIncidentEscalationTask` | 0.0: Incident channel 'incident-ticket-500' not found | 提前/错误完成; gui_steps=12, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostProjectHandoverTask` | 0.0: Alex has not been added to the phoenix channel | 提前/错误完成; gui_steps=20, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostProjectStatusReportTask` | 0.0: No email sent | 提前/错误完成; gui_steps=4, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostReadingGroupTask` | 0.0: Paper not mentioned or MMMU_Pro score not mentioned | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=73, calls=3 | 0.0: Paper not mentioned or MMMU_Pro score not mentioned | 提前/错误完成; gui_steps=54, calls=2 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MattermostReplyToMessageTask` | 0.0: Message not replied to harry's own earlier message | 提前/错误完成; gui_steps=5, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostResourceConflictResolutionTask` | 0.0: No email sent | 提前/错误完成; gui_steps=4, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostSendFileTask` | 0.0: Message not sent to alex privately | 提前/错误完成; gui_steps=66, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostShiftCoverageTask` | 0.0: Did not find denial reply in channel | 提前/错误完成; gui_steps=4, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `MattermostTechnicalDebtTriageTask` | 0.0: SMS not sent to Sarah (14737474173) with PaymentProcessor info | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=89, calls=2 | 0.0: SMS not sent to Sarah (14737474173) with PaymentProcessor info | 提前/错误完成; gui_steps=149, calls=5 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `MattermostVisualInstructionResponseTask` | 0.0: Contact 'Dr. Smith' not found | 提前/错误完成; gui_steps=4, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `PhotoManagementTask` | 0.0: Paris or Tokyo folder is not found | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=94, calls=2 | 0.0: Paris or Tokyo folder is not found | 提前/错误完成; gui_steps=102, calls=3 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `ReadQwen3PaperTask4` | 0.0: incorrect. Expected: 540, Got: 2160.0 | 提前/错误完成; gui_steps=0, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `ReadQwen3PaperTask5` | 0.0: incorrect. Expected: vie Latn,khm Khmr, Got: 3 | 提前/错误完成; gui_steps=0, calls=0 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `RecentTotalExpenseTask` | 0.0: Incorrect answer: 4324 (expected: 1196) | 提前/错误完成; gui_steps=18, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `ReviewPaperEmailTask` | 0.0: No email sent | GUI 调用次数上限; calls=3/3, gui_steps=108 | 0.0: Review PDF files not moved to Document/paper: ['review_draft.pdf'] | GUI 调用次数上限; calls=5/5, gui_steps=118 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `SMSManagement` | 0.0: Spam message found! | 最大运行时间/长程搜索耗尽; timeout=600s, gui_steps=97, calls=2 | 0.0: Spam message found! | 提前/错误完成; gui_steps=73, calls=3 | 存在时间耗尽证据；若 rerun 成功则说明主要是预算敏感，若 rerun 仍超时则更像长程导航/搜索能力不足。 |
| `SendFormsTask` | 0.0: No email found | GUI 调用次数上限; calls=3/3, gui_steps=9 | 0.0: No email found | 提前/错误完成; gui_steps=6, calls=1 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `SharePhotosTask` | 0.0: Wrong number of attachments: 5 (expected: 4) | 提前/错误完成; gui_steps=22, calls=1 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |
| `SuggestPaperTask` | 0.0: No pdf found | GUI 调用次数上限; calls=3/3, gui_steps=17 | 0.0: No pdf found | 提前/错误完成; gui_steps=22, calls=1 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `SumFileLinesTask` | 0.0: Incorrect answer: 3 (expected: 313) | GUI 调用次数上限; calls=3/3, gui_steps=81 | 1.0: Task completed successfully | 成功; score=1.0 | 主要受 GUI 子任务调用次数上限影响，但也常伴随错误完成。 |
| `TextArrivalTimeTask` | 0.0: No reason provided for TextArrivalTimeTask | 提前/错误完成; gui_steps=19, calls=2 | 未运行 | - | 主要是提前确信/错误完成或答案错误，不是最大步数。 |

## Scientific questions / phenomena

| phenomenon | evidence | testable question |
|---|---|---|
| 600s -> 1200s reduces timeout failures but leaves many false completions | base failures: 28 timeout; rerun: 6 timeout | Is the bottleneck long-horizon exploration or incorrect stopping criterion after partial progress? |
| `gui_task` call cap failures shift with max_calls | base cap failures: 11 with max_calls=3; rerun: 4 with max_calls≈5 | Does increasing max_calls improve success, or just allow longer failed exploration? |
| Several tasks finish with explicit success claims while native evaluator gives 0 | examples: ChangeWallpaper, MastodonChangeLanguage, SMSManagement, SuggestPaper | Can a post-action verification prompt reduce false-success termination? |
| Mattermost tasks often stop at login/request_intervention | many Mattermost failures show login-screen intervention or no email/channel action | Are credentials/tool memory/config mismatched for Mattermost, independent of Qwen reasoning? |
| Some outputs contain stale/irrelevant content | examples include “Which country has the largest land area?” in Mastodon share/location/post notice reasons | Is cross-task memory/history contaminating target selection or message composition? |
| File/search tasks often infer absence from incomplete UI search | ReviewPaperEmail, SendForms, SuggestPaper, invoice copy tasks | Does requiring filesystem/ADB verification before done improve reliability? |