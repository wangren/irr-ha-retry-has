# Pushing this repo

The repo is git-initialized locally with an initial commit on `master`.
To publish it, add your remote and push. Replace the URL with your actual
target (host/org/name you'll provide).

## Intel GitHub Enterprise (typical)

```bash
cd "dmr-ha-retry-has"
git remote add origin https://github.intel.com/<ORG>/dmr-ha-retry-has.git
git branch -M main
git push -u origin main
```

## Notes

- `git push` works directly on this machine (schannel honors corp WPAD); no proxy
  needed for git.
- If your team uses a `main` default branch, the `git branch -M main` above renames
  `master`→`main` before the first push.
- Commit was made with `user.name=rwang16` / `user.email=rwang16@intel.com`.
  Adjust with `git commit --amend --author="Name <email>"` if needed before pushing.
