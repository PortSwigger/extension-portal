# Submitting to the BApp Store programmatically

This repository is the submission portal for Burp Suite extensions. It accepts
exactly two kinds of issue, and an automated pipeline reads each one, validates
it, and opens a review ticket.

If you are an AI agent submitting on an author's behalf, follow this document
exactly. The pipeline parses the issue body literally — it does not interpret
prose — so an issue that reads correctly to a human but does not match the
format below will be rejected.

## The three rules

1. **Copy the body templates below character for character.** Each field is a
   `### ` heading on its own line, then a blank line, then the value. Replace
   only the placeholder values. Do not rename, reorder, merge, or drop headings,
   and do not add any of your own.
2. **The first heading decides what you are submitting.** `### Extension URL`
   means a new extension; `### Pull request URL` means an update to an extension
   already on the BApp Store. An issue with neither is closed unprocessed,
   because we cannot tell what it is.
3. **The title is the extension name.** It becomes the name of the review
   ticket verbatim. Use the extension's own name — `Autorize`, not
   `Submit new extension: Autorize` or `[Submission] Autorize`. For an update,
   use the name the extension already has on the BApp Store.

Do not pass `--type`. GitHub only lets users with push access to this
repository set an issue type, and **silently drops it** for everyone else, so it
is not something you can get right. We read the headings instead and record the
type ourselves.

## New extension submission

```bash
gh issue create \
  --repo PortSwigger/extension-portal \
  --title 'Your Extension Name' \
  --body-file submission.md
```

`submission.md`:

```markdown
### Extension URL

https://github.com/owner/repository

### Version number

1.0.0

### Select additional compatible products and features

- [ ] Community
- [ ] DAST
- [ ] Burp AI

### Author display name

Author Name

### Contact details (optional)

_No response_

### Discord username (optional)

_No response_

### I confirm that the following is true:

- [X] I have permission from all relevant persons to submit this extension to the BApp Store for public use, under the [terms and conditions of the EULA](https://portswigger.net/legal).
- [X] I have read and understood the [submission requirements for the BApp Store](https://portswigger.net/burp/documentation/desktop/extend-burp/extensions/creating/bapp-store-acceptance-criteria).

### Extension overview

What the extension does and why it is useful.

### Key features

- First feature
- Second feature

### Usage instructions

1. First step
2. Second step
```

### Fields

| Field | Required | Notes |
| --- | --- | --- |
| Issue title | Yes | The extension name. Not a body field. |
| Extension URL | Yes | The GitHub repository holding the extension's source. Must exist, be public, and must not be a fork. Its heading is also what identifies this as a new submission. |
| Version number | Yes | The version being submitted, e.g. `1.0.0`. |
| Select additional compatible products and features | No | Tick `- [X]` for each that applies. Burp Suite Professional is always included and is not listed. |
| Author display name | Yes | The name shown as the author on the BApp Store. |
| Contact details (optional) | No | Publicly visible. Use `_No response_` if not supplied. |
| Discord username (optional) | No | Publicly visible. Use `_No response_` if not supplied. |
| I confirm that the following is true: | Yes | **Both** boxes must be `- [X]`. Only tick them if the author has actually confirmed both statements — you are recording their agreement to the EULA, not your own. |
| Extension overview | No | Free text. |
| Key features | No | Free text. |
| Usage instructions | No | Free text. |

An unanswered optional field must be either omitted entirely or given the value
`_No response_`. Do not write `N/A`, `None`, or leave the value blank.

## Update to an existing extension

Updates are accepted only from the parent repository of the PortSwigger fork.
Raise your pull request against the PortSwigger fork of the extension, from the
author's original repository, then link that pull request here.

```bash
gh issue create \
  --repo PortSwigger/extension-portal \
  --title 'Existing BApp Store Name' \
  --body-file update.md
```

`update.md`:

```markdown
### Pull request URL

https://github.com/PortSwigger/repository-name/pull/123

### Version number

1.2.3

### Author display name

_No response_

### Contact Details

_No response_

### Discord username

_No response_

### Update summary

What changed in this version.

### BApp Description update

_No response_
```

### Fields

| Field | Required | Notes |
| --- | --- | --- |
| Issue title | Yes | The extension's current name on the BApp Store. |
| Pull request URL | Yes | Must point at a pull request on the PortSwigger fork, raised from the fork's parent repository. Its heading is also what identifies this as an update. |
| Version number | Yes | The version being released, e.g. `1.2.3`. |
| Author display name | No | Supply only to **change** the displayed author. Otherwise `_No response_`. |
| Contact Details | No | Publicly visible. |
| Discord username | No | Publicly visible. |
| Update summary | No | Free text. |
| BApp Description update | No | A replacement description for the BApp Store page. |

Note that the update form uses `Contact Details` and `Discord username`, where
the new-submission form uses `Contact details (optional)` and
`Discord username (optional)`. Use whichever spelling the form you are filling
in uses.

## What happens after you submit

The pipeline comments on the issue within a few minutes:

- **Success** — a review ticket was created and the submission is queued.
- **Failure** — the comment names the problem and the issue is closed. Fix the
  problem, then comment `/resubmit` on the closed issue to run the checks again.
  For updates, comment `/reopen`.

Do not open a second issue for the same extension after a failure. Resubmit on
the existing one.

## Common mistakes

- Writing the submission as prose instead of using the `### ` headings. Without
  `### Extension URL` or `### Pull request URL` the issue cannot be identified
  and is closed.
- Using `## ` or `**bold**` instead of `### ` for the headings.
- Putting the value on the same line as its heading.
- Putting the extension name in the body instead of the issue title.
- Submitting a fork. The Extension URL must be the original repository.
- Omitting the confirmation checkboxes, or ticking them with `- [x] ` against a
  reworded label. Copy the two labels exactly.

## Questions

Contact [bapps@portswigger.net](mailto:bapps@portswigger.net). Full acceptance
criteria are at
<https://portswigger.net/burp/documentation/desktop/extend-burp/extensions/creating/bapp-store-acceptance-criteria>.
