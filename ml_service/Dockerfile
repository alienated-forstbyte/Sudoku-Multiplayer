FROM python:3.11-slim

WORKDIR /app

COPY ml_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ml ./ml
COPY ml_service/app.py ./app.py
COPY ml_service/sudoku_model.pkl ./sudoku_model.pkl

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]