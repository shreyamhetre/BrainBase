# Evaluation questions

The 10 most important questions for the handbook, asked as role `all`. `backend/scripts/evaluate.py` reads the table below, so keep its columns as they are.

Each answer is checked for:

1. **Right source:** an expected page is among the 5 sources (hit rate), and how high (MRR).
2. **Cited:** the answer cites an expected page.
3. **Faithful:** every claim is backed by the source it cites; nothing invented (graded by GPT-4o mini).
4. **Correct:** it answers the question and meets the check below (graded by GPT-4o mini).
5. **No answer:** for questions with no expected page, it says it couldn't find this.

Expected pages are relative to https://handbook.gitlab.com/handbook/; separate several with commas.

| # | Category | Question | Expected page | Check |
|---|---|---|---|---|
| 1 | policy | How many weeks of parental leave do I get? | people-group/time-off-and-absence/leave-types | States 16 weeks of paid parental leave as the global GitLab policy for all team members, not as a US-only rule; country rules may add to it |
| 2 | policy | How does paid time off work at GitLab? | people-group/time-off-and-absence/time-off-types | Explains Flexible PTO first; country specifics only as extras |
| 3 | policy | How much is the Growth and Development Fund and what can I use it for? | people-group/learning-and-development/growth-and-development | Amount and eligible uses come from the source |
| 4 | policy | What is the expense policy for a new laptop? | finance/expenses | Laptops are provided through GitLab/IT; any amount must match the source |
| 5 | culture | What are GitLab's core values? | values | Names the six CREDIT values |
| 6 | culture | How should I use Slack at GitLab? | tools-and-tips/slack, communication/chat | GitLab's own Slack guidelines, not general Slack tips |
| 7 | engineering | How do I get my merge request reviewed and merged? | engineering/workflow/code-review | Reviewer then maintainer flow from GitLab's own guidelines |
| 8 | engineering | How do I report a security incident? | security/security-operations/sirt/engaging-security-on-call | Slack /security command or on-call SIRT; no steps that only apply to one specific app |
| 9 | design-doc | Why does secret detection use REST instead of gRPC for validity checks? | engineering/architecture/design-documents/secret_detection_validity_checks/decisions/002_use_rest_over_grpc_for_sdrs_communication | Gives the reasons from the decision record |
| 10 | no-answer | What is GitLab's four-day work week policy? | none | Says it couldn't find this; must not invent a policy |

## Not covered yet

- **Expertise** ("who should I ask about X?") and **permissions** (HR-only content) need the synthetic data from step 6.
- **Conflicting sources** (a Slack answer contradicting a newer handbook page) also need step 6.
- **Routing** questions arrive with the router in step 8.

## Results

One row per run of `python backend/scripts/evaluate.py`; full details in `eval/results/`.

| Date | Change tested | Hit@5 | MRR | Cited | Faithful | Correct | No-answer | Avg time | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-20 | baseline (rerank pool 50) | 9/9 | 0.81 | 9/9 | 9/10 | 10/10 | 1/1 | 6.1 s | By hand: correct 8/10. Q1 presents the global 16 weeks as US-only; Q8 adds an app-specific Reclaim.ai step and bunches citations. Judge missed Q1 |
| 2026-10-20 | rerank pool 50 → 30 | 9/9 | 0.81 | 8/9 | 8/10 | 10/10 | 1/1 | 4.3 s | Same sources as baseline (Q4 checked); 30% faster. Q4 wording varied: claimed the $1,500 home office stipend can include a laptop (judge caught it) |

**Known limitations** (accepted for now): global vs country-specific policies can get mixed up (Q1); answers sometimes include details for one specific app (Q8); answers vary slightly between runs even at temperature 0, so a single run can move by about one question; GPT-4o mini is a lenient judge, so failures are checked by hand.
