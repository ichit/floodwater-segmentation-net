import os
import random

import torch
import torch.utils.data as data_utils
import segmentation_models_pytorch as smp
import numpy as np
import matplotlib.pyplot as plt
import albumentations
import matplotlib.pyplot as plt
from segtat.metrics import XEDiceLoss


class ModelExplorer:
    """ Class for launching PyTorch Neural networks """

    def __init__(self, working_dir: str, device: str = 'cpu'):
        self.working_dir = working_dir
        # Loss for all models will be the same
        self.loss = smp.utils.losses.DiceLoss()
        self.device = device

    def fit(self, train: torch.tensor, model, **params):
        """ Perform train procedure.
        In **params dict with hyperparameters for neural network can be defined

        :param train: tensor with data for train
        :param model: class PyTorch model
        """
        path_to_save = os.path.join(self.working_dir, 'best_model.pth')
        path_prom_save = os.path.join(self.working_dir, 'prom.pth')
        train_dataset, valid_dataset = self.train_test(train.tensors[0], train.tensors[1], train_size=0.95)
        # Prepare data loaders
        train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=params['batch_size'])
        valid_loader = torch.utils.data.DataLoader(valid_dataset, batch_size=1, shuffle=False)

        optimizer = params['optimizer']
        train_epoch = smp.utils.train.TrainEpoch(
            model,
            loss=self.loss,
            metrics=params['metrics'],
            optimizer=optimizer,
            device=self.device,
            verbose=True,
        )

        valid_epoch = smp.utils.train.ValidEpoch(
            model,
            loss=self.loss,
            metrics=params['metrics'],
            device=self.device,
            verbose=True,
        )

        for i in range(0, params['epochs']):

            print('\nEpoch: {}'.format(i))
            train_logs = train_epoch.run(train_loader)
            valid_logs = valid_epoch.run(valid_loader)

            # When it takes only 0.8 set
            if i == round(params['epochs']*0.8):
                # Decrease decoder learning rate to 1e-5
                optimizer.param_groups[0]['lr'] = 0.000002
            if i == 10 or i == 20 or i == 30 or i == 40 or i == 50:
                torch.save(model, path_prom_save)

        torch.save(model, path_to_save)
        print('Model saved!')
        return model

    def validate(self, test: torch.tensor, model_path: str, model=None,
                 threshold: float = None, **params):
        """ Perform validation on the test set

        :param test: tensor with test data
        :param model_path: path to the serialised PyTorch model
        :param model: class PyTorch model
        :param threshold: threshold for class definition
        """
        if model is None:
            model = torch.load(model_path)

        if params.get('vis') is not None and params['vis'] is True:
            for i in range(0, 5):
                n = np.random.choice(len(test))
                features_tensor = test.tensors[0][n]
                true_label = test.tensors[1][n]

                x_tensor = features_tensor.to(self.device).unsqueeze(0)
                pr_mask = model.predict(x_tensor)
                if threshold is None:
                    pr_mask = pr_mask.squeeze().cpu().numpy().astype(np.uint8)
                else:
                    pr_mask = pr_mask.squeeze().cpu().numpy()
                    pr_mask[pr_mask < threshold] = 0
                    pr_mask[pr_mask >= threshold] = 1

                plt.imshow(pr_mask, cmap='Purples', alpha=1.0)
                #plt.imshow(true_label.numpy()[0], cmap='Blues', alpha=0.2)
                plt.colorbar()
                plt.show()

                plt.imshow(true_label.numpy()[0], cmap='Blues', alpha=0.9)
                plt.colorbar()
                plt.show()

        test_loader = torch.utils.data.DataLoader(test)
        test_epoch = smp.utils.train.ValidEpoch(
            model=model,
            loss=self.loss,
            metrics=params['metrics'],
            device=self.device,
        )

        # Calculate loss
        logs = test_epoch.run(test_loader)

    @staticmethod
    def load_data(features_path: str, target_path: str, as_np: bool = False):
        """ Load data from paths

        :param features_path: path to the features .pt file
        :param target_path: path to the label .pt file
        :param as_np: is it needed to return tensors as numpy arrays
        """

        x_train = torch.load(features_path)
        y_train = torch.load(target_path)

        if as_np:
            x_train = x_train.numpy()
            y_train = y_train.numpy()

        return x_train, y_train

    @staticmethod
    def train_test(x_train: torch.tensor, y_train: torch.tensor, train_size: float = 0.8):
        """ Method for train test split

        :param x_train: pytorch tensor with features
        :param y_train: pytorch tensor with labels
        :param train_size: value from 0.1 to 0.9
        """
        if train_size < 0.1 or train_size > 0.99:
            raise ValueError('train_size value must be value between 0.1 and 0.99')
        dataset = data_utils.TensorDataset(x_train, y_train)
        train_ratio = round(len(dataset) * train_size)
        test_ratio = len(dataset) - train_ratio
        train, test = torch.utils.data.random_split(dataset, [train_ratio, test_ratio])

        train_features, train_target = train.dataset[train.indices]
        test_features, test_target = test.dataset[test.indices]
        train_dataset = data_utils.TensorDataset(train_features, train_target)
        test_dataset = data_utils.TensorDataset(test_features, test_target)
        return train_dataset, test_dataset

    @staticmethod
    def augmentation(dataset: torch.tensor, vis: bool = False) -> data_utils.TensorDataset:
        """ Perform augmentation procedure """
        transformations = albumentations.Compose(
            [
                albumentations.ShiftScaleRotate(),
                albumentations.HorizontalFlip(),
                albumentations.VerticalFlip()
            ]
        )

        features = dataset.tensors[0].numpy()
        features_shape = features.shape
        targets = dataset.tensors[1].numpy()

        # Include test labels into array
        stacked = np.concatenate([features, targets], axis=1)
        random.seed(7)

        # Perform transforms
        # TODO make it more effective
        for i in range(0, len(features)):
            print(i)
            image = stacked[i, 0:features_shape[1], :, :]
            mask = stacked[i, features_shape[1], :, :]
            mask = np.array([mask])
            transformed = transformations(image=image, mask=mask)

            augmented_features = transformed["image"]
            augmented_label = transformed["mask"]

            if vis:
                plt.imshow(stacked[i, 0, :, :], cmap='jet')
                plt.title('Исходная матрица VH')
                plt.colorbar()
                plt.show()

                plt.imshow(stacked[i, 1, :, :], cmap='jet')
                plt.title('Исходная матрица VV')
                plt.colorbar()
                plt.show()

                plt.imshow(stacked[i, 2, :, :], cmap='Blues')
                plt.title('Исходная матрица label')
                plt.colorbar()
                plt.show()

                plt.imshow(augmented_features[0, :, :], cmap='jet')
                plt.title('Преобразованная матрица VH')
                plt.colorbar()
                plt.show()

                plt.imshow(augmented_features[1, :, :], cmap='jet')
                plt.title('Преобразованная матрица VV')
                plt.colorbar()
                plt.show()

                plt.imshow(augmented_label[0, :, :], cmap='Blues')
                plt.title('Преобразованная матрица label')
                plt.colorbar()
                plt.show()

            # Add dimension
            augmented_features = np.array([augmented_features])
            augmented_label = np.array([augmented_label])
            if i == 0:
                augmented_all_features = augmented_features
                augmented_all_labels = augmented_label
            else:
                augmented_all_features = np.concatenate([augmented_all_features, augmented_features])
                augmented_all_labels = np.concatenate([augmented_all_labels, augmented_label])

        features = np.concatenate([features, augmented_all_features])
        targets = np.concatenate([targets, augmented_all_labels])
        print('Augmentation finished')
        return data_utils.TensorDataset(torch.from_numpy(features), torch.from_numpy(targets))
