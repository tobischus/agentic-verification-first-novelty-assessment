# GROBID auf einer 8-GB-Maschine

`grobid.yaml` ist die Konfiguration des Images `grobid/grobid:0.9.0-crf` mit drei
geänderten Werten. Sie gehört ins Repo, weil die Standardwerte auf einem Rechner mit
8 GB RAM nicht nur langsam sind, sondern die Docker-Engine mitreißen.

## Was passiert war

Beim Verarbeiten einer 88-seitigen Submission brach GROBID mit
`HTTP 500: [TIMEOUT] PDF to XML conversion timed out` ab. Kurz darauf antwortete die
Docker-Engine selbst auf jeder API-Route mit HTTP 500.

Die PDF war nicht die Ursache — 23 Fonts, 4105 Vektorbefehle, ein Bild; nach der
Umstellung braucht pdfalto dafür **6 Sekunden**. Es war der Arbeitsspeicher:

| | Standard | hier |
|---|---|---|
| WSL2-VM | halber Host-RAM (3,73 GiB), **kein Swap** | 4,5 GB + 8 GB Swap (`~/.wslconfig`) |
| `pdf.pdfalto.memoryLimitMb` | 6096 — mehr, als die VM insgesamt hat | 1500 |
| `pdf.pdfalto.timeoutSec` | 120 | 400 |
| `concurrency` | 10 | 2 |

GROBID belegt allein ~3,1 GB, und zwar im **nativen** Speicher: die CRF-Modelle laufen
über Wapiti per JNI, deshalb ändert ein `-Xmx` daran nichts. In einer 3,73-GiB-VM blieben
damit ~0,6 GB für eine Konvertierung, die 6 GB anfordern durfte — ohne Swap, der das
hätte abfangen können. `concurrency: 2` genügt, weil die Pipeline immer genau ein PDF
zur Zeit schickt.

Nebeneffekt: `document_processing` fiel von 233 s auf 46 s pro Paper.

## Container aufsetzen

Kein `--rm`: der Container, der einmal mitten im Batch starb, wurde samt seiner Logs
entfernt, und es blieb nichts übrig, das den Grund hätte nennen können.

```bash
docker create --init --ulimit core=0 -p 8070:8070 --restart unless-stopped \
  --name grobid grobid/grobid:0.9.0-crf
docker cp docker/grobid.yaml grobid:/opt/grobid/grobid-home/config/grobid.yaml
docker start grobid
```

Die Konfiguration liegt in der Schreibschicht des Containers und überlebt `restart`,
aber nicht das Neuanlegen — nach einem `docker rm` also wieder einspielen.

## Host-Seite

`~/.wslconfig` (Windows) begrenzt die VM für alle WSL2-Distributionen. Damit eine
Änderung greift, muss die VM wirklich aus sein: Docker Desktop beenden, dann
`wsl --shutdown`, dann Docker Desktop starten. Startet Docker Desktop noch, zieht es die
VM sofort wieder hoch und die alten Werte bleiben stehen.

Kontrolle:

```bash
docker info --format "{{.MemTotal}}"   # erwartet ~4,3 GiB statt 3,73 GiB
docker run --rm alpine free -m         # Swap-Zeile muss 8192 zeigen
```
