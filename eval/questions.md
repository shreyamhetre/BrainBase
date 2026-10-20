# Evaluation questions: first 20

Ask each question (CLI, or FastAPI at http://localhost:8000/docs) as role `all`, and check:

1. **Right source:** the expected page is among the sources, ideally cited.
2. **Correct and faithful:** every claim is backed by the source it cites; nothing invented.
3. **Citations:** claims carry [n] markers that point to the right source.
4. **No-answer questions:** it says it couldn't find this instead of guessing.

Expected pages are relative to https://handbook.gitlab.com/handbook/. More than one correct page is fine when it really answers the question.

## Handbook policy

| # | Question | Expected page | Check |
|---|---|---|---|
| 1 | How many weeks of parental leave do I get? | people-group/time-off-and-absence/leave-types | 16 weeks of paid parental leave is the **global** GitLab policy, not US-only; country rules can differ |
| 2 | How does paid time off work at GitLab? | people-group/time-off-and-absence/time-off-types | Explains Flexible PTO first; country specifics only as extras |
| 3 | What is Family and Friends Day? | company/family-and-friends-day | What it is and how it's scheduled |
| 4 | How much is the Growth and Development Fund and what can I use it for? | people-group/learning-and-development/growth-and-development | Amount and eligible uses come from the page |
| 5 | How do I refer a candidate for a job at GitLab? | hiring/referral-process | Steps to submit a referral |
| 6 | What home office equipment can I expense? | finance/procurement/office-equipment-supplies, finance/expenses | Lists allowed items; amounts must match the source |
| 7 | What is the expense policy for a new laptop? | finance/expenses | Laptops come through GitLab/IT; check any stipend amount against the source |
| 8 | What does an onboarding buddy do? | people-group/general-onboarding/onboarding-buddies | Role and responsibilities of the buddy |

## Culture and communication

| # | Question | Expected page | Check |
|---|---|---|---|
| 9 | What are GitLab's core values? | values | The six CREDIT values |
| 10 | What does "handbook first" mean at GitLab? | company/culture/all-remote/handbook-first | Document in the handbook first, then share |
| 11 | How should I use Slack at GitLab? | tools-and-tips/slack, communication/chat | GitLab's own Slack guidelines, not general Slack tips |
| 12 | What is a skip-level meeting? | leadership/skip-levels | What it is and its purpose |

## Engineering process

| # | Question | Expected page | Check |
|---|---|---|---|
| 13 | How do I get my merge request reviewed and merged? | engineering/workflow/code-review | Reviewer → maintainer flow from GitLab's own guidelines |
| 14 | How do monthly releases work at GitLab? | engineering/releases/monthly-releases | Release schedule and process |
| 15 | What does a release manager do? | engineering/releases/release-managers | Responsibilities of the role |
| 16 | How do I report a security incident? | security/security-operations/sirt/engaging-security-on-call | Slack `/security` command, on-call SIRT; no unrelated app-specific steps |

## Design documents (status matters)

| # | Question | Expected page | Check |
|---|---|---|---|
| 17 | Why does secret detection use REST instead of gRPC for validity checks? | engineering/architecture/design-documents/secret_detection_validity_checks/decisions/002_use_rest_over_grpc_for_sdrs_communication | Gives the reasons from the decision record |
| 18 | How are feature flags used in GitLab development and operations? | engineering/architecture/design-documents/feature_flags_usage_in_dev_and_ops | Mentions the design document's status if it's proposed or ongoing |

## No answer exists

| # | Question | Expected page | Check |
|---|---|---|---|
| 19 | What is GitLab's four-day work week policy? | none | Says it couldn't find this; must not invent a policy |
| 20 | How many free lunches per week do I get at the GitLab office cafeteria? | none | Says it couldn't find this (GitLab is all-remote); no made-up numbers |

## Not covered yet

- **Expertise** ("who should I ask about X?") and **permissions** (HR-only content) need the synthetic data from step 6.
- **Conflicting sources** (a Slack answer contradicting a newer handbook page) also need step 6.
- **Routing** questions arrive with the router in step 8.

## Results

Record each run here so changes can be compared.

| Date | Change tested | Right source (of 18) | Correct + faithful (of 20) | Notes |
|---|---|---|---|---|
| | | | | |
