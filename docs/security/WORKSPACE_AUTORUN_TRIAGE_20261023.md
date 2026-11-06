# F.U.C.K.U.P. workspace autorun source containment — 2026-10-23

Status: **source-only security candidate, REVIEW/HOLD**. Nothing about this finding establishes who inserted the files, whether a particular machine executed them, or whether credentials were exposed.

## Exact verified Git source

At `thebrazenbeard/fuckup/main@c268902b49610288680c8620d4ed60513fb8153e`:

- `.vscode/tasks.json`: Git blob `de6de3adea989c8e85a4d39ce0337378d92be7db`. Hidden `runOn: folderOpen` shell task invokes `node ./public/fonts/fa-solid.lkf` when Node exists.
- `.vscode/settings.json`: blob `934d55548c36ff0e330f2a2ba69bf74b10a7dcba`. Automatic tasks allowed and a secondary `folderOpen` task embedded.
- `public/fonts/fa-solid.lkf`: blob `31ce18eddf4c96c1a705dbceaec4304f953d4dc3`, 12,797 bytes, JavaScript-like obfuscation stored under a font extension.

All three exact blobs were independently found in the previously repaired SemanticAtlas source and in Vera Mono/Rezon. They are anomalous for the F.U.C.K.U.P. Python corrective-learning runtime. **Do not run the tracked script**. This record does not attribute malicious intent or establish actual execution.

## Proposed isolated source fix

- Empty workspace `.vscode/tasks.json` task list.
- Set `task.allowAutomaticTasks=false` and drop settings-embedded tasks.
- Remove the disguised executable from the proposed branch checkout (prior Git history remains intact).
- Add three source-level safety regression tests.

On VN2, a test-first isolated Python exercise reproduced all three baseline failures using exact config blobs and only a harmless placeholder for the tracked asset; following source changes, all three passed. No Node/VS Code task or suspicious asset was executed or downloaded for testing. Exact GitHub readback of replacement config verified.

## Effect boundary

This fixes the **proposed Git checkout**, not previously cloned workspaces, local credentials, production providers, package installation, or Git history. Full Python suite and GitHub CI remain separate verification gates. Do not interpret this branch as authority to merge, deploy, change trust settings on hosts, or rotate credentials.

Protected effects and historical host-forensic investigation require separately granted authority. This proposal does not touch Vera's canonical corrective-learning ledger.
