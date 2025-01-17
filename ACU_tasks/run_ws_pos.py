from transformers import AutoTokenizer, AutoModel, BertTokenizerFast, RobertaTokenizer, RobertaModel, BertTokenizer, BertModel
import torch
from crf import CRF
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import torch.optim as optim
import random
import numpy as np
import torch.nn.functional as F
import re
import test

device = torch.device('cuda:0') if torch.cuda.is_available() else torch.device('cpu')
label_num = 47
idx2label = {
    0: '[PAD]', 1: '[CLS]',
    2: '[SEP]',
    3: 'b-a', 4: 'i-a',
    5: 'b-c', 6: 'i-c',
    7: 'b-d', 8: 'i-d',
    9: 'b-f', 10: 'i-f',
    11: 'b-j', 12: 'i-j',
    13: 'b-m', 14: 'i-m',
    15: 'b-n', 16: 'i-n',
    17: 'b-nr', 18: 'i-nr',
    19: 'b-ns', 20: 'i-ns',
    21: 'b-p', 22: 'i-p',
    23: 'b-q', 24: 'i-q',
    25: 'b-r', 26: 'i-r',
    27: 'b-s', 28: 'i-s',
    29: 'b-t', 30: 'i-t',
    31: 'b-u', 32: 'i-u',
    33: 'b-v', 34: 'i-v',
    35: 'b-sv', 36: 'i-sv',
    37: 'b-wv', 38: 'i-wv',
    39: 'b-yv', 40: 'i-yv',
    41: 'b-y', 42: 'i-y',
    43: 'b-w', 44: 'i-w',
    45: 'b-x', 46: 'i-x'
}

label2idx = {
    '[PAD]': 0, '[CLS]': 1,
    '[SEP]': 2,
    'b-a': 3, 'i-a': 4,
    'b-c': 5, 'i-c': 6,
    'b-d': 7, 'i-d': 8,
    'b-f': 9, 'i-f': 10,
    'b-j': 11, 'i-j': 12,
    'b-m': 13, 'i-m': 14,
    'b-n': 15, 'i-n': 16,
    'b-nr': 17, 'i-nr': 18,
    'b-ns': 19, 'i-ns': 20,
    'b-p': 21, 'i-p': 22,
    'b-q': 23, 'i-q': 24,
    'b-r': 25, 'i-r': 26,
    'b-s': 27, 'i-s': 28,
    'b-t': 29, 'i-t': 30,
    'b-u': 31, 'i-u': 32,
    'b-v': 33, 'i-v': 34,
    'b-sv': 35, 'i-sv': 36,
    'b-wv': 37, 'i-wv': 38,
    'b-yv': 39, 'i-yv': 40,
    'b-y': 41, 'i-y': 42,
    'b-w': 43, 'i-w': 44,
    'b-x': 45, 'i-x': 46
}


class BERT_BiLSTM_CRF(nn.Module):
    def __init__(self, model_path):
        super(BERT_BiLSTM_CRF, self).__init__()
        self.tokenizer = BertTokenizer.from_pretrained(model_path)
        self.bert_layer = BertModel.from_pretrained(model_path)
        self.lstm = nn.LSTM(input_size=768, hidden_size=512,
                    num_layers=2, bidirectional=True, batch_first=True)
        self.fc = nn.Linear(1024, label_num)
        self.dropout = nn.Dropout(p=0.5)
        self.crf_layer = CRF(label_num, batch_first=True)

    def _get_lstm_feats(self, sentence):
        sentence_idx = self.tokenizer(
            sentence,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(device)
        bert_output = self.bert_layer(**sentence_idx)
        lstm_output, (hn, cn) = self.lstm(bert_output['last_hidden_state'])
        lstm_output = self.dropout(lstm_output)
        fc_output = self.fc(lstm_output)
        return fc_output, sentence_idx['attention_mask']

    def cal_loss(self, sentence, tags):
        feats, mask = self._get_lstm_feats(sentence)
        crf_output = self.crf_layer(feats, tags, mask=(mask > 0))
        return crf_output

    def forward(self, sentence):
        feats, mask = self._get_lstm_feats(sentence)
        return self.crf_layer.decode(feats, mask=(mask > 0))

    

class zuozhuan_dataset(Dataset):
    def __init__(self, file_path, model_path):
        self.total_text = []
        self.total_label = []
        print(model_path)
        self.tokenizer = BertTokenizer.from_pretrained(model_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            line = f.readline()
            while line:
                line = line.replace('\n', '')
                if line == '':
                    line = f.readline()
                    continue  
                temp_text = ''
                temp_label = [label2idx['[CLS]']]
                for each_pair in line.split(' '):
                    each_pair = each_pair.split('/')
                    if len(each_pair) == 1:
                        continue  
                    if len(self.tokenizer(each_pair[0])['input_ids']) - len(each_pair[0]) < 2:
                        continue  
                    temp_text += each_pair[0]
                    if label2idx.get('b-' + each_pair[1]) is None:
                        each_pair[1] = 'x' 
                    temp_label.append(label2idx['b-' + each_pair[1]])
                    for i in range(len(each_pair[0])-1):
                        temp_label.append(label2idx['i-' + each_pair[1]])
                    if len(temp_label) > 450 and (each_pair[0] == '，' or each_pair[0] == '。'):  
                        print('seq_len > 450, cut!')
                        temp_label.append(label2idx['[SEP]'])
                        self.total_text.append(temp_text)
                        self.total_label.append(torch.tensor(temp_label))
                        temp_text = ''
                        temp_label = [label2idx['[CLS]']]
                temp_label.append(label2idx['[SEP]'])
                self.total_text.append(temp_text)
                self.total_label.append(torch.tensor(temp_label))
                line = f.readline()
        f.close()

    def __getitem__(self, item):
        return self.total_text[item], self.total_label[item]

    def __len__(self):
        return len(self.total_text)


class my_collate:
    def __init__(self, pad_value):
        self.padding = pad_value

    def __call__(self, batch_data):
        x_ = []
        y_ = []
        for x, y in batch_data:
            x_.append(x)
            y_.append(y)
        y_ = nn.utils.rnn.pad_sequence(y_, batch_first=True, padding_value=self.padding)
        return x_, y_


def generate_train_dev_set(total_file_path):
    with open(total_file_path, 'r', encoding='utf-8') as f:
        total_file = []
        line = f.readline()
        while line:
            total_file.append(line)
            line = f.readline()
    f.close()
    random.shuffle(total_file)
    train_file = total_file[:-900]
    dev_file = total_file[-900:]
    with open('./data/train.txt', 'w', encoding='utf-8') as f:
        for each_line in train_file:
            f.write(each_line)
    f.close()
    with open('./data/dev.txt', 'w', encoding='utf-8') as f:
        for each_line in dev_file:
            f.write(each_line)
    f.close()

    with open('./data/dev.txt', 'r', encoding='utf-8') as f:
        text = f.read()
    f.close()
    text = re.sub('/[a-z]*', '', text)
    text = text.replace(' ', '')
    with open('./data/dev_only_text.txt', 'w', encoding='utf-8') as f:
        f.write(text)
    f.close()



def mask_token(sentence,  rate=0.2):
    mask_num = int(rate * len(sentence))
    mask_array = np.zeros(len(sentence))
    mask_array[:mask_num] = 1
    np.random.shuffle(mask_array)
    new_sentence = ''
    for i in range(len(sentence)):
        if mask_array[i] == 1:
            new_sentence += '[MASK]'
        else:
            new_sentence += sentence[i]
    return new_sentence


if __name__ == "__main__":
    # generate_train_dev_set("./data/zuozhuan_train_utf8.txt")
    model_path = 'path_to_plms'
    save_path = 'path_to_save'
    data = zuozhuan_dataset("./data/train.txt", model_path)
    dataloader = DataLoader(dataset=data, batch_size=50, shuffle=True, collate_fn=my_collate(label2idx['[PAD]']))
    model = BERT_BiLSTM_CRF(model_path).to(device)

    for name, para in model.named_parameters():
        if "bert_layer" in name:
            para.requires_grad_(False)
    optimizer = optim.Adam([p for p in model.parameters() if p.requires_grad], lr=0.01)

    for epoch in range(15):
        running_loss = 0.
        for batch, (text, label) in enumerate(dataloader):

            for i in range(len(text)):
                text[i] = mask_token(text[i])

            optimizer.zero_grad()
            label = label.to(device)
            loss = (-1)*model.cal_loss(text, label).to(device)
            loss = loss.sum()
            loss.backward()
            optimizer.step()
            running_loss += float(loss)
            if batch % 100 == 0:
                print("loss=", loss)
        print("epoch:", epoch+1, "loss:", running_loss)
        torch.save(model, save_path)
        test.dev_test(save_path)
