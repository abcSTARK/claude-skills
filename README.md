# claude-skills

**A growing collection of Claude Code skills — built on real workflows, not hypotheticals.**

Every skill in this repo started as an actual multi-hour session solving a real problem, then got generalized into something reusable. Nothing here was written speculatively; if a skill says "watch out for X," it's because X actually happened and cost someone time to debug.

---

## Install

This repo is a Claude Code plugin marketplace. Add it once, then install whichever skills you want:

```
/plugin marketplace add abcSTARK/claude-skills
/plugin install secure-file-organizer@claude-skills
```

That's it — the skill is now available in any Claude Code session.

---

## Skills

| Skill | What it does |
|---|---|
| [`secure-file-organizer`](plugins/secure-file-organizer) | Organizes a messy filesystem into a clean category structure, detects sensitive personal documents by reading file *content* (not just filenames), and routes them into a macOS encrypted vault it creates and maintains. Also handles deeper domain-specific splits (study material by subject, resumes by year, travel docs by trip). |

More skills will land here over time — same bar: field-tested first, generalized second.

---

## secure-file-organizer, in more detail

### The problem it solves

A typical "organize my Downloads folder" request isn't really a file-sorting problem — it's a judgment problem wearing a file-sorting costume. The files that are easy to categorize (movies, installers, obviously-named documents) aren't the ones that matter. The ones that matter are:

- A PDF named `Unknown-3.pdf` or `scan.12306061442000.pdf` that turns out to be a government ID or someone's academic transcript.
- Two files with the same name in different folders that *look* like duplicates but aren't — a draft vs. a final version.
- An old installer that's genuinely safe to delete vs. one that's actually a rare build you can't easily re-download.
- A filename with an accented character that mysteriously "doesn't exist" when you try to move it (it's a macOS Unicode normalization quirk, not a missing file).

This skill encodes the judgment calls, not just the mechanical sorting.

### What makes it different from "just move files by extension"

- **Reads content to detect PII, not just filenames.** Generic or misleading filenames are exactly where sensitive documents hide. The skill treats ambiguous files as worth opening, not worth guessing about.
- **Creates and maintains a real encrypted vault** (macOS `hdiutil`/sparsebundle), with a hard rule that the agent never sees or types the vault password — the user sets it through the native system dialog.
- **Only deduplicates on cryptographic proof.** Same name, same size, same vibe — none of that is enough. Only a matching checksum gets a file deleted as a duplicate, and even then, only after being shown to the user for anything beyond a few obviously-safe cases.
- **Confirms before anything destructive**, and explains its reasoning when it does.
- **Ships a deterministic dedup scanner** (`scripts/find_duplicates.py`) instead of re-deriving ad hoc `shasum` loops every time.

### Example

> "My Downloads folder is a disaster — movies, random PDFs, some ID scans, duplicate installers everywhere. Can you sort it out?"

The skill will: survey what's actually there, propose a category structure before moving hundreds of files, open ambiguous documents to check for sensitive content, stand up an encrypted vault for anything sensitive it finds, remove only checksum-confirmed duplicates, and hand back a clear summary of what moved where — plus a flagged list of anything it wasn't confident enough to decide on its own.

---

## Repo structure

```
claude-skills/
├── .claude-plugin/
│   └── marketplace.json          # marketplace manifest — lists every plugin below
└── plugins/
    └── secure-file-organizer/
        ├── .claude-plugin/
        │   └── plugin.json
        └── skills/
            └── secure-file-organizer/
                ├── SKILL.md                      # the skill itself
                ├── references/                   # docs loaded in as needed
                │   └── encrypted-vault-guide.md
                ├── scripts/                       # deterministic helper code
                │   └── find_duplicates.py
                └── evals/                          # test cases used to validate it
                    └── evals.json
```

Each future skill gets its own `plugins/<skill-name>/` directory following the same shape.

---

## Contributing / adding a new skill

1. Create `plugins/<name>/.claude-plugin/plugin.json` and `plugins/<name>/skills/<name>/SKILL.md`.
2. Add an entry to `.claude-plugin/marketplace.json`.
3. Write it from a real problem, not a hypothetical — if you haven't hit the edge case yet, you probably don't know the right instruction for it yet either.
4. Test it with realistic prompts before merging — the `evals/` folder convention in `secure-file-organizer` is a reasonable template to follow.

---

## License

[MIT](LICENSE)
