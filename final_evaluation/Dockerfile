# Study dashboard image: build the frontend, then serve it plus the API from one Python
# process. Build context is the REPOSITORY ROOT (so `final_evaluation/` is importable as
# a package) -- see render.yaml's dockerContext.
#
# Nothing in this image reads the pipeline, a model API, or a PDF parser: in cloud mode
# assets come from Supabase Storage and responses go to Supabase Postgres. See
# .dockerignore for what is deliberately kept out.

# ---- stage 1: frontend ----
FROM node:18-alpine AS frontend
WORKDIR /app/frontend
COPY final_evaluation/dashboard/frontend/package.json final_evaluation/dashboard/frontend/package-lock.json ./
RUN npm ci
COPY final_evaluation/dashboard/frontend/ ./
COPY final_evaluation/prompts/human_instructions.md /app/prompts/human_instructions.md
COPY final_evaluation/prompts/criteria.json /app/prompts/criteria.json
# Same sync the CLI's build-frontend does, so the built bundle carries the instruction
# text and rubric the consent hash is computed over.
RUN mkdir -p public \
 && sed -e '1,/-->/d' /app/prompts/human_instructions.md > public/instructions.txt \
 && cp /app/prompts/criteria.json public/criteria.json \
 && npm run build

# ---- stage 2: runtime ----
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY final_evaluation/requirements.txt ./final_evaluation/requirements.txt
RUN pip install --no-cache-dir -r final_evaluation/requirements.txt

COPY final_evaluation/__init__.py final_evaluation/cli.py ./final_evaluation/
COPY final_evaluation/dashboard ./final_evaluation/dashboard
COPY final_evaluation/scripts ./final_evaluation/scripts
COPY final_evaluation/evaluation ./final_evaluation/evaluation
COPY final_evaluation/prompts ./final_evaluation/prompts
COPY final_evaluation/config ./final_evaluation/config
COPY final_evaluation/PROTOCOL.md ./final_evaluation/PROTOCOL.md
COPY --from=frontend /app/frontend/dist ./final_evaluation/dashboard/frontend/dist

# Render provides $PORT. APP_ENV=production makes settings.py refuse to start without
# SESSION_SECRET / ACCESS_CODE_PEPPER / STUDY_CONTACT / a non-SQLite DATABASE_URL.
ENV APP_ENV=production STORAGE_BACKEND=supabase PORT=10000
EXPOSE 10000
CMD ["sh", "-c", "python -m uvicorn final_evaluation.dashboard.backend.app:create_app --factory --host 0.0.0.0 --port ${PORT}"]
