# Conclusion-Re-Scoring-Experiment: baut NUR die finale Conclusion aus dem vorhandenen
# Artifact A neu (kritische Reviewer-Haltung, treu zu den Per-Claim-Verdikten) und laesst
# denselben LLM-as-Judge (Fig 13/14) erneut laufen -- neue Conclusion vs Afzal vs Mensch.
# Schreibt alles nach eval/out_v2/. Die Original-Outputs (eval/out/) bleiben unberuehrt.
#
# Aufruf (im Repo-Root):   .\run-rescore.ps1
#   optional:              .\run-rescore.ps1 -Ids "09JVxsEZPf,1XxNbecjXe"
#                          .\run-rescore.ps1 -N 3        (nur die ersten 3)
#                          .\run-rescore.ps1 -Force      (schon bewertete neu machen)
#
# VORAUSSETZUNG: der Haupt-Eval-Lauf existiert (eval/out/results/*.json + Artifact A) und
# .env hat OPENAI_API_KEY. KEIN GROBID noetig (die Pipeline wird nicht neu ausgefuehrt).

param(
    [string]$Ids = "",
    [int]$N = 0,
    [switch]$Force
)

$env:PYTHONUTF8 = "1"

# Modelle: bewusst dieselben wie im Hauptlauf, damit NUR der Conclusion-Prompt der Unterschied
# ist (nicht das Modell). Conclusion-Synthese gpt-4.1, Judge gpt-4.1 (wie Afzal).
$env:NOVELTY_CONCLUSION_MODEL = "gpt-5.1"
$env:NOVELTY_JUDGE_MODEL      = "gpt-4.1"

$py = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"

$argsList = @("eval/rescore_conclusions.py",
              "--conclusion-model", "$($env:NOVELTY_CONCLUSION_MODEL)",
              "--judge-model", "$($env:NOVELTY_JUDGE_MODEL)")
if ($Ids -ne "") { $argsList += @("--ids", "$Ids") }
if ($N -gt 0)    { $argsList += @("--n", "$N") }
if ($Force)      { $argsList += "--force" }

Write-Host "Conclusion Re-Scoring | Conclusion=$($env:NOVELTY_CONCLUSION_MODEL) Judge=$($env:NOVELTY_JUDGE_MODEL)" -ForegroundColor Cyan
Write-Host "(Neue Conclusions + Report: eval/out_v2/  -- Originale bleiben unangetastet)" -ForegroundColor DarkGray
& $py @argsList
