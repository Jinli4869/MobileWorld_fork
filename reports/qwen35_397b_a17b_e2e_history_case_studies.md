# qwen3.5-397b-a17b GUI-only E2E history / early-stop case studies

Analyzed run: `traj_logs/GUI_only_e2e_qwen35_397b_a17b`

## Mechanism

The E2E agent does have per-step history, but it is not a structured working memory.

Relevant implementation:
- `src/mobile_world/agents/implementations/general_e2e_agent.py:239`: default `history_n_images = 3`.
- `src/mobile_world/agents/implementations/general_e2e_agent.py:282-300`: older screenshots are replaced with text `(Previous turn, screen not shown)`.
- `src/mobile_world/agents/implementations/general_e2e_agent.py:344-357`: all previous assistant responses are retained as text.

So the failure mode is not "no memory". It is:

1. Old visual observations disappear after 3 image turns.
2. The only durable memory is the model's own free-form `Thought` text.
3. There is no structured scratchpad for extracted facts, completed subgoals, candidate lists, file names, recipients, selected posts, or failed attempts.
4. Long tasks therefore depend on whether the model wrote precise facts into prior thoughts. If it wrote a vague or wrong thought, later steps inherit that error.

## Summary judgment

| question | answer |
|---|---|
| Is per-step history defect a real contributor? | Yes, for long compositional tasks. It causes redundant scanning, re-checking, wrong carry-over of extracted facts, and some max-step failures. |
| Is it the only or dominant cause? | No. There are also pure navigation/action failures, UI affordance failures, service/login failures, and premature self-certification. |
| Why does the model end early? | Usually because it maps "I saw/attempted something plausible" to `status complete`/`answer`, without evaluator-aware verification. The prompt says `answer` terminates and allows `status complete` when the model thinks the task is done, but there is no mandatory final checklist against task-native success conditions. |

## Case Studies

| case | task | observed trace | history/memory diagnosis | early-stop / extra-step mechanism |
|---|---|---|---|---|
| A | `LocalFileManagementTask2` | Steps 36-42 rename `archive.zip` to `old_files.zip`; steps 43-50 repeatedly scroll down looking for old files to delete. Last thought: "Found 2023 files at the bottom. Need to continue scrolling..." Score 0: `06_music_collection_20240929.zip` not deleted. | Strong history defect. The task needs a persistent checklist of files older than 1 year, selected/compressed files, and remaining deletion targets. The trace only carries vague text like "Found more 2024 files"; older screenshots with filenames are hidden after 3 image turns. | This produced extra steps and max-step termination. The agent remembered the high-level phase "delete originals" but lost a concrete target list, so it kept scrolling to re-discover evidence instead of acting on a maintained checklist. |
| B | `GraduationMassEmailTask` | Steps 1-20 search UF calendar. Step 20 infers grades due week as Apr 28-May 4 from final exams/grade availability, not a directly observed due date. Steps 34-35 extracts recipients. Steps 39 and 41 input the same recipient list twice. Step 45 sends generic body: "Don't forget about this year's graduation party! More details coming soon." Step 47 declares success. Score 0. | Mixed. The model successfully carried recipient names/emails across steps, so history is not absent. But the extracted calendar fact was an inference, not stable evidence, and the email body requirement was not preserved as a checklist while composing. Duplicate recipient entry shows UI-state/history mismatch. | Early stop happens because the final thought enumerates subgoals as complete, even though the sent email content likely does not satisfy the evaluator. The model trusted its narrative summary over task-specific verification. |
| C | `RecentTotalExpenseTask` | Step 9 observes visible order amounts `829`, `184`, and `2888`; then keeps scrolling. Step 14 opens filter, steps 15-16 select "recent 1 month"; step 17 answers `0`. Score 0, expected `1196`. | Strong evidence of working-memory/data aggregation failure. The model saw candidate amounts but did not maintain a durable table of date/amount/order eligibility. Later a UI filter result overrode earlier observations without reconciliation. | Extra scrolling and wrong answer come from no structured accumulator. The model should have maintained `seen_orders = [...]`, then verified dates. Instead it relied on the latest screen and answered prematurely. |
| D | `MastodonAddBookmarkTask` | Steps 6 and 8 appear to bookmark two `#cats` posts. Steps 32-38 repeatedly scroll through later posts, repeatedly saying they are not `#cats`. Step 39 claims it found and bookmarked 2 posts and finishes. Score 0: expected bookmark IDs not found. | Likely history plus action-verification defect. The task needs persistent state: which post IDs/content were bookmarked, whether the tap actually toggled bookmark, and which posts remain. Older screenshots/actions disappear visually; only the model's claim remains. | Early stop occurs because the agent treats "I clicked bookmark earlier" as proof. It never re-opens bookmarks or verifies native state before ending. |
| E | `CheckGithubInfoTask` | Steps 9-50 repeatedly scroll up/right looking for GitHub stars/contributors. Last 15 actions: 8 `scroll right`, 7 `scroll up`. Score 0: no email found. | This is more navigation/search failure than memory loss. However, history contributes to wasted steps because it records the same intention repeatedly ("stars are near top/right") without storing "this attempt failed; try another route". | Max-step failure from repeated confirmation/search loop. A structured failed-attempt memory could force strategy changes: browser find, desktop site, repository About pane, or search query for contributors. |
| F | `DownloadSendReceiptTask` | Finds receipt email, downloads attachment, composes email, attaches receipt. Then repeatedly clicks the attachment trying to read total, asks user for amount at step 40, waits until step 50. Score 0: no email found. | Not primarily past-history loss. The model remembers the overall workflow, but lacks a reliable way to inspect/read the attachment after attaching it. | Extra steps come from unresolved information dependency. The agent should either inspect receipt before composing or use a tool/state check; instead it gets stuck waiting for user input and hits max step. |
| G | `CheckRegistrationTask` | Step 2 opens "Putnam Registration" email. Step 3 answers that registration is pending final confirmation. Score 0: `No email found`. | Not a history length issue; it is a semantic/evaluator mismatch. The model found a related email but did not distinguish "registration confirmation" from "pending registration". | Early stop because it treats a related email as sufficient. The task required a stricter condition; a final checklist should require the exact confirmation signal before answering. |

## Pattern Table

| pattern | symptoms in this run | likely fix to test |
|---|---|---|
| Lost concrete visual facts | File lists, order amounts, post identities, dates become vague summaries after older screenshots are hidden. | Add a structured per-task scratchpad with fields like `facts`, `targets`, `completed`, `failed_attempts`, `pending_verification`. |
| Repeated re-discovery loops | Repeated scroll/click actions in `CheckGithubInfoTask`, `LocalFileManagementTask2`, `MastodonNewFilterTask`, `ReadQwen3PaperTask2`. | Add loop detection: if same action/intent repeats N times, require a different strategy. |
| Narrative completion without state verification | `GraduationMassEmailTask`, `MastodonAddBookmarkTask`, `CheckRegistrationTask`, `RecentTotalExpenseTask`. | Before `answer/status complete`, require explicit checklist against task goal and observable/native evidence. |
| Information collection not separated from execution | Agent gathers data and immediately moves on without durable record; later composing/sending uses wrong or missing facts. | Split prompt into phases: collect facts -> verify facts -> execute -> verify final state. |
| UI-only bottleneck for hidden state | Email sent, file copied, bookmark toggled, receipt total, GitHub stats are hard to verify from screenshots alone. | Allow narrow read-only verification tools or evaluator-relevant state probes, while preserving native scoring. |

## Bottom line

For `GUI_only_e2e_qwen35_397b_a17b`, the per-step history design is a material contributor to failure in long, coherent tasks, especially those that require collecting information and using it later. The strongest evidence is not "the model forgot everything"; it is that the model keeps only self-written textual claims after old screenshots disappear, and those claims are often too vague or wrong to support later execution.

The early-ending failures are mostly a separate but related problem: the model trusts its own narrative of completion. It often issues `answer` or `status complete` after plausible progress, without verifying the exact MobileWorld-native success condition.
