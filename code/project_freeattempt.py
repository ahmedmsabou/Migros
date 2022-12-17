# -*- coding: utf-8 -*-
"""Project_FreeAttempt.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1NpvHUwGXSZ6rj573xiW7tbb4FIMZab5z
"""

# Commented out IPython magic to ensure Python compatibility.
!pip install transformers
!pip install sentencepiece

# read data and import packages
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
# %matplotlib inline
sns.set_style("whitegrid")

!pip install -U spacy


# import some additional packages
from sklearn.preprocessing import OrdinalEncoder, OneHotEncoder, LabelEncoder
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score
from sklearn. preprocessing import StandardScaler

from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import hstack

import torch.nn as nn
import torch
from transformers import DataCollatorWithPadding,AutoModelForSequenceClassification, Trainer, TrainingArguments,AutoTokenizer,AutoModel,AutoConfig
from transformers.modeling_outputs import TokenClassifierOutput

# train data
df_train = pd.read_csv('training_data.csv')

# Rename Labeling
df_train['difficulty'] = df_train['difficulty'].replace(['A1','A2','B1', 'B2', 'C1', 'C2'],[0,1,2,3,4,5])

# test data
df_test = pd.read_csv('unlabelled_test_data.csv')


# Imports to use a pipeline
import torch
from tqdm import tqdm, trange
from tensorflow import keras 

# Imports for modelling
from sklearn.model_selection import train_test_split
from keras_preprocessing.sequence import pad_sequences
from torch.utils.data import TensorDataset, DataLoader, RandomSampler, SequentialSampler
from transformers import CamembertTokenizer, CamembertForSequenceClassification
from transformers import AdamW, get_linear_schedule_with_warmup
from transformers import BertTokenizer, BertModel
from transformers import BertTokenizer, BertForSequenceClassification


epochs = 7
MAX_LEN = 64
batch_size = 16
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Initialize CamemBERT tokenizer
tokenizer = CamembertTokenizer.from_pretrained('camembert/camembert-large', do_lower_case=True)
# tokenizer = BertTokenizer.from_pretrained('bert-base-multilingual-uncased')



# Split text and labels into lists
text = df_train['sentence'].to_list()
labels = df_train['difficulty'].to_list()

#user tokenizer to convert sentences into tokenizer'
input_ids  = [tokenizer.encode(sent,add_special_tokens=True,max_length=MAX_LEN) for sent in text]

# Pad our input tokens
input_ids = pad_sequences(input_ids, maxlen=MAX_LEN, dtype="long", truncating="post", padding="post")

attention_masks = []

# Create a mask of 1s for each token followed by 0s for padding
for seq in input_ids:
    seq_mask = [float(i>0) for i in seq]  
    attention_masks.append(seq_mask)


# Use train_test_split to split our data into train and validation sets for training
train_inputs, validation_inputs, train_labels, validation_labels, train_masks, validation_masks = train_test_split(input_ids, labels, attention_masks,
                                                            random_state=42, test_size=0.005)


# Convert all of our data into torch tensors, the required datatype for our model
train_inputs = torch.tensor(train_inputs)
validation_inputs = torch.tensor(validation_inputs)
train_labels = torch.tensor(train_labels)
validation_labels = torch.tensor(validation_labels)
train_masks = torch.tensor(train_masks)
validation_masks = torch.tensor(validation_masks)

# Create an iterator of our data with torch DataLoader. This helps save on memory during training because, unlike a for loop, 
# with an iterator the entire dataset does not need to be loaded into memory

train_data = TensorDataset(train_inputs, train_masks, train_labels)
train_sampler = RandomSampler(train_data)
train_dataloader = DataLoader(train_data, sampler=train_sampler, batch_size=batch_size)

validation_data = TensorDataset(validation_inputs, validation_masks, validation_labels)
validation_sampler = SequentialSampler(validation_data)
validation_dataloader = DataLoader(validation_data, sampler=validation_sampler, batch_size=batch_size)

# Customize model

# class CustomModel(nn.Module):
#   def __init__(self,checkpoint,num_labels): 
#     super(CustomModel,self).__init__() 
#     self.num_labels = num_labels 

#     #Load Model with given checkpoint and extract its body
#     self.model = model = AutoModel.from_pretrained("bert-base-multilingual-uncased",config=AutoConfig.from_pretrained("bert-base-multilingual-uncased", output_attentions=True,output_hidden_states=True))
#     self.dropout = nn.Dropout(0.1) 
#     self.classifier = nn.Linear(768,num_labels) # load and initialize weights

#   def forward(self, input_ids=None, attention_mask=None,labels=None):
#     #Extract outputs from the body
#     outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)

#     #Add custom layers
#     sequence_output = self.dropout(outputs[0]) #outputs[0]=last hidden state

#     logits = self.classifier(sequence_output[:,0,:].view(-1,768)) # calculate losses
    
#     loss = None
#     if labels is not None:
#       loss_fct = nn.CrossEntropyLoss()
#       loss = loss_fct(logits.view(-1, self.num_labels), labels.view(-1))
    
#     return TokenClassifierOutput(loss=loss, logits=logits, hidden_states=outputs.hidden_states,attentions=outputs.attentions)



model = CamembertForSequenceClassification.from_pretrained("camembert/camembert-large", num_labels=6)
# model = BertForSequenceClassification.from_pretrained("bert-base-multilingual-uncased", num_labels=6)

# model=CustomModel(checkpoint="bert-base-multilingual-uncased", num_labels=6).to(device)

model.to(device)

param_optimizer = list(model.named_parameters())
no_decay = ['bias', 'gamma', 'beta']
optimizer_grouped_parameters = [
    {'params': [p for n, p in param_optimizer if not any(nd in n for nd in no_decay)],
     'weight_decay_rate': 0.01},
    {'params': [p for n, p in param_optimizer if any(nd in n for nd in no_decay)],
     'weight_decay_rate': 0.0}
]


optimizer = AdamW(optimizer_grouped_parameters, lr=1e-5, eps=1e-8)

# Function to calculate the accuracy of our predictions vs labels
def flat_accuracy(preds, labels):
    pred_flat = np.argmax(preds, axis=1).flatten()
    labels_flat = labels.flatten()
    return np.sum(pred_flat == labels_flat) / len(labels_flat)

# Linear scheduler
scheduler = get_linear_schedule_with_warmup(optimizer, 
                                            num_warmup_steps=0,
                                            num_training_steps=len(train_labels)*epochs)

# Store our loss and accuracy for plotting if we want to visualize training evolution per epochs after the training process
train_loss_set = []

# trange is a tqdm wrapper around the normal python range
for _ in trange(epochs, desc="Epoch"):  
    # Tracking variables for training
    tr_loss = 0
    nb_tr_examples, nb_tr_steps = 0, 0
  
    # Train the model
    model.train()
    for step, batch in enumerate(train_dataloader):
        # Add batch to device CPU or GPU
        batch = tuple(t.to(device) for t in batch)
        # Unpack the inputs from our dataloader
        b_input_ids, b_input_mask, b_labels = batch
        # Clear out the gradients (by default they accumulate)
        optimizer.zero_grad()
        # Forward pass
        outputs = model(b_input_ids,token_type_ids=None, attention_mask=b_input_mask, labels=b_labels)
  # Get loss value
        loss = outputs[0]
        # Add it to train loss list
        train_loss_set.append(loss.item())    
        # Backward pass
        loss.backward()
        # Update parameters and take a step using the computed gradient
        optimizer.step()
        scheduler.step()

    
        # Update tracking variables
        tr_loss += loss.item()
        nb_tr_examples += b_input_ids.size(0)
        nb_tr_steps += 1

    print("Train loss: {}".format(tr_loss/nb_tr_steps))
    
    


    # Tracking variables for validation
    eval_loss, eval_accuracy = 0, 0
    nb_eval_steps, nb_eval_examples = 0, 0
    # Validation of the model
    model.eval()
    # Evaluate data for one epoch
    for batch in validation_dataloader:
        # Add batch to device CPU or GPU
        batch = tuple(t.to(device) for t in batch)
        # Unpack the inputs from our dataloader
        b_input_ids, b_input_mask, b_labels = batch
        # Telling the model not to compute or store gradients, saving memory and speeding up validation
        with torch.no_grad():
            # Forward pass, calculate logit predictions
            outputs =  model(b_input_ids,token_type_ids=None, attention_mask=b_input_mask, labels=b_labels)
            loss, logits = outputs[:2]
    
        # Move logits and labels to CPU if GPU is used
        logits = logits.detach().cpu().numpy()
        label_ids = b_labels.to('cpu').numpy()

        tmp_eval_accuracy = flat_accuracy(logits, label_ids)
    
        eval_accuracy += tmp_eval_accuracy
        nb_eval_steps += 1

    print("Validation Accuracy: {}".format(eval_accuracy/nb_eval_steps))

"""# After Training the model, make predictions

Use the format from the sample submission.
"""

comments = df_test['sentence'].to_list()

# Encode the comments
tokenized_comments_ids = [tokenizer.encode(comment,add_special_tokens=True,max_length=MAX_LEN) for comment in comments]
# Pad the resulted encoded comments
tokenized_comments_ids = pad_sequences(tokenized_comments_ids, maxlen=MAX_LEN, dtype="long", truncating="post", padding="post")

# Create attention masks 
attention_masks = []
for seq in tokenized_comments_ids:
  seq_mask = [float(i>0) for i in seq]
  attention_masks.append(seq_mask)

prediction_inputs = torch.tensor(tokenized_comments_ids)
prediction_masks = torch.tensor(attention_masks)

# Apply the finetuned model (Camembert)
flat_pred = []
with torch.no_grad():
    # Forward pass, calculate logit predictions
    outputs =  model(prediction_inputs.to(device),token_type_ids=None, attention_mask=prediction_masks.to(device))
    logits = outputs[0]
    logits = logits.detach().cpu().numpy() 
    flat_pred.extend(np.argmax(logits, axis=1).flatten())

for i in range(len(flat_pred)):
    print('Comment: ', comments[i])
    print('Label', flat_pred[i])

df_samplesub = pd.read_csv('sample_submission.csv')
df_samplesub['difficulty'] = flat_pred

# Translate back
df_samplesub['difficulty'] = df_samplesub['difficulty'].replace([0,1,2,3,4,5],['A1','A2','B1', 'B2', 'C1', 'C2'])

print(df_samplesub)

# Upload pandas dataframe as csv to drive
from google.colab import drive
drive.mount('drive')

df_samplesub.to_csv('FinalTest4.csv', index = False)
!cp FinalTest4.csv "drive/My Drive/"

df_samplesub['difficulty'] = df_samplesub['difficulty'].replace([0,1,2,3,4,5],['A1','A2','B1', 'B2', 'C1', 'C2'])

# Upload pandas dataframe as csv to drive
from google.colab import drive
drive.mount('drive')

df_samplesub.to_csv('TestSolutions3.csv', index = False)
!cp TestSolutions3.csv "drive/My Drive/"

# Commented out IPython magic to ensure Python compatibility.
# Ensamble

# read data and import packages
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
# %matplotlib inline
sns.set_style("whitegrid")

# Ensamble with 7 models
# lr = pd.read_csv('Ensamble2.csv')
distel = pd.read_csv('FinalTest1.csv')
french = pd.read_csv('FinalTest3.csv')
french_improved = pd.read_csv('FinalTest4.csv')
# extra_1 = pd.read_csv('NewTest5.csv')
# extra_2 = pd.read_csv('NewTest6.csv')
# extra_3 = pd.read_csv('TestSolutions6.csv')


french_improved['distelDifficulty'] = distel['difficulty']
# french_improved['lrDifficulty'] = lr['difficulty']
# french_improved['extra1Difficulty'] = extra_1['difficulty']
# french_improved['extra2Difficulty'] = extra_2['difficulty']
french_improved['frenchDifficulty'] = french['difficulty']
# french_improved['extra3Difficulty'] = extra_3['difficulty']

french_improved['resultEnsamble'] = french_improved.mode(axis=1).iloc[:, 0]


for i in range (0, len(french_improved)):
  if ((french_improved.iloc[i]['difficulty'] != french_improved.iloc[i]['distelDifficulty']) and (french_improved.iloc[i]['distelDifficulty'] != french_improved.iloc[i]['frenchDifficulty']) and (french_improved.iloc[i]['difficulty'] != french_improved.iloc[i]['frenchDifficulty'])):
    french_improved.at[i, 'resultEnsamble'] = french_improved.iloc[i]['difficulty']

# Set into sample solution
df_samplesub = pd.read_csv('sample_submission.csv')
df_samplesub['difficulty'] = french_improved['resultEnsamble']

# Upload pandas dataframe as csv to drive
from google.colab import drive
drive.mount('drive')

df_samplesub.to_csv('Ensamble_Total_Final.csv', index = False)
!cp Ensamble_Total_Final.csv "drive/My Drive/"