# Historical writer gate fixture

`layout.py` and `gitstore.py` are unchanged Git blob bytes from the AgentWorkspace
commit `9e1bf44bfd3b3feb941af4dcc81cacb58ede0aa2`, before the message-v3 layout.
`provenance.json` records their repository, original paths, Git blob IDs and SHA-256
values. `.gitattributes` preserves these bytes on every checkout.

The message migration regression loads the real previous parser and commit
validator from these files. It verifies their hashes before executing them and
still requires the old writer to reject the migrated version-3 Workspace before
publication. Test execution does not fetch or inspect historical Git commits.

As in the original history-based test, the two modules use the current
`agent_workspace` utility/error types and package version through their relative
imports; the old parser's version gate is executed unchanged. This is a focused
old-writer gate check, not a complete previous installation or native-session
acceptance test.

These files are immutable test fixtures, not maintained production modules.
To test another historical writer, add a separately sourced fixture instead of
editing these files or updating their hashes to match local modifications.
