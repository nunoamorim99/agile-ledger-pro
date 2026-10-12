---
description: Show the Agile-Ledger Pro command map — which command belongs to which phase and file
allowed-tools: Read, Grep, Glob
---
Using the **Agile-Ledger Pro** skill, print a concise overview for the user (read-only — change nothing):

1. The **phase → command → file** map (Capture → Triage → Detail → Plan → Execute → Release), naming for
   each command which file in the repo's ledger folder it reads or writes, plus the ledger-setup
   commands (`/init-ledger` · `/register-repo` · `/migrate-ledger` · `/ledger-commit`).
2. The current project's state if a ledger exists: counts of ideas, epics, stories by state, open bugs,
   and the active sprint — a one-glance "where things are."

Name the resolved ledger and repo in one line at the top (`Ledger: ~/Projetos/agile-ledger → repo-a`).

Keep it compact and scannable. If there is no ledger repo yet, explain that `/init-ledger` creates it
and `/register-repo` adds this project, and just show the command map. If the repo has a pre-2.0
`Agile-Ledger/` folder of its own, point at `/migrate-ledger`.
