# Starts the backend API on port 8099 with the evaluated configuration.
# Usage (repository root): powershell -ExecutionPolicy Bypass -File .\start-backend.ps1

$env:PYTHONUTF8 = "1"
$env:NOVELTY_MODEL = "gpt-5.6-luna"
$env:NOVELTY_READING_EFFORT = "low"
$env:NOVELTY_COMPARE_EFFORT = "low"
$env:NOVELTY_EVIDENCE_EFFORT = "low"
$env:NOVELTY_CONCLUSION_EFFORT = "low"
$env:NOVELTY_DEEP_DIVE_WORKERS = "2"
$env:NOVELTY_LLM_TIMEOUT = "420"

python src/novelty_assessment/api.py
