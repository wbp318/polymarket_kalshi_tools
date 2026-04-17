# Claude Code Skills

Skills are pre-packaged capabilities in Claude Code — bundles of instructions + behavior for specific tasks. Invoke by typing `/skillname`, or Claude can invoke them itself when the task matches.

## What /init does

Analyzes the codebase and generates (or regenerates) a `CLAUDE.md` file. That file is loaded into future Claude Code sessions when they open this project, so they hit the ground running without me re-explaining architecture every time.

## Skills available in this environment

| Skill | What it does |
|---|---|
| `/init` | Generates or refreshes `CLAUDE.md` — the onboarding doc for future Claude sessions |
| `/review` | Reviews a pull request (uncommitted changes on current branch) |
| `/security-review` | Security-focused review of pending changes |
| `/simplify` | Reviews recent code changes for reuse, quality, efficiency — offers to fix what it finds |
| `/loop 5m /somecommand` | Runs a command repeatedly on an interval (e.g., poll a deploy) |
| `/schedule` | Creates scheduled remote agents — cron for Claude Code |
| `/less-permission-prompts` | Scans recent transcripts, auto-generates a permission allowlist in `.claude/settings.json` so Claude prompts you less often |
| `/update-config` | Modifies `.claude/settings.json` — permissions, env vars, hooks |
| `/keybindings-help` | Customize keyboard shortcuts |
| `/claude-api` | For building / debugging apps using the Anthropic SDK |

## How to invoke

Two ways:

1. **Type `/skillname` in the chat** — Claude runs the skill directly.
2. **Let Claude invoke it for you** — if the task matches a skill's description, Claude will pick it up. (That's the animation you see when a skill launches.)

## Which ones to try first

- **`/less-permission-prompts`** — high-value early on. After a few sessions of approving lots of `git`, `pip`, and `Edit` calls, this scans the transcripts and proposes a focused allowlist. Fewer approval prompts → faster iteration. Run it after you've done a handful of sessions so it has data to work with.
- **`/review`** — before pushing changes you're unsure about, especially for multi-file edits.
- **`/init`** — when the codebase structure shifts enough that the existing `CLAUDE.md` is drifting from reality.
- **`/simplify`** — after a flurry of edits, to catch accidental duplication or over-engineering.

## Skills vs agents vs tools

These are three different Claude Code concepts — easy to conflate:

- **Tools** are low-level capabilities (Read, Edit, Bash, Grep, Write). Claude uses them constantly; they're the primitives.
- **Agents** are delegated sub-tasks. Claude spawns one with a focused prompt and gets a result back. Useful for parallel exploration, isolated research, or protecting the main conversation from noisy tool output.
- **Skills** are pre-built task *recipes* — a skill bundles specific instructions for a specific job. Invoked by slash command, or Claude picks one up when the task matches its description.

## Where skills live

Skills in this environment are defined globally by Anthropic and surfaced to Claude via the system prompt. You can also author your own project-specific skills (custom slash commands) inside the project's `.claude/` directory — but the ones listed above are the built-in set.
