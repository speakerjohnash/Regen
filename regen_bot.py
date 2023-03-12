import os
import re
import random
import discord
from discord.ext import commands
from discord.ui import View, Button, TextInput, Modal
import pandas as pd
import openai

remote_discord_key = os.getenv("CERES_DISCORD_BOT_KEY")
discord_key = os.getenv("CERES_GOI_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

models = {
	"ceres": "davinci:ft-personal:ceres-refined-2022-10-21-02-46-56"
}

training_data = ""
people = []

class AskModal(Modal, title="Ask Modal"):

	answer = TextInput(label="Answer", max_length=400, style=discord.TextStyle.long)

	def add_view(self, question, view: View):
		self.answer.placeholder = question[0:100]
		self.view = view

	async def on_submit(self, interaction: discord.Interaction):
		embed = discord.Embed(title = "Your Response", description = f"\n{self.answer}")
		embed.set_author(name = interaction.user)
		await interaction.response.send_message(embed=embed)
		print(self.answer)
		self.view.stop()

def response_view(modal_text="default text", modal_label="Response", button_label="Answer"):	

	async def view_timeout():
		modal.stop()	

	view = View()
	view.on_timeout = view_timeout
	view.timeout = None
	view.auto_defer = True

	modal = AskModal(title=modal_label)
	modal.auto_defer = True
	modal.timeout = None

	async def button_callback(interaction):
		answer = await interaction.response.send_modal(modal)

	button = Button(label=button_label, style=discord.ButtonStyle.blurple)
	button.callback = button_callback
	view.add_item(button)
	modal.add_view(modal_text, view)

	return view, modal

@bot.event
async def on_message(message):

	# Get Member
	content = message.content
	user = message.author
	channel = message.channel

	print(content)
	print(user)
	print(channel)

	if not message.content.startswith("/") and isinstance(message.channel, discord.DMChannel) and message.author != bot.user:
		await frankenceres(message)

	# Process all commands
	await bot.process_commands(message)

async def frankenceres(message, answer=""):

	"""
	Queries Frankenceres
	"""

	# Get Ceres One Shot Answer First
	try:
		distillation = openai.Completion.create(
			model=models["ceres"],
			prompt=message.content,
			temperature=0.55,
			max_tokens=222,
			top_p=1,
			frequency_penalty=1.5,
			presence_penalty=1.5,
			stop=["END"]
		)

		ceres_answer = distillation['choices'][0]['text']
		ceres_answer = ceres_answer.replace("###", "").strip()
	except Exception as e:
		print(f"Error: {e}")
		ceres_answer = ""

	if len(answer) > 0:
		ceres_answer = answer + " \n\n" + ceres_answer  

	# Load Chat Context
	messages = []

	async for hist in message.channel.history(limit=50):
		if not hist.content.startswith('/'):
			if hist.embeds:
				messages.append((hist.author, hist.embeds[0].description))
			else:
				messages.append((hist.author.name, hist.content))
			if len(messages) == 18:
				break

	messages.reverse()

	# Construct Chat Thread for API
	conversation = [{"role": "system", "content": "You are are a regenerative bot named Ceres that answers questions about Regen Network"}]
	conversation.append({"role": "user", "content": "Whatever you say be creative in your response. Never simply summarize, always say it a unique way. I asked Ceres and she said: " + ceres_answer})
	conversation.append({"role": "assistant", "content": "I am Ceres. I will answer using Ceres as a guide as well as the rest of the conversation. Ceres said " + ceres_answer + " and I will take that into account in my response as best I can"})
	text_prompt = message.content

	for m in messages:
		if m[0] == bot.user:
			conversation.append({"role": "assistant", "content": m[1]})
		else:
			conversation.append({"role": "user", "content": m[1]})

	conversation.append({"role": "system", "content": ceres_answer})
	conversation.append({"role": "user", "content": text_prompt})

	response = openai.ChatCompletion.create(
		model="gpt-3.5-turbo",
		temperature=1,
		messages=conversation
	)

	response = response.choices[0].message.content.strip()

	# Split response into chunks if longer than 2000 characters
	if len(response) > 2000:
		for chunk in [response[i:i+2000] for i in range(0, len(response), 2000)]:
			await message.channel.send(chunk)
	else:
		await message.channel.send(response)

def elaborate(ctx, prompt="prompt"):

	e_prompt = prompt + ". \n\n More thoughts in detail below. \n\n"

	button = Button(label="elaborate", style=discord.ButtonStyle.blurple)

	async def button_callback(interaction):

		if button.disabled:
			return

		button.disabled = True
		await interaction.response.defer()

		response = openai.Completion.create(
			model=models["ceres"],
			prompt=e_prompt,
			temperature=0.22,
			max_tokens=222,
			top_p=1,
			frequency_penalty=2,
			presence_penalty=2,
			stop=["END"]
		)

		response_text = response.choices[0].text.strip()

		if len(response_text) == 0:

			response = openai.Completion.create(
				model=models["ceres"],
				prompt=e_prompt,
				temperature=0.8,
				max_tokens=222,
				top_p=1,
				frequency_penalty=1.7,
				presence_penalty=1.7,
				stop=["END"]
			)

			response_text = response.choices[0].text.strip()

		response_text = response_text.replace("###", "").strip()

		if len(response_text) == 0: response_text = "Ceres has no more to communicate after two requests"

		embed = discord.Embed(title = "Elaboration (beta)", description = f"**Prompt**\n{prompt}\n\n**Elaboration**\n{response_text}")

		await ctx.send(embed=embed)


	button.callback = button_callback

	return button

def load_training_data():

	global training_data

	try:
		training_data = pd.read_csv('ceres_training-data.csv')
	except:
		with open('ceres_training-data.csv', 'w', encoding='utf-8') as f:
			training_data = pd.DataFrame(columns=['prompt', 'completion', 'speaker'])
			training_data.to_csv('ceres_training-data.csv', encoding='utf-8', index=False)

@bot.event
async def on_ready():
	load_training_data()
	print("Ceres is online")

@bot.event
async def on_close():
	print("Ceres is offline")

@bot.command()
async def faq(ctx, *, topic=""):

	df = pd.read_csv('ceres_training-data.csv')
	prompts = df['prompt'].tolist()
	question_pattern = r'^(.*)\?\s*$'
	questions = list(filter(lambda x: isinstance(x, str) and re.match(question_pattern, x, re.IGNORECASE), prompts))
	questions = list(set(questions))

	question_completion_pairs = []

	# Iterate through each question and find its corresponding completions
	for question in questions:
		completions = df.loc[df['prompt'] == question, 'completion'].tolist()
		for completion in completions:
			question_completion_pairs.append((question, completion))

	# Remove any duplicate question-completion pairs from the list
	question_completion_pairs = list(set(question_completion_pairs))

	message = ctx.message
	random_question = random.choice(question_completion_pairs)
	embed = discord.Embed(title = "FAQ", description=random_question[0])
	message.content = random_question[0]

	await ctx.send(embed=embed)
	await frankenceres(message, answer=random_question[1])

@bot.command(aliases=['ask'])
async def ceres(ctx, *, thought):
	"""
	/ask query an iris and get a response
	"""

	global training_data
	testers = ["John Ash's Username for Discord", "Gregory | RND", "JohnAsh", "Dan | Regen Network"]
	
	# Only Allow Some Users
	if ctx.message.author.name not in testers:
		return

	thought_prompt = thought + "\n\n###\n\n"

	response = openai.Completion.create(
		model=models["ceres"],
		prompt=thought_prompt,
		temperature=0.69,
		max_tokens=222,
		top_p=1,
		frequency_penalty=1.8,
		presence_penalty=1.5,
		stop=["END"]
	)

	text = response['choices'][0]['text']
	text = text.replace("###", "").strip()
	embed = discord.Embed(title = "", description=f"**Prompt**\n{thought}\n\n**Response**\n{text}")

	await ctx.send(embed=embed)

	# Send Clarification and Share UI
	view, modal = response_view(modal_text="Write your clarification here", modal_label="Clarification", button_label="feedback")
	el_prompt = thought + "\n\n" + text
	elaborate_button = elaborate(ctx, prompt=el_prompt)
	view.add_item(elaborate_button)
	await ctx.send(view=view)

	# Save Clarification
	await modal.wait()

	prompt = thought + "\n\n" + text

	if modal.answer.value is not None:
		training_data.loc[len(training_data.index)] = [prompt, modal.answer.value, ctx.message.author.name] 
		training_data.to_csv('ceres_training-data.csv', encoding='utf-8', index=False)


@bot.command()
async def clarify(ctx, *, thought):
	"""
	/clarify send thourght to Greogy for clarification
	"""

	global training_data
	testers = ["John Ash's Username for Discord"]

	# Only Allow Some Users
	if ctx.message.author.name not in testers:
		return

	eve = 1005212665259495544
	gregory = 644279763065634851
	dan = 474842514407292930
	sja = 572900074779049984

	clarifiers = [dan, gregory]

	guild = bot.get_guild(989662771329269890)

	clarifier_accounts, modals = [], {}

	for clarifier in clarifiers:
		member = guild.get_member(clarifier)
		clarifier_accounts.append(member)
		question_embed = discord.Embed(title="Please clarify the below", description = thought)
		view, modal = response_view(modal_text=thought)
		modals[member.name] = modal
		sent_embed = discord.Embed(title = "Sent", description = f"Message sent for clarification")
		await member.send(embed=question_embed)
		await member.send(view=view)

	await ctx.send(embed=sent_embed)

	# Save Clarification
	for clarifier in modals:

		modal = modals[clarifier]

		await modal.wait()

		prompt = thought

		if modal.answer.value is not None:
			training_data.loc[len(training_data.index)] = [prompt, modal.answer.value, clarifier] 
			training_data.to_csv('ceres_training-data.csv', encoding='utf-8', index=False)

@bot.command()
async def claim(ctx, *, thought):
	"""
	/claim log a claim for the iris to learn
	"""

	global training_data

	# Send Clarification and Share UI
	prompt = "Share something about in the general latent space of Regen Network"

	if thought is not None:
		training_data.loc[len(training_data.index)] = [prompt, thought, ctx.message.author.name] 
		training_data.to_csv('ceres_training-data.csv', encoding='utf-8', index=False)

	await ctx.send("Attestation saved")

@bot.command()
async def davinci(ctx, *, thought):
	"""
	/ask query an iris and get a response
	"""

	global training_data
	testers = ["John Ash's Username for Discord", "Gregory | RND", "JohnAsh", "Dan | Regen Network"]
	
	# Only Allow Some Users
	if ctx.message.author.name not in testers:
		return

	thought_prompt = thought

	response = openai.Completion.create(
		model="text-davinci-002",
		prompt=thought_prompt,
		temperature=0.69,
		max_tokens=222,
		top_p=1,
		frequency_penalty=1.8,
		presence_penalty=1.5,
		stop=["END"]
	)

	view = View()
	text = response['choices'][0]['text'].strip()
	embed = discord.Embed(title = "", description=f"**Prompt**\n{thought}\n\n**Response**\n{text}")

	await ctx.send(embed=embed)
	await ctx.send(view=view)

bot.run(discord_key)