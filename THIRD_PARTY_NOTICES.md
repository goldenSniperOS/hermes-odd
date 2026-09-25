# Third-party notices

hermes-odd is MIT-licensed (see [LICENSE](LICENSE)). Parts of it are adapted
from the MIT-licensed projects below. Their copyright and permission notices
are reproduced here, as the MIT License requires, for every derived portion.

Each derived file carries `derived-from` markers naming the upstream
repository, the pinned commit and the upstream source path. hermes-odd is an
independent community project and is not affiliated with, sponsored or
endorsed by the upstream authors; Gentle AI™ and Engram™ are trademarks of
Alan Buscaglia, and gentle-shell and gentle-pi are trademarks of Alan
Buscaglia. See the README for the full notice.

## gentle-ai

- Project: Gentle AI by Gentleman Programming (Alan Buscaglia)
- URL: https://github.com/Gentleman-Programming/gentle-ai
- Copyright: Copyright (c) 2025 Gentleman Programming
- Pinned commit: f182ea2018a6399f5d1b6557cf36d71a3df0f723 (v3.7.0 on `main`; the
  `v3.7.0` tag points at 6dee8f8, same derived sources, see upstream/SUPPORTED.md)
- License: MIT

Files in this repository derived from gentle-ai:

- `hermes_odd/personas.py` (persona behavior rules condensed, in hermes-odd's own
  words and without identity or branding, from
  `internal/assets/hermes/persona-gentleman.md` and
  `internal/assets/hermes/persona-neutral.md`)
- `hermes_odd/prompt.py`
- `skills/codegraph/SKILL.md` (the CodeGraph guidance of
  `CodeGraphGuidanceMarkdown` in
  `internal/components/communitytool/codegraph_guidance.go`, condensed in
  hermes-odd's own words for Hermes and the upstream `codegraph` CLI)
- `skills/engram-protocol/SKILL.md` (the Engram™ memory protocol, full
  variant of `internal/assets/engram/protocol.md`, condensed in hermes-odd's
  own words and bound to Hermes' `mcp__engram__*` tool names)
- `skills/odd-delegation/SKILL.md`
- `skills/odd-feature-tracking/SKILL.md`
- `skills/odd-workflow/SKILL.md`
- `skills/rdd-review/SKILL.md`
- `upstream/odd-routing-hermes.canonical.md` (verbatim render of
  `agentguidance.RenderRouting(model.AgentHermes)` from
  `internal/components/agentguidance/routing.go`, vendored for drift tracking)

License text:

```text
MIT License

Copyright (c) 2025 Gentleman Programming

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## gentle-shell

- Project: gentle-shell (npm package `gentle-pi`), maintained by Alan
  Buscaglia / Gentleman Programming
- URL: https://github.com/Gentleman-Programming/gentle-shell
- Copyright: Copyright (c) 2025 Mario Zechner
- Pinned commit: 4d702a47a31eade9ea197d9280ba1d0afe8b93f4 (v3.7.0+16,
  `git describe`: v3.7.0-16-g4d702a4)
- License: MIT

Files in this repository derived from gentle-shell:

- `hermes_odd/personas.py` (persona rules condensed from
  `GENTLEMAN_PERSONA_PROMPT` and `NEUTRAL_PERSONA_PROMPT` in
  `extensions/gentle-ai.ts`)
- `hermes_odd/prompt.py`
- `skills/odd-delegation/SKILL.md`
- `skills/odd-feature-tracking/SKILL.md`
- `skills/odd-workflow/SKILL.md`
- `skills/rdd-review/SKILL.md`
- `skills/rdd-review-lenses/SKILL.md` (4R lens charters condensed from
  `assets/agents/review-{risk,resilience,readability,reliability}.md` and
  `assets/chains/4r-review.chain.md`)

License text:

```text
MIT License

Copyright (c) 2025 Mario Zechner

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Hermes Agent

- Project: Hermes Agent by Nous Research
- URL: https://github.com/NousResearch/hermes-agent

Hermes Agent is the host platform. hermes-odd uses its public plugin API
(`register(ctx)`, `register_system_prompt_section`, `register_skill`,
`register_command`, `register_tool`, `get_config`/`set_config`, `state`) and copies no Hermes Agent code, so no Hermes Agent
license notice is reproduced here.
