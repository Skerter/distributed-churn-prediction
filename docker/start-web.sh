#!/bin/bash
exec python -m uvicorn src.presentation.web.app:app --host 0.0.0.0 --port "${PORT:-8000}"
