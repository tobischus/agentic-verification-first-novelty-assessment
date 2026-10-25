# GROBID

`grobid.yaml` is the configuration of `grobid/grobid:0.9.0-crf` with three values changed
for machines with 8 GB RAM: `pdf.pdfalto.memoryLimitMb: 1500`,
`pdf.pdfalto.timeoutSec: 400` and `concurrency: 2`.

```bash
docker create --init --ulimit core=0 -p 8070:8070 --restart unless-stopped \
  --name grobid grobid/grobid:0.9.0-crf
docker cp docker/grobid.yaml grobid:/opt/grobid/grobid-home/config/grobid.yaml
docker start grobid
```

On Windows, give the WSL2 VM at least 4.5 GB and some swap in `~/.wslconfig`.
