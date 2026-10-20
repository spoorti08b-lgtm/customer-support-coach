# Safe GitHub Integration (Windows PowerShell)

Nothing here pushes automatically. Run the commands yourself, one block at a time, and read the
output. Replace `C:\path\to\customer-support-coach` with your project folder and
`rag-pipeline.zip` with the ZIP's actual path.

The RAG files are all **new**, so this should not conflict with anyone's work.

## 1. Back up your current work

```powershell
cd C:\path\to\customer-support-coach
robocopy . ..\customer-support-coach-backup /E /XD .venv .git     # exit codes 0-7 mean success
git diff > ..\uncommitted-changes.patch                           # tracked changes (untracked files are in the copy)
```

## 2. Check your branch and working tree

```powershell
git status
git branch --show-current
git fetch origin
git branch -a
```

If `git status` lists changes you want to keep, commit them on your current branch first, or park them:

```powershell
git stash push -u -m "wip before rag-pipeline"     # restore later with: git stash pop
```

## 3. Create the feature branch (from the latest main)

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/rag-pipeline
```

If `git switch -c` says the branch exists, stop and choose a different name instead of deleting anything.

## 4. Extract the ZIP safely (no overwriting)

Extract to a temporary folder, not directly into the repo:

```powershell
Remove-Item -Recurse -Force "$env:TEMP\rag_zip" -ErrorAction SilentlyContinue
Expand-Archive -Path .\rag-pipeline.zip -DestinationPath "$env:TEMP\rag_zip"
$src = "$env:TEMP\rag_zip\customer-support-coach"

# List any ZIP file that already exists in your repo. Expected output: nothing.
Get-ChildItem $src -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($src.Length + 1)
    if (Test-Path $rel) { "ALREADY EXISTS: $rel" }
}
```

If anything prints `ALREADY EXISTS`, stop and compare that file manually before continuing. If
nothing printed, copy without overwriting (`/XC /XN /XO` skips files that already exist):

```powershell
robocopy $src . /E /XC /XN /XO
```

## 5. Review what changed

```powershell
git status -s -uall
```

You should see only the new files listed in `INTEGRATION_NOTES.md` (all `??`) and **no** modified
files (` M`). Modified files mean something went wrong; investigate before continuing.

Keep Python cache folders and the virtual environment out of `git status` on your machine without
touching any shared `.gitignore`:

```powershell
Add-Content .git\info\exclude "__pycache__/"
Add-Content .git\info\exclude "*.pyc"
Add-Content .git\info\exclude ".venv/"
```

## 6. Install dependencies

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements-rag.txt
```

## 7. Run the tests

```powershell
$env:PYTHONPATH = "src"
py -m unittest discover -s tests -v
```

Optional real-model smoke test (first run downloads ~80 MB):

```powershell
$env:RAG_SMOKE = "1"
py -m unittest tests.test_rag_smoke_real_embeddings -v
Remove-Item Env:RAG_SMOKE
```

## 8. Stage only the intended files

Do not use `git add .` or `git add -A`. Name the paths:

```powershell
git add src/customer_support_coach/rag
git add tests/rag_test_support.py tests/test_document_loader.py tests/test_chunker.py `
        tests/test_vector_store.py tests/test_retriever.py tests/test_rag_pipeline.py `
        tests/test_rag_smoke_real_embeddings.py
git add docs/rag_pipeline.md examples/rag_demo.py examples/make_sample_pdfs.py examples/sample_docs
git add requirements-rag.txt data/rag/.gitignore INTEGRATION_NOTES.md GITHUB_INTEGRATION.md

git status
git diff --cached --stat
```

Check that no `.venv`, `__pycache__`, `*.db`, or `data/rag/chroma` files are staged. To unstage a
file: `git restore --staged <path>`.

## 9. Commit

```powershell
git config user.name        # make sure your name/email are set; if blank:
git config user.email       #   git config user.name "Your Name" ; git config user.email "you@example.com"
git commit -m "Add RAG pipeline: PDF ingestion, chunking, embeddings, ChromaDB storage, top-3 retrieval"
```

## 10. Push the feature branch

```powershell
git push -u origin feature/rag-pipeline
```

Never use `--force`. If the push is rejected for permissions, ask the repository owner for
collaborator access (or fork the repo and push there) instead of forcing anything.

## 11. Open a pull request against `main`

Open `https://github.com/spoorti08b-lgtm/customer-support-coach/pulls`, choose **New pull request**,
set base `main` and compare `feature/rag-pipeline`, and paste the summary from `INTEGRATION_NOTES.md`.
Or, with GitHub CLI installed:

```powershell
gh pr create --base main --head feature/rag-pipeline --title "RAG pipeline: ingestion, retrieval" --body-file INTEGRATION_NOTES.md
```

## 12. If main changes before your PR is merged

```powershell
git fetch origin
git merge origin/main          # merge, don't rebase or force-push a branch you already pushed
```

If Git reports conflicts:

```powershell
git status                     # files marked "both added" / "both modified"
# open each file, keep both teammates' intent, delete the <<<<<<< ======= >>>>>>> markers
git add path\to\resolved_file
git commit                     # completes the merge
py -m unittest discover -s tests
git push
```

Not sure what to keep? `git merge --abort` returns you to the state before the merge. Don't resolve
conflicts in a teammate's file by choosing "mine" without asking them.
