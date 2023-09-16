import os
import pandas as pd 
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import transforms

# load custom scripts
from model.torch.ResNet50_pretrained import ResNet50_pretrained
from model.torch.CustomDataset import CustomDataset
from model.torch.fit_torch import fit_torch
from model.torch.validation_accuaracy import validation_accuaracy
from data_prep.utilities.plot_preds import plot_preds
import cons

# create a dataframe of filenames and categories
filenames = os.listdir(cons.train_fdir)
categories = [1 if filename.split('.')[0] == 'dog' else 0 for filename in filenames]
df = pd.DataFrame({'filename': filenames, 'category': categories})
frac = 0.05
df = df.sample(frac = frac)
category_mapper = {0: 'cat', 1: 'dog'}
df["categoryname"] = df["category"].replace(category_mapper) 
df['source'] = df['filename'].str.contains(pat = '[cat|dog].[0-9]+\.jpg', regex = True).map({True:'kaggle', False:'webscraper'})
df["filepath"] = cons.train_fdir + '/' + df['filename']

# prepare data
random_state = 42
validate_df = df[df['source'] == 'kaggle'].sample(n = int(5000 * frac), random_state = random_state)
train_df = df[~df.index.isin(validate_df.index)]
train_df = train_df.reset_index(drop=True)
validate_df = validate_df.reset_index(drop=True)

# set data constants
total_train = train_df.shape[0]
total_validate = validate_df.shape[0]

transform = transforms.Compose([
    transforms.Resize([128, 128]),  # resize the input image to a uniform size
    transforms.ToTensor(),  # convert PIL Image or numpy.ndarray to tensor and normalize to somewhere between [0,1]
    transforms.Normalize(   # standardized processing
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225])
])

# hyper-parameters
num_epochs = 4
batch_size = 64
learning_rate = 0.001

# set train datagen
train_dataset = CustomDataset(train_df, transform, mode = 'train')
train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

# set validation datagen
validation_dataset = CustomDataset(train_df, transform, mode = 'train')
validation_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=True)

# device configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# initiate cnn architecture
model = ResNet50_pretrained(num_classes=2).to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate)

# fit torch model
model, train_loss_list, train_acc_list = fit_torch(model, device, criterion, optimizer, train_loader, num_epochs = num_epochs)

# calculate validation accuracy
validation_accuaracy(model, device, validation_loader)

# save model
model.save(output_fpath=cons.torch_model_pt_fpath)

# load model
model = ResNet50_pretrained(num_classes=2).to(device)
model.load(input_fpath=cons.torch_model_pt_fpath)

# prepare test data
test_filenames = os.listdir(cons.test_fdir)
test_df = pd.DataFrame({'filename': test_filenames})
test_df["filepath"] = cons.test_fdir + '/' + test_df['filename']
test_df["idx"] = test_df['filename'].str.extract(pat = '([0-9]+)').astype(int)
test_df = test_df.set_index('idx').sort_index()
nb_samples = test_df.shape[0]

# set train datagen
test_dataset = CustomDataset(test_df, transform, mode = 'test')
test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

# make test set predictions
predict = model.predict(test_loader, device)
test_df['category'] = np.argmax(predict, axis=-1)
test_df["category"] = test_df["category"].replace(category_mapper) 

# plot random sample predictions
plot_preds(data = test_df, cons = cons, output_fpath = cons.pred_images_fpath)

# make submission
submission_df = test_df.copy()
submission_df['id'] = submission_df['filename'].str.split('.').str[0]
submission_df['label'] = submission_df['category'].replace({ 'dog': 1, 'cat': 0 })
submission_df.to_csv(cons.submission_csv_fpath, index=False)