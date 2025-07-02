# bookmarks-organiser

A personal utility to organise my [Pinboard](https://pinboard.in) bookmarks.

It takes a [JSON export](https://pinboard.in/howto/#export) of bookmarks as input, runs a series of transformations as part of a workflow, and outputs the updated bookmarks in the same JSON format.

## Usage

``` shell
nix develop
uv run prefect server start --background
uv run bookmark-processor <input.json> <output.json>
```

## Workflow Steps

The tool runs the following tasks and transformations in a [`prefect`](https://github.com/PrefectHQ/prefect) workflow:

1. **Liveness check**
  * Checks whether the URL is still accessible, and adds a "not-live" tag if the liveness check fails.
  * Attempts a GET request first, with some timeout and retry logic.
  * If this fails, falls back to a headless browser using [Playwright](https://github.com/microsoft/playwright).
2. **Extract content**
  * Raw HTML source isn't suitable for text processing, so we try and clean this up somewhat.
  * Uses [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) to perform basic stripping.
3. **Summarises article content**
  * Auto-summarisation of the article content, to be used as the bookmark description.
  * Uses the [`llm`](https://github.com/simonw/llm) Python API to call a configured LLM.
4. **Suggest tags**
  * Auto-suggest tags based on the article content.
  * Uses `llm` as above.
5. **Lint tags**
  * Ensure bookmarks have at least one category (see [category definitions](https://github.com/cameronyule/bookmarks-organiser/issues/3#issuecomment-3019019627)) in their tags.
  * Allows control of tags through allow/block lists.

## Development

This project served as an opportunity to spend more time developing with LLMs.

Tooling used included:

* [Aider](https://aider.chat)
* [Google Gemini 2.5 Pro](https://deepmind.google/models/gemini/pro/)
* [Google Gemini 2.5 Flash](https://deepmind.google/models/gemini/flash/)

High-level workflow:

1. Iterated with LLM to define [PLAN.md](docs/PLAN.md).
1. Switched to a new git branch.
1. Instructed the LLM to follow the plan.
1. Heavily iterated with the LLM to achieve functionality.
1. Committed manually when necessary.

If you review the [commit history](https://github.com/cameronyule/bookmarks-organiser/commits/main/), commits from Aider have the `Co-authored-by` trailer in the commit message to distinguish from manual commits I've made alongside working with the LLM. I'd typically rebase commits on a local branch prior to merging (e.g., [this workflow](https://rustc-dev-guide.rust-lang.org/git.html#standard-process)) but here I feel it's valuable to preserve the commit history generated as I was working with Aider. For those unfamiliar with Aider, it [auto-commits](https://aider.chat/docs/config/options.html#--auto-commits) after each change by default.

Lessons learned:

* **Start with a plan**
  * This allowed me to think about my requirements and implementation constraints.
  * Initial progress by the LLM was rapid.
  * The plan needs updated as requirements evolve, else the LLM gets confused.
* **Tool usage is essential**
  * Enables removing yourself from the change → test → iterate loop.
  * Having the LLM (or you!) write tests therefore accelerates progress.
  * Aider doesn't support [MCP](https://modelcontextprotocol.io) ([yet](https://github.com/Aider-AI/aider/pull/3937)), but can [still use tools](https://aider.chat/docs/usage/lint-test.html).
* **Define conventions**
  * The LLM had no point of reference as to which libraries to use.
    * E.g., it would take dependencies on libraries that I didn't want it to use.
    * E.g., it would take dependencies which were unnecessary.
  * The LLM had no point of reference as to coding style.
    * Defining your preferred conventions is likely helpful, but:
    * Auto formatting via tool usage (`nix fmt` in this repository) is preferable.
  * Read more on [defining conventions](https://technicalwriting.dev/ai/agents/#implementation) for agents, including which tools are available.
    * The format for doing this is tool specific currently - e.g., Aider [recommends `CONVENTIONS.md`](https://aider.chat/docs/usage/conventions.html) but is flexible.
* **Context management**
  * While writing good prompts still matters, ensuring the LLM has adequate context is also important.
    * Tools have different approaches to this - e.g., Aider has its [repository map](https://aider.chat/docs/repomap.html) and manual [/add](https://aider.chat/docs/usage/commands.html) command.
  * Regardless of tooling, providing adequate context to requested changes matters for the quality of result.
* **Code review is essential**
  * As impressive as current generation LLMs are, they still make mistakes.
    * Tool usage can eliminate syntax errors, but logical errors can persist.
    * Logical errors in tests can be particularly problematic, as the LLM uses those to justify it's implementation decisions.
  * Undesirable changes are also surprisingly common.
    * E.g., the LLM is tasked with making a change, but refactors other code unnecessarily and without being asked.
    * I've had an LLM swap out dependencies (e.g., Selenium for Playwright) in the middle of an unrelated change.
  * Budget time for reviewing code thoroughly, and give feedback to the LLM.
    * Update your conventions each time you identify undesirable behaviour.
* **Human⭤LLM workflow**
  * Further to the above point on code review, it's important to think about the workflow between you and the LLM.
  * Aider auto-commits after each change by default, so there's a natural point for code review to occur.
  * In addition to reviewing code, it's also important to review progress against your stated plan or goals.

And a few notes and caveats:

* **Model usage**
  * The decision to use the Gemini models was influenced by looking for a balance of cost and performance.
    * LLM leaderboards (e.g., [Aider polygot](https://aider.chat/docs/leaderboards/)) generally have 2.5 Pro near the top and 2.5 Flash around the mid-point.
    * LLM usage (e.g., [OpenRouter Programming](https://openrouter.ai/rankings/programming?view=week))) generally has 2.5 Pro and 2.5 Flash at or near the most popular models.
  * Gemini 2.5 Flash was capable with sufficient prompting and context. 2.5 Pro was able to solve some problems where 2.5 Flash was struggling.
  * I have no point of comparison in similar models, and would be interested in gaining experience with:
    * Claude Opus 4 and Claude Sonnet 4
    * DeepSeek R1 and DeepSeek V3
    * o3/o4-mini and GPT-4.1
  * The approach of [separating code reasoning and editing](https://aider.chat/2024/09/26/architect.html) seen in Aider's `--architect` mode seems sensible, and in line with my original aim of finding a balance between performance (e.g., the more expensive models such as 2.5 Pro, Opus 4, o3) and cost (e.g., middle-ground models like 2.5 Flash, Sonnet 4, GPT-4.1).
* **Tooling**
  * The decision to use Aider was due to a combination of factors:
    * It's model agnostic. Tools tied to a specific model provider may be powerful, but limiting.
    * It's open-source.
    * I didn't want to change my editor, so a terminal-based tool was a good fit.
    * I wanted to start with a tool with a slower iteration cycle, before trying more fully autonomous agents.
  * For future exploration, I'm interested in gaining experience with tools which:
    * Integrate with my editor: [aidermacs](https://github.com/MatthewZMD/aidermacs) and [emigo](https://github.com/MatthewZMD/emigo).
    * Could replace my editor: [Cursor](https://cursor.com), [Windsurf](https://windsurf.com), and [zed](https://zed.dev).
    * Coexist with my editor: [Amp](https://sourcegraph.com/amp), [Claude Code](https://github.com/anthropics/claude-code), [Gemini CLI](https://github.com/google-gemini/gemini-cli) and [OpenAI Codex](https://github.com/openai/codex).
