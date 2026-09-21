# Oversight log

Research data for a PhD on human oversight in agentic software development.

Each row is one **oversight episode**: a point where the human corrected,
rejected or overrode something Claude produced that looked correct and was not.
Rows are appended when the correcting commit is made, and are never rewritten —
see the "Oversight capture" section of [CLAUDE.md](CLAUDE.md) for the rules and
`.claude/commands/oversight.md` for the command that writes them.

`Commit` is the short SHA of the commit carrying the `Oversight-` trailers; the
full trailers live in that commit message. `Durable` is yes when the episode
produced a new or changed rule in CLAUDE.md, a subagent definition, a test or a
lint rule.

| Date | Commit | Type | What looked right but was not | What I did | Durable |
| --- | --- | --- | --- | --- | --- |
