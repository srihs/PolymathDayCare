---
description: Record an oversight episode - commit the current correction on its own with Oversight- trailers and log it
argument-hint: [anything you already want to say about the episode]
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*), Bash(git rev-parse:*), Read, Edit, AskUserQuestion
---

The user has just caught something you produced that looked correct and was not.
Record it as an **oversight episode** for their PhD research, following the
"Oversight capture" rules in CLAUDE.md.

What they said about it, if anything: $ARGUMENTS

Do this in order:

1. **Look at the change.** Run `git status --short` and `git diff` (plus
   `git diff --staged`) so you can describe the correction accurately. If the
   working tree is clean and nothing is staged, say so and stop - there is
   nothing to commit.

2. **Fill in the four trailer values.** Take whatever the user already gave you
   in `$ARGUMENTS` and infer what you safely can from the diff and the
   conversation. For every value still missing or uncertain, ask with
   AskUserQuestion - do not guess, because a false entry is worse than a missing
   one. Ask for them in one call, offering your best reading first:
   - `Oversight-Type`: one of architecture, business-rule, correctness,
     security, scope, data-model, performance, dependency
   - `Oversight-Trigger`: what you produced that looked correct and was not, one
     sentence
   - `Oversight-Action`: what the user did about it, one sentence
   - `Oversight-Durable`: yes if this episode produced a new or changed rule in
     CLAUDE.md, a subagent definition, a test or a lint rule; no otherwise

3. **Stage the current change** with `git add -A`, but leave out anything
   unrelated to this correction, and never stage secrets, database dumps or
   files git is told to ignore. This commit is the correction alone - if
   unrelated feature work is in the tree, ask the user before including it.

4. **Commit** with a short subject line naming the correction, a blank line, a
   one-or-two sentence body if it helps, then a blank line and exactly these
   trailers last, in this order:

   ```
   Oversight-Type: <value>
   Oversight-Trigger: <value>
   Oversight-Action: <value>
   Oversight-Durable: <value>
   ```

   Write the message via a file (`git commit -F <file>`) so the trailers keep
   their line breaks. Keep each trailer on one line. Do not add any other
   trailer to this commit, and never amend, squash, rebase or force-push it
   afterwards.

5. **Append the row to `OVERSIGHT_LOG.md`**, at the end of the table, using the
   committed SHA:

   `| YYYY-MM-DD | <short SHA> | <type> | <trigger> | <action> | <durable> |`

   Escape any `|` in the text as `\|` so the table stays intact. Do not touch
   existing rows. Commit this row itself in a follow-up commit (message e.g.
   `Log oversight episode <short SHA>`) with no `Oversight-` trailers, since
   logging is not itself an episode.

6. **Print the result** to the user: the full commit SHA from
   `git rev-parse HEAD` of the episode commit, its subject line, and the row you
   appended, so they can see it worked.
