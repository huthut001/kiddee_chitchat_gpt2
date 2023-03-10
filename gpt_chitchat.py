# -*- coding: utf-8 -*-
"""gpt-chitchat.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1SiNiAZxli_7cNXwVnpJp7WdHgJryCuE2
"""


token = '<your_token>'

# import the relavant libraries for loggin in
from huggingface_hub import HfApi, HfFolder

# set api for login and save token
api=HfApi()
api.set_access_token(token)
folder = HfFolder()
folder.save_token(token)

from transformers import GPT2LMHeadModel, GPT2Tokenizer
import pandas as pd
import torch
from torch.utils.data import Dataset, random_split
from transformers import GPT2Tokenizer, TrainingArguments, Trainer, GPT2LMHeadModel
import numpy as np
import re
from datasets import load_dataset
import gc
from transformers import EarlyStoppingCallback

pretrained_name = "kobkrit/openthaigpt-gpt2-instructgpt-poc-0.0.3"

tokenizer = GPT2Tokenizer.from_pretrained(pretrained_name, bos_token='<|startoftext|>',unk_token='<|unk|>', eos_token='<|endoftext|>', pad_token='<|pad|>')
model = GPT2LMHeadModel.from_pretrained(pretrained_name).cuda()
model.resize_token_embeddings(len(tokenizer))

tokenizer

prompt = "<|startoftext|> โดนแมวกัดทำไงดี <|endoftext|>"
encoded_input = tokenizer(prompt, return_tensors='pt')

encoded_input

generated = tokenizer("<|startoftext|> โดนแมวกัด", return_tensors="pt").input_ids.cuda()
sample_outputs = model.generate(generated, do_sample=True, top_k=50,  max_length=300, top_p=0.95, temperature=1.9, num_return_sequences=20)

for i, sample_output in enumerate(sample_outputs):
    print("{}: {}".format(i, tokenizer.decode(sample_output, skip_special_tokens=True)))

"""<h1> prepare data"""

# !pip install --upgrade --no-cache-dir gdown

# !gdown 10A8DbHItymMiPIQP7zxAuDKujDIv4DRR

torch.manual_seed(42)

pantip = pd.read_csv('/home/nlp/gpt_nlp/pantip_topic_qa_v1.csv')
pantip = pantip.dropna()

thamma = pd.read_csv('/home/nlp/gpt_nlp/Thamma_dataset.csv')
thamma = thamma.dropna()
# pantip
print("\n load Data already")

# pantip["prompt"][0]

# pantip["comment"][1]

print("\n cleaning data")

pantip_texts = []
for (idx, row) in pantip.iterrows():
  tmp = "Q: "+row["question"][:512]+"\n\nA: "+row["answer"]
  if (tmp!=None and len(tmp)>10):
    cleaned = re.sub(r'[^\u0E00-\u0E7F\u0020-\u007E0-9\n]', '', str(tmp))
    cleaned = re.sub(r'http\S+', '', cleaned)  # remove URLs
    cleaned = re.sub(r'[Spoil] คลิกเพื่อดูข้อความที่ซ่อนไว้', '', cleaned)
    pantip_texts.append(cleaned)

thamma_texts = []
for (idx, row) in thamma.iterrows():
  tmp = "Q: "+row["question"][:512]+"\n\nA: "+row["answer"]
  if (tmp!=None and len(tmp)>10):
    cleaned = re.sub(r'[^\u0E00-\u0E7F\u0020-\u007E0-9\n]', '', str(tmp))
    cleaned = re.sub(r'http\S+', '', cleaned)  # remove URLs
    cleaned = re.sub(r'[Spoil] คลิกเพื่อดูข้อความที่ซ่อนไว้', '', cleaned)
    pantip_texts.append(cleaned)

print('\n clean data already')

# pantip_texts[512]

print(len(thamma_texts))
print(len(pantip_texts))

#-------------------

# dataset = load_dataset("thaiqa_squad")
# print('\n load dataset thaiqa_squad already')

# import pandas as pd

# qas = pd.DataFrame( dataset["train"] )

# qas

# print(qas['context'][0])

# print(qas['question'][0])

# print(qas['answers'][0])

# qas_text = []

# for (idx, row) in qas.iterrows():
#   answers = row["answers"]
#   context_text = re.sub(r"(<.*?>)", "", row['context'])[:500]
#   question_text = row['question']
#   answer_text = answers["answer"][0]
#   text = f"{context_text}\n\nQ:{question_text}\n\nA:{answer_text}"
#   qas_text.append(text)

# qas_text

# all_text = pantip_texts + qas_text
# all_text = all_text[:1000]

#----------------------------------

all_text = pantip_texts + thamma_texts

print('all_text:',len(all_text))

max_length = 1024


# """<h1> train data"""

print("pre train_dataset")

class ThaiDataset(Dataset):
    def __init__(self, txt_list, tokenizer, max_length):
        self.txt_list = txt_list
        self.tokenizer = tokenizer
        self.max_length = max_length
            
    def __len__(self):
        return len(self.txt_list)

    def __getitem__(self, idx):
        encodings_dict = self.tokenizer(f'<|startoftext|> {self.txt_list[idx]} <|endoftext|>', truncation=True,
                                  max_length=self.max_length, padding="max_length")
        input_ids = torch.tensor(encodings_dict['input_ids'])
        attn_masks = torch.tensor(encodings_dict['attention_mask'])
        return input_ids, attn_masks

dataset = ThaiDataset(all_text, tokenizer, max_length=max_length)
train_size = int(0.9 * len(dataset))
train_dataset, val_dataset = random_split(dataset, [train_size, len(dataset) - train_size])

gc.collect()

torch.cuda.empty_cache()
print("training")



training_args = TrainingArguments(output_dir='./results_02', num_train_epochs=100, logging_steps=500, save_steps=500,
                                  per_device_train_batch_size=4, per_device_eval_batch_size=4,
                                  warmup_steps=10, weight_decay=0.05, logging_dir='./logs', report_to = ["wandb"], 
                                  gradient_accumulation_steps=4,
                                  evaluation_strategy ="steps",
                                  eval_steps = 500, # Evaluation and Save happens every 10 steps
                                  save_total_limit = 5, # Only last 5 models are saved. Older ones are deleted.
                                  save_strategy='steps',
                                  load_best_model_at_end=True
                                )

trainer = Trainer(model=model,  args=training_args, train_dataset=train_dataset, callbacks=[EarlyStoppingCallback(early_stopping_patience=10)],
        eval_dataset=val_dataset, data_collator=lambda data: {'input_ids': torch.stack([f[0] for f in data]),
                                                              'attention_mask': torch.stack([f[1] for f in data]),
                                                              'labels': torch.stack([f[0] for f in data])})
trainer.train()
trainer.save_model("/home/nlp/gpt_nlp/hut_chitchat")
# # """<h1> Test Data"""

# generated = tokenizer("<|startoftext|> หลวงพี่เป็นผู้เชี่ยวชาญด้านการเงิน มีคนถามฉันว่า Q:  มีเรื่องมาปรึกษาครับ คือผมต้่องกู้บ้าน ต้องทำอย่างไรบ้างครับ \n\nA:", return_tensors="pt").input_ids.cuda()

# sample_outputs = model.generate(generated, do_sample=True, top_k=50, num_beams=5, no_repeat_ngram_size=2, 
#     early_stopping=True, max_length=150, top_p=0.95, temperature=1.9, num_return_sequences=20)

# for i, sample_output in enumerate(sample_outputs):
#     print("{}: {}".format(i, tokenizer.decode(sample_output, skip_special_tokens=True)))

# """<h1> Save pretrain"""

# model.save_pretrained("/home/nlp/gpt_nlp/hut_chitchat")
print("save already")
