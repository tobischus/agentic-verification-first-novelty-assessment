# Erster Evaluationslauf: MEINE Pipeline vs. Afzals Baseline, bewertet gegen die
# human_novelty_assessments (LLM-as-Judge, Fig 13/14). Ein Aufruf startet alles.
#
# Aufruf (im Repo-Root):   .\run-eval.ps1
#   optional:              .\run-eval.ps1 -N 18
#                          .\run-eval.ps1 -Ids "1XxNbecjXe,2NqssmiXLu"
#                          .\run-eval.ps1 -SkipJudge      (nur Pipeline, kein Judge)
# Falls PowerShell blockiert:  powershell -ExecutionPolicy Bypass -File .\run-eval.ps1
#
# VORAUSSETZUNG: GROBID laeuft (siehe Start.txt) und .env hat OPENAI_API_KEY +
# SEMANTIC_SCHOLAR_API_KEY. Der Lauf ist WIEDERAUFNEHMBAR: schon fertige Paper werden
# uebersprungen, ein erneuter Aufruf setzt fort.

param(
    [int]$N = 18,
    [string]$Ids = "",
    [switch]$SkipJudge
)

$env:PYTHONUTF8 = "1"

# --- Modelle ---
$env:NOVELTY_MODEL            = "gpt-5-mini"  # Pipeline-LLM (auf Wunsch). ACHTUNG: Reasoning-Modell -> langsam (Minuten/Claim); ein 18-Paper-Lauf dauert entsprechend lange. Der Lauf ist wiederaufnehmbar -> ruhig ueber Nacht laufen lassen.
$env:NOVELTY_CONCLUSION_MODEL = "gpt-4.1"     # Schluss-Absatz (Synthese-Schritt) -- bewusst gpt-4.1 (schnell, stark). Auf "gpt-5-mini" setzen fuer volle Modell-Konsistenz.
$env:NOVELTY_JUDGE_MODEL      = "gpt-4.1"     # Judge = GPT-4.1 (wie bei Afzal)

# --- Agent-Konfiguration ---
$env:NOVELTY_AGENT_MAX_RETRIEVALS = "1"
$env:NOVELTY_AGENT_CLOSEST_N      = "10"
$env:NOVELTY_DEEP_DIVE_WORKERS    = "4"     # Deep Dives parallel
$env:NOVELTY_LLM_TIMEOUT          = "300"   # Sekunden/Call (haengende Calls brechen ab)
$env:NOVELTY_LLM_MAX_RETRIES      = "4"

# --- GROBID pruefen ---
try {
    $alive = (Invoke-WebRequest -Uri "http://localhost:8070/api/isalive" -TimeoutSec 5 -UseBasicParsing).Content.Trim()
} catch { $alive = "" }
if ($alive -ne "true") {
    Write-Host "GROBID ist NICHT erreichbar auf http://localhost:8070 (isalive='$alive')." -ForegroundColor Red
    Write-Host "Bitte zuerst GROBID starten (siehe Start.txt), dann erneut aufrufen." -ForegroundColor Red
    exit 1
}
Write-Host "GROBID ok (isalive=true)" -ForegroundColor Green

# --- richtiger Interpreter ---
$py = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"

$argsList = @("eval/run_eval.py", "--n", "$N", "--model", "$($env:NOVELTY_MODEL)", "--judge-model", "$($env:NOVELTY_JUDGE_MODEL)")
if ($Ids -ne "")   { $argsList += @("--ids", "$Ids") }
if ($SkipJudge)    { $argsList += "--skip-judge" }

Write-Host "Starte Evaluation | Pipeline=$($env:NOVELTY_MODEL) Judge=$($env:NOVELTY_JUDGE_MODEL) N=$N" -ForegroundColor Cyan
Write-Host "(Wiederaufnehmbar - schon fertige Paper werden uebersprungen. Ergebnisse: eval/out/report.md)" -ForegroundColor DarkGray
& $py @argsList
