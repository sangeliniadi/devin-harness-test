# Running the harness in Windsurf

## 1. Unzip and open the folder
Unzip `harness_poc.zip` somewhere on your machine, then in Windsurf:
**File → Open Folder** → select the unzipped `harness_poc` folder.

You should see all 7 files in the Explorer sidebar on the left
(`devin_harness_service.py`, `devin_client.py`, `models.py`, `policy.yaml`,
`run_example.py`, `requirements.txt`, `README.md`).

## 2. Open a terminal inside Windsurf
`View → Terminal` (or the backtick key `` ` `` in most Windsurf/VS Code-style
keybindings). This opens a terminal already `cd`'d into the folder you
opened — no need to navigate manually.

## 3. (Recommended) create a virtual environment
Keeps this project's packages separate from anything else on your machine:

```bash
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows
```

You'll know it worked because your terminal prompt will show `(venv)` at
the start of the line. If Windsurf shows a popup asking "Select this
interpreter for the workspace?" — click yes, that just points Windsurf's
Python tooling (linting, etc.) at the same environment.

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

## 5. Set your Devin API key
Two options:

**Quick and temporary** (only lasts for this terminal session):
```bash
export DEVIN_API_KEY=your_actual_key_here
```

**Persistent** (Windsurf will pick it up automatically next time): create a
`.env` file in the folder with:
```
DEVIN_API_KEY=your_actual_key_here
```
and add one line near the top of `run_example.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```
(if you go this route, also add `python-dotenv` to `requirements.txt` and
re-run `pip install -r requirements.txt`). Also add `.env` to a
`.gitignore` if this folder ever becomes a git repo — you don't want the
key committed.

## 6. Edit the test ticket
Open `run_example.py` in Windsurf's editor and change:
```python
repo="your-org/your-repo",
```
to a real repo you have access to. Keep the acceptance criteria as-is for
your first run (it's a small, self-contained example) or write your own
trivial one.

## 7. Run it
Either:
- Click the ▶ Run button Windsurf shows at the top of `run_example.py`, or
- In the terminal: `python run_example.py`

You'll see log lines stream in as it polls Devin (this can take a few
minutes — Devin sessions are asynchronous), then a JSON summary at the end.

## Troubleshooting
- **`DEVIN_API_KEY is not set`** → step 5 didn't take. Run `echo $DEVIN_API_KEY` to check it's actually set in *this* terminal session.
- **`ModuleNotFoundError`** → you're not in the venv. Check for `(venv)` in your prompt; re-run `source venv/bin/activate`.
- **401/403 from the API** → the key is set but doesn't have access to the repo you named, or isn't valid for the v1 API — check with your org's Devin admin.
- **It hangs for a long time** → normal for real sessions; `devin_client.py` polls with backoff up to a 30-minute timeout per step. If it times out, that itself is useful signal (see the doc's Session Insights point about mis-scoped tasks).
