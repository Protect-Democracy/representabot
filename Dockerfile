FROM public.ecr.aws/lambda/python:3.8

COPY pyproject.toml poetry.lock ./
RUN pip install --upgrade pip && pip install poetry
RUN poetry export -f requirements.txt --output requirements.txt
RUN pip install -r requirements.txt
COPY representabot ./
CMD ["representabot.bot.lambda_handler"]
