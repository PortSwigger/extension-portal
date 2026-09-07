# BApp Store Extension Submission Portal

Use this repository to submit new Burp Suite extensions and updates to the BApp Store.

Submissions are automatically added to the review queue and tracked throughout the review process.

## Extension submission requirements

Before submitting an extension, please ensure:
- You have permission from all relevant persons to submit this extension to the BApp Store for public use, under the [terms and conditions of the EULA](https://portswigger.net/legal)
- You have read and understood the [submission requirements for the BApp Store](https://portswigger.net/burp/documentation/desktop/extend-burp/extensions/creating/bapp-store-acceptance-criteria)

## New extension submission

To submit a new extension to the BApp Store:

1. On the [Issues](../../issues) tab, click New Issue.
2. Select New extension submission.
3. Complete the submission form.
4. Click Create.

## Extension update submission

To submit an update for an existing extension on the BApp Store:

1. On the [Issues](../../issues) tab, click New Issue.
2. Select Update for existing extension.
3. Complete the submission form.
4. Click Create.

Note: Updates are accepted from the parent repository of the PortSwigger fork.

## Submitting with an AI agent

If you are using an AI agent to submit on your behalf, point it at
[AGENTS.md](AGENTS.md). It contains the exact issue body and `gh` command for
both forms.

Submissions are parsed literally, so an issue that reads correctly to a human
but does not match that format is closed with an explanation of what to fix.

## Tracking your submission

All submissions are tracked in our [Extension submissions](https://github.com/orgs/PortSwigger/projects/1) GitHub project, where you can monitor the status of your submission through the review process.

## Responding to feedback

If your extension requires changes, we will leave feedback on the issue and close it. This removes it from the review queue while you make the required changes.

When the changes are complete, comment `/reopen` on the closed issue to add it back into the review queue.

## Closing your submission

Closing an issue takes your submission out of the review queue. To withdraw a submission, close it as **Not planned**. You can comment `/reopen` at any point to put it back into the queue.

We use **Completed** to record that our team has finished reviewing a submission, so if an issue is closed as **Completed** before then, we adjust the reason to **Not planned**. The issue stays closed either way.

## Questions or issues?

If you have questions or need clarification, please contact us at [bapps@portswigger.net](mailto:bapps@portswigger.net).
