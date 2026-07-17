# Startet das Novelty-Assessment-Backend mit dem richtigen Python + Konfiguration.
# Aufruf (im Repo-Root):   .\start-backend.ps1
# Falls PowerShell die Ausfuehrung blockiert:  powershell -ExecutionPolicy Bypass -File .\start-backend.ps1

$env:PYTHONUTF8 = "1"

# --- Agent-Konfiguration (hier einmal anpassen, statt jedes Mal einzutippen) ---
$env:NOVELTY_MODEL            = "gpt-5-mini"   # auch moeglich: "gpt-5", "gpt-4.1-mini", "gpt-4.1" (Preise hinterlegt)
$env:NOVELTY_AGENT_MAX_STEPS       = "50"        # Kompatibilitaets-Backstop (Zwei-Phasen-Ablauf terminiert von selbst)
$env:NOVELTY_AGENT_MAX_RETRIEVALS  = "1"         # Re-Entry-Runden (retrieve_more), wenn nichts ueberlappt
$env:NOVELTY_AGENT_CLOSEST_N        = "10"        # nur noch Coverage-/Anzeige-Breite; die Triage schaut IMMER den ganzen Pool an
$env:NOVELTY_DEEP_DIVE_WORKERS      = "4"         # Deep Dives PARALLEL (unabhaengige Vergleiche); 1 = sequenziell. Hoeher = schneller, aber Vorsicht mit dem TPM-Limit des Modells (v.a. gpt-5-mini)
# $env:GROBID_SERVER = "http://localhost:8070"   # nur noetig beim Hochladen eines ganz neuen PDFs

# --- alten Backend-Prozess auf Port 8099 KILLEN, damit der Neustart wirklich den neuen Code laedt ---
$old = Get-NetTCPConnection -LocalPort 8099 -State Listen -ErrorAction SilentlyContinue
if ($old) {
    Write-Host "Beende alten Backend-Prozess auf Port 8099 ..." -ForegroundColor Yellow
    $old.OwningProcess | Select-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

# --- richtiger Interpreter (der mit allen Projekt-Abhaengigkeiten, NICHT conda base) ---
$py = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"

Write-Host "Starte Backend | Modell=$($env:NOVELTY_MODEL) closest_n=$($env:NOVELTY_AGENT_CLOSEST_N) max_steps=$($env:NOVELTY_AGENT_MAX_STEPS) deep_dive_workers=$($env:NOVELTY_DEEP_DIVE_WORKERS)" -ForegroundColor Cyan
& $py src/novelty_assessment/api.py
