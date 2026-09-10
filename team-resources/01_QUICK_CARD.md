# Team quick-reference card

*The 2-minute version. For the full story, read `00_START_HERE.md`.*

## What we built
An AI triage tool for Oil India's safety reports. Workers write near-miss/unsafe-act reports → the tool flags the ones with fatal-accident potential, tags the relevant Life-Saving Rule, highlights the evidence words, and ranks the most dangerous sites/activities on a dashboard. Humans always make the final call.

## The 5 numbers to remember
| What | Number |
|---|---|
| Flags that are right (precision) | **98%** |
| Dangerous reports caught (recall) | **84%** |
| Speed per report | **~0.05 seconds** |
| Works without internet | **Yes — fully** |
| Cheaper than a cloud LLM per report | **~1000×** |

## Demo in 4 steps
1. Paste a near-miss report → amber "High review priority" card with highlighted evidence
2. Paste the calm version of the same event → green "no action needed"
3. Show the site ranking jump after uploading a batch of reports
4. Unplug the internet cable — everything keeps working

## The 3 things to never say
1. "It predicts accidents" — we triage, we don't predict
2. "It learned from OIL's real reports" — public + synthetic data only (OIL data is confidential)
3. "The AI validates itself" — humans labeled the test set blind, without seeing AI output

## If the demo breaks
- Refresh the page (Ctrl+Shift+R)
- Still broken → restart: `./run.sh --stop && ./run.sh` in the project folder
- Total failure → play the backup video: `artifacts/demo/fallback_recording.webm`

## Architecture in one line
Reports → Backend (FastAPI) → AI model (ModernBERT, fine-tuned by us) → Database (SQLite) → Website (React). Explanations by a local LLM (Qwen3-8B). Trained once on Kaggle cloud GPUs; runs forever offline.
