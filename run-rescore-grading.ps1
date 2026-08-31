# Grading-Re-Derivation-Experiment (Schritt 1): leitet NUR das Per-Claim-Verdikt
# (challenged/not_challenged) aus dem VORHANDENEN Artifact A neu ab (Fix A oder B), baut
# damit dieselbe gewichtete Conclusion wie out_v2 und judged erneut. Der Agent wird NICHT
# neu ausgefuehrt. Baseline = out_v2 (gewichtete Conclusion + ALTES Grading) -> der Delta
# isoliert den Grading-Fix.
#
# Aufruf (im Repo-Root):   .\run-rescore-grading.ps1              (Fix A -> eval/out_v3)
#   optional:              .\run-rescore-grading.ps1 -FixB        (Fix B -> eval/out_v3b)
#                          .\run-rescore-grading.ps1 -Ids "CvGqMD5OtX,8zxGruuzr9"
#                          .\run-rescore-grading.ps1 -Force
#
# VORAUSSETZUNG: eval/out (Artifact A) und eval/out_v2 (Baseline) existieren; .env mit OPENAI_API_KEY.
# KEIN GROBID / kein Agent-Re-Run.

param(
    [switch]$FixB,
    [string]$Ids = "",
    [int]$N = 0,
    [switch]$Force
)

$env:PYTHONUTF8 = "1"

# Conclusion-Modell = dasselbe wie im out_v2-Lauf (gpt-5.1), damit v2->v3 NUR das Grading
# unterscheidet. Judge gpt-4.1 (wie Afzal). Grading-Aggregation (nur Fix B) gpt-4.1.
$env:NOVELTY_CONCLUSION_MODEL = "gpt-5.1"
$env:NOVELTY_JUDGE_MODEL      = "gpt-4.1"
$env:NOVELTY_GRADING_MODEL    = "gpt-4.1"

$py = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
$fix = if ($FixB) { "B" } else { "A" }

$argsList = @("eval/rescore_with_grading.py", "--fix", "$fix",
              "--conclusion-model", "$($env:NOVELTY_CONCLUSION_MODEL)",
              "--judge-model", "$($env:NOVELTY_JUDGE_MODEL)",
              "--grading-model", "$($env:NOVELTY_GRADING_MODEL)")
if ($Ids -ne "") { $argsList += @("--ids", "$Ids") }
if ($N -gt 0)    { $argsList += @("--n", "$N") }
if ($Force)      { $argsList += "--force" }

Write-Host "Grading Re-Derivation | Fix=$fix Conclusion=$($env:NOVELTY_CONCLUSION_MODEL) Judge=$($env:NOVELTY_JUDGE_MODEL)" -ForegroundColor Cyan
Write-Host "(Baseline out_v2; neue Outputs eval/out_v3$(if($FixB){'b'}). Agent wird NICHT neu ausgefuehrt.)" -ForegroundColor DarkGray
& $py @argsList
