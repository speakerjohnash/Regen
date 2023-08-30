import os
import csv
import sys
import json
import random
import openai

# Get the API key
openai.api_key = os.getenv("REGEN_OPENAI_KEY")

# TODO load from command line argument
file_id = ""

print(openai.FineTuningJob.list(limit=10))

# Create a fine-tuning job
fine_tuning_job = openai.FineTuningJob.create(
  training_file=file_id,
  model="gpt-3.5-turbo"
)

print(openai.FineTuningJob.list(limit=10))

# print(openai.FineTuningJob.list_events(id="ftjob-yoU51HDTgbapelhAKwJFY2WJ", limit=10))
