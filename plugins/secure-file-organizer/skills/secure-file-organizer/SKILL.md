---
name: secure-file-organizer
description: Organizes a messy filesystem (Downloads, Documents, Desktop, or any directory someone describes as cluttered) into a clean, logical category structure by file type, project, or subject — while actively detecting sensitive personal documents (government IDs, tax/financial records, payslips, credentials, passwords, medical or academic records) by reading file *contents*, not just filenames, and routing them into a dedicated encrypted vault that this skill creates and maintains. Also handles deeper, domain-specific reorganization of an already-categorized folder (e.g. splitting a study-materials folder by subject/language/framework, splitting a resume folder by year, splitting a travel folder by trip). Use this skill whenever someone asks to clean up, declutter, organize, tidy, or "sort out" their Downloads/Documents/Desktop/home folder; wants to find and secure sensitive or PII documents scattered across their filesystem; mentions duplicate files cluttering a folder; asks for a more specific or deeper reorganization of a folder that's already loosely categorized; or asks how to maintain an encrypted vault of personal documents — even if they never say the words "organize" or "PII."
---

# Secure File Organizer

This skill turns an unstructured pile of files into a maintained, categorized structure, and treats "finding sensitive documents" as a first-class part of organizing — not an afterthought. It was distilled from a real multi-hour session reorganizing a genuinely messy home directory (450+ loose files in Downloads, scattered code projects, personal IDs sitting next to movie downloads), so every rule here exists because something specific went wrong or right when it was skipped.

The core tension this skill manages: **organizing is mostly mechanical, but a meaningful fraction of files need actual judgment** — is this a duplicate or a different draft? Is this PDF a boarding pass or someone else's academic transcript? Did that `mv` fail because the file doesn't exist, or because of a filename encoding quirk? Treat every "obviously fine to automate" step as automatable, and treat every ambiguous one as worth slowing down for.

## Process overview

1. **Survey before acting.** List directory contents, get item counts, sample file types (`file`, extensions, sizes). Don't start moving things based on assumptions about what's there — actually look. A directory named "Downloads" can contain anything from installers to a decade of personal documents.

2. **Plan and confirm the target structure before large reorganizations.** If you're about to touch hundreds of files or restructure multiple top-level folders, propose the category structure first and get sign-off before executing. This isn't bureaucracy — it's cheaper to redirect a plan than to undo five hundred file moves. For small, obviously-safe operations (a handful of files, one clear category), just do it.

3. **Derive categories from what's actually present, don't assume a fixed taxonomy.** A software developer's Downloads folder needs different categories than a student's. Common buckets that tend to recur: code projects/repos, media (movies/music/screenshots/wallpapers), documents by type (resume, travel, receipts), study/reference material, installers, and sensitive personal documents. Build the actual structure from what you find, not from a template.

4. **Detect sensitive content by reading files, not by pattern-matching names.** This is the single most important habit in this skill. Obvious filename signals (`aadhar`, `passport`, `ssn`, `tax`, `bank_statement`, `payslip`) catch maybe half of what matters. The rest hides behind generic or misleading names — a browser-exported `Unknown-3.pdf`, a `Report.pdf` that's actually fine, a `scan.12306061442000.pdf` that turns out to be an onboarding checklist, an `India NH Checklist.pdf` that's actually someone else's academic transcripts. When a file's purpose isn't clear from its name:
   - Open it (PDF/image viewers, or extract text/metadata for other formats) and actually look at the content.
   - Treat files with the same odd naming pattern as a likely batch (same random-UUID style name, same "Unknown-N" sequence) as needing the same scrutiny, even if you only fully read one of them.
   - If content reveals identity documents, financial records, credentials, or any other person's sensitive PII (not just the user's own), route it to the vault — third-party PII deserves the same care.
   - **Never paste decoded PII content into your own output or logs.** Determine the *category* (identity doc, financial record, credential) and act on that — don't transcribe account numbers, ID numbers, or personal details into your response. If an automated safety check blocks a command for handling PII, that's a sign to slow down and verify rather than a bug to route around.

5. **Create and use the encrypted vault correctly.** See `references/encrypted-vault-guide.md` for full mechanics. The essentials:
   - Create with `hdiutil create -size <N>g -fs APFS -encryption AES-256 -type SPARSEBUNDLE <path>`.
   - **The passphrase must never be typed by the agent.** Give the user the exact command and have them run it themselves in their own terminal session — macOS pops a native password dialog that the agent never sees. Don't try to script around this.
   - Verify it's genuinely encrypted with `hdiutil info | grep image-encrypted` (expect `TRUE`). Don't rely on `diskutil info` against the *mounted* volume for this check — it reports `Encrypted: No` for the already-unlocked view, which is expected and not a problem; this has caused real confusion before.
   - Stage sensitive files in a clearly-named pending folder if the vault isn't mounted yet (e.g. `_Pending_Secure/`), then do one mount → move-everything-in → unmount pass. Don't leave PII sitting unencrypted on disk longer than necessary, and don't leave the vault mounted longer than the task needs — anything with disk access can read it while unlocked.
   - Always eject (`hdiutil detach`) when done.

6. **Deduplicate only on verified exact matches.** Same filename, same-looking content, similar file size — none of that is enough on its own. Compute a checksum (`shasum`, or use `scripts/find_duplicates.py` for scanning a whole tree at once) and only treat files as duplicates when the hashes match exactly. Near-duplicates (a draft vs. a final version, a re-export with slightly different compression) get kept side by side with a disambiguating suffix like `(downloads-copy)` or `(earlier draft)` — never silently pick one and discard the other. When you do find and remove confirmed duplicates, list what you're removing and why before doing it for anything beyond a handful of obviously-safe cases.

7. **Watch for the filename-encoding trap.** On macOS (APFS/HFS+), typed filenames containing accented or special characters can fail to match actual on-disk filenames due to Unicode normalization differences (NFC vs. NFD) — `mv` or `ls` on a literally-typed name returns "No such file or directory" even though the file is right there and shows up in a directory listing. If a file operation fails this way on a name you can see in `ls` output, don't assume the file vanished — retry using shell glob expansion (`for f in *; do ... "$f"; done`) instead of typing the name out, which sidesteps the normalization mismatch entirely.

8. **Confirm before destructive or judgment-heavy actions.** Bulk deletions, especially of things like old installers or "probably junk" files, should be presented as a reasoned list (what, and why) before executing — not silently auto-deleted under a broad instruction like "delete what's not needed." Exact-duplicate removal (step 6) is the one case safe enough to proceed with transparency rather than a stop-and-ask, since the checksum proof is objective.

9. **Report back clearly.** End with: what moved where (grouped by category, not file-by-file), what got deleted and why, what's flagged for the user's own judgment (ambiguous items you didn't want to guess on), and — if a vault was created or used — a reminder of its location and current lock state.

## Deeper, domain-specific reorganization

After an initial organize pass, someone may ask to go further within one category — "organize my study material by subject," "split my resume folder by year," "break travel docs down by trip." Apply the same discipline at the smaller scale:

- **Read before categorizing**, especially for generic-named files. A file named `India NH Checklist.pdf` sitting in a travel folder might not be a checklist at all.
- **Expect merge artifacts.** When content from multiple sources gets combined (e.g. files moved in from an old folder *and* from a cloned repo that happened to use the same top-level folder name), you'll often find accidental nesting like `Java/Java/Core/...` — this happens when a folder gets moved into a new folder of the same name. Checksum everything inside before flattening; don't assume nested duplicates are safe to delete without verifying.
- **Infer the grouping dimension from the content**, not just the filename. Ticket/booking PDFs often need to be opened to tell which trip they belong to — flight dates and routes in the content are more reliable than the filename.
- **Surface anything genuinely new you find.** Reading content for categorization purposes sometimes reveals things the user didn't know were there (an extra trip buried in "misc tickets," a document that isn't theirs). Call these out explicitly rather than quietly filing them away.

## Bundled resources

- `references/encrypted-vault-guide.md` — full command reference for creating, mounting, adding to, and maintaining the encrypted vault. Read this when setting up or working with the vault.
- `scripts/find_duplicates.py` — scans a directory tree and reports groups of byte-identical files (by size pre-filter, then SHA-256). Use this instead of manually running `shasum` pair-by-pair when checking more than a couple of suspected duplicates.

## Portability beyond Claude Code

The categorization, content-based PII detection, dedup, and confirmation discipline in this skill are platform-agnostic and apply equally well if you're operating as a different coding agent without access to the Skill mechanism — just read this file as a standing set of instructions. The one OS-specific piece is the vault itself (`hdiutil`/`sparsebundle` is macOS-only); on Linux or Windows, substitute an equivalent encrypted-container tool (e.g. VeraCrypt, LUKS) and have the user set the passphrase through its native, non-scriptable prompt for the same reason — the agent should never see or type the vault's password.
