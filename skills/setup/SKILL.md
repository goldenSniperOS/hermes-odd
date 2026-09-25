---
name: setup
description: "First-run setup for hermes-odd over chat: ask persona, answer style, TDD mode, Engram protocol and SOUL cleanup in one clarify call, confirm, then apply with odd_setup_apply."
version: 0.1.0
author: goldenSniperOS
license: MIT
metadata:
  hermes:
    tags: [setup, persona, onboarding, odd, gentle-ai-compatible]
    category: workflow
    related_skills: [odd-workflow]
---

# hermes-odd first-run setup

Records the user's preferences and applies them. The prompt section says
"hermes-odd setup is pending" until this runs, the user skips it, or
`/odd_setup` completes it.

## When

- Only in the **parent session**: `delegate_task` children cannot call
  `clarify`, so never hand setup to a child.
- Only when the user is **not mid-task**: at the start of a conversation, after
  a task closed, or when the user asks for it. Offer it once in one short line;
  if the user is busy or says no, drop it and do not offer again in this session.
- If the user does not want it at all, tell them `/odd_setup skip` stops the
  offer for good (only the user can type it).

## Ask everything in ONE clarify call

One `clarify` call, five questions, at most 4 choices each. Keep the order
and labels below.

The persona question has **no default and no recommended option**: the four
personas are equals and the user picks. Hermes' `clarify` always appends
" (Recommended)" to the first entry of `choices` (`tools/clarify_tool.py`
`mark_recommended`, no parameter turns it off). So the persona question is
sent **without `choices`**: its four options are written in the question
text, the user answers with a number or with their own text, and nothing is
marked. Never add "(Recommended)", "default" or "suggested" to any persona
option, and never order them as a preference.

The other four questions use `choices`; their first choice is the plugin's
default, which is why clarify's marker on it is accurate.

```json
{
  "questions": [
    {
      "question": "Persona for chat replies (all four are equal options, pick one): 1) Mentor rioplatense (voseo) · 2) Mentor neutral · 3) My own text: write it as your answer · 4) None (Hermes default). Reply 1-4, or paste your own persona text."
    },
    {
      "question": "Answer style?",
      "choices": ["Short first", "Detailed"]
    },
    {
      "question": "TDD mode for ODD work?",
      "choices": ["Per project (detect the runner)", "Strict (RED→GREEN→REFACTOR)", "Off"]
    },
    {
      "question": "Engram memory protocol?",
      "choices": ["Auto (when mcp__engram__* tools exist)", "Off"]
    },
    {
      "question": "Clean the gentle-ai blocks out of SOUL.md later?",
      "choices": ["Yes, later with a preview", "No"]
    }
  ]
}
```

Mapping to `odd_setup_apply` arguments:

| Answer | Argument |
|---|---|
| 1 / Mentor rioplatense (voseo) | `persona: "rioplatense"` |
| 2 / Mentor neutral | `persona: "neutral"` |
| 3 without text | ask once, as plain chat, for the text, then stop and wait |
| 3 with text, or any other free text | `persona: "custom"`, `persona_custom_text`: the user's text verbatim (at most 1,500 characters) |
| 4 / None (Hermes default) | `persona: "none"` |
| Short first / Detailed | `verbosity: "short"` / `"detailed"` |
| Per project / Strict / Off | `tdd_mode: "project"` / `"strict"` / `"off"` |
| Auto / Off | `engram_protocol: "auto"` / `"off"` |
| Yes, later with a preview / No | `soul_cleanup: "later"` / `"no"` |

For a closed question, an "Other" answer that is not one of the choices is
invalid: ask that question again. A blank answer means "not answered": omit
that argument.

**Fallback when `clarify` is unavailable** (non-interactive session, or the
tool is missing): send the complete list above as one plain chat message,
each question with its numbered options and the answer syntax (for example
"Reply like: 1, Short first, Strict, Auto, No"), then **stop and wait**. Never
choose, default or infer an answer.

## Confirm, then apply

1. Send **one** summary message: every answer, and, when a persona other than
   None was chosen, that it is written into `SOUL.md` as a single hermes-odd
   block at the top, with a backup of the file first, and nothing else in
   `SOUL.md` changes. For None: an existing hermes-odd block is removed.
   Mention that it takes effect in the next new session.
2. Ask for explicit confirmation of the SOUL.md change (yes/no), then stop
   and wait.
3. Yes: call `odd_setup_apply` with the answers and
   `apply_persona_to_soul: true`.
4. No: call `odd_setup_apply` with the other answers and
   `apply_persona_to_soul: false`; SOUL.md stays untouched. Tell the user
   `/odd_setup persona <id>` previews and applies it later.
5. Relay the tool's `summary` and `note` as they are, including any warning
   (for example two personas coexisting). On an `error`, show it, fix only
   what it names (for example a too long or blocked own text) and ask again.

## Answers that arrive later

- The Engram protocol answer is stored now; the protocol itself activates
  with T9b. Say so if asked.
- The SOUL cleanup answer is stored only; the cleanup (with preview and
  backup) arrives with T9b. Never edit gentle-ai blocks yourself.
- The TDD mode appears in the prompt section as a `TDD mode:` line from the
  next new session; `hermes-odd:odd-workflow` section 6 explains it.

## Commands the user can type

`/odd_setup` (status), `/odd_setup skip`, `/odd_setup reset`,
`/odd_setup persona <rioplatense|neutral|custom|none>` (dry-run preview;
add `confirm` to write), `/odd_setup tdd <off|strict|project>`,
`/odd_setup engram <on|off>`, `/odd_setup verbosity <short|detailed>`.
In the CLI the hyphen form: `/odd-setup`.
